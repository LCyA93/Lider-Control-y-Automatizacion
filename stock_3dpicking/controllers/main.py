# Copyright 2020 Openindustry.it SAS
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl.html).
from odoo import http, tools, _
from odoo.http import request
import json
import logging

_logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

class ThreeDViewController(http.Controller):

    _color = '#875A7B'
    _opacity = 700

    @http.route('/3dview/get_legend/picking_locations', type='json', auth="user", methods=['POST'])
    def get_legend_stock_picking(self, domain, **kwargs):
        return self._get_legend("picking", **kwargs)

    @http.route('/3dview/get_legend/batch_picking_locations', type='json', auth="user", methods=['POST'])
    def get_legend_stock_picking_batch(self, domain, **kwargs):
        return self._get_legend("batch picking", **kwargs)

    @http.route('/3dview/get_legend/empty_locations', type='json', auth="user", methods=['POST'])
    def get_legend_empty_locations(self, domain, **kwargs):
        return self._get_legend("empty", **kwargs)

    @http.route('/3dview/get_legend/not_empty_locations', type='json', auth="user", methods=['POST'])
    def get_legend_full_locations(self, domain, **kwargs):
        return self._get_legend("not empty", **kwargs)

    @http.route('/3dview/get_locations/picking_locations', type='json', auth="user", methods=['POST'])
    def get_locations_stock_picking(self, domain=[], **kwargs):
        return self._get_locations(domain, self._color, **kwargs)

    @http.route('/3dview/get_locations/batch_picking_locations', type='json', auth="user", methods=['POST'])
    def get_locations_stock_picking_batch(self, domain=[], **kwargs):
        return self._get_locations(domain, self._color, **kwargs)

    @http.route('/3dview/get_locations/empty_locations', type='json', auth="user", methods=['POST'])
    def get_locations_empty_locations(self, domain=[], **kwargs):
        all_locations_ids = request.env['stock.location'].search(domain).ids
        full_locations_ids = request.env['stock.quant'].search(
            [ #('location_id.warehouse_id', '=', self.id),
             ('quantity', '>', 0)]
        ).mapped('location_id').ids
        empty_locations_ids = list(set(all_locations_ids) - set(full_locations_ids))
        domain = [('id', 'in', empty_locations_ids)]
        return self._get_locations(domain, self._color, **kwargs)

    @http.route('/3dview/get_locations/not_empty_locations', type='json', auth="user", methods=['POST'])
    def get_locations_full_locations(self, domain=[], **kwargs):
        return self._get_locations(domain, self._color, **kwargs)

    def _get_legend(self, label, **kwargs):
        values = [
            {'name': label, 'color': self._color, 'opacity': self._opacity},
        ]
        return json.dumps(values)

    def _get_locations(self, domain=[], color='#ff0000', **kwargs):
        domain.extend((
            ('sizex', '>', 0),
            ('sizey', '>', 0),
            ('sizez', '>', 0)
        ))
        locations = request.env['stock.location'].search(domain)
        values = []
        for location in locations:
            values.append( {
                'posx': location['posx'],
                'posy': location['posy'],
                'posz': location['posz'],
                'sizex': location['sizex'],
                'sizey': location['sizey'],
                'sizez': location['sizez'],
                'opacity': self._opacity,
                'barcode': location['barcode'],
                'color': color,
                'usage': location['usage'],
                'warehouse': location['warehouse_id']['id']
                })

        return json.dumps(values)
