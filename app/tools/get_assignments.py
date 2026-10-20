from __future__ import annotations

import datetime as dt

from app.catalog import course_matches
from app.schemas import AssignmentItem, GetAssignmentsInput, GetAssignmentsOutput
from app.tools._common import load, resolve_range, stamp, visible
from app.tools.base import Tool, ToolContext

DEFAULT_DAYS = 30


class GetAssignments(Tool):
    name = "get_assignments"
    description = (
        "List assignments due in a date range (default: today to 30 days ahead) "
        "for the student's batch, optionally for one course. Past-due items are "
        "excluded unless an earlier from_date is given."
    )
    input_model = GetAssignmentsInput

    def run(self, ctx: ToolContext, args: GetAssignmentsInput) -> GetAssignmentsOutput:
        meta = load("assignments")
        start, end = resolve_range(args.from_date, args.to_date, ctx, DEFAULT_DAYS)
        rows = [r for r in visible(meta["items"], ctx.batch_id)
                if start <= dt.date.fromisoformat(r["due_date"]) <= end
                and (not args.course or course_matches(r["course"], args.course))]
        rows.sort(key=lambda r: (r["due_date"], r["course"]))
        at, role = stamp(meta)
        return GetAssignmentsOutput(
            from_date=start, to_date=end, updated_at=at, updated_by_role=role,
            assignments=[AssignmentItem(course=r["course"], title=r["title"],
                                        due_date=r["due_date"]) for r in rows],
        )
