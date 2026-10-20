"""Stage 1: regex/keyword rules for obvious intents. Free and instant."""
from __future__ import annotations

import datetime as dt
import re
from typing import Optional

from app.router.params import build_params
from app.schemas import RouteDecision

# Order matters: more specific patterns first.
#   "register me for the hackathon" -> register_event, not get_events
#   "exam schedule"                 -> get_exams, not get_schedule
#   "what will we cover in os"      -> get_session_plan
_RULES: list[tuple[str, re.Pattern]] = [
    ("next_class", re.compile(r"\b(next|agli|agla)\s+(class|lecture|period|lec)\b", re.I)),
    ("register_event", re.compile(
        r"\b(register|registration|sign\s*me\s*up|enrol+|put\s+me\s+(down|in))\b", re.I)),
    ("get_session_plan", re.compile(
        r"(session\s+plan|lesson\s+plan|syllabus|"
        r"\bwhat\s+(will|are|do)\s+(we|i)\s+(cover|covering|learn|learning)\b|"
        r"\btopics?\s+(for|on|in|of)\b)", re.I)),
    ("get_exams", re.compile(r"\b(exams?|examination|tests?|ia\s?\d?|midterms?|viva)\b", re.I)),
    ("get_holidays", re.compile(r"\b(holidays?|chutti|vacation)\b", re.I)),
    ("get_assignments", re.compile(
        r"\b(assignments?|homework|deadlines?|due|submission)\b", re.I)),
    ("get_events", re.compile(r"\b(events?|hackathon|fest|workshops?|seminars?)\b", re.I)),
    ("search_notices", re.compile(r"\b(circular|notice|notices|announcement)s?\b", re.I)),
    ("get_schedule", re.compile(
        r"\b(schedule|timetable|time\s?table|classes|lectures?|class)\b", re.I)),
]


def match_rules(text: str, today: dt.date) -> Optional[RouteDecision]:
    for kind, pattern in _RULES:
        if not pattern.search(text):
            continue
        if kind == "next_class":
            return RouteDecision(
                intent="get_schedule", tool="get_schedule",
                params={"next_class": True}, confidence=0.95, stage="rules")
        params, clar = build_params(kind, text, today)
        return RouteDecision(
            intent=kind, tool=kind, params=params,
            confidence=0.9, stage="rules", clarification=clar)
    return None
