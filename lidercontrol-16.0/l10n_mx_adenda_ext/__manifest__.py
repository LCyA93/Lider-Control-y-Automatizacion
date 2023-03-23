# -*- coding: utf-8 -*-
##############################################################################
#                 @author IT Admin
#
##############################################################################

{
    'name': 'Adenda Order ID',
    'version': '16.01',
    'description': ''' Agrega campos para agregar una addenda.
    ''',
    'category': 'Accounting',
    'author': 'IT Admin',
    'website': 'www.itadmin.com.mx',
    'depends': [
        'sale',
    ],
    'data': [
        'views/account_invoice_view.xml',
	],
    'application': False,
    'installable': True,
}
