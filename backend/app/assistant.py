"""Answer questions about today's board.

The template and the optional Groq call both narrate the same grouped tasks
the Today screen uses. The assistant reports that list. It does not give
medical advice or invent doses.
"""

import asyncio
import json
import logging
import os
import re
from dataclasses import dataclass
from datetime import datetime

import httpx

from app.db import SessionLocal
from app.models import AssistantLog
from app.timefmt import format_stamp, format_time, format_when
from app.today import to_local

logger = logging.getLogger(__name__)

CATEGORY_LABEL = {
    "medicine": "medicine",
    "appointment": "appointment",
    "checkin": "check-in",
}

SYSTEM = (
    "You help a family coordinate one person's care for today. "
    "Use only the task context. Do not invent medicines, doses, symptoms, or appointments. "
    "Do not give medical advice or tell anyone to change treatment. "
    "If a task is pending, say it is still pending. "
    "Mention who completed a task when the context says so. "
    "Answer in two to four short sentences, in plain language, for a tired caregiver. "
    "Use the preferred name. Times in the context are already local."
)


@dataclass(frozen=True)
class LocalTask:
    bucket: str
    title: str
    category: str
    notes: str | None
    due_local: datetime
    completed_local: datetime | None
    completed_by_name: str | None


def groq_enabled() -> bool:
    if os.getenv("TESTING"):
        return False
    return bool(os.getenv("GROQ_API_KEY", "").strip())


def localize(grouped: dict, tz_name: str) -> list[LocalTask]:
    views: list[LocalTask] = []
    for bucket in ("overdue", "due", "done"):
        for task in grouped[bucket]:
            completed = task.completed_at
            who = task.completed_by.name if task.completed_by is not None else None
            views.append(
                LocalTask(
                    bucket=bucket,
                    title=task.title,
                    category=task.category,
                    notes=task.notes,
                    due_local=to_local(task.due_at, tz_name),
                    completed_local=to_local(completed, tz_name) if completed is not None else None,
                    completed_by_name=who,
                )
            )
    return views


def render_context(recipient, grouped: dict, now: datetime) -> str:
    local_now = to_local(now, recipient.timezone)
    views = localize(grouped, recipient.timezone)
    today = local_now.date()

    def lines(bucket: str) -> list[str]:
        items = [_context_line(task, today) for task in views if task.bucket == bucket]
        return items or ["- None"]

    return "\n".join(
        [
            f"Preferred name: {recipient.preferred_name}",
            f"Legal name: {recipient.name}",
            f"Timezone: {recipient.timezone}",
            f"Local time now: {format_stamp(local_now)}",
            "",
            "Overdue:",
            *lines("overdue"),
            "",
            "Due later today:",
            *lines("due"),
            "",
            "Done today:",
            *lines("done"),
            "",
            "Only these tasks are in scope. Do not invent medicines, doses, or appointments.",
        ]
    )


def answer_from_grouped(question: str, recipient, grouped: dict, now: datetime) -> str:
    local_now = to_local(now, recipient.timezone)
    views = localize(grouped, recipient.timezone)
    return _answer(question, recipient.preferred_name, views, local_now)


def save_log(question: str, context: str, answer: str, latency_ms: int, source: str) -> None:
    with SessionLocal() as db:
        db.add(
            AssistantLog(
                question=question,
                context=context,
                answer=answer,
                latency_ms=latency_ms,
                source=source,
            )
        )
        db.commit()


async def stream_words(text: str):
    delay = 0 if os.getenv("TESTING") else 0.04
    parts = text.split(" ")
    for index, word in enumerate(parts):
        yield word if index == 0 else f" {word}"
        if delay:
            await asyncio.sleep(delay)


async def stream_groq(question: str, context: str):
    model = os.getenv("GROQ_MODEL", "llama-3.1-8b-instant")
    payload = {
        "model": model,
        "stream": True,
        "temperature": 0.2,
        "max_tokens": 250,
        "messages": [
            {"role": "system", "content": SYSTEM},
            {"role": "user", "content": f"Context:\n{context}\n\nQuestion: {question}"},
        ],
    }
    timeout = httpx.Timeout(20.0)
    async with httpx.AsyncClient(timeout=timeout) as client:
        async with client.stream(
            "POST",
            "https://api.groq.com/openai/v1/chat/completions",
            headers={"Authorization": f"Bearer {os.environ['GROQ_API_KEY'].strip()}"},
            json=payload,
        ) as response:
            response.raise_for_status()
            async for line in response.aiter_lines():
                if not line.startswith("data:"):
                    continue
                data = line[5:].strip()
                if not data or data == "[DONE]":
                    if data == "[DONE]":
                        break
                    continue
                chunk = json.loads(data)
                delta = chunk["choices"][0].get("delta", {}).get("content") or ""
                if delta:
                    yield delta


def _context_line(task: LocalTask, today) -> str:
    label = CATEGORY_LABEL.get(task.category, task.category)
    note = f", note: {task.notes}" if task.notes else ""
    due = format_when(task.due_local, today)
    if task.bucket == "done":
        who = task.completed_by_name or "someone"
        when = format_time(task.completed_local) if task.completed_local else "an unknown time"
        return f"- {task.title} ({label}){note}, due {due}, done by {who} at {when}"
    return f"- {task.title} ({label}){note}, due {due}, pending"


def _answer(question: str, name: str, views: list[LocalTask], local_now: datetime) -> str:
    if not views:
        return f"Nothing on {name}'s list needs attention today."
    words = set(re.findall(r"[a-z]+", question.lower()))
    overdue = [task for task in views if task.bucket == "overdue"]
    due = [task for task in views if task.bucket == "due"]
    done = [task for task in views if task.bucket == "done"]
    wants_who = bool(words & {"who", "whose"})
    wants_missed = bool(words & {"miss", "missed", "overdue", "late", "forgot", "forgotten", "behind"})
    wants_left = bool(words & {"left", "pending", "still", "remaining", "next", "due"})
    if wants_who and not (wants_missed or wants_left):
        return _who(name, done)
    if wants_missed and not (wants_left or wants_who):
        return _missed(name, overdue, due, local_now)
    if wants_left and not (wants_missed or wants_who):
        return _left(name, overdue, due, done, local_now)
    return _summary(name, overdue, due, done, local_now)


def _who(name: str, done: list[LocalTask]) -> str:
    if not done:
        return f"No one has marked a task done for {name} yet today."
    return f"Today for {name}: {_done_sentence(done)}"


def _missed(name: str, overdue: list[LocalTask], due: list[LocalTask], local_now: datetime) -> str:
    if not overdue:
        if due:
            coming = _join([_describe(task, local_now) for task in due])
            return f"Nothing is overdue for {name}. Still coming up: {coming}."
        return f"Nothing is overdue for {name}."
    pending = _join([_describe(task, local_now) for task in overdue])
    return f"Overdue for {name}: {pending}."


def _left(
    name: str,
    overdue: list[LocalTask],
    due: list[LocalTask],
    done: list[LocalTask],
    local_now: datetime,
) -> str:
    remaining = overdue + due
    if not remaining:
        if done:
            return f"Nothing left for {name} today. {_done_sentence(done)}"
        return f"Nothing is scheduled for {name} today."
    pending = _join([_describe(task, local_now) for task in remaining])
    return f"Still to do for {name}: {pending}."


def _summary(
    name: str,
    overdue: list[LocalTask],
    due: list[LocalTask],
    done: list[LocalTask],
    local_now: datetime,
) -> str:
    sentences = [
        (
            f"{name} has {_count(len(overdue))} overdue, "
            f"{_count(len(due))} still due, and "
            f"{_count(len(done))} done today."
        )
    ]
    if overdue:
        sentences.append(
            "Still pending: " + _join([_describe(task, local_now) for task in overdue]) + "."
        )
    if due:
        sentences.append("Coming up: " + _join([_describe(task, local_now) for task in due]) + ".")
    if done:
        sentences.append(_done_sentence(done))
    return " ".join(sentences)


def _describe(task: LocalTask, local_now: datetime) -> str:
    note = f" ({task.notes})" if task.notes else ""
    when = format_when(task.due_local, local_now.date())
    if task.due_local < local_now:
        return f"{task.title}{note}, due {when}, still pending"
    return f"{task.title}{note}, due {when}"


def _done_sentence(tasks: list[LocalTask]) -> str:
    parts = []
    for task in tasks:
        who = task.completed_by_name or "Someone"
        when = format_time(task.completed_local) if task.completed_local else "an unknown time"
        parts.append(f"{who} did {task.title} at {when}")
    return _join(parts) + "."


def _count(count: int) -> str:
    return "1 task" if count == 1 else f"{count} tasks"


def _join(parts: list[str]) -> str:
    if not parts:
        return ""
    if len(parts) == 1:
        return parts[0]
    if len(parts) == 2:
        return f"{parts[0]} and {parts[1]}"
    return ", ".join(parts[:-1]) + ", and " + parts[-1]
