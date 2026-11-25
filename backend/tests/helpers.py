def create_task(client, **overrides):
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
