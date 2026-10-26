# -*- coding: utf-8 -*-
# Copyright (C) Softhealer Technologies Pvt. Ltd.

from odoo import models, fields, api, _
from odoo.tools import html_escape


class SHPowerBISchemaDiffWizard(models.TransientModel):
    _name = 'sh.powerbi.schema.diff.wizard'
    _description = 'Power BI Schema Diff Wizard'

    push_config_id = fields.Many2one('sh.powerbi.push.config', string='Push Configuration', required=True)
    model_access_id = fields.Many2one('sh.powerbi.model.access', string='Model Access', required=True)

    model_name = fields.Char(string='Model', readonly=True)
    dataset_name = fields.Char(string='Dataset/Table', readonly=True)
    added_count = fields.Integer(string='Added Columns', readonly=True)
    removed_count = fields.Integer(string='Removed Columns', readonly=True)
    changed_count = fields.Integer(string='Changed Column Types', readonly=True)
    summary_message = fields.Char(string='Summary', readonly=True)
    diff_html = fields.Html(string='Schema Comparison', readonly=True)
    is_destructive = fields.Boolean(string='Is Destructive', default=False)
    confirm_button_label = fields.Char(string='Confirm Button Label', readonly=True)

    def action_confirm_update(self):
        """Proceed with dataset recreation/update."""
        self.ensure_one()
        return self.push_config_id.with_context(
            skip_schema_check=True,
            schema_diff_confirmed=True,
        ).action_push_model(self.model_access_id.id)

    @api.model
    def create_from_diff(self, push_config, model_access, odoo_fields, pbi_fields):
        """Factory method to create a wizard populated with diff data."""
        added, removed, changed = self._split_drift(odoo_fields, pbi_fields)

        is_destructive = bool(removed or changed)
        table_names = {
            item.split('.', 1)[0]
            for item in set(odoo_fields) | set(pbi_fields)
            if '.' in item
        }

        html = '<div class="container">'
        if len(table_names) > 1:
            html += (
                '<div class="alert alert-info">'
                '<strong>Power BI table split:</strong> This model uses multiple Power BI tables because '
                'Power BI push datasets allow a maximum of 75 columns per table. Each generated table '
                'contains the shared <code>id</code> column for joining records.'
                '</div>'
            )
        if added:
            html += '<div class="alert alert-success"><strong>Added Columns:</strong><ul>'
            for f in added:
                html += f'<li>{html_escape(f)}</li>'
            html += '</ul></div>'

        if removed:
            html += '<div class="alert alert-danger"><strong>Removed Columns (Destructive):</strong><ul>'
            for f in removed:
                html += f'<li>{html_escape(f)}</li>'
            html += '</ul></div>'
            html += (
                '<p class="text-danger"><strong>WARNING:</strong> Proceeding will delete your existing dataset '
                'and break reports in Power BI.</p>'
            )

        if changed:
            html += '<div class="alert alert-warning"><strong>Changed Column Types (Destructive):</strong><ul>'
            for f in changed:
                html += f'<li>{html_escape(f)}</li>'
            html += '</ul></div>'
            html += (
                '<p class="text-danger"><strong>WARNING:</strong> Power BI cannot change the data type of an '
                'existing column. Proceeding will delete your existing dataset and break reports in Power BI.</p>'
            )

        if not added and not removed and not changed:
            html += '<p class="text-info">No schema difference detected.</p>'
        elif not removed and not changed:
            html += '<p class="text-info">This update is additive. It should be safe but may still require dataset refresh.</p>'

        html += '</div>'

        table_name = model_access.display_alias or model_access.model_id.name or model_access.model_name
        if len(table_names) > 1:
            table_name = _("%(table)s (+ %(parts)s part tables)", table=table_name, parts=len(table_names) - 1)
        summary_message = _(
            "Schema drift detected for %(model)s. Added: %(added)s, Removed: %(removed)s, Changed types: %(changed)s.",
            model=model_access.model_name,
            added=len(added),
            removed=len(removed),
            changed=len(changed),
        )

        return self.create({
            'push_config_id': push_config.id,
            'model_access_id': model_access.id,
            'model_name': model_access.model_name,
            'dataset_name': table_name,
            'added_count': len(added),
            'removed_count': len(removed),
            'changed_count': len(changed),
            'summary_message': summary_message,
            'diff_html': html,
            'is_destructive': is_destructive,
            'confirm_button_label': _('Confirm and Recreate Dataset') if is_destructive else _('Confirm and Update Dataset'),
        })

    @api.model
    def _split_drift(self, odoo_fields, pbi_fields):
        """Split a schema drift into added, removed and type-changed column labels.

        Columns are received as ``table.column:dataType`` labels so that a pure
        data type change is reported on its own instead of being counted both as
        an addition and as a removal.
        """
        odoo_map = {self._split_qualified(item)[0]: self._split_qualified(item)[1] for item in odoo_fields}
        pbi_map = {self._split_qualified(item)[0]: self._split_qualified(item)[1] for item in pbi_fields}
        added = sorted(set(odoo_map) - set(pbi_map))
        removed = sorted(set(pbi_map) - set(odoo_map))
        changed = sorted(
            name for name in set(odoo_map) & set(pbi_map) if odoo_map[name] != pbi_map[name]
        )
        return added, removed, changed

    @staticmethod
    def _split_qualified(qualified):
        """Split a ``table.column:dataType`` label into ``(table.column, dataType)``."""
        name, _separator, data_type = qualified.rpartition(':')
        return name, data_type
