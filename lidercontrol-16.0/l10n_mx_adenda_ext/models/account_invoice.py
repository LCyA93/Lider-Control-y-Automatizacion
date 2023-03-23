# -*- coding: utf-8 -*-

from odoo import fields, models, api, _
import xml.etree.ElementTree as gfg
import logging
import os
import io
_logger = logging.getLogger(__name__)
import base64
from odoo.exceptions import UserError
import json, xmltodict

class AccountInvoice(models.Model):
    _inherit = 'account.move'

    addenda_orderid = fields.Boolean(string='Addenda')
    addenda_id_agregada = fields.Boolean(string='Addenda agregada', readonly=True, default=False)
    orderid = fields.Char(string='Order Identification')

    def action_add_addenda_orderid(self):
        if not self.addenda_orderid:
            raise UserError(_('No está habilitado para generar la addenda.'))

        if not self.orderid:
            raise UserError(_('Falta especificar la identificación de la orden.'))

        if self.addenda_orderid and not self.addenda_id_agregada:
           xml_file = self._get_l10n_mx_edi_signed_edi_document()

           root = gfg.Element("Addenda")

           m1 = gfg.Element('requestForPayment')
           m1.set('orderIdentification', self.orderid)
           root.append (m1)

           _logger.info('adenda %s',  gfg.tostring(root).decode())
           if xml_file:
                _logger.info('pasa 01')
                try:
                    filedata = ''
                    # Read in the file
                    cfdi_data = base64.decodebytes(xml_file.attachment_id.with_context(bin_size=False).datas).decode()

                    # Replace the target string
                    filedata = cfdi_data.replace('</cfdi:Comprobante>', gfg.tostring(root).decode() +'</cfdi:Comprobante>')

                    # Write the file out again
                    text = base64.encodebytes(filedata.encode('utf-8'))
                    xml_file.attachment_id.write({
                      'datas': text,
                      'mimetype': 'application/xml'
                    })
                    self.addenda_id_agregada = True
                except Exception as e:
                    _logger.error(str(e))
                    pass

