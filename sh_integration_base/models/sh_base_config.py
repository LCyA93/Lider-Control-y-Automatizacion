# -*- coding: utf-8 -*-
# Copyright (C) Softhealer Technologies Pvt. Ltd.

from datetime import datetime
from odoo import models,fields,api
from odoo.exceptions import ValidationError

class BaseConfigration(models.Model):
    """A model to manage and configure integrations with third-party services."""
    _name = 'sh.integration.config'
    _description = 'Configration'
    _inherit = [ 'mail.thread', 'mail.activity.mixin']


    name= fields.Char(string="Name")
    sh_type = fields.Selection(selection=[],string='Type',tracking=True)
    company_id =fields.Many2one("res.company",string="Company", default=lambda self: self.env.company,tracking=True)
    # TODO:
    log_ids = fields.One2many('sh.integration.log', 'config_id', string="Log History")
    # TODO: Move in india-mart or any respective module
    auto_imp=fields.Boolean("Auto Import")
    scope_ids = fields.Many2many('sh.api.scope',compute='_compute_scope' )
    state = fields.Selection([
        ("draft", "Draft"),
        ("authorized", "Authorized"),
        ("failed", "Failed"),
    ], string="State", default="draft", tracking=True, copy=False)
    client_id = fields.Char(
        string='Client Id',
    )
    client_secret = fields.Char(
        string='Client Secret',
    )
    access_token = fields.Char(
        string='Access Token',
    )
    refresh_token = fields.Char(
        string='Refresh Token',
    )
    icon_image = fields.Binary(
        string='Icon Image',
    )
    redirect_url = fields.Char(
        string='Redirect Url',
            compute='_compute_redirect_url' )

    @api.depends('sh_type')
    def _compute_redirect_url(self):
        """Computes the redirect URL for OAuth authentication based on the integration type."""
        for record in self:

            if self.sh_type and self.create_uid:
                base_url = self.env['ir.config_parameter'].sudo().get_param('web.base.url')
                record.redirect_url = f"{base_url}/sh_integration_base/auth/{self._origin.id}"
            else:
                record.redirect_url = ""

    @api.constrains('company_id', 'sh_type')
    def _check_unique_company_type(self):
        """Ensures that there is only one configuration per company and integration type."""
        for rec in self:
            existing = self.search([('company_id', '=', rec.company_id.id),('sh_type', '=', rec.sh_type),('id', '!=', rec.id)], limit=1)
            if existing:
                raise ValidationError("A configuration already exists for this company and type.")

    def authorize_btn(self):
        """Handles the authorization process for the integration."""
        if not self.sh_type:
            raise ValidationError("Plz Select the type.")
        return True

    def generate_token(self,auth_code):
        """Generates an access token using the provided authorization code."""
        required_fields = {
            'client_id': self.client_id,
            'client_secret': self.client_secret,
            'redirect_url': self.redirect_url,
            'auth_code': auth_code,
        }

        missing_fields = [field for field, val in required_fields.items() if not val]
        if missing_fields:
            raise ValidationError(f"Missing required fields: {missing_fields}")
        return True

    def _compute_scope(self):
        """
        Add scope according to the module like Google Task,Xero, etc.

        +----------------------------------------------------------+
        | Odoo Module | Zoho Module | Zoho Scope                   |
        +----------------------------------------------------------+
        | crm         | CRM         | ZohoCRM.modules.all          |
        | account     | Books       | ZohoBooks.fullaccess.all     |
        | stock       | Inventory   | ZohoInventory.FullAccess.all |
        | sale        | Sale        | ZohoBooks.salesorders.ALL    |
        | Contact     | Contact     | ZohoBooks.contacts.ALL       |
        |             |             |                              |
        |             | Sale Report | ZohoBooks.reports.All        |
        |             |             | ZohoBooks.settings.ALL       |
        |             | Custom      | ZohoBooks.custommodules.ALL  |
        +----------------------------------------------------------+

        """
        for rec in self:
            rec.scope_ids = False
    # -------------------------------------------------------
    #  Create the log
    # -------------------------------------------------------

    def _log(self, message, log_type=False, state=False,response=False):
        """Creates a log entry for the integration."""
        self.env['sh.integration.log'].create({
            "description": message,
            "state": state,
            "config_id": self.id,
            "response": response,
            "log_type": log_type,
        })