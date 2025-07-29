# Copyright 2019 Sunflower IT <http://sunflowerweb.nl>
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl.html).


def assign_default_groups(env):
    group_save_own_settings = env.ref(
        "bryntum_gantt_enterprise.group_save_own_settings"
    )
    group_set_state_for_all = env.ref(
        "bryntum_gantt_enterprise.group_set_state_for_all"
    )

    all_users = env["res.users"].search([])
    for user in all_users:
        user.groups_id |= group_save_own_settings
        user.groups_id |= group_set_state_for_all


def set_default_bryntum_config_parameter(env):
    config_param = env["ir.config_parameter"]

    if not config_param.get_param("bryntum.bryntum_enable_user_config_edit"):
        config_param.set_param("bryntum.bryntum_enable_user_config_edit", True)


def post_init_hook(env):
    user_demo = env.ref("base.user_demo", raise_if_not_found=False)
    if user_demo:
        user_demo.write(
            {"action_id": env.ref("bryntum_gantt_enterprise.open_gantt_pro").id}
        )
    assign_default_groups(env)
    set_default_bryntum_config_parameter(env)
