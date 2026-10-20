"""Turn a user message into tool params. Shared by rules and the classifier."""
from __future__ import annotations

import datetime as dt
from typing import Optional

from app.catalog import normalize_course
from app.router.dates import resolve_date, resolve_range

_RANGE_INTENTS = {"get_holidays", "get_exams", "get_assignments", "get_events", "get_session_plan"}
_COURSE_INTENTS = {"get_exams", "get_assignments", "get_session_plan"}
_DATE_INTENTS = _RANGE_INTENTS | {"get_schedule"}


def build_params(intent: str, text: str, today: dt.date) -> tuple[dict, Optional[str]]:
    """Returns (params, clarification). Dates are always absolute ISO strings."""
    d = resolve_date(text, today)
    if d.ambiguous and intent in _DATE_INTENTS:
        return {}, "Do you mean yesterday or tomorrow?"

    p: dict = {}
    if intent == "get_schedule":
        p["date"] = (d.date or today).isoformat()
    elif intent in _RANGE_INTENTS:
        rng = resolve_range(text, today, d)
        if rng:
            p["from_date"], p["to_date"] = rng[0].isoformat(), rng[1].isoformat()
        if intent in _COURSE_INTENTS:
            course = normalize_course(text)
            if course:
                p["course"] = course
    elif intent == "register_event":
        p["event_query"] = text
    elif intent == "search_notices":
        p["query"] = text
    return p, None
