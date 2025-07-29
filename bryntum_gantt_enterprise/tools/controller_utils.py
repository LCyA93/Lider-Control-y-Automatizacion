import base64
import re


def get_avatar(value):
    if isinstance(value, (bytes, bytearray)):
        return base64.b64encode(value).decode("ascii")
    else:
        return None


def get_assignment(assignment, task):

    if len(assignment.resource.ids) > 0:
        resource = assignment.resource
        prefix = "u_"

    if len(assignment.resource_base.ids) > 0:
        resource = assignment.resource_base
        prefix = "r_"

    resource_id = prefix + str(resource.id)

    return {
        "id": "%d-%s" % (task.id, resource_id),
        "resource": resource_id,
        "event": task.id,
        "units": assignment.units,
    }


def get_assignments(task, get_assignment):
    if len(task.assigned_resources.ids) > 0:
        return map(
            lambda assignment: get_assignment(assignment, task), task.assigned_resources
        )

    return map(
        lambda user: {
            "id": "%d-%d" % (task.id, user.id),
            "resource": user.id,
            "event": task.id,
            "units": 100,
        },
        task.assigned_ids,
    )


def get_baselines(task, tz, cfn):

    baselines = [
        {
            "name": baseline.name,
            "startDate": cfn(baseline.planned_date_begin, tz),
            "endDate": cfn(baseline.planned_date_end, tz),
        }
        for baseline in task.baselines
    ]

    return baselines


def get_segments(task, tz, cfn):

    segments = [
        {
            "name": segment.name,
            "startDate": cfn(segment.planned_date_begin, tz),
            "endDate": cfn(segment.planned_date_end, tz),
        }
        for segment in task.segments
    ]

    if len(segments) > 0:
        return segments
    else:
        return None


def field_related(data, cfields):
    response = {}
    for o_key, g_key, func in cfields:
        value = data.get(g_key, "0_empty_value_0")
        if value == "0_empty_value_0":
            continue
        if func and value is not None:
            response.update({o_key: func(value)})
        else:
            response.update({o_key: value})
    return response


def to_task_id(gantt_id):
    groups = re.match(r"project-task_(\d+)", gantt_id)
    if groups:
        return int(groups.group(1))
    return None


def to_project_id(gantt_id):
    groups = re.match(r"project_(\d+)", gantt_id)
    if groups:
        return int(groups.group(1))
    return None


def is_gantt_new_id(new_id):
    return bool(re.match(r"_generated.+\d+", new_id))


def gantt_id(_id):
    response = (
        re.match(r"(project-task)_(\d+)", _id)
        or re.match(r"(project-project)_(\d+)", _id)
        or re.match(r"(project)_(\d+)", _id)
    )
    if response:
        return response.group(1), int(response.group(2))
    else:
        return False, False


def get_resource_id(_id):
    groups = re.match(r"u_(\d+)", _id)
    if groups:
        return int(groups.group(1)), None
    groups = re.match(r"r_(\d+)", _id)
    if groups:
        return None, int(groups.group(1))
    return None, None
