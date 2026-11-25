import json
from datetime import datetime, timezone

from sqlalchemy import select

from app import clock
from app.db import SessionLocal
from app.models import AssistantLog
from tests.helpers import create_task

NOW = datetime(2026, 11, 25, 12, 0, tzinfo=timezone.utc)


def test_assistant_logs_the_question_context_answer_and_latency(client, family, monkeypatch):
    monkeypatch.setattr(clock, "now_utc", lambda: NOW)
    create_task(
        client,
        title="Book the doctor visit",
        category="appointment",
        due_date="2026-11-24",
        due_time="16:00",
    )
    create_task(client, title="Blood pressure tablet", due_time="09:00")
    create_task(client, title="Evening medicines", due_time="20:00")

    response = client.post("/api/assistant/ask", json={"question": "What did we miss?"})
    assert response.status_code == 200, response.text
    assert response.headers["content-type"].startswith("text/event-stream")

    answer = []
    saw_done = False
    for line in response.text.splitlines():
        if not line.startswith("data:"):
            continue
        payload = json.loads(line[5:])
        if "token" in payload:
            answer.append(payload["token"])
        if payload.get("done") is True:
            saw_done = True
            assert payload["source"] == "template"
            assert payload["latency_ms"] >= 0
    text = "".join(answer)
    assert saw_done
    assert "Book the doctor visit" in text
    assert "Blood pressure tablet" in text
    assert "Evening medicines" not in text

    with SessionLocal() as session:
        rows = list(session.scalars(select(AssistantLog)))
    assert len(rows) == 1
    log = rows[0]
    assert log.question == "What did we miss?"
    assert log.answer == text
    assert "Blood pressure tablet" in log.context
    assert "Evening medicines" in log.context
    assert "Do not invent medicines" in log.context
    assert log.source == "template"
    assert log.latency_ms >= 0
