from __future__ import annotations

import datetime as dt

from app.catalog import course_matches
from app.schemas import ExamItem, GetExamsInput, GetExamsOutput
from app.tools._common import load, resolve_range, stamp, visible
from app.tools.base import Tool, ToolContext

DEFAULT_DAYS = 120


class GetExams(Tool):
    name = "get_exams"
    description = (
        "List published exams for the student's own batch, optionally for one "
        "course, in a date range (default: next 120 days). Only published exams "
        "are returned; changes still awaiting publication are never shown."
    )
    input_model = GetExamsInput

    def run(self, ctx: ToolContext, args: GetExamsInput) -> GetExamsOutput:
        meta = load("exams")
        start, end = resolve_range(args.from_date, args.to_date, ctx, DEFAULT_DAYS)
        rows = [r for r in visible(meta["items"], ctx.batch_id)
                if start <= dt.date.fromisoformat(r["date"]) <= end
                and (not args.course or course_matches(r["course"], args.course))]
        rows.sort(key=lambda r: (r["date"], r["start"]))
        at, role = stamp(meta)
        return GetExamsOutput(
            from_date=start, to_date=end, updated_at=at, updated_by_role=role,
            exams=[ExamItem(course=r["course"], exam_type=r["exam_type"], date=r["date"],
                            start=r["start"], duration_min=r["duration_min"], room=r["room"])
                   for r in rows],
        )
