# -*- coding: utf-8 -*-
# Copyright (C) Softhealer Technologies Pvt. Ltd.

{
    'name': "Power BI Odoo Connector | Power BI Dashboard | Power BI Odoo Integration",
    'author': 'Softhealer Technologies',
    'website': 'https://www.softhealer.com',
    'support': 'support@softhealer.com',
    'category': 'connector',
    'license': 'OPL-1',
    'depends': ['base', 'web', 'rpc', 'sh_integration_base'],
    'version': '19.0.6.0.0',
    'summary': "Power BI Odoo Connector Odoo Power BI Integration Microsoft Power BI Connector For Odoo Odoo ERP Power BI Odoo to Power BI Sync Odoo Data Visualization Power BI Connector Odoo Business Intelligence Real-time Odoo Reports Odoo Interactive Dashboards Power BI for Odoo Odoo Analytics Tool Odoo Data Reporting Power BI Odoo Integration Tool Odoo Power BI Scheduler Data-driven Decisions Odoo Odoo to Power BI Connector Power BI Connector allows integration of Odoo with Microsoft Power BI ERP and the world of Microsoft data visualization to Power BI data for informed decision-making Power BI Sync Odoo Power BI Data Power BI Sync powerbi odoo integration powerbi odoo connector power bi desktop setups powerbi desktop setups odoo powerbi integration odoo power bi connector odoo powerbi connector Powerbi Dashboard Power bi Dashboard Power bi reports Powerbi reports big data Data studio microsoft powerbi Odoo to Power BI Desktop Connector powerbi service power bi service microsoft powerbi platforms Odoo Microsoft Power BI integration Power BI dashboards in Odoo Real-time Power BI sync Power BI workspace management Power BI dataset export Microsoft Fabric support Eventhouse & KQL integration Embedded BI reports BI analytics Odoo Power BI security & tokens Data visualization Odoo Automatic Power BI export BI reporting tools for Odoo Powerbi connector Powerbi dashboard Power bi dashboard Power bi reports big data Data studio data analytics microsoft power bi Odoo Power BI Dashboard Odoo with Power BI Desktop advanced Odoo Power BI Connector sync real-time Odoo data Sales Inventory HR Accounting CRM powerful analytics data extraction from Odoo to Power BI Odoo to Power BI Integration analyze KPIs Odoo Power BI Desktop Connector Odoo Power BI Dashboard solution Softhealer Analytics & BI Integrations",
    'description': """Connect Odoo with Microsoft Power BI. This connector synchronizes Odoo ERP data with Power BI so users can build interactive reports, schedule updates, and make informed business decisions.""",
    'data': [
        'security/sh_powerbi_groups.xml',
        'security/ir.model.access.csv',
        'security/sh_powerbi_rules.xml',
        'views/sh_powerbi_dashboard_views.xml',
        'views/sh_powerbi_log_views.xml',
        'views/sh_powerbi_model_access_views.xml',
        'views/sh_powerbi_push_config_views.xml',
        'views/sh_powerbi_schema_diff_wizard_views.xml',
        'views/sh_powerbi_push_queue_views.xml',
        # Views (Wizards)
        'wizard/sh_powerbi_fabric_item_wizard_views.xml',
        'wizard/sh_powerbi_report_preview_wizard_views.xml',

        # Views (Models)
        'views/res_config_settings.xml',
        'views/sh_powerbi_fabric_views.xml',
        'views/sh_powerbi_rest_asset_views.xml',
        'views/sh_powerbi_governance_views.xml',
        'views/sh_powerbi_embedded_report_views.xml',
        'data/sh_powerbi_data.xml',
        'data/sh_integration_connector_data.xml',
        'data/sh_integration_entity_data.xml',
        'data/sh_integration_menu_data.xml',
    ],
    'assets': {
        'web.assets_backend': [
            'sh_power_bi_connector/static/src/dashboard/sh_powerbi_dashboard.js',
            'sh_power_bi_connector/static/src/dashboard/sh_powerbi_dashboard.xml',
            'sh_power_bi_connector/static/src/dashboard/sh_powerbi_dashboard.scss',
        ],
    },
    'installable': True,
    'auto_install': False,
    'application': True,
    'images': ['static/description/Power BI Odoo Connector New.gif'],
    'price': 151,
    'currency': 'EUR',
}
