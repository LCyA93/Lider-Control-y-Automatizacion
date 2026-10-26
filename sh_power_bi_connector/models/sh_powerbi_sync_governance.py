# -*- coding: utf-8 -*-
# Copyright (C) Softhealer Technologies Pvt. Ltd.

import ast

from odoo import _, api, fields, models
from odoo.exceptions import UserError


class SHPowerBISyncCheckpoint(models.Model):
    """Per-model sync checkpoint for Power BI and Fabric targets."""

    _name = 'sh.powerbi.sync.checkpoint'
    _description = 'Power BI Sync Checkpoint'
    _order = 'id desc'

    name = fields.Char(string='Name', required=True)
    model_access_id = fields.Many2one('sh.powerbi.model.access', string='Model Access', required=True, ondelete='cascade')
    company_id = fields.Many2one('res.company', string='Company', required=True, default=lambda self: self.env.company)
    target = fields.Selection([
        ('powerbi_push', 'Power BI Push'),
        ('fabric_kql', 'Fabric KQL'),
        ('fabric_pipeline', 'Fabric Pipeline'),
    ], string='Target', required=True, default='powerbi_push')
    last_success_at = fields.Datetime(string='Last Success')
    last_write_date = fields.Datetime(string='Last Write Date')
    last_record_count = fields.Integer(string='Last Record Count')
    state = fields.Selection([
        ('draft', 'Draft'),
        ('running', 'Running'),
        ('done', 'Done'),
        ('failed', 'Failed'),
    ], string='Status', default='draft')
    message = fields.Text(string='Message')


class SHPowerBITombstone(models.Model):
    """Deleted Odoo record marker for downstream delete sync."""

    _name = 'sh.powerbi.tombstone'
    _description = 'Power BI Deleted Record Tombstone'
    _order = 'deleted_at desc, id desc'

    name = fields.Char(string='Reference', required=True)
    model_access_id = fields.Many2one('sh.powerbi.model.access', string='Model Access', ondelete='set null')
    model_name = fields.Char(string='Model', required=True, index=True)
    res_id = fields.Integer(string='Deleted Record ID', required=True, index=True)
    company_id = fields.Many2one('res.company', string='Company', required=True, default=lambda self: self.env.company)
    deleted_at = fields.Datetime(string='Deleted At', default=fields.Datetime.now, required=True)
    synced_powerbi = fields.Boolean(string='Synced to Power BI')
    synced_fabric = fields.Boolean(string='Synced to Fabric')


class SHPowerBIValidationWizard(models.TransientModel):
    """Validate model access before pushing or sending data to Fabric."""

    _name = 'sh.powerbi.validation.wizard'
    _description = 'Power BI Data Quality Validation'

    model_access_id = fields.Many2one('sh.powerbi.model.access', string='Model Access', required=True)
    issue_count = fields.Integer(string='Issues', readonly=True)
    warning_count = fields.Integer(string='Warnings', readonly=True)
    summary_html = fields.Html(string='Validation Summary', readonly=True)

    @api.model
    def default_get(self, fields_list):
        values = super().default_get(fields_list)
        model_access_id = self.env.context.get('default_model_access_id')
        if model_access_id:
            values['model_access_id'] = model_access_id
        return values

    @api.onchange('model_access_id')
    def _onchange_model_access_id(self):
        if self.model_access_id:
            self._run_validation()

    def action_validate(self):
        self.ensure_one()
        self._run_validation()
        return {
            'type': 'ir.actions.act_window',
            'name': _('Data Quality Validation'),
            'res_model': self._name,
            'view_mode': 'form',
            'res_id': self.id,
            'target': 'new',
        }

    def _run_validation(self):
        self.ensure_one()
        model_access = self.model_access_id
        issues = []
        warnings = []
        if not model_access.model_id or not model_access.model_name:
            issues.append(_("Odoo model is missing."))
        else:
            Model = self.env[model_access.model_name]
            try:
                domain = ast.literal_eval(model_access.domain_filter or '[]')
                if not isinstance(domain, list):
                    issues.append(_("Domain filter must evaluate to a list."))
                else:
                    Model.sudo().search_count(domain)
            except Exception as error:
                issues.append(_("Domain filter is invalid: %s") % error)

            field_names = [field.name for field in model_access.allowed_field_ids] or [
                name for name, field in Model._fields.items()
                if field.store and field.type not in ('binary', 'html', 'json', 'properties', 'properties_definition')
            ]
            if 'id' not in field_names:
                warnings.append(_("The shared id field will be added automatically for downstream joins."))
            unsupported = []
            for field_name in field_names:
                field = Model._fields.get(field_name)
                if not field:
                    unsupported.append(field_name)
                    continue
                if not field.store or field.type in ('binary', 'html', 'json', 'properties', 'properties_definition'):
                    unsupported.append(field_name)
            if unsupported:
                issues.append(_("Unsupported fields: %s") % ', '.join(unsupported))
            if len(field_names) > 75 and model_access.target_mode == 'powerbi_push':
                warnings.append(_("More than 75 fields selected; Power BI push will split this model into multiple tables."))
            if model_access.target_mode in ('fabric_kql', 'fabric_pipeline') and not model_access.fabric_config_id:
                issues.append(_("Fabric target mode requires a Fabric configuration."))
            if model_access.target_mode != 'powerbi_push' and not model_access.fabric_target_name:
                warnings.append(_("Fabric target table/item name is empty; Odoo will use the display alias or model name."))

        html = ['<ul>']
        for issue in issues:
            html.append('<li class="text-danger">%s</li>' % issue)
        for warning in warnings:
            html.append('<li class="text-warning">%s</li>' % warning)
        if not issues and not warnings:
            html.append('<li class="text-success">%s</li>' % _("No data quality issues found."))
        html.append('</ul>')
        self.issue_count = len(issues)
        self.warning_count = len(warnings)
        self.summary_html = ''.join(html)
