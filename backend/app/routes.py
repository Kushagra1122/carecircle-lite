"""HTTP API for one family's care tasks.

The board, the writes, and the assistant all read the same rows.
Grouping rules live in app.today so the screen and the assistant can't drift.
"""

import json
import logging
import time

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from sqlalchemy import select, update
from sqlalchemy.orm import Session, joinedload

from app import clock
from app.assistant import (
    answer_from_grouped,
    groq_enabled,
    render_context,
    save_log,
    stream_groq,
    stream_words,
)
from app.db import SessionLocal, get_db
from app.models import CareRecipient, CareTask, FamilyMember
from app.schemas import AskIn, CompleteIn, FamilyOut, TaskCreate, TaskOut, TaskUpdate, TodayOut
from app.timefmt import format_time
from app.today import combine_due, group_tasks, to_local

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api")


@router.get("/health")
def health():
    return {"ok": True}


@router.get("/family", response_model=FamilyOut)
def family(db: Session = Depends(get_db)):
    recipient = _recipient(db)
    members = db.scalars(
        select(FamilyMember)
        .where(FamilyMember.recipient_id == recipient.id)
        .order_by(FamilyMember.id)
    ).all()
    return {"recipient": recipient, "members": list(members)}


@router.get("/today", response_model=TodayOut)
def today(db: Session = Depends(get_db)):
    recipient = _recipient(db)
    now = clock.now_utc()
    grouped = group_tasks(_tasks_for(db, recipient.id), now, recipient.timezone)
    return {
        "timezone": recipient.timezone,
        "now": now,
        "date": to_local(now, recipient.timezone).date(),
        "recipient": recipient,
        "overdue": grouped["overdue"],
        "due": grouped["due"],
        "done": grouped["done"],
    }


@router.get("/tasks", response_model=list[TaskOut])
def list_tasks(db: Session = Depends(get_db)):
    recipient = _recipient(db)
    return _tasks_for(db, recipient.id)


@router.post("/tasks", response_model=TaskOut, status_code=201)
def create_task(body: TaskCreate, db: Session = Depends(get_db)):
    recipient = _recipient(db)
    task = CareTask(
        recipient_id=recipient.id,
        title=body.title,
        category=body.category,
        due_at=combine_due(body.due_date, body.due_time, recipient.timezone),
        notes=body.notes,
        status="pending",
    )
    db.add(task)
    db.commit()
    return _fetch_task(db, task.id)


@router.get("/tasks/{task_id}", response_model=TaskOut)
def get_task(task_id: int, db: Session = Depends(get_db)):
    task = _fetch_task(db, task_id)
    if task is None:
        raise HTTPException(status_code=404, detail="Task not found.")
    return task


@router.patch("/tasks/{task_id}", response_model=TaskOut)
def update_task(task_id: int, body: TaskUpdate, db: Session = Depends(get_db)):
    task = _fetch_task(db, task_id)
    if task is None:
        raise HTTPException(status_code=404, detail="Task not found.")
    recipient = _recipient(db)
    _apply_update(task, body, recipient.timezone)
    db.commit()
    return _fetch_task(db, task_id)


@router.post("/tasks/{task_id}/complete", response_model=TaskOut)
def complete_task(task_id: int, body: CompleteIn, db: Session = Depends(get_db)):
    task = _fetch_task(db, task_id)
    if task is None:
        raise HTTPException(status_code=404, detail="Task not found.")
    member = db.get(FamilyMember, body.member_id)
    if member is None or member.recipient_id != task.recipient_id:
        raise HTTPException(status_code=404, detail="Family member not found.")

    # One UPDATE is the lock. Two phones can both read "pending" and then tap
    # Done; only the write that still sees pending succeeds. The other gets
    # who already recorded it, and the first timestamp stays.
    result = db.execute(
        update(CareTask)
        .where(CareTask.id == task_id, CareTask.status == "pending")
        .values(status="done", completed_by_id=member.id, completed_at=clock.now_utc())
    )
    if result.rowcount != 1:
        db.rollback()
        current = _fetch_task(db, task_id)
        if current is None:
            raise HTTPException(status_code=404, detail="Task not found.")
        raise HTTPException(status_code=409, detail=_already_done(current))
    db.commit()
    return _fetch_task(db, task_id)


@router.post("/tasks/{task_id}/reopen", response_model=TaskOut)
def reopen_task(task_id: int, db: Session = Depends(get_db)):
    task = _fetch_task(db, task_id)
    if task is None:
        raise HTTPException(status_code=404, detail="Task not found.")
    task.status = "pending"
    task.completed_by = None
    task.completed_at = None
    db.commit()
    return _fetch_task(db, task_id)


@router.post("/assistant/ask")
async def ask(body: AskIn):
    with SessionLocal() as db:
        recipient = _recipient(db)
        now = clock.now_utc()
        grouped = group_tasks(_tasks_for(db, recipient.id), now, recipient.timezone)
        context = render_context(recipient, grouped, now)
        template = answer_from_grouped(body.question, recipient, grouped, now)

    async def events():
        started = time.perf_counter()
        final = ""
        source = "template"
        try:
            if groq_enabled():
                source = "groq"
                async for token in stream_groq(body.question, context):
                    final += token
                    yield _sse({"token": token})
                if not final.strip():
                    raise RuntimeError("empty answer")
            else:
                async for token in stream_words(template):
                    final += token
                    yield _sse({"token": token})
        except Exception as exc:
            logger.warning("Assistant stream failed, using the task-list answer: %s", exc)
            if not final:
                source = "template"
                async for token in stream_words(template):
                    final += token
                    yield _sse({"token": token})
        latency_ms = int((time.perf_counter() - started) * 1000)
        try:
            save_log(body.question, context, final, latency_ms, source)
        except Exception:
            logger.exception("Could not store the assistant log")
        yield _sse({"done": True, "latency_ms": latency_ms, "source": source})

    return StreamingResponse(
        events(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )


def _recipient(db: Session) -> CareRecipient:
    recipient = db.scalar(select(CareRecipient).order_by(CareRecipient.id).limit(1))
    if recipient is None:
        raise HTTPException(status_code=404, detail="No care recipient has been set up.")
    return recipient


def _tasks_for(db: Session, recipient_id: int) -> list[CareTask]:
    tasks = db.scalars(
        select(CareTask)
        .options(joinedload(CareTask.completed_by))
        .where(CareTask.recipient_id == recipient_id)
        .order_by(CareTask.due_at)
    ).unique()
    return list(tasks)


def _fetch_task(db: Session, task_id: int) -> CareTask | None:
    # populate_existing: a conditional UPDATE writes SQL without touching the
    # already-loaded object, and this session is set not to expire on commit.
    return db.scalar(
        select(CareTask)
        .options(joinedload(CareTask.completed_by), joinedload(CareTask.recipient))
        .where(CareTask.id == task_id)
        .execution_options(populate_existing=True)
    )


def _apply_update(task: CareTask, body: TaskUpdate, tz_name: str) -> None:
    fields = body.model_fields_set
    if "title" in fields and body.title is not None:
        task.title = body.title
    if "category" in fields and body.category is not None:
        task.category = body.category
    if "notes" in fields:
        task.notes = body.notes
    if "due_date" in fields or "due_time" in fields:
        local = to_local(task.due_at, tz_name)
        task.due_at = combine_due(
            body.due_date or local.date(),
            body.due_time or local.time().replace(tzinfo=None),
            tz_name,
        )
    if body.reopen:
        task.status = "pending"
        task.completed_by_id = None
        task.completed_at = None


def _already_done(task: CareTask) -> dict:
    who = task.completed_by.name if task.completed_by is not None else "Someone"
    if task.completed_at is None:
        when = "an unknown time"
    else:
        zone = task.recipient.timezone if task.recipient is not None else "Asia/Kolkata"
        when = format_time(to_local(task.completed_at, zone))
    return {
        "message": f"{who} already marked this done at {when}.",
        "completed_by_id": task.completed_by.id if task.completed_by is not None else None,
        "completed_by": task.completed_by.name if task.completed_by is not None else None,
        "completed_at": task.completed_at.isoformat() if task.completed_at is not None else None,
    }


def _sse(payload: dict) -> str:
    return f"data: {json.dumps(payload, ensure_ascii=False)}\n\n"
