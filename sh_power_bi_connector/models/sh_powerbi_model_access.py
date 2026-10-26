# -*- coding: utf-8 -*-
# Copyright (C) Softhealer Technologies Pvt. Ltd.

import ast
import base64
import csv
import io
import logging

from odoo import models, fields, api
from odoo.exceptions import UserError, ValidationError

_logger = logging.getLogger(__name__)

POWERBI_MAX_COLUMNS_PER_TABLE = 75
POWERBI_JOIN_FIELD = 'id'


class SHPowerBIModelAccess(models.Model):
    _name = 'sh.powerbi.model.access'
    _description = 'Power BI Model Access Configuration'
    _order = 'sequence, id'

    name = fields.Char(string='Label', required=True)
    company_id = fields.Many2one('res.company', string='Company', required=True, default=lambda self: self.env.company)
    config_id = fields.Many2one('sh.powerbi.push.config', string='Push Configuration', ondelete='cascade')
    model_id = fields.Many2one(
        'ir.model', string='Odoo Model', required=True,
        domain=[('transient', '=', False), ('abstract', '=', False)],
        ondelete='cascade',
    )
    model_name = fields.Char(related='model_id.model', string='Technical Model Name', readonly=True, store=True)
    display_alias = fields.Char(string='Power BI Table Name', help="Custom table name shown in Power BI. Defaults to the model description if blank.")
    target_mode = fields.Selection([
        ('powerbi_push', 'Power BI Push Dataset'),
        ('fabric_kql', 'Fabric Eventhouse / KQL'),
        ('fabric_pipeline', 'Fabric Pipeline / Copy Job'),
    ], string='Sync Target', default='powerbi_push', required=True)
    fabric_config_id = fields.Many2one('sh.powerbi.fabric.config', string='Fabric Configuration', ondelete='set null')
    fabric_item_id = fields.Many2one('sh.powerbi.fabric.item', string='Fabric Target Item', ondelete='set null')
    fabric_target_name = fields.Char(string='Fabric Target Table/Item')
    fabric_sync_state = fields.Selection([
        ('not_synced', 'Not Synced'),
        ('running', 'Running'),
        ('done', 'Done'),
        ('failed', 'Failed'),
    ], string='Fabric Sync State', default='not_synced', readonly=True)
    last_fabric_sync_date = fields.Datetime(string='Last Fabric Sync', readonly=True)
    fabric_last_message = fields.Text(string='Last Fabric Message', readonly=True)
    checkpoint_ids = fields.One2many('sh.powerbi.sync.checkpoint', 'model_access_id', string='Sync Checkpoints')
    allowed_field_ids = fields.Many2many(
        'ir.model.fields', string='Allowed Fields',
        domain="[('model_id', '=', model_id), ('store', '=', True), ('ttype', 'not in', ['binary', 'html', 'json', 'properties', 'properties_definition'])]",
        help="Select specific fields to expose. Leaving blank exposes all stored fields. "
             "If the effective field list has more than 75 columns, Odoo splits it into multiple Power BI tables.",
    )
    domain_filter = fields.Char(string='Row Filter (Domain)', default='[]', help="Odoo domain to restrict which records Power BI can access. E.g. [('state','=','sale')]")
    is_active = fields.Boolean(string='Active', default=True)
    sequence = fields.Integer(string='Sequence', default=10)
    last_push_date = fields.Datetime(string='Last Push', readonly=True)
    last_push_count = fields.Integer(string='Last Push Records', readonly=True)
    powerbi_dataset_id = fields.Char(string='Power BI Dataset ID', readonly=True, copy=False)
    odoo_record_count = fields.Integer(string='Matching Records', compute='_compute_odoo_record_count', store=False)
    powerbi_selected_field_count = fields.Integer(
        string='Power BI Columns',
        compute='_compute_powerbi_table_stats',
        help="Effective column count sent to Power BI, including the shared id column.",
    )
    powerbi_table_count = fields.Integer(
        string='Power BI Tables',
        compute='_compute_powerbi_table_stats',
        help="Estimated number of Power BI push tables generated for this model.",
    )

    # ── Feature 1: Incremental / Delta Push ──────────────────────────────────
    enable_delta = fields.Boolean(
        string='Incremental Push',
        default=False,
        help="When enabled, only records changed since the last push are sent "
             "(write_date > last sync date). Rows are appended — existing rows "
             "are NOT deleted. Disable for a full clear+replace push.",
    )
    last_push_write_date = fields.Datetime(
        string='Last Synced Write Date',
        readonly=True,
        copy=False,
        help="Timestamp of the last successful incremental push. "
             "Next delta push will fetch records with write_date after this value.",
    )

    # ── Feature 2: Real-Time Push on Record Save ─────────────────────────────
    enable_realtime = fields.Boolean(
        string='Real-Time Push on Save',
        default=False,
        help="When enabled, any create or write on this model immediately queues "
             "a Power BI push job. Requires an authorized Push Configuration.",
    )

    @api.depends('model_id', 'domain_filter')
    def _compute_odoo_record_count(self):
        for rec in self:
            if not rec.model_id:
                rec.odoo_record_count = 0
                continue
            try:
                domain = ast.literal_eval(rec.domain_filter or '[]')
                rec.odoo_record_count = self.env[rec.model_name].sudo().search_count(domain)
            except Exception:
                rec.odoo_record_count = 0

    @api.depends('model_id', 'allowed_field_ids', 'company_id.sh_powerbi_relation_format')
    def _compute_powerbi_table_stats(self):
        for rec in self:
            if not rec.model_id or not rec.model_name:
                rec.powerbi_selected_field_count = 0
                rec.powerbi_table_count = 0
                continue
            # Reuse the push-side field builder so the counters always match the
            # dataset that is really created (including companion display columns).
            field_names = self.env['sh.powerbi.push.config']._get_powerbi_field_names(rec)
            column_count = len(field_names)
            chunk_size = POWERBI_MAX_COLUMNS_PER_TABLE - 1
            extra_columns = max(column_count - 1, 0)
            table_count = max((extra_columns + chunk_size - 1) // chunk_size, 1) if column_count else 0
            rec.powerbi_selected_field_count = column_count
            rec.powerbi_table_count = table_count

    @api.constrains('domain_filter')
    def _check_domain_filter(self):
        for rec in self:
            if rec.domain_filter:
                try:
                    ast.literal_eval(rec.domain_filter)
                except Exception as e:
                    raise ValidationError(f"Invalid domain filter: {e}") from e

    @api.onchange('model_id')
    def _onchange_model_id(self):
        self.allowed_field_ids = [(5,)]
        self.powerbi_dataset_id = False

    def action_preview_data(self):
        """Preview first 10 records with configured fields and domain."""
        self.ensure_one()
        if not self.model_id:
            return
        fields_list = [f.name for f in self.allowed_field_ids] or []
        domain = ast.literal_eval(self.domain_filter or '[]')
        try:
            Model = self.env[self.model_name].sudo()
            data = Model.sh_powerbi_search_read(domain=domain, fields=fields_list or None, limit=10)
            if data:
                preview_lines = []
                headers = list(data[0].keys())
                preview_lines.append(' | '.join(str(h) for h in headers))
                preview_lines.append('-' * min(120, len(preview_lines[0])))
                for row in data[:5]:
                    preview_lines.append(' | '.join(str(row.get(h, ''))[:20] for h in headers))
                msg = '\n'.join(preview_lines)
                if len(data) > 5:
                    msg += f'\n... and {len(data) - 5} more rows (showing 5 of {len(data)})'
            else:
                msg = 'No records found matching the current filter.'
        except Exception as e:
            msg = f'Preview failed: {e}'
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': f'Data Preview — {self.name}',
                'message': msg,
                'type': 'info',
                'sticky': True,
            },
        }

    def action_export_csv(self):
        """Export configured model data as a downloadable CSV file."""
        self.ensure_one()
        if not self.model_id:
            raise UserError("Please select a model before exporting.")
        domain = ast.literal_eval(self.domain_filter or '[]')
        field_names = [f.name for f in self.allowed_field_ids] or None
        records = self.env[self.model_name].sudo().sh_powerbi_search_read(
            domain=domain, fields=field_names, limit=None
        )
        if not records:
            raise UserError("No records found for the current configuration.")
        buf = io.StringIO()
        writer = csv.DictWriter(buf, fieldnames=list(records[0].keys()))
        writer.writeheader()
        writer.writerows(records)
        csv_bytes = buf.getvalue().encode('utf-8')
        filename = f"{self.display_alias or self.model_name}.csv"
        attachment = self.env['ir.attachment'].sudo().create({
            'name': filename,
            'type': 'binary',
            'datas': base64.b64encode(csv_bytes).decode(),
            'mimetype': 'text/csv',
            'res_model': self._name,
            'res_id': self.id,
        })
        return {
            'type': 'ir.actions.act_url',
            'url': f'/web/content/{attachment.id}?download=true',
            'target': 'self',
        }

    def action_validate_data_quality(self):
        """Open validation wizard for this model access record."""
        self.ensure_one()
        wizard = self.env['sh.powerbi.validation.wizard'].create({
            'model_access_id': self.id,
        })
        try:
            wizard._run_validation()
        except ValidationError:
            pass
        return {
            'type': 'ir.actions.act_window',
            'name': 'Data Quality Validation',
            'res_model': 'sh.powerbi.validation.wizard',
            'view_mode': 'form',
            'res_id': wizard.id,
            'target': 'new',
        }

    def _get_or_create_checkpoint(self, target=None):
        self.ensure_one()
        target = target or self.target_mode or 'powerbi_push'
        checkpoint = self.env['sh.powerbi.sync.checkpoint'].sudo().search([
            ('model_access_id', '=', self.id),
            ('target', '=', target),
        ], limit=1)
        if not checkpoint:
            checkpoint = self.env['sh.powerbi.sync.checkpoint'].sudo().create({
                'name': f'{self.name} - {target}',
                'model_access_id': self.id,
                'company_id': self.company_id.id,
                'target': target,
            })
        return checkpoint

    def _update_sync_checkpoint(self, target, state='done', message=False, record_count=0, sync_start=False):
        self.ensure_one()
        checkpoint = self._get_or_create_checkpoint(target)
        values = {
            'state': state,
            'message': message or False,
            'last_record_count': record_count or 0,
        }
        if state == 'done':
            values.update({
                'last_success_at': fields.Datetime.now(),
                'last_write_date': sync_start or fields.Datetime.now(),
            })
        checkpoint.write(values)
        return checkpoint

    def action_run_target_sync(self):
        """Run the configured target for this model access."""
        self.ensure_one()
        if self.target_mode == 'powerbi_push':
            config = self.config_id or self.env['sh.powerbi.push.config'].search([
                ('company_id', '=', self.company_id.id),
                ('state', '=', 'authorized'),
            ], limit=1)
            if not config:
                raise UserError("No authorized Power BI push configuration found.")
            return config.action_push_model(self.id)
        return self.action_run_fabric_sync()

    def action_run_fabric_sync(self):
        """Run Fabric-oriented sync using the configured Fabric item or config."""
        self.ensure_one()
        if self.target_mode not in ('fabric_kql', 'fabric_pipeline'):
            raise UserError("Fabric sync is only available for Fabric target modes.")
        if not self.fabric_config_id:
            raise UserError("Please select a Fabric configuration first.")
        sync_start = fields.Datetime.now()
        try:
            domain = ast.literal_eval(self.domain_filter or '[]')
            record_count = self.env[self.model_name].sudo().search_count(domain)
            item = self.fabric_item_id
            if self.target_mode == 'fabric_pipeline':
                if not item:
                    item = self.fabric_config_id.item_ids.filtered(
                        lambda rec: rec.is_default_target and rec.item_type in ('pipeline', 'copy_job')
                    )[:1]
                if not item:
                    raise UserError("Please select a Fabric Pipeline or Copy Job item.")
                run_action = item.action_run_item()
                run_id = run_action.get('res_id')
                if run_id:
                    self.env['sh.powerbi.fabric.pipeline.run'].browse(run_id).write({
                        'model_access_id': self.id,
                        'record_count': record_count,
                    })
                message = "Fabric pipeline/copy job started."
                state = 'running'
            else:
                target_name = self.fabric_target_name or self.display_alias or self.model_id.name or self.model_name
                run = self.env['sh.powerbi.fabric.pipeline.run'].sudo().create({
                    'name': f'Fabric KQL publish - {target_name}',
                    'fabric_config_id': self.fabric_config_id.id,
                    'fabric_item_id': item.id if item else False,
                    'model_access_id': self.id,
                    'company_id': self.company_id.id,
                    'workspace_id': self.fabric_config_id.workspace_id,
                    'item_id': item.external_id if item else False,
                    'state': 'done',
                    'started_at': sync_start,
                    'finished_at': fields.Datetime.now(),
                    'record_count': record_count,
                    'message': 'KQL target prepared from Odoo model access. Use Fabric pipeline/copy job for physical loading.',
                })
                message = run.message
                state = 'done'
            self.write({
                'fabric_sync_state': state,
                'last_fabric_sync_date': fields.Datetime.now(),
                'fabric_last_message': message,
            })
            self._update_sync_checkpoint(self.target_mode, state='done' if state == 'done' else 'running',
                                         message=message, record_count=record_count, sync_start=sync_start)
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': 'Fabric',
                    'message': message,
                    'type': 'success' if state != 'failed' else 'danger',
                },
            }
        except Exception as error:
            self.write({
                'fabric_sync_state': 'failed',
                'fabric_last_message': str(error),
            })
            self._update_sync_checkpoint(self.target_mode, state='failed', message=str(error))
            raise

    @api.model
    @api.readonly
    def get_powerbi_model_config(self):
        """Return configured model list for the Power BI .mez connector.

        Called via /json/2/sh.powerbi.model.access/get_powerbi_model_config
        """
        configs = self.sudo().search([
            ('company_id', '=', self.env.company.id),
            ('is_active', '=', True),
        ], order='sequence, id')
        result = []
        for rec in configs:
            result.append({
                'model': rec.model_name or '',
                'alias': rec.display_alias or rec.model_id.name or rec.model_name,
                'fields': [f.name for f in rec.allowed_field_ids],
                'domain': rec.domain_filter or '[]',
                'target_mode': rec.target_mode,
            })
        return result

    @api.model
    @api.readonly
    def get_powerbi_model_catalog(self):
        """Return a JSON-2-friendly catalog for dynamic model discovery."""
        configs = self.sudo().search([
            ('company_id', '=', self.env.company.id),
            ('is_active', '=', True),
        ], order='sequence, id')
        result = []
        for rec in configs:
            domain = []
            if rec.domain_filter:
                try:
                    domain = ast.literal_eval(rec.domain_filter)
                except Exception:
                    domain = []
            result.append({
                'id': rec.id,
                'model': rec.model_name or '',
                'alias': rec.display_alias or rec.model_id.name or rec.model_name,
                'fields': [f.name for f in rec.allowed_field_ids],
                'domain': domain,
                'fetch_url': f'/json/2/{rec.model_name}/sh_powerbi_fetch_rows' if rec.model_name else '',
                'count_url': f'/json/2/{rec.model_name}/sh_powerbi_count_rows' if rec.model_name else '',
            })
        return result
