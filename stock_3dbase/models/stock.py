# © 2020 OpenIndustry.it
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

from odoo import models, fields, api, _
from odoo.exceptions import ValidationError


class StockLocationTag(models.Model):
    _description = 'Location Tags'
    _name = 'stock.location.tag'
    _order = 'name'

    name = fields.Char(
        string='Tag Name', 
        required=True, 
        translate=True,
    )
    color = fields.Integer(
        string='Color Index',
        default=0,
    )
    opacity = fields.Integer(
        string='Opacity',
        default=500,
    )


class StockWarehouse(models.Model):
    _inherit = 'stock.warehouse'

    spacex = fields.Integer(
        string='Depth (X)',
        default=0,
    )
    spacey = fields.Integer(
        string='Width (Y)',
        default=0,
    )
    spacez = fields.Integer(
        string='Height (Z)',
        default=0,
    )
    planimetry_image = fields.Binary(
        string='Planimetry Image', 
        help="Warehouse planimetry image",
    )

    count_sl = fields.Integer(
        string='Count Stock Locations',
        compute='_compute_count_sl',
    )

    def _compute_count_sl(self):
        for wh in self:
            wh.count_sl = self.env['stock.location'].search_count([
                ('warehouse_id', '=', wh.id),
                ('usage', '=', 'internal'),
            ])

    @api.constrains('view_location_id')
    def _check_view_location_id(self):
        for wh in self:
            duplicate = self.search([('id', '!=', wh.id), ('view_location_id', '=', wh.view_location_id.id)], limit=1)
            if duplicate:
                raise ValidationError(_("Location %s is used for warehouse '%s'") % (wh.view_location_id.name, duplicate.name))

    #@api.multi
    def action_open_stock_locations(self):
        action = self.env.ref('stock_3dbase.act_warehouse_stock_locations').read()[0]
        action['domain'] = [('warehouse_id', '=', self.id)]
        action['context'] = {'search_default_in_location': 1}
        return action


class StockLocation(models.Model):
    _inherit = 'stock.location'

    barcode = fields.Char(
        string='Barcode',
    )
    posx = fields.Integer(
        string='Pos (X)',
        default=0,
    )
    posy = fields.Integer(
        string='Pos (Y)',
        default=0,
    )
    posz = fields.Integer(
        string='Pos (Z)',
        default=0,
    )
    sizex = fields.Integer(
        string='Size (X)', 
        default=0,
    )
    sizey = fields.Integer(
        string='Size (Y)', 
        default=0,
    )
    sizez = fields.Integer(
        string='Size (Z)',
        default=0,
    )
    tag_ids = fields.Many2many(
        comodel_name='stock.location.tag',
        column1='location_id',
        column2='tag_id',
        string='Tags')
    warehouse_id = fields.Many2one(
        comodel_name='stock.warehouse', 
        string='Warehouse',
        compute='_get_warehouse', 
        store=True, 
        help="Location warehouse",
    )

    @api.depends('location_id')
    def _get_warehouse(self):
        for loc in self:
            loc.warehouse_id = loc.get_warehouse()

    @api.model
    def get_sublocations(self):
        res = self.search([('id', 'child_of', self.id)])
        return res

