"""get_events (read) and register_event (write, needs confirmation).

MOCK registrations live in-memory in RegistrationStore. Week 4: Person A's
registration API owns capacity and duplicate checks; this class goes away.
"""
from __future__ import annotations

import datetime as dt
import re
import threading
from typing import Optional

from app.schemas import (EventItem, GetEventsInput, GetEventsOutput,
                         RegisterEventInput, RegisterEventOutput)
from app.tools._common import load, resolve_range, stamp, visible
from app.tools.base import Prepared, Tool, ToolContext

DEFAULT_DAYS = 45
_STOP = {"the", "and", "for", "with", "register", "event", "events"}
# Words that appear in many titles. Matching on these alone is too weak to pick an event.
_WEAK = {"day", "workshop", "lecture", "talk", "meet", "fest", "session", "event", "events"}
# Chit-chat around the event name; ignored when looking for unmatched content words.
_FILLER = {"me", "for", "the", "register", "registration", "sign", "up", "i", "want", "to",
           "join", "enrol", "enroll", "enrolled", "put", "my", "name", "down", "in", "please",
           "pls", "a", "an", "on", "can", "you", "kindly", "into", "us", "we", "am", "go"}


class RegistrationStore:
    def __init__(self):
        self._regs: set[tuple[str, str]] = set()
        self._lock = threading.Lock()

    def has(self, student_id: str, event_id: str) -> bool:
        return (student_id, event_id) in self._regs

    def count(self, event_id: str) -> int:
        return sum(1 for _, e in self._regs if e == event_id)

    def add_if_seat(self, student_id: str, event_id: str, base_taken: int, capacity: int) -> bool:
        """Atomic check-and-add so two students can't both take the last seat."""
        with self._lock:
            if base_taken + self.count(event_id) >= capacity:
                return False
            self._regs.add((student_id, event_id))
            return True


def _seats_left(row: dict, store: RegistrationStore) -> int:
    return row["capacity"] - row["registered_count"] - store.count(row["id"])


def _to_item(row: dict, ctx: ToolContext, store: RegistrationStore) -> EventItem:
    seats = _seats_left(row, store)
    deadline = dt.date.fromisoformat(row["registration_deadline"])
    return EventItem(
        id=row["id"], title=row["title"], category=row["category"],
        date=row["date"], start=row["start"], venue=row["venue"],
        seats_left=max(seats, 0),
        registration_open=ctx.now.date() <= deadline and seats > 0,
        already_registered=store.has(ctx.student_id, row["id"]),
    )


class GetEvents(Tool):
    name = "get_events"
    description = (
        "List upcoming institute events visible to the student, optionally "
        "filtered by category (tech, talk, career, social, sports), in a date "
        "range (default: next 45 days). Shows seats left and whether the "
        "student is already registered."
    )
    input_model = GetEventsInput

    def __init__(self, store: Optional[RegistrationStore] = None):
        self.store = store or RegistrationStore()

    def run(self, ctx: ToolContext, args: GetEventsInput) -> GetEventsOutput:
        meta = load("events")
        start, end = resolve_range(args.from_date, args.to_date, ctx, DEFAULT_DAYS)
        rows = [r for r in visible(meta["items"], ctx.batch_id)
                if start <= dt.date.fromisoformat(r["date"]) <= end
                and (not args.category or r["category"] == args.category.lower())]
        rows.sort(key=lambda r: (r["date"], r["start"]))
        at, role = stamp(meta)
        return GetEventsOutput(
            from_date=start, to_date=end, updated_at=at, updated_by_role=role,
            events=[_to_item(r, ctx, self.store) for r in rows],
        )


class RegisterEvent(Tool):
    name = "register_event"
    description = (
        "Register the student for an event. This does NOT register immediately: "
        "the student is shown the details and must confirm first. Pass event_id "
        "if known, otherwise the event name as event_query."
    )
    input_model = RegisterEventInput
    requires_confirmation = True

    def __init__(self, store: Optional[RegistrationStore] = None):
        self.store = store or RegistrationStore()

    # ----- helpers
    def _upcoming(self, ctx: ToolContext) -> list[dict]:
        today = ctx.now.date()
        return [r for r in visible(load("events")["items"], ctx.batch_id)
                if dt.date.fromisoformat(r["date"]) >= today]

    def _match(self, ctx: ToolContext, args: RegisterEventInput) -> list[dict]:
        rows = self._upcoming(ctx)
        if args.event_id:
            return [r for r in rows if r["id"] == args.event_id]
        words = set(re.findall(r"[a-z0-9]+", (args.event_query or "").lower()))
        content = words - _FILLER - _WEAK          # e.g. {"sports"} in "register me for sports day"
        scored = []
        for r in rows:
            toks = {t for t in re.findall(r"[a-z0-9]+", r["title"].lower())
                    if len(t) >= 3 and t not in _STOP}
            hit = toks & words
            if not hit:
                continue
            # Only generic words matched, but the student named something else:
            # they meant a different event ("sports day" must not become "Open Source Day").
            if not (hit - _WEAK) and (content - toks):
                continue
            scored.append((len(hit), r))
        if not scored:
            return []
        best = max(s for s, _ in scored)
        return [r for s, r in scored if s == best]

    def _problem(self, ctx: ToolContext, row: dict) -> Optional[tuple[str, str]]:
        """(status, message) if the student can't register, else None."""
        title = row["title"]
        if self.store.has(ctx.student_id, row["id"]):
            return "already_registered", f"You're already registered for {title}."
        if ctx.now.date() > dt.date.fromisoformat(row["registration_deadline"]):
            return "closed", f"Registration for {title} has closed."
        if _seats_left(row, self.store) <= 0:
            return "full", f"{title} is full."
        return None

    # ----- step 1: nothing changes
    def prepare(self, ctx: ToolContext, args: RegisterEventInput) -> Prepared:
        matches = self._match(ctx, args)
        if not matches:
            return Prepared(ok=False, message=(
                "I couldn't find an upcoming event with that name. "
                "Ask me \"any events coming up\" to see what's open."))
        if len(matches) > 1:
            names = [m["title"] for m in matches]
            return Prepared(
                ok=False,
                message="Which event do you mean: " + " or ".join(names) + "?",
                quick_replies=[f"Register me for {n}" for n in names])
        row = matches[0]
        problem = self._problem(ctx, row)
        if problem:
            return Prepared(ok=False, message=problem[1])
        when = dt.date.fromisoformat(row["date"]).strftime("%a, %d %b")
        return Prepared(
            ok=True, args=RegisterEventInput(event_id=row["id"]),
            summary=f"Register you for {row['title']} on {when} at {row['start']}, {row['venue']}?",
        )

    # ----- step 2: only after the student confirms
    def run(self, ctx: ToolContext, args: RegisterEventInput) -> RegisterEventOutput:
        meta = load("events")
        at, role = stamp(meta)
        matches = self._match(ctx, args)
        if len(matches) != 1:
            return RegisterEventOutput(status="not_found", updated_at=at, updated_by_role=role,
                                       message="I couldn't find that event.")
        row = matches[0]
        problem = self._problem(ctx, row)
        if problem:
            return RegisterEventOutput(status=problem[0], message=problem[1],
                                       event=_to_item(row, ctx, self.store),
                                       updated_at=at, updated_by_role=role)
        ok = self.store.add_if_seat(ctx.student_id, row["id"],
                                    row["registered_count"], row["capacity"])
        item = _to_item(row, ctx, self.store)
        if not ok:   # lost the race for the last seat
            return RegisterEventOutput(status="full", message=f"{row['title']} just filled up.",
                                       event=item, updated_at=at, updated_by_role=role)
        return RegisterEventOutput(status="registered", event=item,
                                   message=f"You're registered for {row['title']}.",
                                   updated_at=at, updated_by_role=role)
