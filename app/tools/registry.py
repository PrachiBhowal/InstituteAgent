from __future__ import annotations

from app.tools.base import Tool
from app.tools.get_assignments import GetAssignments
from app.tools.get_events import GetEvents, RegisterEvent, RegistrationStore
from app.tools.get_exams import GetExams
from app.tools.get_holidays import GetHolidays
from app.tools.get_schedule import GetSchedule
from app.tools.get_session_plan import GetSessionPlan


def default_tools() -> list[Tool]:
    store = RegistrationStore()   # shared so get_events sees register_event's writes
    return [GetSchedule(), GetHolidays(), GetExams(), GetSessionPlan(),
            GetAssignments(), GetEvents(store), RegisterEvent(store)]


class ToolRegistry:
    def __init__(self, tools: list[Tool] | None = None):
        tools = tools if tools is not None else default_tools()
        self._tools = {t.name: t for t in tools}

    def get(self, name: str) -> Tool | None:
        return self._tools.get(name)

    def has(self, name: str | None) -> bool:
        return name in self._tools

    def specs(self) -> list[dict]:
        return [t.spec() for t in self._tools.values()]
