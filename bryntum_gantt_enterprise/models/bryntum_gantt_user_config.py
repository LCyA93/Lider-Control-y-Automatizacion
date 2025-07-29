from odoo import api, fields, models


class BryntumGanttUserConfig(models.Model):
    _name = "bryntum.gantt.user.config"
    _description = "Bryntum Gantt User Configuration"

    user_id = fields.Many2one("res.users", string="User", required=True)
    config_data = fields.Text("Configuration Data", required=True)

    @api.model
    def cron_cleanup_old_configs(self):
        user_ids = self.env["bryntum.gantt.user.config"].search([]).mapped("user_id.id")
        for user_id in user_ids:
            latest_config = self.search(
                [("user_id", "=", user_id)], order="create_date desc", limit=1
            )
            older_configs = self.search(
                [("user_id", "=", user_id), ("id", "!=", latest_config.id)]
            )
            if older_configs:
                older_configs.unlink()
