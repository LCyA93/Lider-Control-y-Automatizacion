# -*- coding: utf-8 -*-
# Copyright (C) Softhealer Technologies Pvt. Ltd.

import ast
from collections import defaultdict
from datetime import timedelta

from odoo import _, api, fields, models
from odoo.exceptions import AccessError, UserError


class SHPowerBIDashboard(models.Model):
    """Provide dashboard data and actions for the Power BI connector."""

    _inherit = 'sh.powerbi.push.config'

    @api.model
    def _sh_powerbi_check_dashboard_access(self):
        """Ensure the current user can manage the Power BI dashboard."""
        if not self.env.user.has_group('sh_power_bi_connector.group_powerbi_manager'):
            raise AccessError(_("You do not have permission to access the Power BI dashboard."))

    @api.model
    def _sh_powerbi_company_domain(self):
        """Return the company domain applied to dashboard records."""
        return [('company_id', 'in', self.env.companies.ids)]

    @api.model
    def _sh_powerbi_datetime_value(self, value):
        """Return a JSON-friendly datetime value."""
        return fields.Datetime.to_string(value) if value else False

    @api.model
    def _sh_powerbi_count_records(self, model_access):
        """Count matching source records for a model access configuration."""
        try:
            domain = ast.literal_eval(model_access.domain_filter or '[]')
            return self.env[model_access.model_name].sudo().search_count(domain)
        except Exception:
            return 0

    @api.model
    def _sh_powerbi_percent(self, value, total):
        """Return an integer percentage for dashboard chart widths."""
        return int(round((value / total) * 100)) if total else 0

    @api.model
    def _sh_powerbi_label_for_selection(self, model, field_name, value):
        """Return the display label for a selection value."""
        selection = dict(self.env[model]._fields[field_name].selection)
        return selection.get(value, value)

    @api.model
    def _sh_powerbi_sync_state_label(self, state):
        """Return a customer-facing sync status label."""
        labels = {
            'ready': _('Ready'),
            'not_synced': _('Not Synced'),
            'draft': _('Draft'),
            'processing': _('Processing'),
            'done': _('Done'),
            'failed': _('Failed'),
        }
        return labels.get(state, state)

    @api.model
    def _sh_powerbi_get_cron_info(self):
        """Return scheduled action details for the connector cron."""
        cron = self.env.ref('sh_power_bi_connector.sh_powerbi_auto_push_cron', raise_if_not_found=False)
        if not cron:
            return {
                'id': False,
                'name': _('Power BI: Auto Push to Datasets'),
                'active': False,
                'nextcall': False,
                'lastcall': False,
                'interval': _('Not configured'),
                'failure_count': 0,
            }
        interval_type = dict(cron._fields['interval_type'].selection).get(cron.interval_type, cron.interval_type)
        if cron.interval_number == 1 and interval_type and interval_type.endswith('s'):
            interval_type = interval_type[:-1]
        return {
            'id': cron.id,
            'name': cron.cron_name or cron.name,
            'active': bool(cron.active),
            'nextcall': self._sh_powerbi_datetime_value(cron.nextcall),
            'lastcall': self._sh_powerbi_datetime_value(cron.lastcall),
            'interval': _('%(number)s %(type)s', number=cron.interval_number, type=interval_type),
            'failure_count': cron.failure_count or 0,
        }

    @api.model
    def sh_powerbi_get_dashboard_data(self):
        """Return all Power BI dashboard metrics, charts, and detail rows."""
        self._sh_powerbi_check_dashboard_access()

        company_domain = self._sh_powerbi_company_domain()
        Config = self.env['sh.powerbi.push.config'].sudo()
        ModelAccess = self.env['sh.powerbi.model.access'].sudo()
        Queue = self.env['sh.powerbi.push.queue'].sudo()
        Log = self.env['sh.powerbi.log'].sudo()
        FabricConfig = self.env['sh.powerbi.fabric.config'].sudo()
        FabricRun = self.env['sh.powerbi.fabric.pipeline.run'].sudo()

        configs = Config.search(company_domain, order='id desc')
        model_accesses = ModelAccess.search(company_domain, order='sequence, id')
        queues = Queue.search(company_domain, order='id desc', limit=8)
        logs = Log.search(company_domain, order='datetime desc, id desc', limit=8)
        fabric_configs = FabricConfig.search(company_domain, order='id desc')
        fabric_runs = FabricRun.search(company_domain, order='started_at desc, id desc', limit=8)

        queue_states = ['draft', 'processing', 'done', 'failed']
        queue_counts = {
            state: Queue.search_count(company_domain + [('state', '=', state)])
            for state in queue_states
        }
        queue_total = sum(queue_counts.values())

        now = fields.Datetime.now()
        recent_logs = Log.search(company_domain + [('datetime', '>=', now - timedelta(days=13))], order='datetime asc, id asc')
        log_by_day = defaultdict(lambda: {'success': 0, 'error': 0})
        for log in recent_logs:
            day = fields.Date.to_string(fields.Datetime.context_timestamp(self, log.datetime).date())
            if log.state == 'success':
                log_by_day[day]['success'] += 1
            elif log.state == 'error':
                log_by_day[day]['error'] += 1

        chart_days = []
        for day_offset in range(13, -1, -1):
            day = fields.Date.to_string((fields.Datetime.context_timestamp(self, now) - timedelta(days=day_offset)).date())
            values = log_by_day[day]
            total = values['success'] + values['error']
            chart_days.append({
                'label': day[-5:],
                'success': values['success'],
                'error': values['error'],
                'total': total,
                'success_percent': self._sh_powerbi_percent(values['success'], total),
                'error_percent': self._sh_powerbi_percent(values['error'], total),
            })

        latest_queue_by_model = {}
        for queue in Queue.search(company_domain, order='id desc'):
            latest_queue_by_model.setdefault(queue.model_access_id.id, queue)
            if len(latest_queue_by_model) >= len(model_accesses):
                break

        model_rows = []
        for model_access in model_accesses:
            latest_queue = latest_queue_by_model.get(model_access.id)
            dataset_ready = bool(model_access.powerbi_dataset_id)
            sync_state = latest_queue.state if latest_queue else ('ready' if dataset_ready else 'not_synced')
            model_rows.append({
                'id': model_access.id,
                'name': model_access.name,
                'model_name': model_access.model_name,
                'alias': model_access.display_alias or model_access.model_id.name or model_access.model_name,
                'active': bool(model_access.is_active),
                'dataset_ready': dataset_ready,
                'sync_state': sync_state,
                'sync_state_label': self._sh_powerbi_sync_state_label(sync_state),
                'last_push_date': self._sh_powerbi_datetime_value(model_access.last_push_date),
                'last_push_count': model_access.last_push_count or 0,
                'source_count': self._sh_powerbi_count_records(model_access),
                'delta': bool(model_access.enable_delta),
                'realtime': bool(model_access.enable_realtime),
                'queue_id': latest_queue.id if latest_queue else False,
                'queue_error': latest_queue.error_message if latest_queue else False,
            })

        total_models = len(model_rows)
        active_models = len([row for row in model_rows if row['active']])
        dataset_ready_count = len([row for row in model_rows if row['dataset_ready']])
        failed_models = len([row for row in model_rows if row['sync_state'] == 'failed'])
        pending_models = len([row for row in model_rows if row['sync_state'] in ('draft', 'processing')])

        token_expiring_configs = configs.filtered(
            lambda rec: rec.powerbi_token_expiry and rec.powerbi_token_expiry <= now + timedelta(minutes=30)
        )
        authorized_configs = configs.filtered(lambda rec: rec.state == 'authorized')
        authorized_fabric_configs = fabric_configs.filtered(lambda rec: rec.state == 'authorized')
        failed_fabric_runs = FabricRun.search_count(company_domain + [('state', '=', 'failed')])

        alerts = []
        if not configs:
            alerts.append({'level': 'warning', 'message': _('Create and authorize a Power BI push configuration.')})
        if configs and not authorized_configs:
            alerts.append({'level': 'danger', 'message': _('No authorized Power BI configuration is available.')})
        if token_expiring_configs:
            alerts.append({'level': 'warning', 'message': _('One or more Power BI access tokens are expired or close to expiry.')})
        if queue_counts['failed']:
            if queue_counts['failed'] == 1:
                alerts.append({'level': 'danger', 'message': _('1 push queue job failed and needs review.')})
            else:
                alerts.append({'level': 'danger', 'message': _('%s push queue jobs failed and need review.') % queue_counts['failed']})
        if not self._sh_powerbi_get_cron_info()['active']:
            alerts.append({'level': 'warning', 'message': _('The automatic push schedule is disabled.')})
        if fabric_configs and not authorized_fabric_configs:
            alerts.append({'level': 'warning', 'message': _('Fabric configurations exist but none are authorized.')})
        if failed_fabric_runs:
            alerts.append({'level': 'danger', 'message': _('%s Fabric run(s) failed and need review.') % failed_fabric_runs})

        return {
            'generated_at': self._sh_powerbi_datetime_value(now),
            'kpis': [
                {
                    'key': 'configs',
                    'label': _('Authorized Configurations'),
                    'value': len(authorized_configs),
                    'subtitle': _('%s total') % len(configs),
                    'icon': 'fa-key',
                    'tone': 'success' if authorized_configs else 'danger',
                },
                {
                    'key': 'models',
                    'label': _('Active Models'),
                    'value': active_models,
                    'subtitle': _('%s configured') % total_models,
                    'icon': 'fa-table',
                    'tone': 'success' if active_models else 'warning',
                },
                {
                    'key': 'datasets',
                    'label': _('Datasets Ready'),
                    'value': dataset_ready_count,
                    'subtitle': _('%s waiting') % max(total_models - dataset_ready_count, 0),
                    'icon': 'fa-database',
                    'tone': 'success' if dataset_ready_count == total_models and total_models else 'warning',
                },
                {
                    'key': 'queues',
                    'label': _('Queue Health'),
                    'value': queue_counts['failed'],
                    'subtitle': _('Failed Jobs'),
                    'icon': 'fa-tasks',
                    'tone': 'danger' if queue_counts['failed'] else 'success',
                },
                {
                    'key': 'pending',
                    'label': _('Pending Syncs'),
                    'value': pending_models,
                    'subtitle': _('Draft or Processing'),
                    'icon': 'fa-refresh',
                    'tone': 'info' if pending_models else 'muted',
                },
                {
                    'key': 'fabric',
                    'label': _('Fabric Connections'),
                    'value': len(authorized_fabric_configs),
                    'subtitle': _('%s total') % len(fabric_configs),
                    'icon': 'fa-cloud',
                    'tone': 'success' if authorized_fabric_configs else ('warning' if fabric_configs else 'muted'),
                },
            ],
            'alerts': alerts,
            'configs': [{
                'id': config.id,
                'name': config.name,
                'state': config.state,
                'state_label': self._sh_powerbi_label_for_selection('sh.powerbi.push.config', 'state', config.state),
                'workspace_id': config.powerbi_workspace_id or '',
                'token_expiry': self._sh_powerbi_datetime_value(config.powerbi_token_expiry),
                'batch_size': config.push_batch_size or 0,
                'cron_interval_hours': config.cron_interval_hours or 0,
            } for config in configs],
            'cron': self._sh_powerbi_get_cron_info(),
            'queue_chart': [{
                'state': state,
                'label': dict(Queue._fields['state'].selection).get(state, state),
                'count': queue_counts[state],
                'percent': self._sh_powerbi_percent(queue_counts[state], queue_total),
            } for state in queue_states],
            'log_chart': chart_days,
            'model_summary': {
                'total': total_models,
                'ready': dataset_ready_count,
                'pending': pending_models,
                'failed': failed_models,
            },
            'model_rows': model_rows,
            'queue_rows': [{
                'id': queue.id,
                'model_name': queue.model_access_id.name or queue.model_access_id.model_name,
                'config_name': queue.push_config_id.name,
                'state': queue.state,
                'state_label': self._sh_powerbi_label_for_selection('sh.powerbi.push.queue', 'state', queue.state),
                'batch_offset': queue.batch_offset or 0,
                'total_records': queue.total_records or 0,
                'retry_count': queue.retry_count or 0,
                'next_retry_at': self._sh_powerbi_datetime_value(queue.next_retry_at),
                'last_attempt_at': self._sh_powerbi_datetime_value(queue.last_attempt_at),
                'error_message': queue.error_message or '',
            } for queue in queues],
            'log_rows': [{
                'id': log.id,
                'datetime': self._sh_powerbi_datetime_value(log.datetime),
                'type': log.log_type,
                'type_label': self._sh_powerbi_label_for_selection('sh.powerbi.log', 'log_type', log.log_type),
                'state': log.state,
                'state_label': self._sh_powerbi_label_for_selection('sh.powerbi.log', 'state', log.state),
                'model_name': log.model_name or '',
                'message': log.message or '',
                'record_count': log.record_count or 0,
            } for log in logs],
            'fabric_configs': [{
                'id': config.id,
                'name': config.name,
                'state': config.state,
                'state_label': self._sh_powerbi_label_for_selection('sh.powerbi.fabric.config', 'state', config.state),
                'workspace_name': config.workspace_name or '',
                'workspace_id': config.workspace_id or '',
                'target_type': config.default_target_type or '',
                'last_discovery_date': self._sh_powerbi_datetime_value(config.last_discovery_date),
            } for config in fabric_configs],
            'fabric_runs': [{
                'id': run.id,
                'started_at': self._sh_powerbi_datetime_value(run.started_at),
                'name': run.name,
                'config_name': run.fabric_config_id.name,
                'item_name': run.fabric_item_id.name or '',
                'model_name': run.model_access_id.name or run.model_access_id.model_name or '',
                'state': run.state,
                'state_label': self._sh_powerbi_label_for_selection('sh.powerbi.fabric.pipeline.run', 'state', run.state),
                'record_count': run.record_count or 0,
                'message': run.message or '',
            } for run in fabric_runs],
        }

    @api.model
    def sh_powerbi_dashboard_push_now(self, model_access_id):
        """Queue a manual push for the selected model access row."""
        self._sh_powerbi_check_dashboard_access()
        model_access = self.env['sh.powerbi.model.access'].browse(model_access_id).exists()
        if not model_access:
            raise UserError(_("Model access configuration not found."))
        config = model_access.config_id
        if not config:
            config = self.search([
                ('company_id', '=', model_access.company_id.id),
                ('state', '=', 'authorized'),
            ], limit=1)
        if not config:
            raise UserError(_("No authorized Power BI push configuration found for this model."))
        return config.action_push_model(model_access.id)

    @api.model
    def sh_powerbi_dashboard_test_connection(self, config_id):
        """Run the configured Power BI workspace connection test."""
        self._sh_powerbi_check_dashboard_access()
        config = self.browse(config_id).exists()
        if not config:
            raise UserError(_("Power BI configuration not found."))
        return config.action_test_connection()

    @api.model
    def sh_powerbi_dashboard_run_cron_now(self):
        """Run the Power BI scheduled push workflow immediately."""
        self._sh_powerbi_check_dashboard_access()
        self._cron_push_all()
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Power BI Schedule'),
                'message': _('The Power BI synchronization schedule has been executed.'),
                'type': 'success',
            },
        }

    @api.model
    def sh_powerbi_dashboard_toggle_cron(self, active):
        """Enable or disable the Power BI synchronization schedule."""
        self._sh_powerbi_check_dashboard_access()
        cron = self.env.ref('sh_power_bi_connector.sh_powerbi_auto_push_cron', raise_if_not_found=False)
        if not cron:
            raise UserError(_("Power BI synchronization schedule was not found."))
        cron.write({'active': bool(active)})
        return self.sh_powerbi_get_dashboard_data()

    @api.model
    def sh_powerbi_dashboard_process_queue(self, queue_id):
        """Process a queue job from the dashboard."""
        self._sh_powerbi_check_dashboard_access()
        queue = self.env['sh.powerbi.push.queue'].browse(queue_id).exists()
        if not queue:
            raise UserError(_("Power BI queue job not found."))
        queue.action_process_queue()
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Power BI Queue'),
                'message': _('The queue job has been processed.'),
                'type': 'success',
            },
        }

    @api.model
    def sh_powerbi_dashboard_open_model(self, model_access_id):
        """Open a model access record from the dashboard."""
        self._sh_powerbi_check_dashboard_access()
        return {
            'type': 'ir.actions.act_window',
            'name': _('Power BI Model Access'),
            'res_model': 'sh.powerbi.model.access',
            'view_mode': 'form',
            'res_id': model_access_id,
            'target': 'current',
        }
