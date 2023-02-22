from odoo import api, fields, models

class AccountInvoice(models.Model):
    _inherit = 'account.move'

    addenda = fields.Text(string='Addenda')

    @api.model
    def _get_facturae_values(self, move):
        """
        Sobreescribe el método _get_facturae_values() para agregar la addenda a la factura electrónica
        """
        res = super(AccountInvoice, self)._get_facturae_values(move)
        if move.addenda:
            res['addenda'] = move.addenda
        return res
