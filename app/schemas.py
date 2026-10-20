from __future__ import annotations

import datetime as dt
from typing import Any, Literal, Optional

from pydantic import BaseModel, Field


# ---------- Routing ----------
class RouteDecision(BaseModel):
    """Typed decision produced by every routing stage."""

    intent: str                       # e.g. "get_schedule", "unknown"
    tool: Optional[str] = None        # registered tool name, or None
    params: dict[str, Any] = Field(default_factory=dict)
    confidence: float = 0.0
    stage: Literal["rules", "classifier", "llm", "none"] = "none"
    clarification: Optional[str] = None  # one question to ask instead of acting


# ---------- Chat API ----------
class ChatRequest(BaseModel):
    message: str = Field(min_length=1, max_length=1000)
    # In production these come from Person A's auth/session, not the client.
    student_id: str
    batch_id: str
    session_id: str = "default"


class Card(BaseModel):
    type: str                          # "schedule" | "contact" ...
    title: str
    items: list[dict[str, Any]] = Field(default_factory=list)


class Source(BaseModel):
    label: str
    updated_at: Optional[dt.datetime] = None
    updated_by_role: Optional[str] = None


class ChatResponse(BaseModel):
    answer: str
    cards: list[Card] = Field(default_factory=list)
    source: Optional[Source] = None
    fallback: bool = False
    route: RouteDecision


# ---------- get_schedule tool ----------
class GetScheduleInput(BaseModel):
    date: Optional[dt.date] = None     # absolute date, already resolved
    next_class: bool = False


class ScheduleEntry(BaseModel):
    course: str
    start: dt.time
    end: dt.time
    room: str
    teacher: str
    day: dt.date


class GetScheduleOutput(BaseModel):
    date: dt.date
    entries: list[ScheduleEntry]
    updated_at: dt.datetime
    updated_by_role: str
