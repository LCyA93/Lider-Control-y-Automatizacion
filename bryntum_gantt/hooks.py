# Copyright 2019 Sunflower IT <http://sunflowerweb.nl>
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl.html).
from odoo import SUPERUSER_ID, api


def post_init_hook(env):
    env = api.Environment(env.cr, SUPERUSER_ID, {})
    user_demo = env.ref("base.user_demo", raise_if_not_found=False)
    # if in demo DB, on install put demo user action_id (default home action) as gantt.
    if user_demo:
        user_demo.write({"action_id": env.ref("bryntum_gantt.open_gantt_pro").id})
