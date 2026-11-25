from datetime import date, datetime, time
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

Category = Literal["medicine", "appointment", "checkin"]


class InModel(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)


class OutModel(BaseModel):
    model_config = ConfigDict(from_attributes=True)


class RecipientOut(OutModel):
    id: int
    name: str
    preferred_name: str
    timezone: str


class MemberOut(OutModel):
    id: int
    name: str
    relationship: str


class FamilyOut(OutModel):
    recipient: RecipientOut
    members: list[MemberOut]


class TaskOut(OutModel):
    id: int
    title: str
    category: Category
    due_at: datetime
    status: Literal["pending", "done"]
    notes: str | None
    completed_at: datetime | None
    completed_by: MemberOut | None
    created_at: datetime


class TodayOut(OutModel):
    timezone: str
    now: datetime
    date: date
    recipient: RecipientOut
    overdue: list[TaskOut]
    due: list[TaskOut]
    done: list[TaskOut]


class TaskCreate(InModel):
    title: str = Field(min_length=1, max_length=200)
    category: Category
    due_date: date
    due_time: time
    notes: str | None = Field(default=None, max_length=500)

    @field_validator("notes")
    @classmethod
    def blank_notes(cls, value: str | None) -> str | None:
        if value is None:
            return None
        value = value.strip()
        return value or None


class TaskUpdate(InModel):
    title: str | None = Field(default=None, min_length=1, max_length=200)
    category: Category | None = None
    due_date: date | None = None
    due_time: time | None = None
    notes: str | None = Field(default=None, max_length=500)
    reopen: bool = False

    @field_validator("notes")
    @classmethod
    def blank_notes(cls, value: str | None) -> str | None:
        if value is None:
            return None
        value = value.strip()
        return value or None


class CompleteIn(InModel):
    member_id: int


class AskIn(InModel):
    question: str = Field(min_length=1, max_length=500)
