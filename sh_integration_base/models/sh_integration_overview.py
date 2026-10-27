# -*- coding: utf-8 -*-
# Copyright (C) Softhealer Technologies Pvt. Ltd.

import os

from odoo import models, api
from odoo.modules import get_module_path


class ShIntegrationOverview(models.TransientModel):
    """Aggregates data from registered connectors for the overview dashboard."""
    _name = 'sh.integration.overview'
    _description = 'Integration Overview Dashboard'

    # ── Field types shown in the dynamic list view ───────────────────────────
    _LIST_FIELD_TYPES = {
        'char', 'text', 'integer', 'float', 'date',
        'datetime', 'boolean', 'selection', 'many2one', 'monetary',
    }

    # Fields that are always hidden from dynamic list views
    _LIST_SKIP_FIELDS = {
        'id', 'display_name',
        'write_date', 'write_uid', 'create_date', 'create_uid',
        'active', 'message_ids', 'message_follower_ids',
        'message_partner_ids', 'activity_ids',
    }

    @api.model
    def _safe_call(self, record, method_name, default, *args, **kwargs):
        """Safely call a method on a record to prevent a single connector crash from breaking the dashboard."""
        if not hasattr(record, method_name):
            return default
        try:
            return getattr(record, method_name)(*args, **kwargs)
        except Exception:
            return default

    # ── Kanban overview ───────────────────────────────────────────────────────

    @api.model
    def get_dashboard_data(self):
        """Return kanban card data — one entry per installed connector."""
        connectors = self.env['sh.integration.connector'].search([])
        result = []
        for connector in connectors:
            if not self._safe_call(connector, '_is_module_installed', False):
                continue
            if not self._safe_call(connector, '_user_has_access', False):
                continue
            chart = self._safe_call(connector, '_get_chart_data', {}, days=7)
            result.append({
                'id': connector.id,
                'name': connector.name,
                'color': connector.color,
                'connected': self._safe_call(connector, '_get_connection_status', False),
                'entities': self._safe_call(connector, '_get_entity_counts', []),
                'chart_labels': chart.get('labels', []),
                'chart_success': chart.get('success', []),
                'chart_error': chart.get('error', []),
                'queue': self._safe_call(connector, '_get_queue_stats', {'pending': 0, 'done': 0, 'error': 0}),
                'recent_errors': self._safe_call(connector, '_get_recent_errors', [], limit=3),
                'dashboard_action': connector.dashboard_action or False,
                'config_action': connector.config_action or False,
                'menu_name': connector.menu_name or '',
                'last_sync': self._safe_call(connector, '_get_last_sync', False),
                'avatar_url': self._get_connector_avatar_url(connector.technical_name),
                'has_logs': bool(self._safe_call(connector, '_get_log_model_name', False)),
            })
        return result

    def _get_connector_avatar_url(self, technical_name):
        """Return the web URL for the connector's avatar image if the file exists."""
        module_path = get_module_path(technical_name)
        abs_path = os.path.join(module_path, 'static', 'src', 'img', 'sh_kcard_avatar.png') if module_path else False

        if abs_path and os.path.isfile(abs_path):
            return f'/{technical_name}/static/src/img/sh_kcard_avatar.png'
        return False

    # ── Logs action — dynamic list view ──────────────────────────────────────

    @api.model
    def get_log_action(self, connector_id):
        """Return ir.actions.act_window for the connector's log model.

        Strategy:
          1. Resolve the log model name (log_model_id Many2one  >  log_model char).
          2. Look for an existing standalone primary list view for that model.
          3. If found → use it directly.
          4. If not found → build a dynamic list view arch from the model's fields
             and create / reuse a persistent ir.ui.view record.
          5. Return an act_window pointing to that view (list only, read-only).
        """
        connector = self.env['sh.integration.connector'].browse(connector_id)
        if not connector.exists():
            return False

        log_model_name = self._safe_call(connector, '_get_log_model_name', False)
        if not log_model_name or log_model_name not in self.env:
            return False

        model_rec = self.env['ir.model'].sudo().search(
            [('model', '=', log_model_name)], limit=1
        )
        display_name = model_rec.name if model_rec else log_model_name

        view_id = self._resolve_list_view(log_model_name)

        return {
            'type': 'ir.actions.act_window',
            'name': f'{connector.name} — {display_name}',
            'res_model': log_model_name,
            'view_mode': 'list',
            'view_id': view_id,
            'views': [(view_id, 'list')],
            'target': 'current',
            'context': {},
        }

    def _resolve_list_view(self, model_name):
        """Return an ir.ui.view id for a list view of model_name.

        Prefers an existing primary list view; otherwise creates a dynamic one.
        """
        # 1 — look for existing standalone primary list view
        existing = self.env['ir.ui.view'].sudo().search([
            ('model', '=', model_name),
            ('type', '=', 'list'),
            ('mode', '=', 'primary'),
            ('active', '=', True),
        ], limit=1, order='priority asc')

        if existing:
            return existing.id

        # 2 — no existing view → build dynamic one from model fields
        return self._get_or_create_dynamic_list_view(model_name)

    def _get_or_create_dynamic_list_view(self, model_name):
        """Create (or retrieve a previously created) dynamic list view for model_name."""
        view_name = f'sh_integration_base.dynamic_log_list_{model_name.replace(".", "_")}'

        # Reuse if already created in a previous session
        dynamic_view = self.env['ir.ui.view'].sudo().search([
            ('name', '=', view_name),
            ('model', '=', model_name),
            ('type', '=', 'list'),
        ], limit=1)

        if dynamic_view:
            return dynamic_view.id

        arch = self._build_list_arch(model_name)
        try:
            new_view = self.env['ir.ui.view'].sudo().create({
                'name': view_name,
                'type': 'list',
                'model': model_name,
                'arch_base': arch,
                'active': True,
                'priority': 99,
            })
            return new_view.id
        except Exception:
            return False

    def _build_list_arch(self, model_name):
        """Generate a <list> arch string using all relevant fields of the model."""
        try:
            model_obj = self.env[model_name]
            all_fields = model_obj.fields_get(attributes=['string', 'type', 'readonly'])
        except Exception:
            return '<list create="0" edit="0"><field name="id"/></list>'

        # Separate into priority buckets so important columns appear first
        date_fields = []
        state_fields = []
        name_type_fields = []
        other_fields = []

        priority_names = {'state', 'status', 'sh_state', 'sh_status', 'type_', 'sh_type'}
        date_types = {'date', 'datetime'}
        name_hints = {'name', 'sh_message', 'error', 'description', 'sh_details'}

        for fname, finfo in all_fields.items():
            if fname in self._LIST_SKIP_FIELDS or fname.startswith('_'):
                continue
            if finfo.get('type') not in self._LIST_FIELD_TYPES:
                continue

            node = f'<field name="{fname}"/>'
            ftype = finfo.get('type', '')

            if ftype in date_types:
                date_fields.append(node)
            elif fname in priority_names or ftype == 'selection':
                state_fields.append(node)
            elif fname in name_hints or ftype == 'char':
                name_type_fields.append(node)
            else:
                other_fields.append(node)

        ordered_nodes = date_fields + state_fields + name_type_fields + other_fields

        if not ordered_nodes:
            ordered_nodes = ['<field name="id"/>']

        fields_xml = ''.join(ordered_nodes)
        return f'<list create="0" edit="0" delete="0">{fields_xml}</list>'

    # ── Connector detail view ─────────────────────────────────────────────────

    @api.model
    def get_connector_detail(self, connector_id):
        """Return full detail data for one connector (opened from kanban card)."""
        connector = self.env['sh.integration.connector'].browse(connector_id)
        if not connector.exists():
            return {}
        chart = self._safe_call(connector, '_get_chart_data', {}, days=7)
        entities = self._safe_call(connector, '_get_entity_counts', [])
        queue = self._safe_call(connector, '_get_queue_stats', {'pending': 0, 'done': 0, 'error': 0})
        errors = self._safe_call(connector, '_get_recent_errors', [], limit=6)
        return {
            'id': connector.id,
            'name': connector.name,
            'color': connector.color,
            'connected': self._safe_call(connector, '_get_connection_status', False),
            'entities': entities,
            'chart_labels': chart.get('labels', []),
            'chart_success': chart.get('success', []),
            'chart_error': chart.get('error', []),
            'queue': queue or {'pending': 0, 'done': 0, 'error': 0},
            'recent_errors': errors,
        }
