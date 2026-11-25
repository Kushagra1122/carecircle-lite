"""Sample day for an empty database.

Times are relative to now so opening the app shows overdue, due, and done
whenever that is possible. After 9:12am the story matches a real morning:
Ravi has given the 9am tablet, and the 8pm tablet is still open.
"""

import logging
from dataclasses import dataclass
from datetime import datetime, time, timedelta, timezone

from sqlalchemy import select

from app import clock
from app.models import CareRecipient, CareTask, FamilyMember
from app.today import to_local

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class TaskSpec:
    title: str
    category: str
    due_local: datetime
    done_by: str | None
    completed_local: datetime | None
    notes: str | None = None


def plan_day(local_now: datetime) -> list[TaskSpec]:
    if local_now.tzinfo is None:
        raise ValueError("local_now must be timezone-aware")
    today = local_now.date()
    zone = local_now.tzinfo

    def at(day_offset: int, hour: int, minute: int) -> datetime:
        moment = datetime.combine(
            today + timedelta(days=day_offset),
            time(hour, minute),
            tzinfo=zone,
        )
        return moment

    specs = [
        TaskSpec(
            title="Book the doctor visit",
            category="appointment",
            due_local=at(-1, 16, 0),
            done_by=None,
            completed_local=None,
        )
    ]

    morning_due = at(0, 9, 0)
    if local_now >= at(0, 9, 12):
        specs.append(
            TaskSpec(
                title="Morning blood pressure tablet",
                category="medicine",
                due_local=morning_due,
                done_by="Ravi",
                completed_local=at(0, 9, 12),
                notes="After food",
            )
        )
    elif local_now >= morning_due:
        finished = (local_now - timedelta(minutes=2)).replace(second=0, microsecond=0)
        specs.append(
            TaskSpec(
                title="Morning blood pressure tablet",
                category="medicine",
                due_local=morning_due,
                done_by="Ravi",
                completed_local=finished,
                notes="After food",
            )
        )
    else:
        specs.append(
            TaskSpec(
                title="Morning blood pressure tablet",
                category="medicine",
                due_local=morning_due,
                done_by=None,
                completed_local=None,
                notes="After food",
            )
        )

    specs.append(
        TaskSpec(
            title="Evening blood pressure tablet",
            category="medicine",
            due_local=at(0, 20, 0),
            done_by=None,
            completed_local=None,
            notes="After food",
        )
    )

    if not _has_open_task_later_today(specs, local_now):
        slot = _next_slot(local_now)
        if slot is not None:
            specs.append(
                TaskSpec(
                    title="Night check-in",
                    category="checkin",
                    due_local=slot,
                    done_by=None,
                    completed_local=None,
                )
            )

    if not any(spec.done_by for spec in specs):
        if local_now >= at(0, 7, 10):
            specs.append(
                TaskSpec(
                    title="Morning check-in",
                    category="checkin",
                    due_local=at(0, 7, 0),
                    done_by="Priya",
                    completed_local=at(0, 7, 10),
                )
            )
        elif local_now >= at(0, 0, 20):
            specs.append(
                TaskSpec(
                    title="Night check-in",
                    category="checkin",
                    due_local=at(0, 0, 10),
                    done_by="Anita",
                    completed_local=at(0, 0, 15),
                )
            )
    return specs


def seed_if_empty(db) -> None:
    existing = db.scalar(select(CareRecipient.id).limit(1))
    if existing is not None:
        return
    recipient = CareRecipient(
        name="Asha Menon",
        preferred_name="Mum",
        timezone="Asia/Kolkata",
    )
    db.add(recipient)
    db.flush()
    members = [
        FamilyMember(recipient_id=recipient.id, name="Ravi", relationship="son"),
        FamilyMember(recipient_id=recipient.id, name="Priya", relationship="daughter"),
        FamilyMember(recipient_id=recipient.id, name="Anita", relationship="caregiver"),
    ]
    db.add_all(members)
    db.flush()
    by_name = {member.name: member for member in members}
    local_now = to_local(clock.now_utc(), recipient.timezone)
    for spec in plan_day(local_now):
        done = spec.done_by is not None
        db.add(
            CareTask(
                recipient_id=recipient.id,
                title=spec.title,
                category=spec.category,
                due_at=spec.due_local.astimezone(timezone.utc),
                status="done" if done else "pending",
                notes=spec.notes,
                completed_by_id=by_name[spec.done_by].id if done else None,
                completed_at=(
                    spec.completed_local.astimezone(timezone.utc) if spec.completed_local else None
                ),
            )
        )
    db.commit()
    logger.info("Seeded a sample day for %s", recipient.preferred_name)


def _has_open_task_later_today(specs: list[TaskSpec], local_now: datetime) -> bool:
    return any(
        spec.done_by is None
        and spec.due_local >= local_now
        and spec.due_local.date() == local_now.date()
        for spec in specs
    )


def _next_slot(local_now: datetime) -> datetime | None:
    candidate = (local_now + timedelta(minutes=30)).replace(second=0, microsecond=0)
    add = (15 - candidate.minute % 15) % 15
    candidate = candidate + timedelta(minutes=add)
    if candidate.date() == local_now.date() and candidate > local_now:
        return candidate
    last = datetime.combine(local_now.date(), time(23, 45), tzinfo=local_now.tzinfo)
    if last > local_now:
        return last
    return None
