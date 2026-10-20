import datetime as dt
from zoneinfo import ZoneInfo

import pytest

from app.config import Settings
from app.llm.adapter import LLMAdapter, LLMResult, ToolCall
from app.orchestrator import Orchestrator
from app.router.router import Router
from app.tools.registry import ToolRegistry

IST = ZoneInfo("Asia/Kolkata")
# Tuesday 20 Oct 2026, 10:00 IST
NOW = dt.datetime(2026, 10, 20, 10, 0, tzinfo=IST)


class ScriptedProvider:
    """Fake LLM that replays a scripted list of LLMResults."""
    available = True

    def __init__(self, script):
        self.script, self.calls = list(script), 0

    def complete(self, messages, tools, model):
        self.calls += 1
        return self.script.pop(0) if self.script else LLMResult(text="")


@pytest.fixture
def settings():
    return Settings(llm_provider="mock", admin_contact_email="admin@test.edu")


def make_orch(settings, provider=None, now=NOW):
    llm = LLMAdapter(settings, provider=provider) if provider else LLMAdapter(settings)
    return Orchestrator(settings, Router(settings.classifier_threshold),
                        ToolRegistry(), llm, clock=lambda: now)


@pytest.fixture
def orch(settings):
    return make_orch(settings)
