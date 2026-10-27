# -*- coding: utf-8 -*-
# Copyright (C) Softhealer Technologies Pvt. Ltd.

from odoo import _,fields, models

class ShApiScope(models.Model):
    """A model to manage the API scopes for various integrations."""
    _name = 'sh.api.scope'
    _description = "Manage the scope for api"

    name = fields.Char(readonly=True)
    code = fields.Char(
        string='code',readonly=True
    )
    is_active = fields.Boolean(default=True,readonly=True)
    api_type = fields.Selection(selection=[],string='Api Type',readonly=True)
