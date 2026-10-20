"""Tiny rule-based date resolver (English + a little Hinglish).

Returns absolute dates so tools never receive relative words like "tomorrow".
The LLM path also gets today's date in the prompt, but rules handle the
common cases for free.
"""
from __future__ import annotations

import datetime as dt
import re
from dataclasses import dataclass
from typing import Optional

_DAYS = {
    "monday": 0, "mon": 0, "tuesday": 1, "tue": 1, "tues": 1,
    "wednesday": 2, "wed": 2, "thursday": 3, "thu": 3, "thur": 3, "thurs": 3,
    "friday": 4, "fri": 4, "saturday": 5, "sat": 5, "sunday": 6, "sun": 6,
}


@dataclass
class DateResult:
    date: Optional[dt.date] = None
    ambiguous: bool = False   # e.g. Hinglish "kal" = yesterday OR tomorrow
    found: bool = False


def resolve_date(text: str, today: dt.date) -> DateResult:
    t = text.lower()
    words = re.findall(r"[a-z]+", t)

    if "kal" in words and not any(w in words for w in ("tomorrow", "yesterday")):
        return DateResult(ambiguous=True, found=True)
    if "today" in words or "aaj" in words:
        return DateResult(today, found=True)
    if any(w in words for w in ("tomorrow", "tmrw", "tmr", "tomorow")):
        return DateResult(today + dt.timedelta(days=1), found=True)
    if "yesterday" in words:
        return DateResult(today - dt.timedelta(days=1), found=True)

    for i, w in enumerate(words):
        if w in _DAYS:
            target = _DAYS[w]
            strictly_after = i > 0 and words[i - 1] == "next"
            delta = (target - today.weekday()) % 7
            if strictly_after and delta == 0:
                delta = 7
            return DateResult(today + dt.timedelta(days=delta), found=True)

    # ISO date, e.g. 2026-11-12
    m = re.search(r"\b(\d{4})-(\d{2})-(\d{2})\b", t)
    if m:
        try:
            return DateResult(dt.date(*map(int, m.groups())), found=True)
        except ValueError:
            pass
    return DateResult()
