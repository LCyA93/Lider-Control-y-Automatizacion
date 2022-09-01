# Copyright 2021 Openindustry.it SAS
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl.html).
from odoo import models, fields, exceptions, api, _
from odoo.exceptions import Warning, UserError
from datetime import date, datetime
import logging
import csv
import base64
import io

_logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

class StockLocationImportWizard(models.TransientModel):
    _name = "stock.location.import.wizard"

    file = fields.Binary('File')
    log = []

    def import_csv(self):
        try:
            file_to_import = base64.b64decode(self.file)
            data_file = io.StringIO(file_to_import.decode("utf-8"))
            data_file.seek(0)
            reader = csv.reader(data_file, delimiter=';')
            lines = []
            # header
            for index, row in enumerate(reader):
                headers = row
                break
            # parse
            parsed_data_lines = csv.DictReader(data_file, fieldnames=headers, delimiter=';')
            # data
            for index, row in enumerate(parsed_data_lines):
                values = {
                    'USAGE': str(row['usage']).strip(),
                    'BARCODE': str(row['barcode']).strip(),
                    'POSX': str(row['posx']).strip(),
                    'POSY': str(row['posy']).strip(),
                    'POSZ': str(row['posz']).strip(),
                    'NAME': str(row['name']).strip(),
                    'SIZEX': str(row['sizex']).strip(),
                    'SIZEY': str(row['sizey']).strip(),
                    'SIZEZ': str(row['sizez']).strip(),
                    'PARENT': str(row['parent']).strip(),
                }

                lines.append(values)

            self.import_data(lines)

        except Exception as e:
            raise UserError(e)

    def load_locations(self, lines):
        stk = self.env['stock.location']
        locations = {}
        for index, row in enumerate(lines):
            # location
            barcode = row['BARCODE'].strip()
            location_obj = stk.search([('barcode', '=', barcode)], limit=1)
            # parent location
            parent = row['PARENT']
            parent_obj = stk.search([('barcode', '=', parent)], limit=1)
            if not parent_obj:
                continue
            # description
            name = row['NAME']
            # usage
            usage = row['USAGE']
            # x y z
            posx = row['POSX']
            posy = row['POSY']
            posz = row['POSZ']
            # x y z
            sizex = row['SIZEX']
            sizey = row['SIZEY']
            sizez = row['SIZEZ']

            values = {}
            if not location_obj:
                values.update({'barcode': barcode})
                values.update({'name': name})
            if not location_obj or location_obj.location_id != parent_obj.id:
                values.update({'location_id': parent_obj.id})

            if not location_obj or location_obj.posx != posx:
                values.update({'posx': posx})
            if not location_obj or location_obj.posy != posy:
                values.update({'posy': posy})
            if not location_obj or location_obj.posz != posz:
                values.update({'posz': posz})

            if not location_obj or location_obj.sizex != sizex:
                values.update({'sizex': sizex})
            if not location_obj or location_obj.sizey != sizey:
                values.update({'sizey': sizey})
            if not location_obj or location_obj.sizez != sizez:
                values.update({'sizez': sizez})

            if not values:
                continue

            if not location_obj:
                location_obj = stk.with_context(tracking_disable=True).create(values)
            else:
                stk.with_context(tracking_disable=True).write(values)

            locations[barcode] = location_obj.id

        return locations


    def import_data(self, lines):
        #self.log = []

        locations = self.load_locations(lines)

        #if self.log:
        #    raise Exception(*self.log)
