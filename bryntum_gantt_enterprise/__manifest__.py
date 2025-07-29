{
    "name": "Gantt View PRO (Enterprise)",
    "summary": """
    Manage and visualise your projects with the fastest Gantt chart on the web.
    """,
    "author": "Bryntum AB",
    "website": "https://www.bryntum.com/forum/viewforum.php?f=58",
    # Categories can be used to filter modules in modules listing
    # for the full list
    "category": "Project",
    "version": "18.0.1.0.5",
    "price": 890.00,
    "currency": "EUR",
    "license": "Other proprietary",
    "support": "odoosupport@bryntum.com",
    "live_test_url": "https://odoo-gantt17.bryntum.com",
    # any module necessary for this one to work correctly
    "depends": ["project_enterprise", "hr"],
    "images": [
        "images/banner.png",
        "images/main_screenshot.png",
        "images/reschedule.gif",
    ],
    # always loaded
    "data": [
        "security/ir.model.access.csv",
        "security/res_groups.xml",
        "data/ir_cron_data.xml",
        "views/project_views.xml",
        "views/res_config_settings_views.xml",
        "views/res_users.xml",
    ],
    "application": True,
    # only loaded in demonstration mode
    "demo": [
        "demo/demo.xml",
    ],
    "assets": {
        "web.assets_backend": [
            "/bryntum_gantt_enterprise/static/src/js/bryntum_gantt_controller.js",
            "/bryntum_gantt_enterprise/static/src/js/bryntum_arch_parser.js",
            "/bryntum_gantt_enterprise/static/src/**/*.xml",
            "/bryntum_gantt_enterprise/static/src/js/bryntum_gantt_renderer.js",
            "/bryntum_gantt_enterprise/static/src/js/view.js",
            "/bryntum_gantt_enterprise/static/src/js/error_service.esm.js",
            "/bryntum_gantt_enterprise/static/src/css/main.css",
        ]
    },
    "post_init_hook": "post_init_hook",
}
