"""Turns tool output into the student-facing answer, cards and source line."""
from __future__ import annotations

import datetime as dt

from app.config import Settings
from app.schemas import Card, ChatResponse, GetScheduleOutput, RouteDecision, Source


def _fmt_day(d: dt.date) -> str:
    return d.strftime("%a, %d %b %Y")


def _fmt_t(t: dt.time) -> str:
    return t.strftime("%H:%M")


def contact_card(s: Settings) -> Card:
    return Card(
        type="contact",
        title="Contact",
        items=[{
            "name": s.admin_contact_name,
            "email": s.admin_contact_email,
            "phone": s.admin_contact_phone,
        }],
    )


def fallback(s: Settings, route: RouteDecision, reason: str | None = None) -> ChatResponse:
    msg = "I don't have that information. Please contact the admin office."
    if reason:
        msg = f"{reason} Please contact the admin office."
    return ChatResponse(answer=msg, cards=[contact_card(s)], fallback=True, route=route)


def clarify(question: str, route: RouteDecision) -> ChatResponse:
    return ChatResponse(answer=question, route=route)


def schedule_answer(out: GetScheduleOutput, batch_id: str, next_class: bool,
                    route: RouteDecision) -> ChatResponse:
    source = Source(
        label=f"Class schedule ({batch_id})",
        updated_at=out.updated_at, updated_by_role=out.updated_by_role,
    )
    if not out.entries:
        text = ("I couldn't find an upcoming class in the next week."
                if next_class else f"No classes are scheduled for {_fmt_day(out.date)}.")
        return ChatResponse(answer=text, source=source, route=route)

    lines = [f"{_fmt_t(e.start)}–{_fmt_t(e.end)}  {e.course} ({e.room}, {e.teacher})"
             for e in out.entries]
    head = (f"Your next class is on {_fmt_day(out.date)}:" if next_class
            else f"Your classes for {_fmt_day(out.date)}:")
    card = Card(
        type="schedule", title=_fmt_day(out.date),
        items=[{"course": e.course, "start": _fmt_t(e.start), "end": _fmt_t(e.end),
                "room": e.room, "teacher": e.teacher} for e in out.entries],
    )
    return ChatResponse(answer=head + "\n" + "\n".join(lines), cards=[card],
                        source=source, route=route)
