# -*- coding: utf-8 -*-
# Copyright (C) Softhealer Technologies Pvt. Ltd.
{
     "name": "Base Integration",
    "author": "Softhealer Technologies",
    "website": "https://www.softhealer.com",
    "support": "support@softhealer.com",
    "version": "19.0.2.0.3",
    "license": "OPL-1",
    "category": "Extra Tools",
    "summary": " Base module for Integration Base Integration Odoo",
    "description": """Base Integration module is a base module for below modules.""",
    "depends": ["base","mail"],
    "data": [
        # Security
        'data/sh_api_group_config.xml',
        'security/ir.model.access.csv',

        # DATA
        
        'data/sh_mass_action_queue.xml',
        'data/sh_ir_log_sequence.xml',

        # VIEW'S
        'views/sh_api_scope_view.xml',
        'views/sh_base_config.xml',
        # 'views/sh_lead_log.xml',
        'views/sh_queue_view.xml',
        'views/sh_integration_log_view.xml',

        # MENU (must load before overview so sh_base_config_root exists)
        'views/sh_integration_menu.xml',
        'views/sh_integration_overview_views.xml',
        'views/sh_integration_connector_views.xml',
        'views/sh_integration_entity_views.xml',
    ],
    
    "assets": {
        "web.assets_backend": [
            "sh_integration_base/static/src/css/sh_integration_dashboard.css",
            ("include", "web.chartjs_lib"),
            "sh_integration_base/static/src/xml/sh_integration_dashboard.xml",
            "sh_integration_base/static/src/js/sh_integration_dashboard.js",
        ],
    },
    "auto_install": False,
    "installable": True,
    "application": True,
    "images": ["static/description/background.png", ],
    "price": 18,
    "currency": "EUR"
}
