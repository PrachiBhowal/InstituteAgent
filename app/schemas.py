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
    quick_replies: list[str] = Field(default_factory=list)   # UI buttons (Yes/No, choices)
    pending_action: Optional["PendingInfo"] = None            # set while awaiting confirmation


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


# ======================================================================
# Week 3 tools
# ======================================================================
class _Stamped(BaseModel):
    """Every data tool returns who last changed it and when (for answer wording)."""
    updated_at: dt.datetime
    updated_by_role: str


class DateRangeInput(BaseModel):
    from_date: Optional[dt.date] = None   # absolute dates; tool applies a default
    to_date: Optional[dt.date] = None


# ---- get_holidays
class GetHolidaysInput(DateRangeInput):
    pass


class HolidayItem(BaseModel):
    date: dt.date
    name: str


class GetHolidaysOutput(_Stamped):
    from_date: dt.date
    to_date: dt.date
    holidays: list[HolidayItem]


# ---- get_exams
class GetExamsInput(DateRangeInput):
    course: Optional[str] = None


class ExamItem(BaseModel):
    course: str
    exam_type: str
    date: dt.date
    start: dt.time
    duration_min: int
    room: str


class GetExamsOutput(_Stamped):
    from_date: dt.date
    to_date: dt.date
    exams: list[ExamItem]


# ---- get_session_plan
class GetSessionPlanInput(DateRangeInput):
    course: Optional[str] = None


class SessionItem(BaseModel):
    course: str
    date: dt.date
    topics: list[str]


class GetSessionPlanOutput(_Stamped):
    from_date: dt.date
    to_date: dt.date
    sessions: list[SessionItem]


# ---- get_assignments
class GetAssignmentsInput(DateRangeInput):
    course: Optional[str] = None


class AssignmentItem(BaseModel):
    course: str
    title: str
    due_date: dt.date


class GetAssignmentsOutput(_Stamped):
    from_date: dt.date
    to_date: dt.date
    assignments: list[AssignmentItem]


# ---- get_events / register_event
class GetEventsInput(DateRangeInput):
    category: Optional[str] = None


class EventItem(BaseModel):
    id: str
    title: str
    category: str
    date: dt.date
    start: dt.time
    venue: str
    seats_left: Optional[int] = None
    registration_open: bool = True
    already_registered: bool = False


class GetEventsOutput(_Stamped):
    from_date: dt.date
    to_date: dt.date
    events: list[EventItem]


class RegisterEventInput(BaseModel):
    # Either an exact id, or free text to match against event titles.
    # NOTE: there is deliberately NO `confirmed` field. The model cannot confirm
    # on the student's behalf; confirmation is handled by the orchestrator.
    event_id: Optional[str] = None
    event_query: Optional[str] = None


class RegisterEventOutput(_Stamped):
    status: Literal["registered", "already_registered", "full", "closed", "not_found"]
    event: Optional[EventItem] = None
    message: str


# ---- chat additions
class PendingInfo(BaseModel):
    tool: str
    expires_at: dt.datetime


ChatResponse.model_rebuild()
