# -*- coding: utf-8 -*-
{
    'name': "Stock 3D View",
    'version': '1.0',
    'category': 'Warehouse',
    'summary': """Virtual 3D Visualization of warehouses and Locations""",
    'description': """This module innovative addition to the inventory and 
     warehouse management module, enhancing the traditional methods of tracking 
     stock and warehouse operations. Leveraging advanced visualization 
     technology, this app provides users with an immersive and dynamic 
     three-dimensional representation of their warehouses, inventory items, and 
     stock movements.""",
    'author': 'Cloud Open Technologies/K8 Team',
    'depends': ['stock', 'web'],
    'data': [
        'views/stock_location_views.xml',
    ],
    'assets': {
        'web.assets_backend': [
            'stock_3d_custom_view/static/src/js/form_3d_view.js',
            'stock_3d_custom_view/static/src/js/listview_3d.js',
            'stock_3d_custom_view/static/src/css/3d_view.scss',
            'https://cdnjs.cloudflare.com/ajax/libs/three.js/r128/three.js',
            'https://cdnjs.cloudflare.com/ajax/libs/three.js/r128/three.min.js',
            "https://cdn.jsdelivr.net/npm/three@0.122.0/examples/js/controls/OrbitControls.min.js",
            'stock_3d_custom_view/static/src/xml/stock_location_3d_templates.xml',
            'stock_3d_custom_view/static/src/xml/stock_location_breadcrumb_templates.xml',
            'stock_3d_custom_view/static/src/xml/stock_location_modal_templates.xml',
        ],
    },
    'images': [
        'static/description/assets/screenshots/3.png',
    ],
    'license': 'LGPL-3',
    'installable': True,
    'auto_install': False,
    'application': False,
}
