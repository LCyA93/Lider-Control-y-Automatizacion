import datetime

import dateutil.parser
import pytz


def get_gantt_date(date_field, tz=None):
    if not date_field:
        return ""
    if tz and hasattr(date_field, "astimezone"):
        return date_field.astimezone(tz).strftime("%Y-%m-%dT%H:%M:%S")
    return date_field.strftime("%Y-%m-%dT%H:%M:%S")


def from_gantt_date(value):
    try:
        dt = datetime.datetime.strptime(value, "%Y-%m-%dT%H:%M:%S%z")
        dt = dt.astimezone(pytz.utc)
        return dt.replace(tzinfo=None)
    except ValueError:
        return dateutil.parser.parse(value, ignoretz=True)
