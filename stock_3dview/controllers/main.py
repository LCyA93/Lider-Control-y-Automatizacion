# Copyright 2020 Openindustry.it SAS
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl.html).
from odoo import http, tools, _
from odoo.http import request
import json
import logging
import base64

_logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')


class ThreeDViewController(http.Controller):
    # color-index-v14
    _colors = {
            0:  '#FFFFFF', # white
            1:  '#F06050', # red
            2:  '#F4A460', # orange
            3:  '#F7CD1F', # yellow
            4:  '#6CC1ED', # light blue
            5:  '#814968', # dark purple
            6:  '#EB7E7F', # salmon pink
            7:  '#2C8397', # medium blue
            8:  '#475577', # dark blue
            9:  '#D6145F', # fushia
            10: '#30C381', # green
            11: '#9365B8'  # purple
        }


    @http.route('/stock_3dview/get_locations/all', type='json', auth="user", methods=['POST'])
    def get_locations_stock_warehouse(self, domain=[], **kwargs):
        #print("locations/all")
        return self.get_locations(domain, **kwargs)

    @http.route('/stock_3dview/get_locations/tagged', type='json', auth="user", methods=['POST'])
    def get_locations(self, domain=[], **kwargs):
        domain.extend((
            ('sizex', '>', 0),
            ('sizey', '>', 0),
            ('sizez', '>', 0)
        ))
        locations = request.env['stock.location'].search(domain)
        values = []
        for location in locations:
            tags = location.tag_ids
            if tags:
                color = self._colors[tags[0].color]
                opacity = tags[0].opacity
            else:
                color = '#8F8F8F'
                opacity = 500
            # shape
            shape_file = ''
            if location['shape_id']:
                shape_file = location['shape_id']['shape_file'].decode()
            # gltf
            gltf_file = ''
            if location['gltf_3d_model']:
                gltf_file = location['gltf_3d_model'].decode()
            values.append( {
                'posx': location['posx'],
                'posy': location['posy'],
                'posz': location['posz'],
                'sizex': location['sizex'],
                'sizey': location['sizey'],
                'sizez': location['sizez'],
                'rotx': location['rotx'],
                'roty': location['roty'],
                'rotz': location['rotz'],
                'scale_factor': location['scale_factor'],
                'geometry': shape_file,
                'gltf': gltf_file,
                'opacity': opacity,
                'barcode': location['barcode'],
                'color': color,
                'usage': location['usage'],
                'warehouse': location['warehouse_id']['id']
                })

        return json.dumps(values)

    @http.route('/stock_3dview/get_warehouses', type='json', auth="user", methods=['POST'])
    def get_warehouses(self, domain, **kwargs):
        # warehouse
        warehouses = request.env['stock.warehouse'].search([
            ('planimetry_image', '!=', False),
            ('spacex', '>', 0),
            ('spacey', '>', 0),
            ('spacez', '>', 0)
        ])

        values = []

        for wh in warehouses:
            data = {'id': wh.id, 'name': wh.name}
            # camera
            data['camera'] = {
                    'camx': wh.spacex / 2 or 1000,
                    'camy': wh.spacey / 2 or 1000,
                    'camz': wh.spacez * 8 or 1000,
                    'camfov': 50,
                }
            # planimetry
            data['ground'] = {
                    'sizex': wh.spacex,
                    'sizey': wh.spacey,
                    'sizez': wh.spacez,
                    'planimetry_image': wh.planimetry_image.decode()
                }
            values.append(data)

        return json.dumps(values)

    @http.route('/stock_3dview/get_legend/tagged', type='json', auth="user", methods=['POST'])
    def get_legend(self, domain, **kwargs):
        tags = request.env['stock.location.tag'].search([])
        values = []
        for tag in tags:
            values.append({
                'name': tag['name'],
                'color': self._colors[tag['color']],
                'opacity': tag['opacity'],
            })
        return json.dumps(values)

    '''
    @http.route('/3dview/get_legend/stock.warehouse', type='json', auth="user", methods=['POST'])
    def get_legend_stock_warehouse(self, domain, **kwargs):
        return self.get_legend(domain, **kwargs)
    '''

    @http.route('/stock_3dview/get_location_info', type='json', auth="user", methods=['POST'])
    def get_info(self, domain, **kwargs):
        locations = request.env['stock.location'].search(domain)
        sq = []
        for stock_quant in request.env['stock.quant'].search( [('location_id', '=', locations[0]['id'])] ):
            sq.append({
                'product_name': stock_quant.product_id.name,
                'product_qty': stock_quant.quantity,
                'product_code': stock_quant.product_id.default_code,
                'product_lot': stock_quant.lot_id.name,
            })
        return json.dumps({
                'barcode': locations[0]['barcode'],
                'id': locations[0]['id'],
                'camx': locations[0]['posx']+2000,
                'camy': locations[0]['posy']+1500,
                'camz': 1800,
                'complete_name': locations[0]['complete_name'],
                'specific_info': self.format_specific_info(sq),
            })
            
    def format_specific_info(self, sq):
        
        if len(sq)==0:
            return '<p>No product is stored here at the moment.</p>'
        
        html = '<ul style="padding-left: 16px;">'
        for p in sq:
            code = ''
            if p['product_code'] and p['product_lot']:
                code = p['product_code'] + ' lot:' + p['product_lot']
            elif p['product_code'] and not p['product_lot']:
                code = p['product_code']
            elif not p['product_code'] and p['product_lot']:
                code = 'lot:' + p['product_lot']
            name = p['product_name'] if p['product_name'] else ''
            html += '<li>' + code + ': ' + name + '(' + str(p['product_qty']) + ')</li>'
        
        html += '</ul>'
        
        return html
