from odoo import _, fields, models
from odoo.exceptions import AccessError, UserError


class ResUsers(models.Model):
    _inherit = "res.users"

    bryntum_user_config = fields.Text(
        string="Bryntum Gantt Config",
        compute="_compute_bryntum_user_config",
        readonly=True,
    )

    def _compute_bryntum_user_config(self):
        for user in self:
            latest_config = self.env["bryntum.gantt.user.config"].search(
                [("user_id", "=", user.id)], order="create_date desc", limit=1
            )
            user.bryntum_user_config = (
                latest_config.config_data if latest_config else "{}"
            )

    def action_copy_settings_to_all(self):
        self.ensure_one()
        if not self.env.user.has_group(
            "bryntum_gantt_enterprise.group_set_state_for_all"
        ):
            raise AccessError(
                _("You do not have permission to copy settings to all users.")
            )
        current_user_config = self.env["bryntum.gantt.user.config"].search(
            [("user_id", "=", self.env.user.id)], order="create_date desc", limit=1
        )
        if not current_user_config:
            raise UserError(_("No configuration found to copy."))
        all_users = self.env["res.users"].search([("id", "!=", self.env.user.id)])
        for user in all_users:
            self.env["bryntum.gantt.user.config"].create(
                {"user_id": user.id, "config_data": current_user_config.config_data}
            )
        return True
