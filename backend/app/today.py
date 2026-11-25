from datetime import date, datetime, time, timezone
from typing import Protocol
from zoneinfo import ZoneInfo


class Schedulable(Protocol):
    due_at: datetime
    status: str
    completed_at: datetime | None


def ensure_utc(dt: datetime) -> datetime:
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def to_local(dt: datetime, tz_name: str) -> datetime:
    return ensure_utc(dt).astimezone(ZoneInfo(tz_name))


def combine_due(due_date: date, due_time: time, tz_name: str) -> datetime:
    """Interpret a wall-clock date and time in the family's zone, store UTC."""
    wall = time(due_time.hour, due_time.minute, due_time.second)
    local = datetime.combine(due_date, wall, tzinfo=ZoneInfo(tz_name))
    return local.astimezone(timezone.utc)


def classify_task(task: Schedulable, now: datetime, tz_name: str) -> str | None:
    """Place one task on today's board.

    Done today stays in done, even if it was due earlier or finished early.
    Anything unfinished and already past due is overdue, including earlier days.
    Unfinished tasks later today are due. Later days, and tasks finished on
    another day, stay off the board.
    """
    now = ensure_utc(now)
    today = to_local(now, tz_name).date()
    if task.status == "done":
        if task.completed_at is not None and to_local(task.completed_at, tz_name).date() == today:
            return "done"
        return None
    due_at = ensure_utc(task.due_at)
    if due_at < now:
        return "overdue"
    if to_local(due_at, tz_name).date() == today:
        return "due"
    return None


def group_tasks(tasks: list, now: datetime, tz_name: str) -> dict[str, list]:
    """Group one family's tasks. The list is small, so the rules stay in Python
    instead of being rewritten as timezone arithmetic in SQL.
    """
    grouped: dict[str, list] = {"overdue": [], "due": [], "done": []}
    for task in tasks:
        bucket = classify_task(task, now, tz_name)
        if bucket is not None:
            grouped[bucket].append(task)
    grouped["overdue"].sort(key=lambda task: ensure_utc(task.due_at))
    grouped["due"].sort(key=lambda task: ensure_utc(task.due_at))
    grouped["done"].sort(
        key=lambda task: ensure_utc(task.completed_at or task.due_at),
        reverse=True,
    )
    return grouped
