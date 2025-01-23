# -*- coding: utf-8 -*-

from odoo import fields, models, api, _
import xml.etree.ElementTree as gfg
import logging
import os
import io
_logger = logging.getLogger(__name__)
import base64
from odoo.exceptions import UserError

class AccountInvoice(models.Model):
    _inherit = 'account.move'

    addenda_orderid = fields.Boolean(string='Addenda')
    addenda_id_agregada = fields.Boolean(string='Addenda agregada', readonly=True, default=False)
    orderid = fields.Char(string='Order Identification')

    def _get_l10n_mx_edi_signed_edi_document(self):
        self.ensure_one()
        if self.l10n_mx_edi_cfdi_attachment_id:
            _logger.info("Signed document found: %s", self.l10n_mx_edi_cfdi_attachment_id.name)

            # Registra todos los documentos y sus atributos
            for document in self.edi_document_ids:
                _logger.info(
                    "Document ID: %s, Code: %s, Attachment: %s",
                    document.id,
                    document.edi_format_id.code,
                    document.sudo().attachment_id.name if document.sudo().attachment_id else "No attachment"
                )

            # Aplica el filtro Simple
            signed_document = self.l10n_mx_edi_document_ids.filtered(lambda document: document.sudo().attachment_id)

            # Aplica el filtro Simple Complejo No Funciona
            # signed_document = self.edi_document_ids.filtered(lambda document: document.edi_format_id.code in ['cfdi_3_3', 'cfdi_4_0'] and document.sudo().attachment_id)

            if signed_document:
                _logger.info("Signed document found for record: %s", self.id)
                return signed_document
            else:
                _logger.warning("No signed document passed the filter for record: %s", self.id)
        else:
            _logger.warning("No CFDI attachment ID found for record: %s", self.id)
        return None

    def action_add_addenda_orderid(self):
        if not self.addenda_orderid:
            raise UserError(_('No está habilitado para generar la addenda.'))

        if not self.orderid:
            raise UserError(_('Falta especificar la identificación de la orden.'))

        if self.addenda_orderid and not self.addenda_id_agregada:
            xml_file = self._get_l10n_mx_edi_signed_edi_document()
            if not xml_file:
                _logger.warning("No se encontró el documento firmado.")
                return
            else:
                _logger.info("Documento firmado encontrado: %s", xml_file.attachment_id.name)

            root = gfg.Element("cfdi:Addenda")

            m1 = gfg.Element('requestForPayment')
            m1.set('orderIdentification', self.orderid)
            root.append(m1)

            # _logger.info('adenda %s',  gfg.tostring(root).decode())
            if xml_file:
                # _logger.info('pasa 01')
                try:
                    filedata = ''
                    # Read in the file
                    cfdi_data = base64.decodebytes(xml_file.attachment_id.with_context(bin_size=False).datas).decode()

                    # Replace the target string
                    filedata = cfdi_data.replace('</cfdi:Comprobante>',
                                                 gfg.tostring(root).decode() + '</cfdi:Comprobante>')

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
