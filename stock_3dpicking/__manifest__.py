# Copyright 2022 Openindustry.it SAS
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl.html).
{
    'name': 'Stock 3d Locate per Picking',
    'version': '15.0.3.0.0',
    'license': 'AGPL-3',
    'summary': """
        From picking and batch picking the Locate button open the 3D view
        to show the locations containing the products in the pickings
    """,
    'description': """
        Stock 3D locate products in 3D view per picking and batch picking
    """,
    'author': 'Andrea Piovesana, Loris Tissino, Davide Corio, Matteo Boscolo',
    'support': 'andrea.m.piovesana@gmail.com',
    'website': 'https://openindustry.it',
    'category': 'Warehouse',
    'depends': [
        'stock_3dview',
        'stock_picking_batch',
    ],
    'data': [
        'views/stock_view.xml',
    ],
    'images': [
        'images/stock_3dpicking.png',
    ],
    'installable': True,
    'application': False,
    'auto_install': False,
    'price': 100.00,
    'currency': 'EUR',
}
