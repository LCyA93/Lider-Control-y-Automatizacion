# Copyright 2022 Openindustry.it SAS
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl.html).
{
    "name": "Stock 3D View",
    "version": "15.0.10.0.0",
    "license": "AGPL-3",
    "summary": """
        Stock 3D View enable to view pan and zoom multi warehouse locations in a 3d space
    """,
    "description": """
        Stock 3D View Multi Warehouse
    """,
    "category": "Inventory",
    "company": "https://openindustry.it",
    "author": "Openindustry.it,Tissino.it",
    "maintainers": ["andreampiovesana"],
    "support": "andrea.m.piovesana@gmail.com",
    "website": "https://openindustry.it",
    "depends": [
        "stock_3dbase",
        "web",
    ],
    "data": [
        "views/stock_view.xml",
    ],
    "assets": {
        "web.assets_backend": [
            "stock_3dview/static/src/css/style.css",
            "stock_3dview/static/src/js/libs/three.min.js",
            "stock_3dview/static/src/js/libs/stats.min.js",
            "stock_3dview/static/src/js/libs/dat.gui.min.js",
            "stock_3dview/static/src/js/libs/OrbitControls.js",
            "stock_3dview/static/src/js/libs/Detector.js",
            "stock_3dview/static/src/js/libs/GLTFLoader.js",
            "stock_3dview/static/src/js/controller.js",
            "stock_3dview/static/src/js/renderer.js",
            "stock_3dview/static/src/js/model.js",
            "stock_3dview/static/src/js/threedview.js",
            "stock_3dview/static/src/js/base_3dview_controller.js",
            "stock_3dview/static/src/js/base_3dview_renderer.js",
            "stock_3dview/static/src/js/base_3dview_model.js",
            "stock_3dview/static/src/js/owl_3dview_renderer.js",
        ],
        "web.assets_qweb": [
            "stock_3dview/static/src/xml/templates.xml",
            "stock_3dview/static/src/xml/owl_3dview_renderer_view.xml",
        ],
    },
    "images": [
        "images/stock_3dview.png",
    ],
    "installable": True,
    "application": False,
    "auto_install": False,
    "price": 150.00,
    "currency": "EUR",
}
