"""Course catalog + aliases (MOCK). Week 3+: fetch the batch's courses from Person A's API."""
from __future__ import annotations

import re
from typing import Optional

COURSES = [
    "Database Systems", "Operating Systems", "Computer Networks",
    "Software Engineering", "Python Lab", "Database Lab",
]

# Longest phrases first so "database lab" wins over "database".
_ALIASES: list[tuple[str, str]] = [
    ("database lab", "Database Lab"), ("dbms lab", "Database Lab"),
    ("python lab", "Python Lab"),
    ("software engineering", "Software Engineering"),
    ("operating systems", "Operating Systems"), ("operating system", "Operating Systems"),
    ("computer networks", "Computer Networks"), ("networking", "Computer Networks"),
    ("networks", "Computer Networks"),
    ("database systems", "Database Systems"), ("databases", "Database Systems"),
    ("database", "Database Systems"), ("dbms", "Database Systems"),
    ("python", "Python Lab"),
    ("os", "Operating Systems"), ("cn", "Computer Networks"),
    # NOTE: no "se" alias: it is a common Hinglish word ("se" = "from").
]


def normalize_course(text: str) -> Optional[str]:
    t = " " + re.sub(r"[^a-z0-9 ]+", " ", text.lower()) + " "
    for alias, canon in _ALIASES:
        if f" {alias} " in t:
            return canon
    return None


def course_matches(item_course: str, query: str) -> bool:
    canon = normalize_course(query)
    if canon:
        return item_course == canon
    return query.strip().lower() in item_course.lower()
