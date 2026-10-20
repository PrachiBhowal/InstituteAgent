from __future__ import annotations

from app.tools.base import Tool
from app.tools.get_schedule import GetSchedule


class ToolRegistry:
    def __init__(self, tools: list[Tool] | None = None):
        tools = tools if tools is not None else [GetSchedule()]
        self._tools = {t.name: t for t in tools}

    def get(self, name: str) -> Tool | None:
        return self._tools.get(name)

    def has(self, name: str | None) -> bool:
        return name in self._tools

    def specs(self) -> list[dict]:
        return [t.spec() for t in self._tools.values()]
