from __future__ import annotations

import datetime as dt

from app.catalog import course_matches
from app.schemas import GetSessionPlanInput, GetSessionPlanOutput, SessionItem
from app.tools._common import load, resolve_range, stamp, visible
from app.tools.base import Tool, ToolContext

DEFAULT_DAYS = 7


class GetSessionPlan(Tool):
    name = "get_session_plan"
    description = (
        "Get the planned topics for upcoming class sessions of the student's "
        "batch, optionally for one course, in a date range (default: next 7 days)."
    )
    input_model = GetSessionPlanInput

    def run(self, ctx: ToolContext, args: GetSessionPlanInput) -> GetSessionPlanOutput:
        meta = load("session_plans")
        start, end = resolve_range(args.from_date, args.to_date, ctx, DEFAULT_DAYS)
        rows = [r for r in visible(meta["items"], ctx.batch_id)
                if start <= dt.date.fromisoformat(r["date"]) <= end
                and (not args.course or course_matches(r["course"], args.course))]
        rows.sort(key=lambda r: (r["date"], r["course"]))
        at, role = stamp(meta)
        return GetSessionPlanOutput(
            from_date=start, to_date=end, updated_at=at, updated_by_role=role,
            sessions=[SessionItem(course=r["course"], date=r["date"], topics=r["topics"])
                      for r in rows],
        )
