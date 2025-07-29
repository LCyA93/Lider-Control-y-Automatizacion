from odoo import fields, models

from ..tools.odoo_utils import get_odoo_major_version


def _get_field_selection():
    version = get_odoo_major_version()

    if version == "13.0":
        return fields.Selection(selection_add=[("BryntumGantt", "Bryntum Gantt")])

    return fields.Selection(
        selection_add=[("BryntumGantt", "Bryntum Gantt")],
        default="BryntumGantt",
        ondelete={"BryntumGantt": "set default"},
    )


class View(models.Model):
    _inherit = "ir.ui.view"
    type = _get_field_selection()

    def _get_view_info(self):
        return {"BryntumGantt": {"icon": "fa fa-th-list"}} | super()._get_view_info()


class ActWindowView(models.Model):
    _inherit = "ir.actions.act_window.view"
    view_mode = _get_field_selection()
