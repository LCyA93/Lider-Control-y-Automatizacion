# -*- coding: utf-8 -*-
# Copyright (C) Softhealer Technologies Pvt. Ltd.

import json
from ast import literal_eval
from datetime import datetime, timedelta

from odoo import models, fields, api


class ShIntegrationConnector(models.Model):
    """Registry model — each connector module creates one record here via XML data file."""
    _name = 'sh.integration.connector'
    _description = 'Integration Connector Registry'
    _order = 'sequence, name'

    name = fields.Char(string='Connector Name', required=True)
    sequence = fields.Integer(default=10)
    technical_name = fields.Char(
        string='Module Technical Name', required=True,
        help='e.g. sh_mailchimp_connector'
    )
    color = fields.Integer(default=0)
    active = fields.Boolean(default=True)

    # ── Connection status detection ─────────────────────────────────────────
    config_model = fields.Char(
        string='Config Model', help='e.g. sh.mailchimp.configuration'
    )
    connected_field = fields.Char(
        string='Status Field', help='Field on config model that holds connection state'
    )
    connected_value = fields.Char(
        string='Connected Value', help='Value of status field when connected, e.g. success'
    )

    # ── Entity definitions (JSON array) ────────────────────────────────────
    entity_definitions = fields.Text(
        string='Entity Definitions (JSON)',
        help='JSON array describing entities this connector syncs'
    )

    # ── Log model — char (set by registration XML) ──────────────────────────
    log_model = fields.Char(string='Log Model (Technical Name)')
    log_date_field = fields.Char(string='Log Date Field')
    log_state_field = fields.Char(string='Log State Field')
    log_error_value = fields.Char(string='Log Error Value', default='error')
    log_message_field = fields.Char(string='Log Message Field')

    # ── Log model — Many2one (user-selectable via UI, takes priority) ───────
    log_model_id = fields.Many2one(
        'ir.model',
        string='Log Model',
        domain=[('transient', '=', False)],
        ondelete='set null',
        help='Select the Odoo model whose records are displayed when the user clicks "Logs".'
             ' When set, this overrides the Log Model technical name field above.'
    )

    # ── Action XML IDs for kanban card buttons ─────────────────────────────
    dashboard_action = fields.Char(
        string='Dashboard Action XML ID',
        help='Full XML ID of the connector\'s own dashboard client action, '
             'e.g. sh_brevo_connector.action_sh_brevo_dashboard'
    )
    config_action = fields.Char(
        string='Config Action XML ID',
        help='Full XML ID of the connector\'s configuration form action, '
             'e.g. sh_mailchimp_connector.sh_mailchimp_configuration_action'
    )

    # ── Entities (One2many — shown inline in form view) ────────────────────
    entity_ids = fields.One2many(
        'sh.integration.entity',
        'connector_id',
        string='Entities',
    )

    # ── Queue model (optional) ──────────────────────────────────────────────
    queue_model = fields.Char(string='Queue Model')
    queue_state_field = fields.Char(string='Queue State Field')
    queue_pending_value = fields.Char(string='Queue Pending Value', default='draft')
    queue_done_value = fields.Char(string='Queue Done Value', default='done')
    queue_error_value = fields.Char(string='Queue Error Value', default='error')

    # ── Menu configuration ─────────────────────────────────────────────────
    menu_name = fields.Char(
        string='Menu Label',
        help='Label for the parent submenu under API Integration. '
             'Defaults to the connector name if left empty.',
    )
    menu_sequence = fields.Integer(
        string='Menu Sequence',
        default=10,
        help='Controls the order of this connector\'s submenu under API Integration.',
    )
    menu_parent_id = fields.Many2one(
        'ir.ui.menu',
        string='Generated Parent Menu',
        readonly=True,
        ondelete='set null',
        help='Auto-managed dynamically created folder for the connector menus.',
    )

    # ───────────────────────────────────────────────────────────────────────
    # Menu sync
    # ───────────────────────────────────────────────────────────────────────

    def _dynamic_reparent_menus(self):
        """Dynamically reparent the connector's root menus under the Integration Hub."""
        root_menu = self.env.ref('sh_integration_base.sh_base_config_root', raise_if_not_found=False)
        if not root_menu:
            return
        
        for connector in self:
            if not connector.technical_name:
                continue
                
            # Find all menus defined in this module
            self.env.cr.execute("""
                SELECT res_id FROM ir_model_data 
                WHERE model='ir.ui.menu' AND module=%s
            """, (connector.technical_name,))
            menu_ids = [row[0] for row in self.env.cr.fetchall()]
            
            if not menu_ids:
                continue
                
            menus = self.env['ir.ui.menu'].sudo().browse(menu_ids)
            
            # Find the connector's root menus (no parent, or parent is Integration Hub, or parent is our generated folder)
            # We exclude our own generated menu_parent_id from this list of root menus
            root_menus = menus.filtered(lambda m: (not m.parent_id or 
                                                   m.parent_id.id == root_menu.id or 
                                                   (connector.menu_parent_id and m.parent_id.id == connector.menu_parent_id.id))
                                                  and (not connector.menu_parent_id or m.id != connector.menu_parent_id.id))
            
            if not root_menus:
                continue

            # Ensure the connector's folder menu exists under Integration Hub
            label = connector.menu_name or connector.name
            parent_vals = {
                'name': label,
                'parent_id': root_menu.id,
                'sequence': connector.menu_sequence or 10,
            }
            if connector.menu_parent_id:
                connector.menu_parent_id.write(parent_vals)
            else:
                parent = self.env['ir.ui.menu'].create(parent_vals)
                connector.sudo().write({'menu_parent_id': parent.id})
            
            # Reparent all connector root menus into the generated folder menu
            for menu in root_menus:
                menu.write({'parent_id': connector.menu_parent_id.id})
                
                # Ensure base.group_system is in group_ids so admin is never locked out
                admin_group = self.env.ref('base.group_system', raise_if_not_found=False)
                if admin_group and admin_group not in menu.group_ids:
                    menu.write({'group_ids': [(4, admin_group.id)]})

    def action_sync_menus(self):
        self._dynamic_reparent_menus()
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': 'Menus Synchronized',
                'message': 'Menu items have been dynamically reparented successfully.',
                'type': 'success',
            },
        }

    @api.model_create_multi
    def create(self, vals_list):
        records = super().create(vals_list)
        records._dynamic_reparent_menus()
        return records

    def write(self, vals):
        res = super().write(vals)
        if any(k in vals for k in ('menu_name', 'menu_sequence', 'name')):
            self._dynamic_reparent_menus()
        return res

    @api.model
    def action_sync_menus_by_module(self, technical_name):
        """Called automatically at the end of connector module upgrades via XML <function> tag."""
        connector = self.search([('technical_name', '=', technical_name)], limit=1)
        if connector:
            connector._dynamic_reparent_menus()

    # ───────────────────────────────────────────────────────────────────────
    # Internal helper
    # ───────────────────────────────────────────────────────────────────────

    def _get_log_model_name(self):
        """Return the effective log model technical name.

        Priority: log_model_id (user-selected via UI) > log_model (char from XML).
        """
        self.ensure_one()
        if self.log_model_id:
            return self.log_model_id.model
        return self.log_model or ''

    # ───────────────────────────────────────────────────────────────────────
    # Helpers called by sh.integration.overview
    # ───────────────────────────────────────────────────────────────────────

    def _is_module_installed(self):
        self.ensure_one()
        module = self.env['ir.module.module'].sudo().search(
            [('name', '=', self.technical_name), ('state', '=', 'installed')], limit=1
        )
        return bool(module)

    def _user_has_access(self):
        """Return True if the current user may see this connector's kanban card.

        Admins (base.group_system) always see every card.
        For other users: collect all group_ids from menu_item_ids — if none are
        configured the card is visible to all; otherwise the user must belong to
        at least one of those groups.
        """
        self.ensure_one()
        if self.env.user.has_group('base.group_system'):
            return True
            
        all_groups = self.env['res.groups'].browse()
        if self.technical_name:
            self.env.cr.execute("""
                SELECT res_id FROM ir_model_data 
                WHERE model='ir.ui.menu' AND module=%s
            """, (self.technical_name,))
            menu_ids = [row[0] for row in self.env.cr.fetchall()]
            if menu_ids:
                menus = self.env['ir.ui.menu'].sudo().browse(menu_ids)
                root_menu = self.env.ref('sh_integration_base.sh_base_config_root', raise_if_not_found=False)
                # Find root menus (no parent, parent is Integration Hub, or parent is our generated folder)
                root_menus = menus.filtered(lambda m: (not m.parent_id or 
                                                       (root_menu and m.parent_id.id == root_menu.id) or 
                                                       (self.menu_parent_id and m.parent_id.id == self.menu_parent_id.id))
                                                      and (not self.menu_parent_id or m.id != self.menu_parent_id.id))
                for menu in root_menus:
                    # Exclude base.group_system from the check since we already handled admin above
                    admin_group = self.env.ref('base.group_system', raise_if_not_found=False)
                    all_groups |= menu.group_ids.filtered(lambda g: g != admin_group)
                    
        if not all_groups:
            return True
        return bool(all_groups & self.env.user.group_ids)

    def _get_last_sync(self):
        """Return the datetime string of the most recent log entry, or None."""
        self.ensure_one()
        log_model_name = self._get_log_model_name()
        if not log_model_name or log_model_name not in self.env:
            return None
        date_field = self.log_date_field or 'create_date'
        try:
            rec = self.env[log_model_name].sudo().search(
                [], order=f'{date_field} desc', limit=1
            )
            if rec:
                val = getattr(rec, date_field, None)
                return val.strftime('%Y-%m-%d %H:%M:%S') if val else None
        except Exception:
            pass
        return None

    def _get_connection_status(self):
        self.ensure_one()
        if not self.config_model or self.config_model not in self.env:
            return False
        config = self.env[self.config_model].sudo().search([], limit=1)
        if not config:
            return False
        if not self.connected_field:
            return True
        value = getattr(config, self.connected_field, None)
        if self.connected_value:
            return str(value) == self.connected_value
        return bool(value)

    def _get_entity_counts(self):
        self.ensure_one()
        result = []

        # Primary: use sh.integration.entity model records
        entity_recs = self.env['sh.integration.entity'].search([
            ('connector_id', '=', self.id),
            ('active', '=', True),
        ])
        if entity_recs:
            for ent in entity_recs:
                model_name = ent.model_name
                if not model_name or model_name not in self.env:
                    continue
                try:
                    domain = literal_eval(ent.domain or '[]')
                    if not isinstance(domain, list):
                        domain = []
                    count = self.env[model_name].sudo().search_count(domain)
                except Exception:
                    domain, count = [], 0
                result.append({
                    'label': ent.name,
                    'model': model_name,
                    'icon': ent.icon or 'fa-database',
                    'count': count,
                    'domain': domain,
                })
            return result

        # Fallback: use JSON entity_definitions (backward compatibility)
        if not self.entity_definitions:
            return result
        try:
            definitions = json.loads(self.entity_definitions)
        except (json.JSONDecodeError, TypeError):
            return result
        for defn in definitions:
            model_name = defn.get('model')
            domain_str = defn.get('domain', '[]')
            if not model_name or model_name not in self.env:
                continue
            try:
                domain = literal_eval(domain_str)
                if not isinstance(domain, list):
                    domain = []
                count = self.env[model_name].sudo().search_count(domain)
            except Exception:
                domain, count = [], 0
            result.append({
                'label': defn.get('label', model_name),
                'model': model_name,
                'icon': defn.get('icon', 'fa-database'),
                'count': count,
                'domain': domain,
            })
        return result

    def _get_chart_data(self, days=7):
        self.ensure_one()
        log_model_name = self._get_log_model_name()
        if not log_model_name or log_model_name not in self.env:
            return {'labels': [], 'success': [], 'error': []}

        labels = []
        success_data = []
        error_data = []
        today = datetime.now().replace(hour=23, minute=59, second=59)
        date_field = self.log_date_field or 'create_date'
        state_field = self.log_state_field or 'state'
        error_val = self.log_error_value or 'error'

        for i in range(days - 1, -1, -1):
            day_start = (today - timedelta(days=i)).replace(hour=0, minute=0, second=0)
            day_end = (today - timedelta(days=i)).replace(hour=23, minute=59, second=59)
            labels.append(day_start.strftime('%a'))
            base_domain = [
                (date_field, '>=', day_start.strftime('%Y-%m-%d %H:%M:%S')),
                (date_field, '<=', day_end.strftime('%Y-%m-%d %H:%M:%S')),
            ]
            try:
                total = self.env[log_model_name].sudo().search_count(base_domain)
                errors = self.env[log_model_name].sudo().search_count(
                    base_domain + [(state_field, '=', error_val)]
                )
            except Exception:
                total, errors = 0, 0
            error_data.append(errors)
            success_data.append(max(total - errors, 0))

        return {'labels': labels, 'success': success_data, 'error': error_data}

    def _get_recent_errors(self, limit=3):
        self.ensure_one()
        log_model_name = self._get_log_model_name()
        if not log_model_name or log_model_name not in self.env:
            return []
        date_field = self.log_date_field or 'create_date'
        state_field = self.log_state_field or 'state'
        error_val = self.log_error_value or 'error'
        message_field = self.log_message_field or 'name'
        try:
            records = self.env[log_model_name].sudo().search(
                [(state_field, '=', error_val)],
                order=f'{date_field} desc',
                limit=limit
            )
        except Exception:
            return []
        result = []
        for rec in records:
            msg = getattr(rec, message_field, '') or ''
            date_val = getattr(rec, date_field, None)
            result.append({
                'message': str(msg)[:100],
                'connector': self.name,
                'date': date_val.strftime('%Y-%m-%d %H:%M:%S') if date_val else '',
            })
        return result

    def _get_queue_stats(self):
        self.ensure_one()
        if not self.queue_model or self.queue_model not in self.env:
            return None
        state_field = self.queue_state_field or 'state'
        try:
            pending = self.env[self.queue_model].sudo().search_count(
                [(state_field, '=', self.queue_pending_value or 'draft')]
            )
            done = self.env[self.queue_model].sudo().search_count(
                [(state_field, '=', self.queue_done_value or 'done')]
            )
            error = self.env[self.queue_model].sudo().search_count(
                [(state_field, '=', self.queue_error_value or 'error')]
            )
        except Exception:
            pending, done, error = 0, 0, 0
        return {'pending': pending, 'done': done, 'error': error}
