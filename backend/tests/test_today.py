from datetime import datetime, timezone
from types import SimpleNamespace
from zoneinfo import ZoneInfo

from app import clock
from app.seed import plan_day
from app.today import classify_task, group_tasks
from tests.helpers import create_task

NOW = datetime(2026, 11, 25, 12, 0, tzinfo=timezone.utc)
ZONE = "Asia/Kolkata"


def _task(**overrides):
    data = {
        "title": "Task",
        "due_at": NOW,
        "status": "pending",
        "completed_at": None,
    }
    data.update(overrides)
    return SimpleNamespace(**data)


def test_classify_overdue_due_done_and_the_ist_midnight_boundary():
    overdue = _task(due_at=datetime(2026, 11, 25, 3, 30, tzinfo=timezone.utc))
    due = _task(due_at=datetime(2026, 11, 25, 14, 30, tzinfo=timezone.utc))
    yesterday = _task(due_at=datetime(2026, 11, 24, 10, 30, tzinfo=timezone.utc))
    tomorrow = _task(due_at=datetime(2026, 11, 26, 3, 30, tzinfo=timezone.utc))
    done_today = _task(
        due_at=datetime(2026, 11, 25, 3, 30, tzinfo=timezone.utc),
        status="done",
        completed_at=datetime(2026, 11, 25, 4, 0, tzinfo=timezone.utc),
    )
    done_yesterday = _task(
        status="done",
        due_at=datetime(2026, 11, 24, 10, 30, tzinfo=timezone.utc),
        completed_at=datetime(2026, 11, 24, 11, 0, tzinfo=timezone.utc),
    )
    finished_early = _task(
        due_at=datetime(2026, 11, 25, 14, 30, tzinfo=timezone.utc),
        status="done",
        completed_at=NOW,
    )
    just_before_local_midnight = _task(due_at=datetime(2026, 11, 25, 18, 29, tzinfo=timezone.utc))
    just_after_local_midnight = _task(due_at=datetime(2026, 11, 25, 18, 31, tzinfo=timezone.utc))

    assert classify_task(overdue, NOW, ZONE) == "overdue"
    assert classify_task(due, NOW, ZONE) == "due"
    assert classify_task(yesterday, NOW, ZONE) == "overdue"
    assert classify_task(tomorrow, NOW, ZONE) is None
    assert classify_task(done_today, NOW, ZONE) == "done"
    assert classify_task(done_yesterday, NOW, ZONE) is None
    assert classify_task(finished_early, NOW, ZONE) == "done"
    assert classify_task(just_before_local_midnight, NOW, ZONE) == "due"
    assert classify_task(just_after_local_midnight, NOW, ZONE) is None

    grouped = group_tasks(
        [overdue, due, yesterday, tomorrow, done_today, done_yesterday, finished_early],
        NOW,
        ZONE,
    )
    assert [task.title for task in grouped["overdue"]] == ["Task", "Task"]
    assert grouped["due"] == [due]
    assert done_today in grouped["done"] and finished_early in grouped["done"]
    assert tomorrow not in grouped["overdue"] + grouped["due"] + grouped["done"]
    assert done_yesterday not in grouped["overdue"] + grouped["due"] + grouped["done"]
    assert done_today not in grouped["overdue"]


def test_today_groups_overdue_due_and_done(client, family, monkeypatch):
    monkeypatch.setattr(clock, "now_utc", lambda: NOW)
    create_task(
        client,
        title="Book the doctor visit",
        category="appointment",
        due_date="2026-11-24",
        due_time="16:00",
    )
    create_task(client, title="Blood pressure tablet", due_time="09:00")
    evening = create_task(client, title="Evening medicines", due_time="20:00")
    create_task(
        client,
        title="Tomorrow check-in",
        category="checkin",
        due_date="2026-11-26",
        due_time="09:00",
    )

    before = client.get("/api/today")
    assert before.status_code == 200, before.text
    body = before.json()
    assert body["date"] == "2026-11-25"
    assert body["timezone"] == "Asia/Kolkata"
    assert [task["title"] for task in body["overdue"]] == [
        "Book the doctor visit",
        "Blood pressure tablet",
    ]
    assert [task["title"] for task in body["due"]] == ["Evening medicines"]
    assert body["done"] == []
    assert "Tomorrow check-in" not in str(body["overdue"]) + str(body["due"]) + str(body["done"])

    completed = client.post(
        f"/api/tasks/{evening['id']}/complete",
        json={"member_id": family["ravi_id"]},
    )
    assert completed.status_code == 200, completed.text
    assert completed.json()["completed_by"]["name"] == "Ravi"
    assert completed.json()["completed_at"].startswith("2026-11-25T12:00:00")

    after = client.get("/api/today").json()
    assert after["due"] == []
    assert [task["title"] for task in after["done"]] == ["Evening medicines"]
    assert after["done"][0]["completed_by"]["relationship"] == "son"


def test_reschedule_moves_a_task_out_of_overdue(client, family, monkeypatch):
    monkeypatch.setattr(clock, "now_utc", lambda: NOW)
    task = create_task(client, title="Morning dose", due_time="09:00")
    overdue = client.get("/api/today").json()["overdue"]
    assert [item["title"] for item in overdue] == ["Morning dose"]

    moved = client.patch(f"/api/tasks/{task['id']}", json={"due_time": "20:00"})
    assert moved.status_code == 200, moved.text

    board = client.get("/api/today").json()
    assert board["overdue"] == []
    assert [item["title"] for item in board["due"]] == ["Morning dose"]


def _specs_as_tasks(local_now):
    tasks = []
    for spec in plan_day(local_now):
        tasks.append(
            SimpleNamespace(
                title=spec.title,
                due_at=spec.due_local.astimezone(timezone.utc),
                status="done" if spec.done_by else "pending",
                completed_at=(
                    spec.completed_local.astimezone(timezone.utc) if spec.completed_local else None
                ),
            )
        )
    return tasks


def test_sample_evening_shows_the_morning_dose_done_and_the_evening_dose_open():
    zone = ZoneInfo("Asia/Kolkata")
    local_now = datetime(2026, 11, 25, 22, 33, tzinfo=zone)
    grouped = group_tasks(_specs_as_tasks(local_now), local_now.astimezone(timezone.utc), ZONE)
    assert [task.title for task in grouped["overdue"]] == [
        "Book the doctor visit",
        "Evening blood pressure tablet",
    ]
    assert [task.title for task in grouped["due"]] == ["Night check-in"]
    assert [task.title for task in grouped["done"]] == ["Morning blood pressure tablet"]


def test_sample_morning_keeps_both_doses_due():
    zone = ZoneInfo("Asia/Kolkata")
    local_now = datetime(2026, 11, 25, 8, 30, tzinfo=zone)
    grouped = group_tasks(_specs_as_tasks(local_now), local_now.astimezone(timezone.utc), ZONE)
    assert [task.title for task in grouped["overdue"]] == ["Book the doctor visit"]
    assert [task.title for task in grouped["due"]] == [
        "Morning blood pressure tablet",
        "Evening blood pressure tablet",
    ]
    assert [task.title for task in grouped["done"]] == ["Morning check-in"]
