# -*- coding: utf-8 -*-
# Copyright (C) Softhealer Technologies Pvt. Ltd.

import json
import logging
import time as _time
from datetime import timedelta

import requests

from odoo import _, api, fields, models
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)

FABRIC_BASE_URL = 'https://api.fabric.microsoft.com/v1'
FABRIC_TOKEN_SCOPE = 'https://api.fabric.microsoft.com/.default'
FABRIC_TIMEOUT = 30
FABRIC_MAX_RETRIES = 3


class SHPowerBIFabricConfig(models.Model):
    """Microsoft Fabric service-principal configuration for Power BI connector."""

    _name = 'sh.powerbi.fabric.config'
    _description = 'Power BI Fabric Configuration'
    _order = 'id desc'

    name = fields.Char(string='Configuration Name', required=True)
    company_id = fields.Many2one('res.company', string='Company', required=True, default=lambda self: self.env.company)
    state = fields.Selection([
        ('draft', 'Draft'),
        ('authorized', 'Authorized'),
        ('error', 'Error'),
    ], string='Status', default='draft', readonly=True)
    azure_tenant_id = fields.Char(string='Azure Tenant ID')
    azure_client_id = fields.Char(string='Azure Client ID')
    azure_client_secret = fields.Char(string='Azure Client Secret')
    fabric_access_token = fields.Char(string='Fabric Access Token', readonly=True, copy=False)
    fabric_token_expiry = fields.Datetime(string='Fabric Token Expiry', readonly=True, copy=False)
    workspace_id = fields.Char(string='Fabric Workspace ID')
    workspace_name = fields.Char(string='Fabric Workspace Name', readonly=True)
    capacity_id = fields.Char(string='Fabric Capacity ID')
    default_target_type = fields.Selection([
        ('lakehouse', 'Lakehouse'),
        ('warehouse', 'Warehouse'),
        ('eventhouse', 'Eventhouse'),
        ('kql_database', 'KQL Database'),
        ('pipeline', 'Data Pipeline'),
        ('copy_job', 'Copy Job'),
    ], string='Default Target Type', default='lakehouse')
    last_discovery_date = fields.Datetime(string='Last Discovery', readonly=True)
    item_ids = fields.One2many('sh.powerbi.fabric.item', 'fabric_config_id', string='All Fabric Items')
    lakehouse_ids = fields.One2many('sh.powerbi.fabric.item', 'fabric_config_id', string='Lakehouses', domain=[('item_type', '=', 'lakehouse')])
    warehouse_ids = fields.One2many('sh.powerbi.fabric.item', 'fabric_config_id', string='Warehouses', domain=[('item_type', '=', 'warehouse')])
    eventhouse_ids = fields.One2many('sh.powerbi.fabric.item', 'fabric_config_id', string='Eventhouses', domain=[('item_type', '=', 'eventhouse')])
    kql_database_ids = fields.One2many('sh.powerbi.fabric.item', 'fabric_config_id', string='KQL Databases', domain=[('item_type', '=', 'kql_database')])
    pipeline_ids = fields.One2many('sh.powerbi.fabric.item', 'fabric_config_id', string='Pipelines', domain=[('item_type', 'in', ('pipeline', 'copy_job'))])
    
    pipeline_run_ids = fields.One2many('sh.powerbi.fabric.pipeline.run', 'fabric_config_id', string='Pipeline Runs')

    # Smart button counts
    count_lakehouses = fields.Integer(compute='_compute_item_counts', string="Lakehouse Count")
    count_warehouses = fields.Integer(compute='_compute_item_counts', string="Warehouse Count")
    count_eventhouses = fields.Integer(compute='_compute_item_counts', string="Eventhouse Count")
    count_kql_databases = fields.Integer(compute='_compute_item_counts', string="KQL Database Count")
    count_pipelines = fields.Integer(compute='_compute_item_counts', string="Pipeline Count")
    count_pipeline_runs = fields.Integer(compute='_compute_item_counts', string="Pipeline Run Count")

    def _compute_item_counts(self):
        for rec in self:
            rec.count_lakehouses = sum(1 for i in rec.item_ids if i.item_type == 'lakehouse')
            rec.count_warehouses = sum(1 for i in rec.item_ids if i.item_type == 'warehouse')
            rec.count_eventhouses = sum(1 for i in rec.item_ids if i.item_type == 'eventhouse')
            rec.count_kql_databases = sum(1 for i in rec.item_ids if i.item_type == 'kql_database')
            rec.count_pipelines = sum(1 for i in rec.item_ids if i.item_type == 'pipeline')
            rec.count_pipeline_runs = len(rec.pipeline_run_ids)

    def action_view_lakehouses(self):
        self.ensure_one()
        return self._get_item_action('lakehouse', 'Lakehouses')

    def action_view_warehouses(self):
        self.ensure_one()
        return self._get_item_action('warehouse', 'Warehouses')

    def action_view_eventhouses(self):
        self.ensure_one()
        return self._get_item_action('eventhouse', 'Eventhouses')

    def action_view_kql_databases(self):
        self.ensure_one()
        return self._get_item_action('kql_database', 'KQL Databases')

    def action_view_pipelines(self):
        self.ensure_one()
        return self._get_item_action('pipeline', 'Pipelines')

    def action_view_pipeline_runs(self):
        self.ensure_one()
        return {
            'name': 'Pipeline Runs',
            'type': 'ir.actions.act_window',
            'res_model': 'sh.powerbi.fabric.pipeline.run',
            'view_mode': 'list,form',
            'domain': [('fabric_config_id', '=', self.id)],
            'context': {'default_fabric_config_id': self.id},
        }

    def _get_item_action(self, item_type, name):
        return {
            'name': name,
            'type': 'ir.actions.act_window',
            'res_model': 'sh.powerbi.fabric.item',
            'view_mode': 'list,form',
            'domain': [('fabric_config_id', '=', self.id), ('item_type', '=', item_type)],
            'context': {'default_fabric_config_id': self.id, 'default_item_type': item_type},
        }


    def _log_fabric(self, message, state='success', model_access=False, run=False):
        self.ensure_one()
        values = {
            'name': _('Fabric Event'),
            'fabric_config_id': self.id,
            'company_id': self.company_id.id,
            'state': 'done' if state == 'success' else 'failed',
            'message': message,
        }
        if model_access:
            values['model_access_id'] = model_access.id
        if run:
            values.update(run)
        return self.env['sh.powerbi.fabric.pipeline.run'].sudo().create(values)

    def action_authorize(self):
        """Authorize against Microsoft Fabric using client credentials."""
        for config in self:
            if not all([config.azure_tenant_id, config.azure_client_id, config.azure_client_secret]):
                raise UserError(_("Please fill in Tenant ID, Client ID, and Client Secret before authorizing Fabric."))
            url = f"https://login.microsoftonline.com/{config.azure_tenant_id}/oauth2/v2.0/token"
            data = {
                'grant_type': 'client_credentials',
                'client_id': config.azure_client_id,
                'client_secret': config.azure_client_secret,
                'scope': FABRIC_TOKEN_SCOPE,
            }
            try:
                response = requests.post(url, data=data, timeout=FABRIC_TIMEOUT)
            except requests.exceptions.RequestException as error:
                config.state = 'error'
                config._log_fabric(_("Fabric authorization request failed: %s") % error, state='error')
                raise UserError(_("Fabric authorization request failed: %s") % error) from error

            if response.status_code != 200:
                try:
                    error_msg = response.json().get('error_description') or response.text
                except Exception:
                    error_msg = response.text
                config.state = 'error'
                config._log_fabric(_("Fabric authorization failed: %s") % error_msg, state='error')
                raise UserError(_("Fabric authorization failed: %s") % error_msg)

            token_data = response.json()
            config.write({
                'fabric_access_token': token_data['access_token'],
                'fabric_token_expiry': fields.Datetime.now() + timedelta(seconds=token_data.get('expires_in', 3600)),
                'state': 'authorized',
            })
            config._log_fabric(_("Fabric authorization successful."))
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Fabric'),
                'message': _('Fabric authorization successful.'),
                'type': 'success',
                'next': {'type': 'ir.actions.client', 'tag': 'reload'},
            },
        }

    def _refresh_fabric_token_if_needed(self):
        self.ensure_one()
        if not self.fabric_access_token:
            self.action_authorize()
            return
        if self.fabric_token_expiry and fields.Datetime.now() >= self.fabric_token_expiry - timedelta(minutes=5):
            self.action_authorize()

    def _get_fabric_headers(self):
        return {
            'Authorization': f'Bearer {self.fabric_access_token}',
            'Content-Type': 'application/json',
            'Accept': 'application/json',
        }

    def _make_fabric_request(self, method, endpoint, data=None, params=None):
        """Generic Fabric REST request with 429 retry support."""
        self.ensure_one()
        self._refresh_fabric_token_if_needed()
        endpoint = endpoint.lstrip('/')
        url = f"{FABRIC_BASE_URL}/{endpoint}"

        for attempt in range(FABRIC_MAX_RETRIES):
            try:
                response = requests.request(
                    method,
                    url,
                    headers=self._get_fabric_headers(),
                    json=data,
                    params=params,
                    timeout=FABRIC_TIMEOUT,
                )
            except requests.exceptions.RequestException as error:
                return False, str(error)

            if response.status_code == 429:
                retry_after = min(int(response.headers.get('Retry-After', 10)), 60)
                if attempt < FABRIC_MAX_RETRIES - 1:
                    _logger.warning("Fabric rate limit hit. Retrying in %s seconds.", retry_after)
                    _time.sleep(retry_after)
                    continue
                return False, _("Fabric API rate limit exceeded after %s retries.") % FABRIC_MAX_RETRIES

            if response.status_code in (200, 201, 202, 204):
                payload = {}
                if response.text:
                    try:
                        payload = response.json()
                    except Exception:
                        payload = {'raw': response.text}
                payload['__headers'] = dict(response.headers)
                payload['__status_code'] = response.status_code
                return True, payload

            try:
                error_json = response.json()
                error_msg = (
                    error_json.get('message')
                    or error_json.get('error', {}).get('message')
                    or error_json.get('errorCode')
                    or response.text
                )
            except Exception:
                error_msg = response.text
            return False, error_msg

        return False, _("Unexpected Fabric request loop exit.")

    def action_test_connection(self):
        """Verify the service principal can read Fabric workspaces."""
        self.ensure_one()
        success, result = self._make_fabric_request('GET', 'workspaces')
        if not success:
            self._log_fabric(_("Fabric connection test failed: %s") % result, state='error')
            raise UserError(_("Fabric connection test failed: %s") % result)
        self._log_fabric(_("Fabric connection test successful."))
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Fabric'),
                'message': _('Successfully connected to Microsoft Fabric.'),
                'type': 'success',
            },
        }

    def action_discover_items(self):
        """Discover Fabric workspaces and items visible to this service principal."""
        for config in self:
            success, workspace_result = config._make_fabric_request('GET', 'workspaces')
            if not success:
                config._log_fabric(_("Fabric workspace discovery failed: %s") % workspace_result, state='error')
                raise UserError(_("Fabric workspace discovery failed: %s") % workspace_result)

            workspace_values = workspace_result.get('value') or workspace_result.get('workspaces') or []
            for workspace in workspace_values:
                workspace_id = workspace.get('id') or workspace.get('workspaceId')
                display_name = workspace.get('displayName') or workspace.get('name') or workspace_id
                if not workspace_id:
                    continue
                item = self.env['sh.powerbi.fabric.item'].sudo().search([
                    ('fabric_config_id', '=', config.id),
                    ('external_id', '=', workspace_id),
                    ('item_type', '=', 'workspace'),
                ], limit=1)
                values = {
                    'name': display_name,
                    'external_id': workspace_id,
                    'workspace_id': workspace_id,
                    'item_type': 'workspace',
                    'fabric_config_id': config.id,
                    'company_id': config.company_id.id,
                    'raw_payload': json.dumps(workspace, default=str),
                }
                if item:
                    item.write(values)
                else:
                    self.env['sh.powerbi.fabric.item'].sudo().create(values)

                if config.workspace_id and workspace_id != config.workspace_id:
                    continue
                if not config.workspace_id:
                    config.write({'workspace_id': workspace_id, 'workspace_name': display_name})

                item_success, item_result = config._make_fabric_request('GET', f'workspaces/{workspace_id}/items')
                if not item_success:
                    _logger.warning("Fabric item discovery failed for workspace %s: %s", workspace_id, item_result)
                    continue
                for fabric_item in item_result.get('value', []):
                    config._upsert_fabric_item(workspace_id, fabric_item)
            config.write({'last_discovery_date': fields.Datetime.now()})
            config._log_fabric(_("Fabric discovery completed."))
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Fabric'),
                'message': _('Fabric workspaces and items have been discovered.'),
                'type': 'success',
                'next': {'type': 'ir.actions.client', 'tag': 'reload'},
            },
        }

    def _upsert_fabric_item(self, workspace_id, fabric_item):
        self.ensure_one()
        external_id = fabric_item.get('id')
        if not external_id:
            return False
        item_type = self.env['sh.powerbi.fabric.item']._normalize_item_type(fabric_item.get('type'))
        item = self.env['sh.powerbi.fabric.item'].sudo().search([
            ('fabric_config_id', '=', self.id),
            ('external_id', '=', external_id),
        ], limit=1)
        values = {
            'name': fabric_item.get('displayName') or fabric_item.get('name') or external_id,
            'external_id': external_id,
            'workspace_id': workspace_id,
            'item_type': item_type,
            'fabric_config_id': self.id,
            'company_id': self.company_id.id,
            'description': fabric_item.get('description'),
            'raw_payload': json.dumps(fabric_item, default=str),
        }
        if item:
            item.write(values)
        else:
            item = self.env['sh.powerbi.fabric.item'].sudo().create(values)
        return item

    def action_create_fabric_item(self):
        """Open a wizard to create a new Fabric item."""
        self.ensure_one()
        return {
            'name': _('Create Fabric Item'),
            'type': 'ir.actions.act_window',
            'res_model': 'sh.powerbi.fabric.item.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {
                'default_fabric_config_id': self.id,
            }
        }

    def action_run_pipeline(self):
        """Run the first selected pipeline/copy job item for this configuration."""
        self.ensure_one()
        target = self.item_ids.filtered(lambda item: item.is_default_target and item.item_type in ('pipeline', 'copy_job'))[:1]
        if not target:
            target = self.item_ids.filtered(lambda item: item.item_type in ('pipeline', 'copy_job'))[:1]
        if not target:
            raise UserError(_("Please discover or create a Fabric Pipeline or Copy Job first."))
        return target.action_run_item()


class SHPowerBIFabricItem(models.Model):
    """Cached Fabric workspace item."""

    _name = 'sh.powerbi.fabric.item'
    _description = 'Power BI Fabric Item'
    _order = 'workspace_id, item_type, name'

    name = fields.Char(string='Name', required=True)
    fabric_config_id = fields.Many2one('sh.powerbi.fabric.config', string='Fabric Configuration', required=True, ondelete='cascade')
    company_id = fields.Many2one('res.company', string='Company', required=True, default=lambda self: self.env.company)
    external_id = fields.Char(string='Fabric Item ID', required=True, index=True)
    workspace_id = fields.Char(string='Workspace ID', index=True)
    workspace_rel_id = fields.Many2one('sh.powerbi.workspace', compute='_compute_workspace_rel', store=True, string='Workspace Link')

    item_type = fields.Selection([
        ('workspace', 'Workspace'),
        ('lakehouse', 'Lakehouse'),
        ('warehouse', 'Warehouse'),
        ('eventhouse', 'Eventhouse'),
        ('kql_database', 'KQL Database'),
        ('pipeline', 'Data Pipeline'),
        ('copy_job', 'Copy Job'),
        ('semantic_model', 'Semantic Model'),
        ('report', 'Report'),
        ('other', 'Other'),
    ], string='Item Type', default='other', required=True)
    description = fields.Text(string='Description')
    is_default_target = fields.Boolean(string='Default Target')
    raw_payload = fields.Text(string='Raw Payload', readonly=True)
    last_run_id = fields.Char(string='Last Run ID', readonly=True)
    last_run_state = fields.Char(string='Last Run State', readonly=True)
    last_run_date = fields.Datetime(string='Last Run Date', readonly=True)

    @api.model
    def _normalize_item_type(self, item_type):
        normalized = (item_type or '').replace(' ', '').replace('_', '').lower()
        mapping = {
            'workspace': 'workspace',
            'lakehouse': 'lakehouse',
            'sqldatabase': 'warehouse',
            'warehouse': 'warehouse',
            'eventhouse': 'eventhouse',
            'kqldatabase': 'kql_database',
            'datapipeline': 'pipeline',
            'pipeline': 'pipeline',
            'copyjob': 'copy_job',
            'semanticmodel': 'semantic_model',
            'dataset': 'semantic_model',
            'report': 'report',
        }
        return mapping.get(normalized, 'other')

    @api.depends('workspace_id')
    def _compute_workspace_rel(self):
        for rec in self:
            if rec.workspace_id:
                rec.workspace_rel_id = self.env['sh.powerbi.workspace'].search([('external_id', '=', rec.workspace_id)], limit=1)
            else:
                rec.workspace_rel_id = False

    def action_set_default_target(self):
        for item in self:
            item.fabric_config_id.item_ids.write({'is_default_target': False})
            item.is_default_target = True

    def action_run_item(self):
        """Start a Fabric pipeline or copy job item."""
        self.ensure_one()
        if self.item_type not in ('pipeline', 'copy_job'):
            raise UserError(_("Only Fabric Pipeline and Copy Job items can be run from Odoo."))
        endpoint = f'workspaces/{self.workspace_id}/items/{self.external_id}/jobs/instances'
        job_type = 'Pipeline' if self.item_type == 'pipeline' else 'CopyJob'
        success, result = self.fabric_config_id._make_fabric_request('POST', endpoint, params={'jobType': job_type})
        if not success:
            run = self.env['sh.powerbi.fabric.pipeline.run'].sudo().create({
                'name': self.name,
                'fabric_config_id': self.fabric_config_id.id,
                'fabric_item_id': self.id,
                'company_id': self.company_id.id,
                'workspace_id': self.workspace_id,
                'item_id': self.external_id,
                'state': 'failed',
                'started_at': fields.Datetime.now(),
                'message': str(result),
            })
            raise UserError(_("Fabric run failed to start: %s") % result)

        headers = result.get('__headers', {})
        run_id = result.get('id') or result.get('runId') or headers.get('x-ms-operation-id') or headers.get('Location')
        run = self.env['sh.powerbi.fabric.pipeline.run'].sudo().create({
            'name': self.name,
            'fabric_config_id': self.fabric_config_id.id,
            'fabric_item_id': self.id,
            'company_id': self.company_id.id,
            'workspace_id': self.workspace_id,
            'item_id': self.external_id,
            'run_id': run_id,
            'status_url': headers.get('Location') or headers.get('Operation-Location'),
            'state': 'running',
            'started_at': fields.Datetime.now(),
            'message': json.dumps(result, default=str),
        })
        self.write({
            'last_run_id': run_id,
            'last_run_state': 'running',
            'last_run_date': fields.Datetime.now(),
        })
        return {
            'type': 'ir.actions.act_window',
            'name': _('Fabric Pipeline Run'),
            'res_model': 'sh.powerbi.fabric.pipeline.run',
            'view_mode': 'form',
            'res_id': run.id,
            'target': 'current',
        }


class SHPowerBIFabricPipelineRun(models.Model):
    """Fabric pipeline/copy job run status."""

    _name = 'sh.powerbi.fabric.pipeline.run'
    _description = 'Power BI Fabric Pipeline Run'
    _order = 'started_at desc, id desc'

    name = fields.Char(string='Name', required=True)
    fabric_config_id = fields.Many2one('sh.powerbi.fabric.config', string='Fabric Configuration', required=True, ondelete='cascade')
    fabric_item_id = fields.Many2one('sh.powerbi.fabric.item', string='Fabric Item', ondelete='set null')
    model_access_id = fields.Many2one('sh.powerbi.model.access', string='Model Access', ondelete='set null')
    company_id = fields.Many2one('res.company', string='Company', required=True, default=lambda self: self.env.company)
    workspace_id = fields.Char(string='Workspace ID')
    item_id = fields.Char(string='Item ID')
    run_id = fields.Char(string='Run ID')
    status_url = fields.Char(string='Status URL')
    state = fields.Selection([
        ('draft', 'Draft'),
        ('running', 'Running'),
        ('done', 'Done'),
        ('failed', 'Failed'),
        ('cancelled', 'Cancelled'),
    ], string='Status', default='draft')
    started_at = fields.Datetime(string='Started At')
    finished_at = fields.Datetime(string='Finished At')
    duration_seconds = fields.Float(string='Duration (s)', compute='_compute_duration_seconds', store=True)
    record_count = fields.Integer(string='Records')
    message = fields.Text(string='Message')

    @api.depends('started_at', 'finished_at')
    def _compute_duration_seconds(self):
        for run in self:
            if run.started_at and run.finished_at:
                run.duration_seconds = (run.finished_at - run.started_at).total_seconds()
            else:
                run.duration_seconds = 0.0

    def action_poll_status(self):
        """Poll a Fabric run status URL when Microsoft returns one."""
        for run in self:
            if not run.status_url:
                raise UserError(_("This Fabric run does not have a status URL to poll."))
            config = run.fabric_config_id
            config._refresh_fabric_token_if_needed()
            try:
                response = requests.get(run.status_url, headers=config._get_fabric_headers(), timeout=FABRIC_TIMEOUT)
            except requests.exceptions.RequestException as error:
                raise UserError(_("Fabric run status request failed: %s") % error) from error
            if response.status_code not in (200, 202):
                raise UserError(_("Fabric run status failed: %s") % response.text)
            try:
                payload = response.json() if response.text else {}
            except Exception:
                payload = {'raw': response.text}
            status = (payload.get('status') or payload.get('state') or '').lower()
            values = {'message': json.dumps(payload, default=str)}
            if status in ('succeeded', 'completed', 'done'):
                values.update({'state': 'done', 'finished_at': fields.Datetime.now()})
            elif status in ('failed', 'cancelled', 'canceled'):
                values.update({'state': 'failed' if status == 'failed' else 'cancelled', 'finished_at': fields.Datetime.now()})
            elif status:
                values['state'] = 'running'
            run.write(values)
            if run.fabric_item_id:
                run.fabric_item_id.write({
                    'last_run_state': run.state,
                    'last_run_id': run.run_id,
                    'last_run_date': fields.Datetime.now(),
                })
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Fabric'),
                'message': _('Fabric run status has been refreshed.'),
                'type': 'success',
            },
        }
