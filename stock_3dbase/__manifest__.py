# © 2020 OpenIndustry.it
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).
{
    "name": "Base Stock 3D Location",
    "version": "15.0.1.0.0",
    "license": "AGPL-3",
    "summary": """
        Define xyz coordinates for location position and location dimension in mm
        Define xyz rotation and schale factor for shape_id
        Set tags to locations to filter and identify with color in 3D view
        Set Warehouse image for the plant and define xyz dimension of the site.
    """,
    "description": """
        Base stock 3d Location data to easy filter by warehouse
    """,
    "category": "Inventory",
    "company": "https://openindustry.it",
    "author": "Openindustry.it,Tissino.it",
    "maintainers": ["andreampiovesana"],
    "support": "andrea.m.piovesana@gmail.com",
    "website": "https://openindustry.it",
    "depends": [
        "stock",
        "web_widget_model_viewer_15",
    ],
    "data": [
        "security/ir.model.access.csv",
        "views/stock_views.xml",
        "data/location_tag_data.xml",
        "data/config_settings_data.xml",
    ],
    "images": [
        "images/stock_3dbase.png",
    ],
    "installable": True,
    "application": False,
    "auto_install": False,
    "price": 50.00,
    "currency": "EUR",
}
