# -*- coding: utf-8 -*-
# Copyright (C) Softhealer Technologies Pvt. Ltd.

from datetime import timedelta

from odoo import models, fields, api, _
import logging

_logger = logging.getLogger(__name__)

MAX_RETRY_COUNT = 3
RETRY_BACKOFF_MINUTES = 10

class SHPowerBIPushQueue(models.Model):
    _name = 'sh.powerbi.push.queue'
    _description = 'Power BI Push Queue'
    _order = 'id'

    push_config_id = fields.Many2one('sh.powerbi.push.config', string='Push Configuration', required=True, ondelete='cascade')
    model_access_id = fields.Many2one('sh.powerbi.model.access', string='Model Access', required=True, ondelete='cascade')
    company_id = fields.Many2one('res.company', related='push_config_id.company_id', store=True)
    
    state = fields.Selection([
        ('draft', 'Draft'),
        ('processing', 'Processing'),
        ('done', 'Done'),
        ('failed', 'Failed'),
    ], string='Status', default='draft', readonly=True)
    
    batch_offset = fields.Integer(string='Last Offset Processed', default=0)
    total_records = fields.Integer(string='Total Records to Push', default=0)
    retry_count = fields.Integer(string='Retry Count', default=0)
    max_retry_count = fields.Integer(string='Max Retries', default=MAX_RETRY_COUNT, readonly=True)
    last_attempt_at = fields.Datetime(string='Last Attempt At', readonly=True)
    next_retry_at = fields.Datetime(string='Next Retry At', readonly=True)
    error_message = fields.Text(string='Error Message', readonly=True)
    is_delta = fields.Boolean(string='Incremental Push', default=False, readonly=True,
        help="When True, only records changed since last_push_write_date are pushed (rows appended, not cleared).")
    is_realtime = fields.Boolean(string='Real-Time Job', default=False, readonly=True,
        help="When True, this job was triggered automatically by a record create/write.")

    def _mark_failed(self, error):
        """Mark a queue as failed and schedule retry if attempts remain."""
        self.ensure_one()
        retry_count = self.retry_count + 1
        vals = {
            'state': 'failed',
            'error_message': str(error),
            'retry_count': retry_count,
            'last_attempt_at': fields.Datetime.now(),
        }
        if retry_count < (self.max_retry_count or MAX_RETRY_COUNT):
            vals['next_retry_at'] = fields.Datetime.now() + timedelta(minutes=RETRY_BACKOFF_MINUTES * retry_count)
        else:
            vals['next_retry_at'] = False
        self.write(vals)
    
    def action_process_queue(self):
        """Process this queue job in batches."""
        self.ensure_one()
        if self.state == 'done':
            return
            
        self.write({
            'state': 'processing',
            'last_attempt_at': fields.Datetime.now(),
            'next_retry_at': False,
            'error_message': False,
        })
        self.env.cr.commit()
        
        try:
            # Re-authorize if needed
            self.push_config_id._refresh_token_if_needed()

            import ast
            base_domain = ast.literal_eval(self.model_access_id.domain_filter or '[]')
            # Bind the model to the company that owns the configuration so that the
            # allowed fields, domain filter and relational field format are always
            # resolved against the target company and never the executing user's.
            target_company = (
                self.model_access_id.company_id
                or self.push_config_id.company_id
                or self.env.company
            )
            Model = self.env[self.model_access_id.model_name].sudo().with_company(target_company)
            batch_size = self.push_config_id.push_batch_size or 1000

            dataset_id = self.model_access_id.powerbi_dataset_id
            force_full_push = False
            if not dataset_id:
                dataset_id = self.push_config_id._create_dataset(self.model_access_id)
                force_full_push = True
            else:
                drifted, odoo_cols, pbi_cols = self.push_config_id._get_schema_diff(
                    self.model_access_id, dataset_id
                )
                if drifted:
                    if not pbi_cols:
                        _logger.info(
                            "Power BI dataset/table missing for %s — recreating dataset.",
                            self.model_access_id.model_name,
                        )
                        self.model_access_id.sudo().write({'powerbi_dataset_id': False})
                        dataset_id = self.push_config_id._create_dataset(self.model_access_id)
                        force_full_push = True
                    elif self.push_config_id._sh_powerbi_type_only_drift(odoo_cols, pbi_cols):
                        # Only the column data types changed (for example the foreign key
                        # moved from String to Int64). Power BI cannot alter a column type
                        # in place, so the dataset is rebuilt instead of failing the push.
                        _logger.warning(
                            "Power BI dataset for %s recreated due to a column type change.",
                            self.model_access_id.model_name,
                        )
                        self.model_access_id.sudo().write({'powerbi_dataset_id': False})
                        dataset_id = self.push_config_id._create_dataset(self.model_access_id)
                        force_full_push = True
                        self.push_config_id._log(
                            f"Dataset recreated due to a column type change for "
                            f"{self.model_access_id.model_name}. Please rebind existing reports.",
                            log_type='push', state='success',
                            model_name=self.model_access_id.model_name,
                        )
                    else:
                        raise ValueError(
                            "Schema drift detected for %s. Review the schema diff screen from Push Now before recreating the dataset."
                            % self.model_access_id.model_name
                        )

            if force_full_push and self.is_delta:
                self.write({'is_delta': False})
                self.env.cr.commit()

            # ── Delta: narrow domain to records changed since last push ──────
            sync_start = fields.Datetime.now()
            if self.is_delta and self.model_access_id.last_push_write_date:
                base_domain = base_domain + [
                    ('write_date', '>', self.model_access_id.last_push_write_date)
                ]

            # Get total count if not set
            if not self.total_records:
                self.write({'total_records': Model.search_count(base_domain)})
                self.env.cr.commit()

            # Delta and realtime jobs append rows; full jobs clear first
            if self.batch_offset == 0 and not self.is_delta and not self.is_realtime:
                self.push_config_id._clear_rows(self.model_access_id, dataset_id)

            while self.batch_offset < self.total_records:
                records = Model.sh_powerbi_search_read(
                    domain=base_domain,
                    fields=[f.name for f in self.model_access_id.allowed_field_ids] or None,
                    offset=self.batch_offset,
                    limit=batch_size,
                )
                if not records:
                    break
                self.push_config_id._push_rows(
                    self.model_access_id,
                    dataset_id,
                    records,
                    batch_size=batch_size,
                )
                batch_offset = self.batch_offset + len(records)
                self.write({'batch_offset': batch_offset})
                self.env.cr.commit()
                _logger.info(
                    "Power BI Push: Processed batch for %s, offset: %s",
                    self.model_access_id.model_name, self.batch_offset,
                )

            # ── Update post-push timestamps ──────────────────────────────────
            access_vals = {
                'last_push_date': fields.Datetime.now(),
                'last_push_count': self.total_records,
            }
            if self.is_delta:
                # Record the sync_start time so next delta catches writes after this run
                access_vals['last_push_write_date'] = sync_start
            elif not self.is_delta and not self.is_realtime:
                # Full push — seed last_push_write_date so delta can be enabled next time
                access_vals['last_push_write_date'] = sync_start
            self.model_access_id.write(access_vals)
            self.model_access_id._update_sync_checkpoint(
                'powerbi_push',
                state='done',
                message=_('Queued Power BI push completed.'),
                record_count=self.total_records,
                sync_start=sync_start,
            )

            self.write({'state': 'done', 'error_message': False, 'next_retry_at': False})
            
            # Send real-time bus notification on successful sync
            model_desc = self.model_access_id.display_alias or self.model_access_id.name or self.model_access_id.model_name
            self.env['bus.bus']._sendone(self.env.user.partner_id, 'simple_notification', {
                'title': _('Power BI Push Success'),
                'message': _('Successfully pushed %(count)s records for %(model)s.') % {
                    'count': self.total_records,
                    'model': model_desc
                },
                'type': 'success',
            })

            self.push_config_id._log(
                f'Queued push completed for {self.model_access_id.model_name}.',
                log_type='push',
                state='success',
                model_name=self.model_access_id.model_name,
                record_count=self.total_records,
            )
            self.env.cr.commit()
            
        except Exception as e:
            self.env.cr.rollback()
            self._mark_failed(e)
            self.env.cr.commit()
            _logger.error("Power BI Push failed for queue %s: %s", self.id, e)
            self.model_access_id._update_sync_checkpoint('powerbi_push', state='failed', message=str(e))
            
            # Send real-time bus notification on failure
            model_desc = self.model_access_id.display_alias or self.model_access_id.name or self.model_access_id.model_name
            self.env['bus.bus']._sendone(self.env.user.partner_id, 'simple_notification', {
                'title': _('Power BI Push Failed'),
                'message': _('Failed to push records for %(model)s: %(error)s') % {
                    'model': model_desc,
                    'error': str(e)
                },
                'type': 'danger',
            })
            
            self.push_config_id._log(str(e), log_type='error', state='error', model_name=self.model_access_id.model_name)
