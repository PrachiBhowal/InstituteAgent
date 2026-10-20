"""get_schedule: STUB backed by mock data.

Week 3: replace _load_entries() with a call to Person A's schedule API.
The input/output schemas stay the same, so nothing else changes.
"""
from __future__ import annotations

import datetime as dt
import json
from pathlib import Path

from app.schemas import GetScheduleInput, GetScheduleOutput, ScheduleEntry
from app.tools.base import Tool, ToolContext

_DATA = Path(__file__).resolve().parent.parent / "mock_data" / "schedule.json"


def _load() -> dict:
    return json.loads(_DATA.read_text())


class GetSchedule(Tool):
    name = "get_schedule"
    description = (
        "Get the class timetable for the student's own batch. Use for questions "
        "about today's/tomorrow's/a specific day's classes, or the next class. "
        "Dates must be absolute (YYYY-MM-DD). Never guess a schedule."
    )
    input_model = GetScheduleInput

    def _entries_for(self, ctx: ToolContext, day: dt.date) -> list[ScheduleEntry]:
        data = _load()
        rows = data["batches"].get(ctx.batch_id, {}).get(str(day.weekday()), [])
        return [
            ScheduleEntry(
                course=r["course"],
                start=dt.time.fromisoformat(r["start"]),
                end=dt.time.fromisoformat(r["end"]),
                room=r["room"],
                teacher=r["teacher"],
                day=day,
            )
            for r in rows
        ]

    def run(self, ctx: ToolContext, args: GetScheduleInput) -> GetScheduleOutput:
        meta = _load()
        stamp = dt.datetime.fromisoformat(meta["updated_at"])
        today = ctx.now.date()

        if args.next_class:
            # Look at today (classes not yet started), then the next 7 days.
            for offset in range(0, 8):
                day = today + dt.timedelta(days=offset)
                entries = self._entries_for(ctx, day)
                if offset == 0:
                    entries = [e for e in entries if e.start > ctx.now.time()]
                if entries:
                    return GetScheduleOutput(
                        date=day, entries=entries[:1],
                        updated_at=stamp, updated_by_role=meta["updated_by_role"],
                    )
            return GetScheduleOutput(
                date=today, entries=[],
                updated_at=stamp, updated_by_role=meta["updated_by_role"],
            )

        day = args.date or today
        return GetScheduleOutput(
            date=day, entries=self._entries_for(ctx, day),
            updated_at=stamp, updated_by_role=meta["updated_by_role"],
        )
