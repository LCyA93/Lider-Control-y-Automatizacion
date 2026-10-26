# -*- coding: utf-8 -*-
# Copyright (C) Softhealer Technologies Pvt. Ltd.

from odoo import models, fields


class ResCompany(models.Model):
    _inherit = 'res.company'

    # ── Existing fields — must not be renamed (backward compatibility) ─────────
    sh_powerbi_api_key = fields.Char(string="API Key", readonly=True)
    sh_powerbi_odoo_url = fields.Char(string="Odoo URL", readonly=True)
    sh_powerbi_db_name = fields.Char(string="Database Name", readonly=True)

    # ── New fields (v19.0.3.0.0) ───────────────────────────────────────────────
    sh_powerbi_key_expiry = fields.Datetime(string="API Key Expiry", readonly=True)
    sh_powerbi_fetch_mode = fields.Selection([
        ('all', 'All Accessible Models'),
        ('configured', 'Configured Models Only'),
    ], string='Power BI Data Access Mode', default='all',
        help="All: Power BI can access every model the API key user has read permission for.\n"
             "Configured: Only models listed in Power BI Model Access are exposed.")

    sh_powerbi_relation_format = fields.Selection([
        ('id_and_display', 'ID and Display Name (Recommended for Power BI Modeling)'),
        ('id_only', 'Numeric ID Only'),
        ('display_only', 'Display Name Only (Legacy)'),
    ], string='Relational Field Format', default='id_and_display',
        help="ID and Display Name: Foreign keys (e.g. product_tmpl_id) contain numeric IDs for table relationships in Power BI, with companion display fields (e.g. product_tmpl_id_display).\n"
             "Numeric ID Only: Foreign keys contain only integer IDs.\n"
             "Display Name Only: Legacy format where foreign keys contain display name text.")
