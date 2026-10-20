import datetime as dt

from app.schemas import GetScheduleInput
from app.tools.base import ToolContext
from app.tools.get_schedule import GetSchedule
from tests.conftest import IST, NOW

tool = GetSchedule()


def ctx(batch="BATCH-A", now=NOW):
    return ToolContext("S1", batch, now)


def test_tuesday_schedule():
    out = tool.run(ctx(), GetScheduleInput(date=dt.date(2026, 10, 20)))
    assert [e.course for e in out.entries] == ["Computer Networks", "Database Systems"]
    assert out.updated_by_role == "teacher"


def test_weekend_is_empty():
    assert tool.run(ctx(), GetScheduleInput(date=dt.date(2026, 10, 24))).entries == []


def test_unknown_batch_is_empty_not_error():
    assert tool.run(ctx("NOPE"), GetScheduleInput(date=dt.date(2026, 10, 20))).entries == []


def test_next_class_later_today():
    out = tool.run(ctx(), GetScheduleInput(next_class=True))
    assert out.date == dt.date(2026, 10, 20) and out.entries[0].course == "Database Systems"


def test_next_class_rolls_to_next_day_after_hours():
    late = dt.datetime(2026, 10, 20, 18, 0, tzinfo=IST)
    out = tool.run(ctx(now=late), GetScheduleInput(next_class=True))
    assert out.date == dt.date(2026, 10, 21)


def test_next_class_skips_weekend():
    fri_late = dt.datetime(2026, 10, 23, 18, 0, tzinfo=IST)
    out = tool.run(ctx(now=fri_late), GetScheduleInput(next_class=True))
    assert out.date == dt.date(2026, 10, 26)


def test_model_cannot_override_batch():
    # A model-supplied batch_id is not part of the input schema and is ignored.
    args = GetScheduleInput.model_validate({"date": "2026-10-20", "batch_id": "OTHER"})
    assert not hasattr(args, "batch_id")
