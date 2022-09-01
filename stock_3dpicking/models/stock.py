# Copyright 2020 Openindustry.it SAS
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl.html).
from odoo import models, fields, api, _


class StockPicking(models.Model):
    _inherit = 'stock.picking'

    #@api.multi
    def action_locate(self):
        product_ids = []
        location_ids = []
        product_ids = self.move_ids_without_package.mapped('product_id').ids
        location_ids = self.env['stock.quant'].search([('product_id', 'in', product_ids)]).mapped('location_id').ids
        return {
            'name': _('Picking'),
            'type': 'ir.actions.act_window',
            'customdata_request_type': 'picking_locations',
            #'view_type': 'threedview',
            'view_mode': 'threedview',
            'res_model': 'stock.location',
            'domain': [('id', 'in', location_ids)],
        }


class StockPickingBatch(models.Model):
    _inherit = 'stock.picking.batch'

    #@api.multi
    def action_locate_batch(self):
        batch_product_ids = []
        batch_location_ids = []
        for picking_id in self.picking_ids:
            product_ids = picking_id.move_ids_without_package.mapped('product_id').ids
            if not batch_product_ids:
                batch_product_ids = product_ids
            else:
                batch_product_ids = list(set(batch_product_ids) | set(product_ids))
        batch_location_ids = self.env['stock.quant'].search([('product_id', 'in', batch_product_ids)]).mapped('location_id').ids
        return {
            'name': _('Batch'),
            'type': 'ir.actions.act_window',
            'customdata_request_type': 'batch_picking_locations',
            #'view_type': 'threedview',
            'view_mode': 'threedview',
            'res_model': 'stock.location',
            'domain': [('id', 'in', batch_location_ids)],
        }


class StockWarehouse(models.Model):
    _inherit = 'stock.warehouse'

    #@api.multi
    def action_locate_tagged_locations(self):
        location_ids = self.env['stock.location'].search([('warehouse_id', '=', self.id)]).ids
        return {
            'name': _('Warehouse'),
            'customdata_request_type': 'tagged',
            'type': 'ir.actions.act_window',
            #'view_type': 'threedview',
            'view_mode': 'threedview',
            'res_model': 'stock.location',
            'domain': [('id', 'in', location_ids)],
        }

    #@api.multi
    def action_locate_empty_locations(self):
        all_locations_ids = self.env['stock.location'].search(
            [('warehouse_id', '=', self.id)]
        ).ids
        full_locations_ids = self.env['stock.quant'].search(
            [('location_id.warehouse_id', '=', self.id),
             ('quantity', '>', 0)]
        ).mapped('location_id').ids
        empty_locations_ids = list(set(all_locations_ids) - set(full_locations_ids))

        return {
            'name': _('Warehouse'),
            'customdata_request_type': 'empty_locations',
            'type': 'ir.actions.act_window',
            #'view_type': 'threedview',
            'view_mode': 'threedview',
            'res_model': 'stock.location',
            'domain': [('id', 'in', empty_locations_ids)],
        }

    #@api.multi
    def action_locate_not_empty_locations(self):
        full_locations_ids = self.env['stock.quant'].search(
            [('location_id.warehouse_id', '=', self.id),
             ('quantity', '>', 0)]
        ).mapped('location_id').ids

        return {
            'name': _('Warehouse'),
            'customdata_request_type': 'not_empty_locations',
            'type': 'ir.actions.act_window',
            #'view_type': 'threedview',
            'view_mode': 'threedview',
            'res_model': 'stock.location',
            'domain': [('id', 'in', full_locations_ids)]
        }
