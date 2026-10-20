"""Stage 1: regex/keyword rules for obvious intents. Free and instant."""
from __future__ import annotations

import datetime as dt
import re
from typing import Optional

from app.router.dates import resolve_date
from app.schemas import RouteDecision

# Order matters: more specific patterns first ("exam schedule" is an exam query).
_RULES: list[tuple[str, str, re.Pattern]] = [
    ("get_schedule", "next_class",
     re.compile(r"\b(next|agli|agla)\s+(class|lecture|period|lec)\b", re.I)),
    ("get_exams", "get_exams", re.compile(r"\b(exams?|examination|tests?|ia\s?\d?|midterms?)\b", re.I)),
    ("get_holidays", "get_holidays", re.compile(r"\b(holidays?|chutti|vacation)\b", re.I)),
    ("get_assignments", "get_assignments",
     re.compile(r"\b(assignments?|homework|deadlines?|due|submission)\b", re.I)),
    ("get_events", "get_events", re.compile(r"\b(events?|hackathon|fest|workshop|seminar)\b", re.I)),
    ("search_notices", "search_notices", re.compile(r"\b(circular|notice|notices|announcement)s?\b", re.I)),
    ("get_schedule", "schedule",
     re.compile(r"\b(schedule|timetable|time\s?table|classes|lectures?|class)\b", re.I)),
]


def build_schedule_params(text: str, today: dt.date) -> tuple[dict, Optional[str]]:
    """Shared by rules and classifier. Returns (params, clarification)."""
    res = resolve_date(text, today)
    if res.ambiguous:
        return {}, "Do you mean yesterday or tomorrow?"
    return {"date": (res.date or today).isoformat()}, None


def match_rules(text: str, today: dt.date) -> Optional[RouteDecision]:
    for intent, kind, pattern in _RULES:
        if not pattern.search(text):
            continue
        if kind == "next_class":
            return RouteDecision(
                intent="get_schedule", tool="get_schedule",
                params={"next_class": True}, confidence=0.95, stage="rules",
            )
        if kind == "schedule":
            params, clar = build_schedule_params(text, today)
            return RouteDecision(
                intent="get_schedule", tool="get_schedule", params=params,
                confidence=0.9, stage="rules", clarification=clar,
            )
        # Other intents: recognised now, tools arrive in Week 3 / Week 7.
        params = {"query": text} if intent == "search_notices" else {}
        return RouteDecision(
            intent=intent, tool=intent, params=params, confidence=0.9, stage="rules",
        )
    return None
