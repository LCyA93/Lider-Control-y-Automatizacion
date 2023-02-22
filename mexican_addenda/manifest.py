# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.
{
    'name': 'Mexican Addenda',
    'category': 'Accounting/Invoicing',
    'author': 'Kevin Hernandez',
    'description': """ 
        'Adds support for Mexican addenda in invoices',
    """,
    'version': '1.0',
    
    'depends': ['account'],
    
    'data': [
        'views/account_invoice_views.xml',
        'views/report_invoice.xml',
    ],
    'installable': True,
    'auto_install': False,
}}