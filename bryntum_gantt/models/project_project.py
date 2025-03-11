from datetime import datetime

from odoo import api, fields, models

from ..tools.date_utils import get_gantt_date


class ProjectProject(models.Model):
    _inherit = "project.project"

    project_start_date = fields.Datetime(default=datetime.today())

    bryntum_auto_scheduling = fields.Boolean(
        "Auto scheduling", compute="_compute_bryntum_settings"
    )
    bryntum_user_assignment = fields.Boolean(
        "User assignment", compute="_compute_bryntum_settings"
    )

    def _compute_bryntum_settings(self):
        res = self.get_bryntum_values()
        self.bryntum_user_assignment = res.get("bryntum_user_assignment")
        self.bryntum_auto_scheduling = res.get("bryntum_auto_scheduling")

    @api.returns("self", lambda value: value.id)
    def copy(self, default=None):
        self = self.with_context(task_mapping_keys=dict())
        project = super(ProjectProject, self).copy(default)
        task_mapping = self.env.context.get("task_mapping_keys")
        tasks = self.tasks
        task_linked_env = self.env["project.task.linked"]
        task_segments_env = self.env["project.task.segment"]

        for task in tasks:
            for dependency in task.linked_ids:
                if dependency.dep_active:
                    from_id = task_mapping.get(dependency.from_id.id, None)
                    to_id = task_mapping.get(dependency.to_id.id, None)
                    if from_id is not None and to_id is not None:
                        task_linked_env.create(
                            {
                                "from_id": from_id,
                                "to_id": to_id,
                                "lag": dependency.lag,
                                "lag_unit": dependency.lag_unit,
                                "dep_active": True,
                                "type": dependency.type,
                            }
                        )

            for segment in task.segments:
                task_id = task_mapping.get(task.id, None)
                if task_id is not None:
                    task_segments_env.create(
                        {
                            "task": task_id,
                            "name": segment.name,
                            "planned_date_begin": segment.planned_date_begin,
                            "planned_date_end": segment.planned_date_end,
                        }
                    )

        return project

    def get_calendars(self):

        calendar_env = self.env["resource.calendar"]
        calendars = calendar_env.search([])
        calendars_objs = [
            {
                "id": str(calendar.id),
                "name": calendar.name,
                "company_id": calendar.company_id.id,
                "active": True,
                "hours_per_day": calendar.hours_per_day,
                "working_intervals": [
                    {
                        "name": interval.name,
                        "day_period": interval.day_period,
                        "day_of_week": interval.dayofweek,
                        "resource_id": interval.resource_id.id,
                        "resource_name": interval.resource_id.name,
                        "hour_from": interval.hour_from,
                        "hour_to": interval.hour_to,
                        "date_from": interval.date_from,
                        "date_to": interval.date_to,
                    }
                    for interval in calendar.attendance_ids
                ],
                "leave_intervals": [
                    {
                        "name": interval.name,
                        "time_type": interval.time_type,
                        "resource_id": interval.resource_id.id,
                        "resource_name": interval.resource_id.name,
                        "date_from": get_gantt_date(interval.date_from),
                        "date_to": get_gantt_date(interval.date_to),
                    }
                    for interval in calendar.leave_ids
                ],
            }
            for calendar in calendars
        ]
        return calendars_objs

    def get_default_calendar(self):
        return [
            {
                "id": "general",
                "name": "General",
                "intervals": [],
                "expanded": True,
                "children": [
                    {
                        "id": "business",
                        "name": "Business",
                        "intervals": [
                            {
                                "recurrentStartDate": "every weekday at 12:00",
                                "recurrentEndDate": "every weekday at 13:00",
                                "isWorking": False,
                            },
                            {
                                "recurrentStartDate": "every weekday at 17:00",
                                "recurrentEndDate": "every weekday at 08:00",
                                "isWorking": False,
                            },
                        ],
                    },
                    {
                        "id": "night",
                        "name": "Night shift",
                        "intervals": [
                            {
                                "recurrentStartDate": "every weekday at 6:00",
                                "recurrentEndDate": "every weekday at 22:00",
                                "isWorking": False,
                            }
                        ],
                    },
                ],
            }
        ]

    @api.model
    def get_lib_version(self):
        module = self.env.ref("base.module_bryntum_gantt", raise_if_not_found=False)
        if module and module.latest_version:
            return "v" + module.latest_version
        return "v0"

    @api.model
    def get_bryntum_values(self):

        lang_env = self.env["res.lang"]
        lang = self.env.user.lang
        lang_rec = lang_env.search([("code", "=", lang)])

        su = self.env["ir.config_parameter"].sudo()

        res = {
            "lib_version": self.get_lib_version(),
            "lang": lang,
            "week_start": lang_rec.week_start,
            "bryntum_auto_scheduling": su.get_param("bryntum.auto_scheduling")
            == "True",
            "bryntum_user_assignment": su.get_param("bryntum.user_assignment")
            == "True",
            "bryntum_readonly_project": su.get_param("bryntum.readonly_projects")
            == "True",
            "bryntum_save_wbs": su.get_param("bryntum.save_wbs") == "True",
            "bryntum_gantt_config": su.get_param("bryntum.gantt_config") or "{}",
            "bryntum_copy_dependencies": su.get_param("bryntum.copy_dependencies"),
        }
        return res
