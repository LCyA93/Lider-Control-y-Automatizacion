# -*- coding: utf-8 -*-
##############################################################################
#                 @author IT Admin
#
##############################################################################

{
    'name': 'Addenda Order ID',
    'version': '17.01',
    'description': ''' Agrega campos para añadir una addenda.
    ''',
    'category': 'Accounting',
    'author': 'Kevin Hernández',
    'website': 'lidercontrol.com.mx',
    'depends': [
        'sale',
    ],
    'data': [
        'views/account_invoice_view.xml',
	],
    'application': False,
    'installable': True,
}
