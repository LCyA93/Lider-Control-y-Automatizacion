# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl.html).
import datetime
import json
import logging

from odoo import fields
from odoo.tests.common import HttpCase, TransactionCase

from odoo.addons.website.tools import MockRequest

from ..controllers.controllers import BryntumGantt
from ..tools.date_utils import from_gantt_date

_logger = logging.getLogger(__name__)


class TestProjectTaskCommon(TransactionCase):
    def _create_resource(self, name):
        return self.env["resource.resource"].create(
            [
                {
                    "name": name,
                    "company_id": self.env.company.id,
                    "resource_type": "material",
                }
            ]
        )

    def _create_internal_user(self, sequence):
        # NB. tx and time efficiency, while required, have defaults.
        name = "Test user {}".format(sequence)
        email = "test{}@example.com".format(sequence)
        return self.env["res.users"].create(
            {
                "email": email,
                "groups_id": [(4, self.env.ref("base.group_user").id, 0)],
                "login": email,
                "password": "test",
                "name": name,
            }
        )

    def _create_employee(self, sequence):
        name = "Test employee {}".format(sequence)
        return self.env["hr.employee"].create(
            [
                {
                    "name": name,
                    "gender": "female",
                    "company_id": self.env.company.id,
                    "country_id": self.env.ref("base.nl").id,
                    "private_street": "straat A",
                    "private_zip": "6020",
                    "private_city": "Amsterdam",
                }
            ]
        )

    def _create_bryntum_dict(self, task, resources=None, users=None):
        # create JSON to post to controller where we assign u1, u2 to task
        # NB: the gantt lib sends a redundant dictionary, with one complete set of
        # "new data" for every crud operation: e.g if we delete 1 #24 record and
        # add 2 records #60 and #62, we will get 3 dicts imposing [60,62] repeated.
        resource_ids = resources.ids if resources else []
        user_ids = users.ids if users else []
        return {
            "model": {"id": "project-task_%s" % task.id},
            "newData": {
                "assignedList": False,
                "assignedResources": [
                    {
                        "task_id": "project-task_%s" % task.id,
                        "resource_id": "r_%s" % resource_id,
                        "units": 100,
                    }
                    for resource_id in resource_ids
                ]
                + [
                    {
                        "task_id": "project-task_%s" % task.id,
                        "resource_id": "u_%s" % user_id,
                        "units": 100,
                    }
                    for user_id in user_ids
                ],
            },
        }

    def _create_bryntum_load_dict(self, task):
        # create a load data for the project of task
        return {"project_ids": ["%s" % task.project_id.id]}

    def _test_assignments_loaded(self, task, res, resources=None, users=None):
        """
        Example response:
        {'assignments': {'rows': [
          {'event': 'project-task_252',
           'id': '252-r_359',
           'resource': 'r_359',
           'units': 100},
          {'event': 'project-task_252',
           'id': '252-r_356',
           'resource': 'r_356',
           'units': 100},
          {'event': 'project-task_252',
           'id': '252-r_357',
           'resource': 'r_357',
           'units': 100}]},
        """
        resource_ids = resources.ids if resources else []
        user_ids = users.ids if users else []
        rows = res.get("assignments", {}).get("rows", [])
        task_str = "project-task_{}".format(task.id)
        rows_resource = [
            x
            for x in rows
            if x.get("event") == task_str and x.get("resource", "").startswith("r_")
        ]
        res_resource_ids = [int(x.get("resource").split("_")[1]) for x in rows_resource]
        rows_user = [
            x
            for x in rows
            if x.get("event") == task_str and x.get("resource", "").startswith("u_")
        ]
        res_user_ids = [int(x.get("resource").split("_")[1]) for x in rows_user]
        self.assertItemsEqual(res_resource_ids, resource_ids)
        self.assertItemsEqual(res_user_ids, user_ids)

    @classmethod
    def setUpClass(cls):
        super().setUpClass()

        # Create test users
        cls.test_user1 = cls._create_internal_user(cls, 1)
        cls.test_partner1 = cls.test_user1.partner_id
        cls.test_user2 = cls._create_internal_user(cls, 2)
        cls.test_partner2 = cls.test_user2.partner_id

        # Create resources.
        # We must verify that resourceA and resourceB have id's different than test_user1
        # and test_user2, because their IDS will be mixed in a set to determine how many
        # resource and resource_base are present. Duplicate id's would make set smaller.
        invalid_ids = [cls.test_user2.id, cls.test_user1.id]
        while True:
            resource = cls._create_resource(cls, "Resource A")
            if resource.id not in invalid_ids:
                cls.test_resourceA = resource
                break
            resource.unlink()
        while True:
            resource = cls._create_resource(cls, "Resource B")
            if resource.id not in invalid_ids:
                cls.test_resourceB = resource
                break
            resource.unlink()

        # create test employees
        # Verify that underlying resource ids are unique
        invalid_ids.append(cls.test_resourceA.id)
        invalid_ids.append(cls.test_resourceB.id)
        while True:
            employee = cls._create_employee(cls, 1)
            if employee.resource_id.id not in invalid_ids:
                cls.test_employee1 = employee
                break
            employee.unlink()
        while True:
            employee = cls._create_employee(cls, 2)
            if employee.resource_id.id not in invalid_ids:
                cls.test_employee2 = employee
                break
            employee.unlink()

        cls.project_test1 = (
            cls.env["project.project"]
            .with_context(mail_create_nolog=True)
            .create(
                {
                    "name": "test1",
                    "privacy_visibility": "employees",
                    "alias_name": "test1",
                    "partner_id": cls.test_partner1.id,
                }
            )
        )
        cls.task_1 = (
            cls.env["project.task"]
            .with_context(mail_create_nolog=True)
            .create(
                {
                    "name": "TestTask1",
                    "user_ids": [cls.test_user1.id],
                    "project_id": cls.project_test1.id,
                }
            )
        )
        cls.task_2 = (
            cls.env["project.task"]
            .with_context(mail_create_nolog=True)
            .create(
                {
                    "name": "TestTask2",
                    "user_ids": [cls.test_user2.id],
                    "project_id": cls.project_test1.id,
                }
            )
        )


class TestRegular(TestProjectTaskCommon):
    def test_unique_ids(self):
        """Verify that there are no overlapping ids"""
        u1 = self.test_user1
        u2 = self.test_user2
        rA = self.test_resourceA
        rB = self.test_resourceB
        r1 = self.test_employee1.resource_id
        r2 = self.test_employee2.resource_id

        # Assert that there are no overlaps in ids
        self.assertEqual(len({u1, u2, rA, rB, r1, r2}), 6)

    def test_employee_ids_field(self):
        """Tests employee_ids field on task"""
        task1 = self.task_1
        task2 = self.task_2
        r1 = self.test_employee1.resource_id
        r2 = self.test_employee2.resource_id
        e1 = self.test_employee1
        e2 = self.test_employee2

        # In the beginning there is nothing set
        self.assertFalse(task1.assigned_resources)
        self.assertFalse(task1.employee_ids)

        # If we add or remove resources, it should reflect in employees
        a1 = self.env["project.task.assignment"].create(
            {
                "task": task1.id,
                "resource": False,
                "resource_base": r1.id,
                "units": int(100),
            }
        )
        self.assertEqual(task1.employee_ids, e1)
        self.env["project.task.assignment"].create(
            {
                "task": task1.id,
                "resource": False,
                "resource_base": r2.id,
                "units": int(100),
            }
        )
        self.assertEqual(task1.employee_ids, e1 + e2)
        a1.unlink()
        self.assertEqual(task1.employee_ids, e2)

        # if we modify employees, it should reflect in assignments
        task1.write({"employee_ids": [(4, e1.id)]})
        self.assertEqual(task1.employee_ids, e1 + e2)
        task1.write({"employee_ids": [(3, e2.id)]})
        self.assertEqual(task1.employee_ids, e1)

        # we need to be able to search tasks by employees
        task2.write({"employee_ids": [(4, e2.id)]})
        self.assertEqual(task2.employee_ids, e2)
        tasks = self.env["project.task"].search(
            [("employee_ids", "=", "Test employee 2")]
        )
        self.assertEqual(tasks, task2)


class TestControllers(TestProjectTaskCommon, HttpCase):
    def test_project_task_assignment_CRUD(self):

        # Assign shorthand variables
        task1 = self.task_1
        u1 = self.test_user1
        u2 = self.test_user2
        rA = self.test_resourceA
        rB = self.test_resourceB
        e1 = self.test_employee1
        e2 = self.test_employee2
        r1 = self.test_employee1.resource_id
        r2 = self.test_employee2.resource_id

        # first we set bryntum_user_assignment as True, otherwise we would not be able
        # to select the users as resource.
        # task1.project_id.bryntum_user_assignment = True

        # Assign user 1 and user 2 to task 1
        data_component = self._create_bryntum_dict(task1, users=u1 + u2)
        data = [data_component, data_component]
        ctrl = BryntumGantt()
        with MockRequest(self.env):
            res = ctrl.bryntum_gantt_update(data=json.dumps(data))
            self.assertTrue(res["success"])
            self.assertEqual(res.get("status"), "updated")
            self.assertFalse(task1.employee_ids)
            assignments = task1.mapped("assigned_resources")
            self.assertEqual(len(assignments), 2)
            self.assertEqual(assignments.mapped("resource"), u1 + u2)
            # TODO: we dont yet sync user_ids field and not know if we should
            # self.assertEqual(task1.user_ids, u1 + u2)
            data = {"project_ids": [task1.project_id.id]}
            res = ctrl.bryntum_gantt_load(data=json.dumps(data))
            self._test_assignments_loaded(task1, res, users=u1 + u2)

        # now we change resource settings to use resources + employees not users
        # task1.project_id.bryntum_user_assignment = False

        # Assign resource 1, 2, A, B to task 1
        data = self._create_bryntum_dict(task1, resources=r1 + r2 + rA + rB)
        with MockRequest(self.env):
            res = ctrl.bryntum_gantt_update(data=json.dumps([data]))
            self.assertTrue(res["success"])
            self.assertEqual(res.get("status"), "updated")
            self.assertEqual(len(task1.assigned_resources), 4)
            self.assertEqual(task1.employee_ids, e1 + e2)
            self.assertFalse(task1.assigned_resources.mapped("resource"))
            self.assertEqual(
                task1.assigned_resources.mapped("resource_base"), r1 + r2 + rA + rB
            )
            data = {"project_ids": [task1.project_id.id]}
            res = ctrl.bryntum_gantt_load(data=json.dumps(data))
            self._test_assignments_loaded(task1, res, resources=r1 + r2 + rA + rB)

        # Now remove r1, leave r2, rA, rB
        data = self._create_bryntum_dict(task1, resources=r2 + rA + rB)
        with MockRequest(self.env):
            res = ctrl.bryntum_gantt_update(data=json.dumps([data]))
            self.assertTrue(res["success"])
            self.assertEqual(res.get("status"), "updated")
            self.assertEqual(task1.employee_ids, e2)
            self.assertEqual(len(task1.assigned_resources), 3)
            self.assertFalse(task1.assigned_resources.mapped("resource"))
            self.assertEqual(
                task1.assigned_resources.mapped("resource_base"), r2 + rA + rB
            )
            data = {"project_ids": [task1.project_id.id]}
            res = ctrl.bryntum_gantt_load(data=json.dumps(data))
            self._test_assignments_loaded(task1, res, resources=r2 + rA + rB)

        # add an employee from backend, make sure all project.task.assignments
        # are correctly updated,
        # I add employee1 from backendi, employee can be added because we are still in
        # bryntum_user_assignment=false mode:
        task1.write({"employee_ids": [(4, e1.id)]})
        self.assertEqual(task1.employee_ids, e1 + e2)
        self.assertEqual(len(task1.assigned_resources), 4)
        self.assertFalse(task1.assigned_resources.mapped("resource"))
        self.assertEqual(
            task1.assigned_resources.mapped("resource_base"), r1 + r2 + rA + rB
        )
        pta = self.env["project.task.assignment"].search([("task", "=", task1.id)])
        self.assertEqual(len(pta), 4)
        # I remove employee2 from backend employee_ids
        task1.write({"employee_ids": [(3, e2.id)]})
        self.assertEqual(task1.employee_ids, e1)
        self.assertEqual(len(task1.assigned_resources), 3)
        self.assertFalse(task1.assigned_resources.mapped("resource"))
        self.assertEqual(task1.assigned_resources.mapped("resource_base"), r1 + rA + rB)
        pta = self.env["project.task.assignment"].search([("task", "=", task1.id)])
        self.assertEqual(len(pta), 3)
        with MockRequest(self.env):
            data = {"project_ids": [task1.project_id.id]}
            res = ctrl.bryntum_gantt_load(data=json.dumps(data))
            self._test_assignments_loaded(task1, res, resources=r1 + rA + rB)

        # test create from backend with employee_ids 1 and 2
        # and check project_task_assignments is created with correct resources r1, r2.
        created_task = (
            self.env["project.task"]
            .with_context(mail_create_nolog=True)
            .create(
                {
                    "name": "CreatedTask",
                    "user_ids": [u1.id],
                    "project_id": self.project_test1.id,
                    "employee_ids": [(6, 0, [e1.id, e2.id])],
                }
            )
        )
        self.assertEqual(len(created_task.assigned_resources), 2)
        resources = created_task.assigned_resources.mapped("resource_base")
        self.assertEqual(resources, r1 + r2)
        users = created_task.assigned_resources.mapped("resource")
        self.assertFalse(users)

        # test project.task.assignment Backend edit/save
        # and then we check that employee_ids is in sync with assigned resources,
        # only one assignment, associated with employee1
        new_assignment = self.env["project.task.assignment"].create(
            {
                "task": created_task.id,
                "resource": False,
                "resource_base": r1.id,
                "units": int(100),
            }
        )
        created_task.write({"assigned_resources": [(6, 0, [new_assignment.id])]})
        self.assertEqual(len(created_task.assigned_resources), 1)
        self.assertEqual(created_task.employee_ids, e1)

        # we test writing from backend employee and assigned_resources.
        created_task.write(
            {
                "employee_ids": [
                    (
                        6,
                        0,
                        [e1.id, e2.id],
                    )
                ],
            }
        )
        # In this case the employee will create 2 new records.
        self.assertEqual(len(created_task.assigned_resources), 2)
        # should have 2 employees:
        self.assertEqual(created_task.employee_ids, e1 + e2)

    def test_load_and_update_dates(self):
        # Assign shorthand variables
        task1 = self.task_1
        project = self.task_1.project_id
        ctrl = BryntumGantt()
        FIELD_START = "planned_date_begin"
        FIELD_END = "date_deadline"
        self.assertIn(FIELD_START, task1._fields)
        self.assertIn(FIELD_END, task1._fields)
        with MockRequest(self.env):
            today = fields.Date.context_today(project)
            yesterday = today + datetime.timedelta(days=-1)
            start_end_values = [
                (today, False),
                (False, today),
                (today, yesterday),
                (False, False),
            ]
            for start, end in start_end_values:
                _logger.info("START %s END %s", start, end)
                # we verify if load is correct with current start and enddate
                setattr(task1, FIELD_START, start)
                setattr(task1, FIELD_END, end)
                data = self._create_bryntum_load_dict(task1)
                res = ctrl.bryntum_gantt_load(data=json.dumps(data))
                tasks_dict = {
                    x["id"]: x
                    for x in res["tasks"]["rows"][0]["children"]
                    if x["id"] == f"project-task_{task1.id}"
                }
                task1_key = f"project-task_{task1.id}"
                task1_dict = tasks_dict[task1_key]
                seen_start = from_gantt_date(task1_dict["startDate"])
                seen_end = from_gantt_date(task1_dict["endDate"])
                self.assertTrue(seen_start)
                self.assertTrue(seen_end)
                self.assertLessEqual(seen_start, seen_end)
                setattr(task1, FIELD_START, False)
                setattr(task1, FIELD_END, False)
                data = self._create_bryntum_load_dict(task1)
                res = ctrl.bryntum_gantt_load(data=json.dumps(data))
                tasks_dict = {
                    x["id"]: x
                    for x in res["tasks"]["rows"][0]["children"]
                    if x["id"] == f"project-task_{task1.id}"
                }
                task1_key = f"project-task_{task1.id}"
                task1_dict = tasks_dict[task1_key]
                seen_start = from_gantt_date(task1_dict["startDate"])
                seen_end = from_gantt_date(task1_dict["endDate"])
                self.assertTrue(seen_start)
                self.assertTrue(seen_end)
                self.assertLessEqual(seen_start, seen_end)
