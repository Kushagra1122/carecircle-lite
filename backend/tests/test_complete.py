from datetime import datetime, timezone

from app import clock
from tests.helpers import create_task

NOW = datetime(2026, 11, 25, 12, 0, tzinfo=timezone.utc)


def test_second_complete_keeps_the_first_person(client, family, monkeypatch):
    current = {"at": NOW}
    monkeypatch.setattr(clock, "now_utc", lambda: current["at"])
    task = create_task(client, title="Evening medicines", due_time="20:00")

    first = client.post(
        f"/api/tasks/{task['id']}/complete",
        json={"member_id": family["ravi_id"]},
    )
    assert first.status_code == 200, first.text

    current["at"] = datetime(2026, 11, 25, 13, 0, tzinfo=timezone.utc)
    second = client.post(
        f"/api/tasks/{task['id']}/complete",
        json={"member_id": family["priya_id"]},
    )
    assert second.status_code == 409, second.text
    assert second.json()["detail"]["message"] == "Ravi already marked this done at 5:30 pm."
    assert second.json()["detail"]["completed_by_id"] == family["ravi_id"]

    saved = client.get(f"/api/tasks/{task['id']}")
    assert saved.status_code == 200
    body = saved.json()
    assert body["status"] == "done"
    assert body["completed_by"]["name"] == "Ravi"
    assert body["completed_at"].startswith("2026-11-25T12:00:00")


def test_reopen_puts_a_finished_task_back_on_the_board(client, family, monkeypatch):
    monkeypatch.setattr(clock, "now_utc", lambda: NOW)
    task = create_task(client, title="Blood pressure tablet", due_time="09:00")
    done = client.post(
        f"/api/tasks/{task['id']}/complete",
        json={"member_id": family["priya_id"]},
    )
    assert done.status_code == 200, done.text

    board = client.get("/api/today").json()
    assert [item["title"] for item in board["done"]] == ["Blood pressure tablet"]
    assert board["overdue"] == []

    reopened = client.post(f"/api/tasks/{task['id']}/reopen")
    assert reopened.status_code == 200, reopened.text
    assert reopened.json()["status"] == "pending"
    assert reopened.json()["completed_by"] is None
    assert reopened.json()["completed_at"] is None

    again = client.get("/api/today").json()
    assert [item["title"] for item in again["overdue"]] == ["Blood pressure tablet"]
    assert again["done"] == []
