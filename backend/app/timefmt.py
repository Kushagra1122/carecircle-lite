from datetime import date, datetime, timedelta

WEEKDAYS = [
    "Monday",
    "Tuesday",
    "Wednesday",
    "Thursday",
    "Friday",
    "Saturday",
    "Sunday",
]
MONTHS = [
    "January",
    "February",
    "March",
    "April",
    "May",
    "June",
    "July",
    "August",
    "September",
    "October",
    "November",
    "December",
]


def format_time(dt: datetime) -> str:
    hour = dt.hour % 12 or 12
    suffix = "am" if dt.hour < 12 else "pm"
    return f"{hour}:{dt.minute:02d} {suffix}"


def format_when(dt: datetime, today: date) -> str:
    clock = format_time(dt)
    if dt.date() == today:
        return clock
    if dt.date() == today - timedelta(days=1):
        return f"yesterday {clock}"
    return f"{dt.day} {MONTHS[dt.month - 1][:3]} {clock}"


def format_stamp(dt: datetime) -> str:
    return (
        f"{WEEKDAYS[dt.weekday()]} {dt.day} {MONTHS[dt.month - 1]} {dt.year}, "
        f"{format_time(dt)}"
    )
