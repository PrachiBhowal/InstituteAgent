"""Stage 2: embedding-similarity classifier against example queries per intent.

The embedder is pluggable. The default HashingEmbedder (character n-grams, no
downloads, no network) keeps dev/CI fast and deterministic. In Week 5 swap in
multilingual-e5-small behind the same `embed()` interface and re-tune the
threshold on the eval set.
"""
from __future__ import annotations

import math
import re
import zlib
from typing import Protocol

DIM = 512


class Embedder(Protocol):
    def embed(self, text: str) -> list[float]: ...


class HashingEmbedder:
    def embed(self, text: str) -> list[float]:
        vec = [0.0] * DIM
        for word in re.findall(r"[a-z0-9]+", text.lower()):
            padded = f"#{word}#"
            grams = [padded[i : i + 3] for i in range(max(1, len(padded) - 2))]
            for g in grams + [word]:
                vec[zlib.crc32(g.encode()) % DIM] += 1.0
        norm = math.sqrt(sum(v * v for v in vec)) or 1.0
        return [v / norm for v in vec]


def cosine(a: list[float], b: list[float]) -> float:
    return sum(x * y for x, y in zip(a, b))


# Example queries per intent. Grow these from the eval set.
EXAMPLES: dict[str, list[str]] = {
    "get_schedule": [
        "what classes do I have today",
        "what lectures do I have tomorrow",
        "show my timetable for friday",
        "what is on my schedule this week",
        "mera aaj ka time table kya hai",
        "kya padhai hai aaj",
        "which subjects do we have on monday",
        "am I free tomorrow afternoon",
        "when does my first lecture start",
        "what's happening in college today",
    ],
    "get_exams": [
        "when is the dbms exam",
        "exam dates for this semester",
        "kab hai exam",
        "when do my tests start",
    ],
    "get_holidays": [
        "is there a holiday this month",
        "which days is college closed",
        "diwali vacation dates",
    ],
    "get_assignments": [
        "what assignments are pending",
        "what is due this week",
        "submission deadline for os lab",
    ],
    "get_events": [
        "any events coming up",
        "is there a hackathon this month",
        "upcoming workshops and seminars",
    ],
    "search_notices": [
        "what did the circular say about fees",
        "any notice about scholarship forms",
        "latest announcement from the director",
    ],
}


class IntentClassifier:
    def __init__(self, embedder: Embedder | None = None):
        self.embedder = embedder or HashingEmbedder()
        self._index = [
            (intent, self.embedder.embed(ex))
            for intent, exs in EXAMPLES.items()
            for ex in exs
        ]

    def classify(self, text: str) -> tuple[str, float]:
        q = self.embedder.embed(text)
        best_intent, best = "unknown", 0.0
        for intent, vec in self._index:
            s = cosine(q, vec)
            if s > best:
                best_intent, best = intent, s
        return best_intent, best
