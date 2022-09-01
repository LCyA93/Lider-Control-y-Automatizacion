# Copyright 2020 Openindustry.it SAS
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl.html).
from odoo import models, fields, api, _

class StockLocation(models.Model):
    _inherit = 'stock.location'

    def threedView(self):
        return {
            'name': _('Location 3D View'),
            'type': 'ir.actions.act_window',
            'customdata_request_type': 'tagged',
            'view_mode': 'threedview',
            'res_model': 'stock.location',
            'domain': [('id', 'child_of', self.id)],
        }

