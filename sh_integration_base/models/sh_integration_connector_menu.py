# -*- coding: utf-8 -*-
# Copyright (C) Softhealer Technologies Pvt. Ltd.

from odoo import models, fields


class ShIntegrationConnectorMenu(models.Model):
    """Manages mirrored menu items for connectors within the Integration Hub.
    Allows selected menus from a connector module to be displayed under its
    folder in the Hub dashboard.
    """
    _name = 'sh.integration.connector.menu'
    _description = 'Connector Menu Mirror'
    _order = 'sequence, id'

    connector_id = fields.Many2one(
        'sh.integration.connector',
        string='Connector',
        required=True,
        ondelete='cascade',
        index=True,
    )
    source_menu_id = fields.Many2one(
        'ir.ui.menu',
        string='Source Menu',
        required=True,
        ondelete='cascade',
    )
    sequence = fields.Integer(default=10)
    group_ids = fields.Many2many(
        'res.groups',
        string='Groups',
        help='Groups that can see this mirrored menu item.',
    )
