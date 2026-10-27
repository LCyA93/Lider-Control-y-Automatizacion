# -*- coding: utf-8 -*-
# Copyright (C) Softhealer Technologies Pvt. Ltd.

from odoo import models, fields


class ShIntegrationEntity(models.Model):
    """Defines clickable entity boxes shown on each connector's kanban card.
    Each record represents one entity type (e.g. Contacts, Campaigns) with
    the model to open and an optional domain filter applied on click.
    """
    _name = 'sh.integration.entity'
    _description = 'Integration Connector Entity'
    _order = 'connector_id, sequence, name'

    connector_id = fields.Many2one(
        'sh.integration.connector',
        string='Connector',
        required=True,
        ondelete='cascade',
        index=True,
    )
    name = fields.Char(string='Label', required=True, help='Display label shown on the card, e.g. "Contacts"')
    model_id = fields.Many2one(
        'ir.model',
        string='Model',
        required=True,
        domain=[('transient', '=', False)],
        ondelete='cascade',
    )
    model_name = fields.Char(
        related='model_id.model',
        string='Model Technical Name',
        store=True,
        readonly=True,
    )
    domain = fields.Char(
        string='Filter Domain',
        default='[]',
        help='Python domain expression applied when opening the list view, '
             'e.g. [[\"sh_mailchimp_member_id\",\"!=\",False]]',
    )
    icon = fields.Char(
        string='FA Icon Class',
        default='fa-database',
        help='Font Awesome icon class shown above the count, e.g. fa-users',
    )
    sequence = fields.Integer(default=10)
    active = fields.Boolean(default=True)
