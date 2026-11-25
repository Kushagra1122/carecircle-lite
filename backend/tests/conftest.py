import os

os.environ["DATABASE_URL"] = "sqlite://"
os.environ["TESTING"] = "1"
os.environ.pop("GROQ_API_KEY", None)

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import delete

from app.db import SessionLocal
from app.main import app
from app.models import AssistantLog, CareRecipient, CareTask, FamilyMember


def _wipe() -> None:
    with SessionLocal() as session:
        session.execute(delete(CareTask))
        session.execute(delete(AssistantLog))
        session.execute(delete(FamilyMember))
        session.execute(delete(CareRecipient))
        session.commit()


@pytest.fixture
def client():
    with TestClient(app) as test_client:
        _wipe()
        yield test_client
        _wipe()


@pytest.fixture
def db(client):
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()


@pytest.fixture
def family(db):
    recipient = CareRecipient(
        name="Asha Menon",
        preferred_name="Mum",
        timezone="Asia/Kolkata",
    )
    db.add(recipient)
    db.flush()
    ravi = FamilyMember(recipient_id=recipient.id, name="Ravi", relationship="son")
    priya = FamilyMember(recipient_id=recipient.id, name="Priya", relationship="daughter")
    db.add_all([ravi, priya])
    db.commit()
    return {"ravi_id": ravi.id, "priya_id": priya.id}


def create_task(client: TestClient, **overrides):
    payload = {
        "title": "Tablet",
        "category": "medicine",
        "due_date": "2026-11-25",
        "due_time": "09:00",
    }
    payload.update(overrides)
    response = client.post("/api/tasks", json=payload)
    assert response.status_code == 201, response.text
    return response.json()
