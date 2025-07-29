import dateutil.parser

from odoo import api, fields, models


def check_gantt_date(value):
    if isinstance(value, str):
        return dateutil.parser.parse(value, ignoretz=True)
    else:
        return value


class ProjectTask(models.Model):
    _inherit = "project.task"  # pylint: disable=R8180

    duration = fields.Integer(string="Duration (days)", default=-1)
    duration_unit = fields.Char(default="d")

    percent_done = fields.Integer(string="Done %", default=0)
    parent_index = fields.Integer(default=0)

    assigned_ids = fields.Many2many(
        "res.users", relation="assigned_resources", string="Assigned resources"
    )
    assigned_resources = fields.One2many(
        "project.task.assignment", inverse_name="task", string="Assignments"
    )
    baselines = fields.One2many("project.task.baseline", inverse_name="task")
    segments = fields.One2many("project.task.segment", inverse_name="task")

    effort = fields.Integer(string="Effort (hours)", default=0)

    gantt_calendar_flex = fields.Char(string="Gantt Calendar Ids")
    linked_ids = fields.One2many(
        "project.task.linked", inverse_name="to_id", string="Linked"
    )
    scheduling_mode = fields.Selection(
        [
            ("Normal", "Normal"),
            ("FixedDuration", "Fixed Duration"),
            ("FixedEffort", "Fixed Effort"),
            ("FixedUnits", "Fixed Units"),
        ],
    )
    constraint_type = fields.Selection(
        [
            ("assoonaspossible", "As soon as possible"),
            ("aslateaspossible", "As late as possible"),
            ("muststarton", "Must start on"),
            ("mustfinishon", "Must finish on"),
            ("startnoearlierthan", "Start no earlier than"),
            ("startnolaterthan", "Start no later than"),
            ("finishnoearlierthan", "Finish no earlier than"),
            ("finishnolaterthan", "Finish no later than"),
        ],
    )
    constraint_date = fields.Datetime()
    effort_driven = fields.Boolean(default=False)
    manually_scheduled = fields.Boolean(default=False)
    bryntum_rollup = fields.Boolean(string="Rollup", default=False)
    wbs_value = fields.Char(string="WBS Value")

    employee_ids = fields.Many2many(
        "hr.employee",
        string="Employees",
        compute="_compute_employee_ids",
        inverse="_inverse_employee_ids",
        search="_search_employee_ids",
        store=False,
        help="Employees assigned to this task (Bryntum Gantt field)",
    )
    replace_user_by_employee = fields.Boolean(compute="_compute_has_view_users_group")
    inactive = fields.Boolean(default=False)
    show_in_timeline = fields.Boolean(default=True)
    milestone = fields.Boolean(default=False)

    @api.depends("assigned_resources")
    def _compute_employee_ids(self):
        for this in self:
            resources = this.assigned_resources.mapped("resource_base")
            employees = self.env["hr.employee"].search(
                [("resource_id", "in", resources.ids)]
            )
            this.employee_ids = employees

    def _inverse_employee_ids(self):
        for this in self:
            new_resources_emp = this.employee_ids.mapped("resource_id")
            old_resources_all = this.assigned_resources.mapped("resource_base")
            old_resources_emp = (
                self.env["hr.employee"]
                .search([("resource_id", "in", old_resources_all.ids)])
                .mapped("resource_id")
            )
            res_to_add = set(new_resources_emp.ids).difference(
                set(old_resources_emp.ids)
            )
            res_to_unlink = set(old_resources_emp.ids).difference(
                set(new_resources_emp.ids)
            )
            ass_to_delete = this.assigned_resources.filtered(
                lambda a: a.resource_base.id in res_to_unlink
            ).ids
            this.assigned_resources = [(2, _id) for _id in list(ass_to_delete)] + [
                (0, False, {"units": 100, "resource_base": _id})
                for _id in list(res_to_add)
            ]

    @api.model
    def _search_employee_ids(self, operator, value):
        employees = self.env["hr.employee"].search([("name", operator, value)])
        resources = employees.mapped("resource_id")
        return [("assigned_resources.resource_base", "in", resources.ids)]

    @api.returns("self", lambda value: value.id)
    def copy(self, default=None):
        task_copy = self.env["project.task"]
        for this in self:
            new_task = super(ProjectTask, this).copy(default)
            task_copy += new_task
            task_mapping = this.env.context.get("task_mapping_keys", {})
            task_mapping[this.id] = new_task.id
        return task_copy

    @api.onchange("constraint_type")
    def _onchange_constraint_type(self):
        if not self.constraint_type:
            self.constraint_date = None
        else:
            self.constraint_date = {
                "assoonaspossible": self.planned_date_begin,
                "aslateaspossible": self.date_deadline,
                "muststarton": self.planned_date_begin,
                "mustfinishon": self.date_deadline,
                "startnoearlierthan": self.planned_date_begin,
                "startnolaterthan": self.planned_date_begin,
                "finishnoearlierthan": self.date_deadline,
                "finishnolaterthan": self.date_deadline,
            }[self.constraint_type]

    def _get_replace_user_by_employee_value(self):
        su = self.env["ir.config_parameter"].sudo()
        return su.get_param("bryntum.replace_user_by_employee_in_views")

    def _compute_has_view_users_group(self):
        self.env["ir.config_parameter"].sudo()
        self.replace_user_by_employee = self._get_replace_user_by_employee_value()

    @api.model
    def _get_view(self, view_id=None, view_type="form", **options):
        arch, view = super()._get_view(view_id, view_type, **options)
        # conditionally hide user_ids, it is impossible to hide the column conditionally in a
        # non-form treeview.
        if view_type == "list" and self._get_replace_user_by_employee_value():
            for node in arch.xpath("//field[@name='user_ids']"):
                node.set("column_invisible", "True")
        return arch, view

    def _read_start_date(self, default_date):
        _date = None
        if self.planned_date_begin and self.date_deadline:
            _date = min(self.planned_date_begin, self.date_deadline)
        elif self.planned_date_begin and not self.date_deadline:
            _date = self.planned_date_begin
        elif self.date_deadline and not self.planned_date_begin:
            _date = self.date_deadline
        else:
            _date = default_date
        return _date

    def _read_end_date(self, default_date):
        _date = None
        if self.planned_date_begin and self.date_deadline:
            _date = max(self.planned_date_begin, self.date_deadline)
        elif self.planned_date_begin and not self.date_deadline:
            _date = self.planned_date_begin
        elif self.date_deadline and not self.planned_date_begin:
            _date = self.date_deadline
        else:
            _date = default_date
        return _date


class ProjectTaskLinked(models.Model):
    _name = "project.task.linked"
    _description = "Project Task Linked"

    from_id = fields.Many2one("project.task", ondelete="cascade", string="From")
    to_id = fields.Many2one("project.task", ondelete="cascade", string="To")
    lag = fields.Integer(default=0)
    lag_unit = fields.Char(default="d")
    type = fields.Integer(default=2)
    dep_active = fields.Boolean(string="Active", default=True)


class ProjectTaskAssignmentUser(models.Model):
    _name = "project.task.assignment"
    _description = "Project Task User Assignment"

    task = fields.Many2one("project.task", ondelete="cascade")
    resource = fields.Many2one("res.users", ondelete="cascade", string="User")
    resource_base = fields.Many2one(
        "resource.resource", ondelete="cascade", string="Resource"
    )
    units = fields.Integer(default=0)


class ProjectTaskBaseline(models.Model):
    _name = "project.task.baseline"
    _description = "Project Task User Assignment"

    task = fields.Many2one("project.task", ondelete="cascade")
    name = fields.Char(default="")
    planned_date_begin = fields.Datetime("Start date")
    planned_date_end = fields.Datetime("End date")


class ProjectTaskSegment(models.Model):
    _name = "project.task.segment"
    _description = "Project Task Segment"

    task = fields.Many2one("project.task", ondelete="cascade")
    name = fields.Char(default="")
    planned_date_begin = fields.Datetime("Start date")
    planned_date_end = fields.Datetime("End date")
