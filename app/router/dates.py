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


_MONTHS = {
    "january": 1, "jan": 1, "february": 2, "feb": 2, "march": 3, "april": 4,
    "may": 5, "june": 6, "july": 7, "august": 8, "aug": 8, "september": 9,
    "sept": 9, "october": 10, "oct": 10, "november": 11, "nov": 11,
    "december": 12, "dec": 12,
}
# "mar"/"may" short forms are omitted on purpose where they collide with common words.


def _month_bounds(year: int, month: int) -> tuple[dt.date, dt.date]:
    first = dt.date(year, month, 1)
    nxt = dt.date(year + (month == 12), month % 12 + 1, 1)
    return first, nxt - dt.timedelta(days=1)


def resolve_range(text: str, today: dt.date,
                  single: Optional[DateResult] = None) -> Optional[tuple[dt.date, dt.date]]:
    """Return (from, to) for phrases like 'this week', 'next month', 'in november'.

    A single resolved date becomes a one-day range. None means 'no range given';
    the tool then applies its own default.
    """
    single = single or resolve_date(text, today)
    if single.found and single.date:
        return single.date, single.date

    t = text.lower()
    monday = today - dt.timedelta(days=today.weekday())
    if re.search(r"\bthis\s+week\b", t):
        return max(monday, today), monday + dt.timedelta(days=6)   # never reaches into the past
    if re.search(r"\bnext\s+week\b", t):
        return monday + dt.timedelta(days=7), monday + dt.timedelta(days=13)
    if re.search(r"\bthis\s+month\b", t):
        return today, _month_bounds(today.year, today.month)[1]
    if re.search(r"\bnext\s+month\b", t):
        y, m = today.year + (today.month == 12), today.month % 12 + 1
        return _month_bounds(y, m)
    for w in re.findall(r"[a-z]+", t):
        if w in _MONTHS:
            m = _MONTHS[w]
            y = today.year + (1 if m < today.month else 0)
            first, last = _month_bounds(y, m)
            return (max(first, today) if (y, m) == (today.year, today.month) else first), last
    return None
