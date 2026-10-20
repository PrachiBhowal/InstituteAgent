"""Turns tool output into the student-facing answer, cards and source line."""
from __future__ import annotations

import datetime as dt
from typing import Optional

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


# ======================================================================
# Week 3 answers
# ======================================================================
from app.schemas import (GetAssignmentsOutput, GetEventsOutput, GetExamsOutput,  # noqa: E402
                         GetHolidaysOutput, GetSessionPlanOutput, RegisterEventOutput)


def _src(label: str, out) -> Source:
    return Source(label=label, updated_at=out.updated_at, updated_by_role=out.updated_by_role)


def _span(out) -> str:
    if out.from_date == out.to_date:
        return _fmt_day(out.from_date)
    return f"{out.from_date.strftime('%d %b')} to {out.to_date.strftime('%d %b %Y')}"


def _list_answer(head, empty, lines, card, source, route) -> ChatResponse:
    if not lines:
        return ChatResponse(answer=empty, source=source, route=route)
    return ChatResponse(answer=head + "\n" + "\n".join(lines),
                        cards=[card], source=source, route=route)


def holidays_answer(out: GetHolidaysOutput, route) -> ChatResponse:
    lines = [f"{h.date.strftime('%a, %d %b')}  {h.name}" for h in out.holidays]
    card = Card(type="holidays", title="Holidays",
                items=[{"date": h.date.isoformat(), "name": h.name} for h in out.holidays])
    return _list_answer(f"Holidays ({_span(out)}):", f"No holidays between {_span(out)}.",
                        lines, card, _src("Holiday calendar", out), route)


def exams_answer(out: GetExamsOutput, route) -> ChatResponse:
    lines = [f"{e.date.strftime('%a, %d %b')} {_fmt_t(e.start)}  {e.course} "
             f"({e.exam_type}, {e.duration_min} min, {e.room})" for e in out.exams]
    card = Card(type="exams", title="Exams", items=[
        {"course": e.course, "type": e.exam_type, "date": e.date.isoformat(),
         "start": _fmt_t(e.start), "duration_min": e.duration_min, "room": e.room}
        for e in out.exams])
    return _list_answer(f"Exams ({_span(out)}):", f"No exams scheduled for {_span(out)}.",
                        lines, card, _src("Exam timetable", out), route)


def session_plan_answer(out: GetSessionPlanOutput, route) -> ChatResponse:
    lines = [f"{s.date.strftime('%a, %d %b')}  {s.course}: {'; '.join(s.topics)}"
             for s in out.sessions]
    card = Card(type="session_plan", title="Session plan", items=[
        {"course": s.course, "date": s.date.isoformat(), "topics": s.topics}
        for s in out.sessions])
    return _list_answer(f"Session plan ({_span(out)}):",
                        f"No session plan has been published for {_span(out)}.",
                        lines, card, _src("Session plan", out), route)


def assignments_answer(out: GetAssignmentsOutput, route) -> ChatResponse:
    lines = [f"{a.due_date.strftime('%a, %d %b')}  {a.course}: {a.title}"
             for a in out.assignments]
    card = Card(type="assignments", title="Assignments", items=[
        {"course": a.course, "title": a.title, "due": a.due_date.isoformat()}
        for a in out.assignments])
    return _list_answer(f"Assignments due ({_span(out)}):",
                        f"Nothing is due between {_span(out)}.",
                        lines, card, _src("Assignments", out), route)


def _event_line(e) -> str:
    extra = ("you're registered" if e.already_registered
             else f"{e.seats_left} seats left" if e.registration_open
             else "registration closed or full")
    return (f"{e.date.strftime('%a, %d %b')} {_fmt_t(e.start)}  {e.title}, "
            f"{e.venue} ({extra})")


def events_answer(out: GetEventsOutput, route) -> ChatResponse:
    card = Card(type="events", title="Events", items=[
        {"id": e.id, "title": e.title, "date": e.date.isoformat(), "start": _fmt_t(e.start),
         "venue": e.venue, "seats_left": e.seats_left,
         "registration_open": e.registration_open, "already_registered": e.already_registered}
        for e in out.events])
    resp = _list_answer(f"Upcoming events ({_span(out)}):", f"No events between {_span(out)}.",
                        [_event_line(e) for e in out.events], card, _src("Events", out), route)
    resp.quick_replies = [f"Register me for {e.title}" for e in out.events
                          if e.registration_open and not e.already_registered][:4]
    return resp


def register_answer(out: RegisterEventOutput, route) -> ChatResponse:
    cards = []
    if out.event:
        cards = [Card(type="event", title=out.event.title, items=[
            {"id": out.event.id, "date": out.event.date.isoformat(),
             "start": _fmt_t(out.event.start), "venue": out.event.venue}])]
    return ChatResponse(answer=out.message, cards=cards,
                        source=_src("Event registration", out), route=route)


def answer_for(out, batch_id: str, route) -> Optional[ChatResponse]:
    """Dispatch a tool output to its formatter. None = unknown output type."""
    if isinstance(out, GetScheduleOutput):
        return schedule_answer(out, batch_id, bool(route.params.get("next_class")), route)
    table = [(GetHolidaysOutput, holidays_answer), (GetExamsOutput, exams_answer),
             (GetSessionPlanOutput, session_plan_answer),
             (GetAssignmentsOutput, assignments_answer), (GetEventsOutput, events_answer),
             (RegisterEventOutput, register_answer)]
    for cls, fn in table:
        if isinstance(out, cls):
            return fn(out, route)
    return None
