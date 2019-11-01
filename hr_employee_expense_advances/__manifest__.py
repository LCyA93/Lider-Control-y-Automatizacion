
# -*- coding: utf-8 -*-
###############################################################################
#
#    Odoo, Open Source Management Solution
#
#    Copyright (c) All rights reserved:
#        (c) 2015  TM_FULLNAME
#
#    This program is free software: you can redistribute it and/or modify
#    it under the terms of the GNU Affero General Public License as
#    published by the Free Software Foundation, either version 3 of the
#    License, or (at your option) any later version.
#
#    This program is distributed in the hope that it will be useful,
#    but WITHOUT ANY WARRANTY; without even the implied warranty of
#    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
#    GNU Affero General Public License for more details.
#
#    You should have received a copy of the GNU Affero General Public License
#    along with this program.  If not, see http://www.gnu.org/licenses
#
###############################################################################
{
    'name': 'HR Employee Expense Advance',
    'version': '12',
    'category': 'General',
	'summary': 'HR Employee Expense Advance',
	'author': 'Ananthu krishna',
    'website': 'http://www.codersfort.com',
    "images": ['images/expense_advance_request.png'],
    'description': """HR Employee Expense Advance""",
    'depends': ['base','hr_expense','account','mail'],
    'data': [
        'security/user_groups.xml',
        'security/ir.model.access.csv',
        'data/hr_expense_data.xml',
        'views/hr_expense_advances_views.xml',
    ],
    'license': 'AGPL-3',
    'demo': [],
    'installable': True,
    'application': True,
    'auto_install': False,
    'qweb': [],
}
