# -*- coding: utf-8 -*-
# Copyright (C) Softhealer Technologies Pvt. Ltd.

import base64
import json
import logging

import requests

from odoo import _, api, fields, models
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)

POWERBI_EXPORT_TIMEOUT = 30


class SHPowerBIWorkspace(models.Model):
    """Cached Power BI workspace."""

    _name = 'sh.powerbi.workspace'
    _description = 'Power BI Workspace'
    _order = 'name'

    name = fields.Char(string='Workspace Name', required=True)
    external_id = fields.Char(string='Workspace ID', required=True, index=True)
    push_config_id = fields.Many2one('sh.powerbi.push.config', string='Push Configuration', required=True, ondelete='cascade')
    company_id = fields.Many2one('res.company', string='Company', required=True, default=lambda self: self.env.company)
    is_selected = fields.Boolean(string='Selected')
    raw_payload = fields.Text(string='Raw Payload', readonly=True)
    description = fields.Html(string='Description')
    
    count_datasets = fields.Integer(string='Dataset Count', compute='_compute_asset_counts')
    count_reports = fields.Integer(string='Report Count', compute='_compute_asset_counts')
    count_dashboards = fields.Integer(string='Dashboard Count', compute='_compute_asset_counts')
    count_eventhouses = fields.Integer(string='Eventhouse Count', compute='_compute_asset_counts')
    count_databases = fields.Integer(string='Database Count', compute='_compute_asset_counts')

    dataset_ids = fields.One2many('sh.powerbi.dataset', 'workspace_rel_id', string='Datasets')
    report_ids = fields.One2many('sh.powerbi.report', 'workspace_rel_id', string='Reports')
    dashboard_ids = fields.One2many('sh.powerbi.dashboard.asset', 'workspace_rel_id', string='Dashboards')
    eventhouse_ids = fields.One2many('sh.powerbi.fabric.item', 'workspace_rel_id', string='Eventhouses', domain=[('item_type', '=', 'eventhouse')])

    def _compute_asset_counts(self):
        for rec in self:
            rec.count_datasets = len(rec.dataset_ids)
            rec.count_reports = len(rec.report_ids)
            rec.count_dashboards = len(rec.dashboard_ids)
            rec.count_eventhouses = len(rec.eventhouse_ids)
            rec.count_databases = self.env['sh.powerbi.fabric.item'].search_count([
                ('workspace_id', '=', rec.external_id),
                ('item_type', 'in', ('kql_database', 'warehouse'))
            ])

    def action_use_workspace(self):
        for workspace in self:
            workspace.push_config_id.write({'powerbi_workspace_id': workspace.external_id})
            workspace.push_config_id.workspace_ids.write({'is_selected': False})
            workspace.is_selected = True

    def action_view_dashboards(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('Dashboards'),
            'res_model': 'sh.powerbi.dashboard.asset',
            'view_mode': 'list,form',
            'domain': [('workspace_rel_id', '=', self.id)],
            'context': {'default_workspace_rel_id': self.id, 'default_push_config_id': self.push_config_id.id},
        }

    def action_view_datasets(self):
        self.ensure_one()
        return {
            'name': 'Datasets',
            'type': 'ir.actions.act_window',
            'res_model': 'sh.powerbi.dataset',
            'view_mode': 'list,form',
            'domain': [('workspace_id', '=', self.external_id)],
            'context': {'default_workspace_id': self.external_id, 'default_push_config_id': self.push_config_id.id},
        }

    def action_view_reports(self):
        self.ensure_one()
        return {
            'name': 'Reports',
            'type': 'ir.actions.act_window',
            'res_model': 'sh.powerbi.report',
            'view_mode': 'list,form',
            'domain': [('workspace_id', '=', self.external_id)],
            'context': {'default_workspace_id': self.external_id, 'default_push_config_id': self.push_config_id.id},
        }

    def action_view_eventhouses(self):
        self.ensure_one()
        return {
            'name': 'Eventhouses',
            'type': 'ir.actions.act_window',
            'res_model': 'sh.powerbi.fabric.item',
            'view_mode': 'list,form',
            'domain': [('workspace_id', '=', self.external_id), ('item_type', '=', 'eventhouse')],
            'context': {'default_workspace_id': self.external_id, 'default_push_config_id': self.push_config_id.id, 'default_item_type': 'eventhouse'},
        }

    def action_view_databases(self):
        self.ensure_one()
        return {
            'name': 'Databases',
            'type': 'ir.actions.act_window',
            'res_model': 'sh.powerbi.fabric.item',
            'view_mode': 'list,form',
            'domain': [('workspace_id', '=', self.external_id), ('item_type', 'in', ('kql_database', 'warehouse'))],
            'context': {'default_workspace_id': self.external_id, 'default_push_config_id': self.push_config_id.id},
        }

    def action_fetch_eventhouses(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': 'Fetching Eventhouses',
                'message': 'Command sent to fetch Eventhouses for this Workspace.',
                'type': 'info',
                'sticky': False,
            }
        }

    def action_fetch_datasets(self):
        self.ensure_one()
        if hasattr(self.push_config_id, 'action_sync_datasets'):
            self.push_config_id.action_sync_datasets()
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': 'Fetching Datasets',
                'message': 'Datasets fetch triggered.',
                'type': 'success',
                'sticky': False,
            }
        }

    def action_fetch_reports(self):
        self.ensure_one()
        if hasattr(self.push_config_id, 'action_sync_reports'):
            self.push_config_id.action_sync_reports()
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': 'Fetching Reports',
                'message': 'Reports fetch triggered.',
                'type': 'success',
                'sticky': False,
            }
        }

    def action_fetch_dashboards(self):
        """Discover dashboards in the configured workspace."""
        self.ensure_one()
        if not self.external_id:
            raise UserError(_("Workspace ID is required to fetch dashboards."))
        endpoint = f"groups/{self.external_id}/dashboards"
        success, result = self.push_config_id._make_powerbi_request('GET', endpoint, scoped=False)
        if not success:
            raise UserError(_("Failed to discover Power BI dashboards. API Response: %r") % result)
            
        Dashboard = self.env['sh.powerbi.dashboard.asset'].sudo()
        for dash in result.get('value', []):
            dash_id = dash.get('id')
            if not dash_id:
                continue
                
            record = Dashboard.search([
                ('push_config_id', '=', self.push_config_id.id),
                ('external_id', '=', dash_id),
            ], limit=1)
            
            values = {
                'name': dash.get('displayName') or dash_id,
                'external_id': dash_id,
                'push_config_id': self.push_config_id.id,
                'workspace_id': self.external_id,
                'company_id': self.company_id.id,
                'is_read_only': dash.get('isReadOnly', False),
                'web_url': dash.get('webUrl', ''),
                'embed_url': dash.get('embedUrl', ''),
            }
            if record:
                record.write(values)
            else:
                Dashboard.create(values)

        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Power BI'),
                'message': _('Power BI dashboards have been discovered.'),
                'type': 'success',
                'next': {'type': 'ir.actions.client', 'tag': 'reload'},
            },
        }

class SHPowerBIDashboardAsset(models.Model):
    """Cached Power BI Dashboard."""

    _name = 'sh.powerbi.dashboard.asset'
    _description = 'Power BI Dashboard Asset'
    _order = 'name'

    name = fields.Char(string='Dashboard Name', required=True)
    external_id = fields.Char(string='Dashboard ID', required=True, index=True)
    push_config_id = fields.Many2one('sh.powerbi.push.config', string='Push Configuration', required=True, ondelete='cascade')
    workspace_id = fields.Char(string='Workspace ID')
    workspace_rel_id = fields.Many2one('sh.powerbi.workspace', compute='_compute_workspace_rel', store=True, string='Workspace Link')
    company_id = fields.Many2one('res.company', string='Company', required=True, default=lambda self: self.env.company)
    
    is_read_only = fields.Boolean(string='Read Only', readonly=True)
    web_url = fields.Char(string='Web URL', readonly=True)
    embed_url = fields.Char(string='Embed URL', readonly=True)
    embed_token = fields.Char(string='Embed Token', readonly=True, copy=False)
    embed_token_expiry = fields.Datetime(string='Embed Token Expiry', readonly=True, copy=False)

    @api.depends('workspace_id')
    def _compute_workspace_rel(self):
        for rec in self:
            if rec.workspace_id:
                ws = self.env['sh.powerbi.workspace'].search([('external_id', '=', rec.workspace_id)], limit=1)
                rec.workspace_rel_id = ws.id if ws else False
            else:
                rec.workspace_rel_id = False

    def action_open_in_powerbi(self):
        """Open the dashboard directly in app.powerbi.com."""
        self.ensure_one()
        url = self.web_url or f"https://app.powerbi.com/groups/{self.workspace_id}/dashboards/{self.external_id}"
        return {
            'type': 'ir.actions.act_url',
            'url': url,
            'target': 'new',
        }

    def action_generate_embed_token(self):
        for dashboard in self:
            payload = {'accessLevel': 'view'}
            endpoint = f"dashboards/{dashboard.external_id}/GenerateToken"
            success, result = dashboard.push_config_id._make_powerbi_request('POST', endpoint, data=payload, scoped=True)
            
            if not success:
                raise UserError(_("Power BI dashboard embed token generation failed: %s") % result)
                
            expiry_str = result.get('expiration', '')
            try:
                from datetime import datetime as _dt
                from datetime import timedelta
                expiry = _dt.strptime(expiry_str, '%Y-%m-%dT%H:%M:%SZ') if expiry_str else (
                    fields.Datetime.now() + timedelta(hours=1)
                )
            except Exception:
                from datetime import timedelta
                expiry = fields.Datetime.now() + timedelta(hours=1)
            
            dashboard.write({
                'embed_token': result.get('token'),
                'embed_token_expiry': expiry,
            })
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Power BI'),
                'message': _('Dashboard embed token has been generated.'),
                'type': 'success',
                'sticky': False,
            }
        }

    def action_view_embedded(self):
        """Open the embedded dashboard view."""
        self.ensure_one()
        if not self.embed_url or not self.embed_token:
            self.action_generate_embed_token()
        return {
            'name': _('Dashboard Preview'),
            'type': 'ir.actions.act_window',
            'res_model': 'sh.powerbi.report.preview.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {
                'default_dashboard_id': self.id,
                'default_embed_type': 'dashboard',
            }
        }




class SHPowerBIDataset(models.Model):
    """Cached Power BI semantic model/dataset."""

    _name = 'sh.powerbi.dataset'
    _description = 'Power BI Dataset'
    _order = 'name'

    name = fields.Char(string='Dataset Name', required=True)
    external_id = fields.Char(string='Dataset ID', required=True, index=True)
    push_config_id = fields.Many2one('sh.powerbi.push.config', string='Push Configuration', required=True, ondelete='cascade')
    workspace_id = fields.Char(string='Workspace ID')
    workspace_rel_id = fields.Many2one('sh.powerbi.workspace', compute='_compute_workspace_rel', store=True, string='Workspace Link')
    company_id = fields.Many2one('res.company', string='Company', required=True, default=lambda self: self.env.company)
    configured_by = fields.Char(string='Configured By')
    is_refreshable = fields.Boolean(string='Refreshable')
    last_refresh_status = fields.Char(string='Last Refresh Status', readonly=True)
    last_refresh_date = fields.Datetime(string='Last Refresh', readonly=True)
    refresh_history = fields.Text(string='Refresh History', readonly=True)
    raw_payload = fields.Text(string='Raw Payload', readonly=True)

    @api.depends('workspace_id')
    def _compute_workspace_rel(self):
        for rec in self:
            if rec.workspace_id:
                rec.workspace_rel_id = self.env['sh.powerbi.workspace'].search([('external_id', '=', rec.workspace_id)], limit=1)
            else:
                rec.workspace_rel_id = False


    def action_refresh_dataset(self):
        for dataset in self:
            endpoint = f"datasets/{dataset.external_id}/refreshes"
            success, result = dataset.push_config_id._make_powerbi_request('POST', endpoint, data={'notifyOption': 'NoNotification'})
            if not success:
                raise UserError(_("Power BI dataset refresh failed: %s") % result)
            dataset.write({
                'last_refresh_status': _('Requested'),
                'last_refresh_date': fields.Datetime.now(),
                'refresh_history': json.dumps(result, default=str),
            })
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Power BI'),
                'message': _('Dataset refresh has been requested.'),
                'type': 'success',
            },
        }

    def action_get_refresh_history(self):
        for dataset in self:
            endpoint = f"datasets/{dataset.external_id}/refreshes"
            success, result = dataset.push_config_id._make_powerbi_request('GET', endpoint)
            if not success:
                raise UserError(_("Power BI refresh history failed: %s") % result)
            refreshes = result.get('value', [])
            latest = refreshes[0] if refreshes else {}
            dataset.write({
                'last_refresh_status': latest.get('status') or '',
                'last_refresh_date': fields.Datetime.now(),
                'refresh_history': json.dumps(result, default=str),
            })
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Power BI'),
                'message': _('Refresh history has been updated.'),
                'type': 'success',
            },
        }

    def action_push_now(self):
        """Push Odoo data for every model_access linked to this dataset."""
        pushed = 0
        for dataset in self:
            model_access_records = self.env['sh.powerbi.model.access'].sudo().search([
                ('powerbi_dataset_id', '=', dataset.external_id),
                ('config_id', '=', dataset.push_config_id.id),
                ('is_active', '=', True),
            ])
            if not model_access_records:
                # Fallback: push all active model_access records for this config
                model_access_records = self.env['sh.powerbi.model.access'].sudo().search([
                    ('config_id', '=', dataset.push_config_id.id),
                    ('is_active', '=', True),
                ])
            for ma in model_access_records:
                dataset.push_config_id.action_push_model(ma.id)
                pushed += 1
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Power BI'),
                'message': _('Push Now queued for %d model(s).') % pushed,
                'type': 'success',
            },
        }


class SHPowerBIReport(models.Model):
    """Cached Power BI report."""

    _name = 'sh.powerbi.report'
    _description = 'Power BI Report'
    _order = 'name'

    name = fields.Char(string='Report Name', required=True)
    external_id = fields.Char(string='Report ID', required=True, index=True)
    push_config_id = fields.Many2one('sh.powerbi.push.config', string='Push Configuration', required=True, ondelete='cascade')
    dataset_id = fields.Many2one('sh.powerbi.dataset', string='Dataset', ondelete='set null')
    powerbi_dataset_id = fields.Char(string='Power BI Dataset ID')
    workspace_id = fields.Char(string='Workspace ID')
    workspace_rel_id = fields.Many2one('sh.powerbi.workspace', compute='_compute_workspace_rel', store=True, string='Workspace Link')
    company_id = fields.Many2one('res.company', string='Company', required=True, default=lambda self: self.env.company)
    report_type = fields.Char(string='Report Type')
    web_url = fields.Char(string='Web URL')
    embed_url = fields.Char(string='Embed URL')
    embed_token = fields.Char(string='Embed Token', readonly=True, copy=False)
    embed_token_expiry = fields.Datetime(string='Embed Token Expiry', readonly=True, copy=False)
    raw_payload = fields.Text(string='Raw Payload', readonly=True)

    def action_view_embedded(self):
        """Show an embedded preview of the report inside an Odoo popup."""
        self.ensure_one()
        if not self.embed_url or not self.embed_token:
            self.action_generate_embed_token()
        
        wizard = self.env['sh.powerbi.report.preview.wizard'].create({'report_id': self.id})
        return {
            'name': f'Preview: {self.name}',
            'type': 'ir.actions.act_window',
            'res_model': 'sh.powerbi.report.preview.wizard',
            'res_id': wizard.id,
            'view_mode': 'form',
            'target': 'new',
        }

    def action_open_in_powerbi(self):
        """Open the report directly in app.powerbi.com."""
        self.ensure_one()
        workspace_id = self.workspace_id or self.push_config_id.workspace_id
        url = self.web_url or f"https://app.powerbi.com/groups/{workspace_id}/reports/{self.external_id}"
        return {
            'type': 'ir.actions.act_url',
            'url': url,
            'target': 'new',
        }

    @api.depends('workspace_id')
    def _compute_workspace_rel(self):
        for rec in self:
            if rec.workspace_id:
                rec.workspace_rel_id = self.env['sh.powerbi.workspace'].search([('external_id', '=', rec.workspace_id)], limit=1)
            else:
                rec.workspace_rel_id = False


    def action_generate_embed_token(self):
        for report in self:
            if not report.powerbi_dataset_id:
                raise UserError(_("Power BI Dataset ID is required to generate an embed token."))
            payload = {
                'reports': [{'id': report.external_id}],
                'datasets': [{'id': report.powerbi_dataset_id}],
                'targetWorkspaces': [{'id': report.workspace_id or report.push_config_id.powerbi_workspace_id}],
            }
            success, result = report.push_config_id._make_powerbi_request(
                'POST',
                'GenerateToken',
                data=payload,
                scoped=False,
            )
            if not success:
                raise UserError(_("Power BI embed token generation failed: %s") % result)
            expiry_str = result.get('expiration', '')
            try:
                from datetime import datetime as _dt
                from datetime import timedelta
                expiry = _dt.strptime(expiry_str, '%Y-%m-%dT%H:%M:%SZ') if expiry_str else (
                    fields.Datetime.now() + timedelta(hours=1)
                )
            except Exception:
                from datetime import timedelta
                expiry = fields.Datetime.now() + timedelta(hours=1)
            
            report.write({
                'embed_token': result.get('token'),
                'embed_token_expiry': expiry,
            })
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Power BI'),
                'message': _('Embed token has been generated.'),
                'type': 'success',
            },
        }

    def action_export_pdf(self):
        return self._create_export_job('PDF')

    def action_export_pptx(self):
        return self._create_export_job('PPTX')

    def action_export_png(self):
        return self._create_export_job('PNG')

    def _create_export_job(self, export_format):
        self.ensure_one()
        job = self.env['sh.powerbi.export.job'].create({
            'name': f"{self.name} - {export_format}",
            'push_config_id': self.push_config_id.id,
            'report_id': self.id,
            'company_id': self.company_id.id,
            'export_format': export_format,
        })
        job.action_start_export()
        return {
            'type': 'ir.actions.act_window',
            'name': _('Power BI Export Job'),
            'res_model': 'sh.powerbi.export.job',
            'view_mode': 'form',
            'res_id': job.id,
            'target': 'current',
        }

    def action_rebind_to_dataset(self):
        self.ensure_one()
        if not self.dataset_id:
            raise UserError(_("Please select a target dataset before rebinding the report."))
        endpoint = f"reports/{self.external_id}/Rebind"
        success, result = self.push_config_id._make_powerbi_request(
            'POST',
            endpoint,
            data={'datasetId': self.dataset_id.external_id},
        )
        if not success:
            raise UserError(_("Power BI report rebind failed: %s") % result)
        self.powerbi_dataset_id = self.dataset_id.external_id
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Power BI'),
                'message': _('Report has been rebound to the selected dataset.'),
                'type': 'success',
            },
        }


class SHPowerBIExportJob(models.Model):
    """Power BI export-to-file job."""

    _name = 'sh.powerbi.export.job'
    _description = 'Power BI Export Job'
    _order = 'id desc'

    name = fields.Char(string='Name', required=True)
    push_config_id = fields.Many2one('sh.powerbi.push.config', string='Push Configuration', required=True, ondelete='cascade')
    report_id = fields.Many2one('sh.powerbi.report', string='Report', required=True, ondelete='cascade')
    company_id = fields.Many2one('res.company', string='Company', required=True, default=lambda self: self.env.company)
    export_format = fields.Selection([
        ('PDF', 'PDF'),
        ('PPTX', 'PowerPoint'),
        ('PNG', 'PNG'),
    ], string='Format', required=True, default='PDF')
    export_id = fields.Char(string='Export ID', readonly=True)
    state = fields.Selection([
        ('draft', 'Draft'),
        ('running', 'Running'),
        ('done', 'Done'),
        ('failed', 'Failed'),
    ], string='Status', default='draft')
    percent_complete = fields.Integer(string='Percent Complete', readonly=True)
    error_message = fields.Text(string='Error Message', readonly=True)
    export_file = fields.Binary(string='Exported File', readonly=True)
    export_filename = fields.Char(string='Filename', readonly=True)
    raw_payload = fields.Text(string='Raw Payload', readonly=True)

    def action_start_export(self):
        for job in self:
            endpoint = f"reports/{job.report_id.external_id}/ExportTo"
            payload = {'format': job.export_format}
            success, result = job.push_config_id._make_powerbi_request('POST', endpoint, data=payload)
            if not success:
                job.write({'state': 'failed', 'error_message': str(result)})
                # Do not raise UserError, so the failed job gets saved and displayed.
                return {
                    'type': 'ir.actions.client',
                    'tag': 'display_notification',
                    'params': {
                        'title': _('Export Failed'),
                        'message': _("Power BI export failed to start: %s") % result,
                        'type': 'danger',
                        'sticky': True,
                    },
                }
            job.write({
                'export_id': result.get('id'),
                'state': 'running',
                'percent_complete': result.get('percentComplete') or 0,
                'raw_payload': json.dumps(result, default=str),
            })
        return True

    def action_poll_export(self):
        for job in self:
            if not job.export_id:
                raise UserError(_("Export ID is missing."))
            endpoint = f"reports/{job.report_id.external_id}/exports/{job.export_id}"
            success, result = job.push_config_id._make_powerbi_request('GET', endpoint)
            if not success:
                job.write({'state': 'failed', 'error_message': str(result)})
                raise UserError(_("Power BI export polling failed: %s") % result)
            status = (result.get('status') or '').lower()
            values = {
                'percent_complete': result.get('percentComplete') or job.percent_complete,
                'raw_payload': json.dumps(result, default=str),
            }
            if status == 'succeeded':
                values['state'] = 'done'
            elif status == 'failed':
                values.update({'state': 'failed', 'error_message': result.get('error', {}).get('message')})
            else:
                values['state'] = 'running'
            job.write(values)
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Power BI'),
                'message': _('Export status has been refreshed.'),
                'type': 'success',
            },
        }

    def action_download_export(self):
        self.ensure_one()
        if not self.export_id:
            raise UserError(_("Export ID is missing."))
        endpoint = (
            f"{self.push_config_id._get_powerbi_base_endpoint()}"
            f"/reports/{self.report_id.external_id}/exports/{self.export_id}/file"
        )
        self.push_config_id._refresh_token_if_needed()
        try:
            response = requests.get(
                endpoint,
                headers={'Authorization': f'Bearer {self.push_config_id.powerbi_access_token}'},
                timeout=POWERBI_EXPORT_TIMEOUT,
            )
        except requests.exceptions.RequestException as error:
            raise UserError(_("Power BI export download failed: %s") % error) from error
        if response.status_code != 200:
            raise UserError(_("Power BI export download failed: %s") % response.text)
        filename = f"{self.report_id.name}.{self.export_format.lower()}"
        self.write({
            'export_file': base64.b64encode(response.content),
            'export_filename': filename,
            'state': 'done',
        })
        return {
            'type': 'ir.actions.act_url',
            'url': f'/web/content/{self._name}/{self.id}/export_file/{filename}?download=true',
            'target': 'self',
        }
