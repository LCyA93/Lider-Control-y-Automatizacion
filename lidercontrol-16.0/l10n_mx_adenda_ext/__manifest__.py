# -*- coding: utf-8 -*-
##############################################################################
#                 @author Kevin Hernández Velázquez
#
##############################################################################

{
    'name': 'Addenda Order ID',
    'version': '17.01',
    'description': ''' Agrega campos para agregar una addenda.
    ''',
    'category': 'Accounting',
    'author': 'Kevin Hernández',
    'website': 'www.lidercontrol.com.mx',
    'depends': [
        'sale',
    ],
    'data': [
        'views/account_invoice_view.xml',
	],
    'application': False,
    'installable': True,
}
