"""Typed-decision router. Cheapest stage first; every stage returns RouteDecision."""
from __future__ import annotations

import datetime as dt

from app.router.classifier import IntentClassifier
from app.router.rules import build_schedule_params, match_rules
from app.schemas import RouteDecision


class Router:
    def __init__(self, threshold: float = 0.55, classifier: IntentClassifier | None = None):
        self.threshold = threshold
        self.classifier = classifier or IntentClassifier()

    def route(self, text: str, today: dt.date) -> RouteDecision:
        # Stage 1: rules
        decision = match_rules(text, today)
        if decision:
            return decision

        # Stage 2: classifier
        intent, score = self.classifier.classify(text)
        if intent != "unknown" and score >= self.threshold:
            params, clar = {}, None
            if intent == "get_schedule":
                params, clar = build_schedule_params(text, today)
            elif intent == "search_notices":
                params = {"query": text}
            return RouteDecision(
                intent=intent, tool=intent, params=params,
                confidence=round(score, 3), stage="classifier", clarification=clar,
            )

        # Unresolved: orchestrator escalates to the LLM (stage 3).
        return RouteDecision(intent="unknown", confidence=round(score, 3), stage="none")
