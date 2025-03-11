{
    "name": "Gantt View PRO",
    "summary": """
    Manage and visualise your projects with the fastest Gantt chart on the web.
    """,
    "author": "Bryntum AB",
    "website": "https://www.bryntum.com/forum/viewforum.php?f=58",
    # Categories can be used to filter modules in modules listing
    # for the full list
    "category": "Project",
    "version": "18.0.1.0.1",
    "price": 890.00,
    "currency": "EUR",
    "license": "Other proprietary",
    "support": "odoosupport@bryntum.com",
    "live_test_url": "https://odoo-gantt18ce.bryntum.com",
    # any module necessary for this one to work correctly
    "depends": ["base", "web", "project", "hr"],
    "images": [
        "images/banner.png",
        "images/main_screenshot.png",
        "images/reschedule.gif",
    ],
    # always loaded
    "data": [
        "security/ir.model.access.csv",
        "views/project_views.xml",
        "views/res_config_settings_views.xml",
    ],
    "application": True,
    # only loaded in demonstration mode
    "demo": [
        "demo/demo.xml",
    ],
    "assets": {
        "web.assets_backend": [
            "/bryntum_gantt/static/src/js/bryntum_gantt_controller.js",
            "/bryntum_gantt/static/src/js/bryntum_arch_parser.js",
            "/bryntum_gantt/static/src/**/*.xml",
            "/bryntum_gantt/static/src/js/bryntum_gantt_renderer.js",
            "/bryntum_gantt/static/src/js/view.js",
            "/bryntum_gantt/static/src/js/error_service.esm.js",
            "/bryntum_gantt/static/src/css/main.css",
        ]
    },
    "post_init_hook": "post_init_hook",
}
