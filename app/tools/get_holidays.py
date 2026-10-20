from __future__ import annotations

import datetime as dt

from app.schemas import GetHolidaysInput, GetHolidaysOutput, HolidayItem
from app.tools._common import load, resolve_range, stamp, visible
from app.tools.base import Tool, ToolContext

DEFAULT_DAYS = 120


class GetHolidays(Tool):
    name = "get_holidays"
    description = (
        "List institute holidays in a date range (default: the next 120 days). "
        "Dates must be absolute (YYYY-MM-DD). Never guess a holiday."
    )
    input_model = GetHolidaysInput

    def run(self, ctx: ToolContext, args: GetHolidaysInput) -> GetHolidaysOutput:
        meta = load("holidays")
        start, end = resolve_range(args.from_date, args.to_date, ctx, DEFAULT_DAYS)
        rows = [r for r in visible(meta["items"], ctx.batch_id)
                if start <= dt.date.fromisoformat(r["date"]) <= end]
        rows.sort(key=lambda r: r["date"])
        at, role = stamp(meta)
        return GetHolidaysOutput(
            from_date=start, to_date=end, updated_at=at, updated_by_role=role,
            holidays=[HolidayItem(date=r["date"], name=r["name"]) for r in rows],
        )
