# -*- coding: utf-8 -*-
# Copyright (C) Softhealer Technologies Pvt. Ltd.

import base64
import json
import logging
import time as _time
from datetime import timedelta

import requests

from odoo import models, fields, api, _
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)

POWERBI_BASE_URL = 'https://api.powerbi.com/v1.0/myorg'
POWERBI_TIMEOUT = 30
PUSH_BATCH_SIZE = 1000
MAX_RETRIES = 3
POWERBI_MAX_COLUMNS_PER_TABLE = 75
POWERBI_JOIN_FIELD = 'id'

# Odoo field type → Power BI column dataType mapping
FIELD_TYPE_MAP = {
    'char': 'String',
    'text': 'String',
    'html': 'String',
    'selection': 'String',
    'many2one': 'Int64',
    'one2many': 'String',
    'many2many': 'String',
    'reference': 'String',
    'integer': 'Int64',
    'float': 'Double',
    'monetary': 'Double',
    'boolean': 'Boolean',
    'date': 'DateTime',
    'datetime': 'DateTime',
}


class SHPowerBIPushConfig(models.Model):
    _name = 'sh.powerbi.push.config'
    _description = 'Power BI Push Configuration'
    _order = 'id desc'

    name = fields.Char(string='Configuration Name', required=True)
    company_id = fields.Many2one('res.company', string='Company', required=True, default=lambda self: self.env.company)
    state = fields.Selection([
        ('draft', 'Draft'),
        ('authorized', 'Authorized'),
        ('error', 'Error'),
    ], string='Status', default='draft', readonly=True)

    # Azure AD OAuth credentials
    azure_tenant_id = fields.Char(string='Azure Tenant ID', help="Found in Azure Active Directory → Overview → Tenant ID")
    azure_client_id = fields.Char(string='Azure Client ID', help="Application (client) ID of your Azure AD app registration")
    azure_client_secret = fields.Char(string='Azure Client Secret')
    powerbi_workspace_id = fields.Char(string='Power BI Workspace ID', help="The GUID of your Power BI workspace (group). Found in the workspace URL.")

    # OAuth token (internal)
    powerbi_access_token = fields.Char(string='Access Token', readonly=True, copy=False)
    powerbi_token_expiry = fields.Datetime(string='Token Expiry', readonly=True, copy=False)

    # Auto-push schedule
    cron_interval_hours = fields.Integer(string='Auto-Push Every (hours)', default=1, help="Interval for the scheduled push action. Set 0 to disable.")
    push_batch_size = fields.Integer(string='Push Batch Size', default=1000, help="Number of records sent to Power BI per API call. Max allowed by Power BI API is 10,000. Default: 1000.")

    # Relations
    model_access_ids = fields.One2many(
        'sh.powerbi.model.access', 'config_id',
        string='Model Access',
    )
    workspace_ids = fields.One2many('sh.powerbi.workspace', 'push_config_id', string='Power BI Workspaces')
    dataset_ids = fields.One2many('sh.powerbi.dataset', 'push_config_id', string='Power BI Datasets')
    report_ids = fields.One2many('sh.powerbi.report', 'push_config_id', string='Power BI Reports')
    export_job_ids = fields.One2many('sh.powerbi.export.job', 'push_config_id', string='Export Jobs')
    pbix_file = fields.Binary(string='PBIX File')
    pbix_filename = fields.Char(string='PBIX Filename')

    # Smart button counts
    count_workspaces = fields.Integer(compute='_compute_asset_counts', string="Workspaces")
    count_datasets = fields.Integer(compute='_compute_asset_counts', string="Datasets")
    count_reports = fields.Integer(compute='_compute_asset_counts', string="Reports")
    count_export_jobs = fields.Integer(compute='_compute_asset_counts', string="Export Job Count")

    def _compute_asset_counts(self):
        for rec in self:
            rec.count_workspaces = len(rec.workspace_ids)
            rec.count_datasets = len(rec.dataset_ids)
            rec.count_reports = len(rec.report_ids)
            rec.count_export_jobs = len(rec.export_job_ids)

    def action_view_workspaces(self):
        self.ensure_one()
        return {
            'name': 'Workspaces',
            'type': 'ir.actions.act_window',
            'res_model': 'sh.powerbi.workspace',
            'view_mode': 'list,form',
            'domain': [('push_config_id', '=', self.id)],
            'context': {'default_push_config_id': self.id},
        }

    def action_view_datasets(self):
        self.ensure_one()
        return {
            'name': 'Datasets',
            'type': 'ir.actions.act_window',
            'res_model': 'sh.powerbi.dataset',
            'view_mode': 'list,form',
            'domain': [('push_config_id', '=', self.id)],
            'context': {'default_push_config_id': self.id},
        }

    def action_view_reports(self):
        self.ensure_one()
        return {
            'name': 'Reports',
            'type': 'ir.actions.act_window',
            'res_model': 'sh.powerbi.report',
            'view_mode': 'list,form',
            'domain': [('push_config_id', '=', self.id)],
            'context': {'default_push_config_id': self.id},
        }

    def action_view_export_jobs(self):
        self.ensure_one()
        return {
            'name': 'Export Jobs',
            'type': 'ir.actions.act_window',
            'res_model': 'sh.powerbi.export.job',
            'view_mode': 'list,form',
            'domain': [('push_config_id', '=', self.id)],
            'context': {'default_push_config_id': self.id},
        }

    # ── OAuth ──────────────────────────────────────────────────────────────────

    def action_authorize(self):
        """Get OAuth 2.0 token using Azure AD client credentials flow."""
        self.ensure_one()
        if not all([self.azure_tenant_id, self.azure_client_id, self.azure_client_secret]):
            raise UserError("Please fill in Azure Tenant ID, Client ID, and Client Secret before authorizing.")

        url = f"https://login.microsoftonline.com/{self.azure_tenant_id}/oauth2/v2.0/token"
        data = {
            'grant_type': 'client_credentials',
            'client_id': self.azure_client_id,
            'client_secret': self.azure_client_secret,
            'scope': 'https://analysis.windows.net/powerbi/api/.default',
        }
        try:
            response = requests.post(url, data=data, timeout=POWERBI_TIMEOUT)
        except requests.exceptions.RequestException as e:
            self.state = 'error'
            self._log(f'Authorization request failed: {e}', log_type='error', state='error')
            raise UserError(f"Authorization request failed: {e}") from e

        if response.status_code == 200:
            token_data = response.json()
            self.write({
                'powerbi_access_token': token_data['access_token'],
                'powerbi_token_expiry': fields.Datetime.now() + timedelta(seconds=token_data.get('expires_in', 3600)),
                'state': 'authorized',
            })
            self._log('Authorization successful.', log_type='auth', state='success')
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': 'Success', 
                    'message': 'Power BI authorization successful.', 
                    'type': 'success',
                    'next': {'type': 'ir.actions.client', 'tag': 'reload'},
                },
            }
        else:
            error_msg = response.json().get('error_description', response.text)
            self.state = 'error'
            self._log(f'Authorization failed: {error_msg}', log_type='error', state='error')
            raise UserError(f"Authorization failed: {error_msg}")

    def action_test_connection(self):
        """Test if the Service Principal can access the configured workspace."""
        self.ensure_one()
        if not self.powerbi_workspace_id:
            raise UserError("Please set a Power BI Workspace ID before testing the connection.")
        if self.powerbi_workspace_id.lower() == 'me':
            raise UserError(
                "Service principals can't use 'My workspace'. Please enter a Group Workspace ID (GUID) from Power BI Service."
            )
        # Try to list datasets in the workspace as a connectivity test
        success, result = self._make_powerbi_request('GET', 'datasets')
        if success:
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': 'Connection Success',
                    'message': 'Successfully connected to Power BI Workspace.',
                    'type': 'success',
                },
            }
        else:
            raise UserError(f"Connection Failed: {result}")

    def _refresh_token_if_needed(self):
        """Re-authorize if token is expired or missing."""
        self.ensure_one()
        if not self.powerbi_access_token:
            self.action_authorize()
            return
        if self.powerbi_token_expiry and fields.Datetime.now() >= self.powerbi_token_expiry - timedelta(minutes=5):
            self.action_authorize()

    def _get_headers(self):
        return {
            'Authorization': f'Bearer {self.powerbi_access_token}',
            'Content-Type': 'application/json',
            'Accept': 'application/json',
        }

    def create(self, vals):
        """Sanitize input IDs by stripping whitespace."""
        for field in ['azure_tenant_id', 'azure_client_id', 'powerbi_workspace_id']:
            if vals.get(field):
                vals[field] = vals[field].strip()
        return super().create(vals)

    def write(self, vals):
        """Sanitize input IDs by stripping whitespace."""
        for field in ['azure_tenant_id', 'azure_client_id', 'powerbi_workspace_id']:
            if vals.get(field):
                vals[field] = vals[field].strip()
        return super().write(vals)

    # ── Generic Power BI REST request ──────────────────────────────────────────

    def _get_powerbi_base_endpoint(self):
        """Return the active Power BI REST base endpoint for this config."""
        self.ensure_one()
        if not self.powerbi_workspace_id or self.powerbi_workspace_id.lower() == 'me':
            return POWERBI_BASE_URL
        return f"{POWERBI_BASE_URL}/groups/{self.powerbi_workspace_id}"

    def _make_powerbi_request(self, method, endpoint, data=None, params=None, scoped=True):
        """Generic Power BI REST API call with automatic 429 retry. Returns (success, response_data)."""
        self._refresh_token_if_needed()

        if scoped:
            url = f"{self._get_powerbi_base_endpoint()}/{endpoint}"
        else:
            url = f"{POWERBI_BASE_URL}/{endpoint}"

        for attempt in range(MAX_RETRIES):
            try:
                resp = requests.request(
                    method,
                    url,
                    headers=self._get_headers(),
                    json=data,
                    params=params,
                    timeout=POWERBI_TIMEOUT,
                )
            except requests.exceptions.RequestException as e:
                return False, str(e)

            # ── 429 Rate Limit ─────────────────────────────────────────────
            if resp.status_code == 429:
                retry_after = min(int(resp.headers.get('Retry-After', 10)), 60)
                if attempt < MAX_RETRIES - 1:
                    _logger.warning(
                        "Power BI rate limit hit (429). Retrying in %ss (attempt %s/%s).",
                        retry_after, attempt + 1, MAX_RETRIES,
                    )
                    _time.sleep(retry_after)
                    continue
                return False, "Power BI API rate limit exceeded after %d retries." % MAX_RETRIES

            # ── Success ────────────────────────────────────────────────────
            if resp.status_code in (200, 201, 202, 204):
                try:
                    return True, resp.json() if resp.text else {}
                except Exception:
                    return True, {}

            # ── Error Parsing ──────────────────────────────────────────────
            try:
                error_json = resp.json()
                error_obj = error_json.get('error', {})
                err = error_obj.get('message')
                code = error_obj.get('code')
                pbi_error = error_obj.get('pbi.error', {})

                if not err:
                    if code == 'PowerBIEntityNotFound':
                        err = "The specified Power BI entity (Workspace or Dataset) was not found."
                    elif code == 'PowerBINotAuthorizedException':
                        err = "The service principal is not authorized to access this Power BI workspace."
                    elif pbi_error and pbi_error.get('code'):
                        err = f"{pbi_error.get('code')}: {pbi_error.get('parameters', {})}"
                    else:
                        err = code or resp.text

                if 'PowerBIEntityNotFound' in str(error_json):
                    err += ("\n\n💡 TROUBLESHOOTING TIP:\n"
                            "1. Ensure the 'Power BI Workspace ID' is a valid GUID.\n"
                            "2. Ensure you have added your Azure AD App (Service Principal) as an 'Admin' or 'Member' "
                            "in the Power BI Workspace 'Manage access' settings.\n"
                            "3. Verify that 'Allow service principals to use Power BI APIs' is enabled in the Power BI Admin Portal.")
                elif code == 'PowerBINotAuthorizedException' or pbi_error.get('code') == 'PowerBINotAuthorizedException':
                    err += (
                        "\n\nTROUBLESHOOTING TIP:\n"
                        "1. In Fabric/Power BI Admin Portal -> Developer settings, enable service principals to use Power BI APIs.\n"
                        "2. Add this Azure AD App (service principal) to an allowed security group if your tenant setting is scoped.\n"
                        "3. In the target Power BI workspace, add the service principal as Member or Admin.\n"
                        "4. Use a Group Workspace GUID from app.powerbi.com, not 'My workspace' and not the workspace name.\n"
                        "5. Re-authorize in Odoo after changing tenant or workspace permissions."
                    )
            except Exception:
                err = resp.text

            return False, err

        return False, "Unexpected error: request loop exited without a response."

    def action_sync_workspaces(self):
        """Discover Power BI workspaces available to the service principal."""
        self.ensure_one()
        success, result = self._make_powerbi_request('GET', 'groups', scoped=False)
        if not success:
            raise UserError(f"Failed to discover Power BI workspaces: {result}")
        for workspace in result.get('value', []):
            workspace_id = workspace.get('id')
            if not workspace_id:
                continue
            record = self.env['sh.powerbi.workspace'].sudo().search([
                ('push_config_id', '=', self.id),
                ('external_id', '=', workspace_id),
            ], limit=1)
            values = {
                'name': workspace.get('name') or workspace.get('displayName') or workspace_id,
                'external_id': workspace_id,
                'push_config_id': self.id,
                'company_id': self.company_id.id,
                'is_selected': workspace_id == self.powerbi_workspace_id,
                'raw_payload': json.dumps(workspace, default=str),
            }
            if record:
                record.write(values)
            else:
                self.env['sh.powerbi.workspace'].sudo().create(values)
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': 'Power BI',
                'message': 'Power BI workspaces have been discovered.',
                'type': 'success',
                'next': {'type': 'ir.actions.client', 'tag': 'reload'},
            },
        }

    def action_sync_datasets(self):
        """Discover datasets/semantic models in the configured workspace."""
        self.ensure_one()
        if not self.powerbi_workspace_id:
            raise UserError("Please set a Power BI Workspace ID before discovering datasets.")
        success, result = self._make_powerbi_request('GET', 'datasets')
        if not success:
            raise UserError(f"Failed to discover Power BI datasets: {result}")
        for dataset in result.get('value', []):
            dataset_id = dataset.get('id')
            if not dataset_id:
                continue
            record = self.env['sh.powerbi.dataset'].sudo().search([
                ('push_config_id', '=', self.id),
                ('external_id', '=', dataset_id),
            ], limit=1)
            values = {
                'name': dataset.get('name') or dataset_id,
                'external_id': dataset_id,
                'push_config_id': self.id,
                'workspace_id': self.powerbi_workspace_id,
                'company_id': self.company_id.id,
                'configured_by': dataset.get('configuredBy'),
                'is_refreshable': bool(dataset.get('isRefreshable')),
                'raw_payload': json.dumps(dataset, default=str),
            }
            if record:
                record.write(values)
            else:
                self.env['sh.powerbi.dataset'].sudo().create(values)
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': 'Power BI',
                'message': 'Power BI datasets have been discovered.',
                'type': 'success',
                'next': {'type': 'ir.actions.client', 'tag': 'reload'},
            },
        }

    def action_sync_reports(self):
        """Discover reports in the configured workspace."""
        self.ensure_one()
        if not self.powerbi_workspace_id:
            raise UserError("Please set a Power BI Workspace ID before discovering reports.")
        success, result = self._make_powerbi_request('GET', 'reports')
        if not success:
            raise UserError(f"Failed to discover Power BI reports: {result}")
        Dataset = self.env['sh.powerbi.dataset'].sudo()
        for report in result.get('value', []):
            report_id = report.get('id')
            if not report_id:
                continue
            powerbi_dataset_id = report.get('datasetId')
            dataset = Dataset.search([
                ('push_config_id', '=', self.id),
                ('external_id', '=', powerbi_dataset_id),
            ], limit=1)
            record = self.env['sh.powerbi.report'].sudo().search([
                ('push_config_id', '=', self.id),
                ('external_id', '=', report_id),
            ], limit=1)
            values = {
                'name': report.get('name') or report_id,
                'external_id': report_id,
                'push_config_id': self.id,
                'dataset_id': dataset.id or False,
                'powerbi_dataset_id': powerbi_dataset_id,
                'workspace_id': self.powerbi_workspace_id,
                'company_id': self.company_id.id,
                'web_url': report.get('webUrl'),
                'embed_url': report.get('embedUrl'),
                'raw_payload': json.dumps(report, default=str),
            }
            if record:
                record.write(values)
            else:
                self.env['sh.powerbi.report'].sudo().create(values)
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': 'Power BI',
                'message': 'Power BI reports have been discovered.',
                'type': 'success',
                'next': {'type': 'ir.actions.client', 'tag': 'reload'},
            },
        }

    def action_import_pbix(self):
        """Import an uploaded PBIX file into the configured Power BI workspace."""
        self.ensure_one()
        if not self.pbix_file or not self.pbix_filename:
            raise UserError("Please upload a PBIX file before importing.")
        self._refresh_token_if_needed()
        url = f"{self._get_powerbi_base_endpoint()}/imports"
        params = {'datasetDisplayName': self.pbix_filename, 'nameConflict': 'CreateOrOverwrite'}
        files = {
            'file': (self.pbix_filename, base64.b64decode(self.pbix_file), 'application/octet-stream'),
        }
        headers = {'Authorization': f'Bearer {self.powerbi_access_token}'}
        try:
            response = requests.post(url, headers=headers, params=params, files=files, timeout=POWERBI_TIMEOUT)
        except requests.exceptions.RequestException as e:
            raise UserError(f"PBIX import request failed: {e}") from e
        if response.status_code not in (200, 201, 202):
            raise UserError(f"PBIX import failed: {response.text}")
        self._log(f'PBIX import requested for {self.pbix_filename}.', log_type='push', state='success')
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': 'Power BI',
                'message': 'PBIX import has been requested.',
                'type': 'success',
            },
        }

    # ── Dataset management ─────────────────────────────────────────────────────

    def _get_powerbi_table_name(self, model_access):
        """Return the base Power BI table name configured for a model access."""
        return model_access.display_alias or model_access.model_id.name or model_access.model_name

    def _sh_powerbi_get_relation_format(self, model_access):
        """Return the relational field format configured for the model access company."""
        target_company = model_access.company_id or self.env.company
        return getattr(target_company, 'sh_powerbi_relation_format', 'id_and_display') or 'id_and_display'

    def _get_powerbi_field_groups(self, model_access):
        """Return the exposed Odoo fields as atomic [base, companion?] groups.

        A Many2one field and its ``<field>_display`` companion are always kept in
        the same group so that the 75-column split can never separate them.
        """
        Model = self.env[model_access.model_name].sudo()
        relation_format = self._sh_powerbi_get_relation_format(model_access)
        field_names = [f.name for f in model_access.allowed_field_ids] or [
            name for name, field in Model._fields.items()
            if field.store and field.type not in ('binary', 'html', 'json', 'properties', 'properties_definition')
        ]
        seen = set()
        groups = []
        for fname in [POWERBI_JOIN_FIELD] + field_names:
            if fname in seen or fname not in Model._fields:
                continue
            field = Model._fields[fname]
            if fname != POWERBI_JOIN_FIELD and (
                not field.store
                or field.type in ('binary', 'html', 'json', 'properties', 'properties_definition')
            ):
                continue
            seen.add(fname)
            group = [fname]
            if field.type == 'many2one' and relation_format == 'id_and_display':
                disp_fname = f"{fname}_display"
                # Never shadow a real Odoo field with the synthetic companion
                if disp_fname not in seen and disp_fname not in Model._fields:
                    group.append(disp_fname)
                    seen.add(disp_fname)
            groups.append(group)
        return groups

    def _get_powerbi_field_names(self, model_access):
        """Return the effective Odoo field names exposed to Power BI, with id first."""
        return [fname for group in self._get_powerbi_field_groups(model_access) for fname in group]

    def _build_column_schema(self, model_access, field_names=None):
        """Build Power BI column definitions from an Odoo model's fields."""
        Model = self.env[model_access.model_name].sudo()
        relation_format = self._sh_powerbi_get_relation_format(model_access)
        field_names = field_names or self._get_powerbi_field_names(model_access)
        columns = []
        seen_cols = set()
        for fname in field_names:
            if fname not in Model._fields:
                # Synthetic companion column - only valid in id_and_display mode
                if (
                    relation_format == 'id_and_display'
                    and fname.endswith('_display')
                    and fname[:-8] in Model._fields
                    and fname not in seen_cols
                ):
                    columns.append({'name': fname, 'dataType': 'String'})
                    seen_cols.add(fname)
                continue
            field = Model._fields[fname]
            if field.type == 'many2one':
                # Foreign keys stay integers so Power BI can build PK-FK relationships,
                # unless the company runs the legacy display-name format.
                pbi_type = 'String' if relation_format == 'display_only' else 'Int64'
            else:
                pbi_type = FIELD_TYPE_MAP.get(field.type, 'String')
            if fname not in seen_cols:
                columns.append({'name': fname, 'dataType': pbi_type})
                seen_cols.add(fname)
            if field.type == 'many2one' and relation_format == 'id_and_display':
                disp_fname = f"{fname}_display"
                if disp_fname not in Model._fields and disp_fname not in seen_cols:
                    columns.append({'name': disp_fname, 'dataType': 'String'})
                    seen_cols.add(disp_fname)
        return columns

    def _build_powerbi_table_schemas(self, model_access):
        """Build one or more Power BI table schemas, keeping each table under the 75-column limit."""
        table_name = self._get_powerbi_table_name(model_access)
        groups = self._get_powerbi_field_groups(model_access)
        chunk_size = POWERBI_MAX_COLUMNS_PER_TABLE - 1

        if not groups:
            groups = [[POWERBI_JOIN_FIELD]]

        total_columns = sum(len(group) for group in groups)
        if total_columns <= POWERBI_MAX_COLUMNS_PER_TABLE:
            field_names = [fname for group in groups for fname in group]
            return [{
                'name': table_name,
                'fields': field_names,
                'columns': self._build_column_schema(model_access, field_names),
            }]

        # Pack atomic groups so a base field and its companion never split apart
        non_join_groups = [group for group in groups if POWERBI_JOIN_FIELD not in group]
        chunks = []
        current, current_size = [], 0
        for group in non_join_groups:
            if current and current_size + len(group) > chunk_size:
                chunks.append(current)
                current, current_size = [], 0
            current.extend(group)
            current_size += len(group)
        if current:
            chunks.append(current)

        tables = []
        for index, chunk in enumerate(chunks):
            part_number = index + 1
            part_fields = [POWERBI_JOIN_FIELD] + chunk
            part_table_name = table_name if part_number == 1 else f'{table_name}_part_{part_number}'
            tables.append({
                'name': part_table_name,
                'fields': part_fields,
                'columns': self._build_column_schema(model_access, part_fields),
            })
        return tables

    def _get_qualified_schema_columns(self, model_access):
        """Return expected schema columns qualified as table.column:dataType labels."""
        columns = set()
        for table in self._build_powerbi_table_schemas(model_access):
            columns.update(
                f"{table['name']}.{column['name']}:{column['dataType']}"
                for column in table['columns']
            )
        return columns

    def _sh_powerbi_type_only_drift(self, odoo_columns, pbi_columns):
        """True when both sides declare the same column names but different data types."""
        odoo_names = {column.rsplit(':', 1)[0] for column in odoo_columns}
        pbi_names = {column.rsplit(':', 1)[0] for column in pbi_columns}
        return bool(odoo_names) and odoo_names == pbi_names and odoo_columns != pbi_columns

    def _sh_powerbi_parse_qualified(self, qualified):
        """Split a 'table.column:dataType' label into ('table.column', 'dataType')."""
        name, _separator, data_type = qualified.rpartition(':')
        return name, data_type

    def _sh_powerbi_split_drift(self, odoo_columns, pbi_columns):
        """Split a schema drift into added, removed and type-changed column labels."""
        odoo_map = {self._sh_powerbi_parse_qualified(item)[0]: self._sh_powerbi_parse_qualified(item)[1]
                    for item in odoo_columns}
        pbi_map = {self._sh_powerbi_parse_qualified(item)[0]: self._sh_powerbi_parse_qualified(item)[1]
                   for item in pbi_columns}
        added = sorted(set(odoo_map) - set(pbi_map))
        removed = sorted(set(pbi_map) - set(odoo_map))
        changed = sorted(
            name for name in set(odoo_map) & set(pbi_map) if odoo_map[name] != pbi_map[name]
        )
        return added, removed, changed

    def _slice_rows_for_table(self, records, field_names):
        """Keep only the fields that belong to one Power BI split table."""
        field_set = set(field_names)
        return [
            {key: value for key, value in record.items() if key in field_set}
            for record in records
        ]

    def _create_dataset(self, model_access):
        """Create a Power BI push dataset for a model access config. Returns dataset_id."""
        table_name = self._get_powerbi_table_name(model_access)
        tables = self._build_powerbi_table_schemas(model_access)
        payload = {
            'name': f'Odoo — {table_name}',
            'defaultMode': 'Push',
            'tables': [
                {'name': table['name'], 'columns': table['columns']}
                for table in tables
            ],
        }
        success, result = self._make_powerbi_request('POST', 'datasets', data=payload)
        if not success:
            raise UserError(f"Failed to create Power BI dataset: {result}")
        dataset_id = result.get('id')
        model_access.sudo().write({'powerbi_dataset_id': dataset_id})
        return dataset_id

    def _clear_rows(self, model_access, dataset_id):
        """Delete all rows from every Power BI table before a full refresh push."""
        for table in self._build_powerbi_table_schemas(model_access):
            success, result = self._make_powerbi_request(
                'DELETE',
                f"datasets/{dataset_id}/tables/{table['name']}/rows",
            )
            if not success:
                _logger.warning("Power BI clear rows failed for %s: %s", table['name'], result)

    def _push_rows(self, model_access, dataset_id, records, batch_size=None):
        """Push records to Power BI in batches across all generated table parts."""
        tables = self._build_powerbi_table_schemas(model_access)
        total_pushed = 0
        batch_size = batch_size or self.push_batch_size or PUSH_BATCH_SIZE
        for i in range(0, len(records), batch_size):
            batch = records[i:i + batch_size]
            for table in tables:
                endpoint = f"datasets/{dataset_id}/tables/{table['name']}/rows"
                table_rows = self._slice_rows_for_table(batch, table['fields'])
                success, result = self._make_powerbi_request('POST', endpoint, data={'rows': table_rows})
                if not success:
                    raise UserError(
                        f"Failed to push rows to table '{table['name']}' "
                        f"(batch {i // batch_size + 1}): {result}"
                    )
            total_pushed += len(batch)
        return total_pushed

    # ── Schema drift detection ─────────────────────────────────────────────────

    def _get_schema_diff(self, model_access, dataset_id):
        """Compare current Odoo field list vs Power BI dataset schema.
        Returns (drift_detected, odoo_columns, pbi_columns)
        """
        odoo_columns = self._get_qualified_schema_columns(model_access)
        pbi_columns = set()
        for table in self._build_powerbi_table_schemas(model_access):
            success, result = self._make_powerbi_request(
                'GET',
                f"datasets/{dataset_id}/tables/{table['name']}/columns",
            )
            if not success:
                # If we can't get columns (e.g. a part table is missing), assume drift.
                return True, odoo_columns, pbi_columns
            pbi_columns.update(
                f"{table['name']}.{col['name']}:{col.get('dataType')}"
                for col in result.get('value', [])
            )
        return pbi_columns != odoo_columns, odoo_columns, pbi_columns

    # ── Full push workflow ─────────────────────────────────────────────────────

    def action_push_model(self, model_access_id):
        """Push a single model's data to Power BI now."""
        self.ensure_one()
        if not self.powerbi_workspace_id:
            raise UserError("Please set a Power BI Workspace ID before pushing.")

        model_access = self.env['sh.powerbi.model.access'].browse(model_access_id)
        if not model_access.exists() or not model_access.model_name:
            raise UserError("Invalid model access configuration.")

        try:
            # Ensure dataset exists
            dataset_id = model_access.powerbi_dataset_id
            dataset_created = False
            if not dataset_id:
                dataset_id = self._create_dataset(model_access)
                dataset_created = True
            else:
                # Recreate if schema drifted
                drifted, odoo_cols, pbi_cols = self._get_schema_diff(model_access, dataset_id)
                if drifted:
                    if not pbi_cols:
                        _logger.info(
                            "Power BI dataset/table missing for %s — recreating dataset.",
                            model_access.model_name,
                        )
                        model_access.sudo().write({'powerbi_dataset_id': False})
                        dataset_id = self._create_dataset(model_access)
                        dataset_created = True
                    elif self.env.context.get('powerbi_background_push'):
                        # Background job (cron): no UI can be presented, so the dataset is
                        # recreated automatically and the change is audited. Returning a
                        # wizard action here would silently skip the push.
                        _logger.warning(
                            "Power BI dataset for %s recreated due to schema drift (background push). "
                            "Existing reports must be rebound to the new dataset.",
                            model_access.model_name,
                        )
                        model_access.sudo().write({'powerbi_dataset_id': False})
                        dataset_id = self._create_dataset(model_access)
                        dataset_created = True
                        self._log(
                            f"Dataset recreated due to a schema change for {model_access.model_name}. "
                            "Please rebind existing Power BI reports to the new dataset.",
                            log_type='push', state='success',
                            model_name=model_access.model_name,
                        )
                    elif not self.env.context.get('skip_schema_check'):
                        # Open wizard for manual confirmation
                        wizard = self.env['sh.powerbi.schema.diff.wizard'].create_from_diff(
                            self, model_access, odoo_cols, pbi_cols
                        )
                        return {
                            'name': 'Schema Drift Verification',
                            'type': 'ir.actions.act_window',
                            'res_model': 'sh.powerbi.schema.diff.wizard',
                            'view_mode': 'form',
                            'res_id': wizard.id,
                            'target': 'new',
                        }
                    else:
                        _logger.info("Schema drift detected for %s — recreating dataset.", model_access.model_name)
                        model_access.sudo().write({'powerbi_dataset_id': False})
                        dataset_id = self._create_dataset(model_access)
                        dataset_created = True

            # Determine if incremental (delta) push applies
            is_delta = (
                getattr(model_access, 'enable_delta', False)
                and not dataset_created
                and bool(model_access.powerbi_dataset_id)
                and bool(model_access.last_push_write_date)
            )
            queue = self.env['sh.powerbi.push.queue'].create({
                'push_config_id': self.id,
                'model_access_id': model_access.id,
                'is_delta': is_delta,
            })
            queue.action_process_queue()
            if queue.state == 'failed':
                raise UserError(queue.error_message or "Power BI push failed. Please review the push queue.")
            
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': 'Sync Completed',
                    'message': (
                        f'Synchronization for "{model_access.name}" '
                        f'({queue.total_records} records) has been pushed to Power BI.'
                    ),
                    'type': 'success',
                },
            }
        except Exception as e:
            self._log(str(e), log_type='error', state='error', model_name=model_access.model_name)
            raise

    # ── Scheduled cron ─────────────────────────────────────────────────────────

    @api.model
    def _cron_push_all(self):
        """Scheduled auto-push: 
        1. Process any pending queue jobs first.
        2. Create new queue jobs for active configurations.
        """
        # 1. Process pending/failed queue jobs (batching with commits happens inside)
        pending_queue = self.env['sh.powerbi.push.queue'].search([
            ('state', 'in', ['draft', 'processing']),
        ], limit=5)
        failed_ready_queue = self.env['sh.powerbi.push.queue'].search([
            ('state', '=', 'failed'),
            ('retry_count', '<', 3),
            '|',
            ('next_retry_at', '=', False),
            ('next_retry_at', '<=', fields.Datetime.now()),
        ], limit=5)
        pending_queue |= failed_ready_queue
        for job in pending_queue:
            job.action_process_queue()

        # 2. Add new active configs to queue if it is time
        configs = self.sudo().search([('state', '=', 'authorized')])
        for config in configs:
            model_accesses = self.env['sh.powerbi.model.access'].sudo().search([
                ('company_id', '=', config.company_id.id),
                ('is_active', '=', True),
            ])
            for ma in model_accesses:
                # Check if a job already exists for this config/model
                exists = self.env['sh.powerbi.push.queue'].search_count([
                    ('push_config_id', '=', config.id),
                    ('model_access_id', '=', ma.id),
                    ('state', 'in', ['draft', 'processing'])
                ])
                if not exists:
                    # Simple interval check logic could go here based on cron_interval_hours
                    config.with_context(powerbi_background_push=True).action_push_model(ma.id)

    def action_rebuild_all_datasets(self):
        """Recreate every Power BI dataset of this configuration.

        Required after a relational field format change, because the foreign key
        column type changes from String to Int64 and Power BI push datasets
        cannot alter a column type in place.
        """
        self.ensure_one()
        model_accesses = self.env['sh.powerbi.model.access'].sudo().search([
            ('company_id', '=', self.company_id.id),
            ('is_active', '=', True),
        ])
        rebuilt = self.env['sh.powerbi.model.access']
        for model_access in model_accesses:
            model_access.sudo().write({'powerbi_dataset_id': False})
            self._create_dataset(model_access)
            rebuilt |= model_access
        self._log(
            f"Recreated {len(rebuilt)} Power BI dataset(s) for configuration {self.name}.",
            log_type='push', state='success',
        )
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Datasets rebuilt'),
                'message': _(
                    '%(count)s Power BI dataset(s) were recreated. Please rebind existing reports '
                    'to the new datasets.',
                    count=len(rebuilt),
                ),
                'type': 'success',
            },
        }

    # ── Logging helper ─────────────────────────────────────────────────────────

    def _log(self, message, log_type='push', state='success', model_name=None, record_count=0, duration_ms=0.0):
        self.env['sh.powerbi.log'].sudo().create({
            'log_type': log_type,
            'state': state,
            'message': message,
            'model_name': model_name,
            'record_count': record_count,
            'duration_ms': duration_ms,
            'company_id': self.company_id.id,
        })
