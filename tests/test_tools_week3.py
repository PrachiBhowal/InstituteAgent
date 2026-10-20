import datetime as dt

import pytest

from app.catalog import normalize_course
from app.schemas import (GetAssignmentsInput, GetEventsInput, GetExamsInput,
                         GetHolidaysInput, GetSessionPlanInput, RegisterEventInput)
from app.tools.base import ToolContext
from app.tools.get_assignments import GetAssignments
from app.tools.get_events import GetEvents, RegisterEvent, RegistrationStore
from app.tools.get_exams import GetExams
from app.tools.get_holidays import GetHolidays
from app.tools.get_session_plan import GetSessionPlan
from tests.conftest import IST, NOW

D = dt.date


def ctx(batch="BATCH-A", student="S1", now=NOW):
    return ToolContext(student, batch, now)


# ---------------- holidays
def test_holidays_default_range_sorted_and_excludes_past_and_draft():
    out = GetHolidays().run(ctx(), GetHolidaysInput())
    names = [h.name for h in out.holidays]
    assert names == ["Institute Foundation Day", "Diwali", "Diwali break", "Christmas"]
    assert "Gandhi Jayanti" not in names            # before today
    assert not any("draft" in n.lower() for n in names)


def test_holidays_range_filter():
    out = GetHolidays().run(ctx(), GetHolidaysInput(from_date=D(2026, 11, 1), to_date=D(2026, 11, 30)))
    assert [h.name for h in out.holidays] == ["Diwali", "Diwali break"]
    assert out.updated_by_role == "admin"


def test_holidays_reversed_range_is_swapped():
    out = GetHolidays().run(ctx(), GetHolidaysInput(from_date=D(2026, 11, 30), to_date=D(2026, 11, 1)))
    assert len(out.holidays) == 2


# ---------------- exams
def test_exams_only_published_own_batch():
    out = GetExams().run(ctx(), GetExamsInput())
    assert [e.course for e in out.exams] == ["Database Systems", "Operating Systems", "Computer Networks"]
    # draft SE exam, past viva, and BATCH-B exam are all absent


def test_exams_other_batch_sees_own_only():
    out = GetExams().run(ctx("BATCH-B"), GetExamsInput())
    assert [(e.course, e.room) for e in out.exams] == [("Database Systems", "Hall 3")]


def test_exams_course_alias_filter():
    out = GetExams().run(ctx(), GetExamsInput(course="dbms"))
    assert [e.course for e in out.exams] == ["Database Systems"]


def test_exams_empty_when_course_has_only_draft():
    assert GetExams().run(ctx(), GetExamsInput(course="Software Engineering")).exams == []


# ---------------- session plan
def test_session_plan_default_is_next_7_days():
    out = GetSessionPlan().run(ctx(), GetSessionPlanInput())
    assert {s.date for s in out.sessions} == {D(2026, 10, 20), D(2026, 10, 21)}


def test_session_plan_course_and_date():
    out = GetSessionPlan().run(ctx(), GetSessionPlanInput(
        course="os", from_date=D(2026, 10, 27), to_date=D(2026, 10, 27)))
    assert len(out.sessions) == 1 and "Banker's algorithm" in out.sessions[0].topics


def test_session_plan_hides_draft_and_other_batch():
    out = GetSessionPlan().run(ctx(), GetSessionPlanInput(
        from_date=D(2026, 10, 27), to_date=D(2026, 10, 28)))
    flat = [t for s in out.sessions for t in s.topics]
    assert "Different batch, different plan" not in flat
    assert "Draft topic not yet confirmed" not in flat


# ---------------- assignments
def test_assignments_default_excludes_past_due_and_draft():
    out = GetAssignments().run(ctx(), GetAssignmentsInput())
    titles = [a.title for a in out.assignments]
    assert titles == ["Subnetting worksheet", "ER diagram for a library system",
                      "Process scheduling simulation", "SRS draft"]


def test_assignments_can_look_back_when_asked():
    out = GetAssignments().run(ctx(), GetAssignmentsInput(from_date=D(2026, 10, 1)))
    assert "Past due lab record" in [a.title for a in out.assignments]


def test_assignments_course_filter():
    out = GetAssignments().run(ctx(), GetAssignmentsInput(course="CN"))
    assert [a.title for a in out.assignments] == ["Subnetting worksheet"]


# ---------------- events
def test_events_visibility_audience_and_draft():
    out = GetEvents().run(ctx(), GetEventsInput())
    titles = [e.title for e in out.events]
    assert "Batch B Orientation" not in titles       # other batch's audience
    assert "Sports Day" not in titles                # draft
    assert "Alumni Meet" not in titles               # past
    assert titles[0] == "Open Source Day"            # sorted by date


def test_events_audience_visible_to_its_batch():
    titles = [e.title for e in GetEvents().run(ctx("BATCH-B"), GetEventsInput()).events]
    assert "Batch B Orientation" in titles


def test_events_registration_flags():
    out = {e.title: e for e in GetEvents().run(ctx(), GetEventsInput()).events}
    assert out["Robotics Workshop"].seats_left == 0 and not out["Robotics Workshop"].registration_open
    assert out["Open Source Day"].seats_left == 27 and not out["Open Source Day"].registration_open  # deadline passed
    assert out["Hackathon 2026"].registration_open and out["Hackathon 2026"].seats_left == 19


def test_events_category_filter():
    out = GetEvents().run(ctx(), GetEventsInput(category="career"))
    assert [e.title for e in out.events] == ["Resume Writing Workshop"]


# ---------------- register_event: prepare (no side effects)
@pytest.fixture
def reg():
    store = RegistrationStore()
    return RegisterEvent(store), GetEvents(store), store


def test_prepare_resolves_by_name_and_changes_nothing(reg):
    tool, _, store = reg
    p = tool.prepare(ctx(), RegisterEventInput(event_query="register me for the hackathon"))
    assert p.ok and p.args.event_id == "EV-101" and "Hackathon 2026" in p.summary
    assert store.count("EV-101") == 0


def test_prepare_ambiguous_returns_choices(reg):
    tool, _, _ = reg
    p = tool.prepare(ctx(), RegisterEventInput(event_query="register me for the workshop"))
    assert not p.ok and "Robotics Workshop" in p.message and "Resume Writing Workshop" in p.message
    assert "Register me for Robotics Workshop" in p.quick_replies


def test_prepare_more_specific_name_wins(reg):
    tool, _, _ = reg
    p = tool.prepare(ctx(), RegisterEventInput(event_query="register me for the resume workshop"))
    assert p.ok and p.args.event_id == "EV-106"


@pytest.mark.parametrize("query,word", [
    ("register me for the robotics workshop", "full"),
    ("register me for open source day", "closed"),
    ("register me for sports day", "couldn't find"),          # draft is invisible
    ("register me for batch b orientation", "couldn't find"),  # other batch's event
    ("register me for something unknown", "couldn't find"),
])
def test_prepare_rejections(reg, query, word):
    tool, _, _ = reg
    p = tool.prepare(ctx(), RegisterEventInput(event_query=query))
    assert not p.ok and word in p.message


# ---------------- register_event: run (after confirmation)
def test_run_registers_and_events_reflect_it(reg):
    tool, events, _ = reg
    out = tool.run(ctx(), RegisterEventInput(event_id="EV-101"))
    assert out.status == "registered"
    ev = {e.title: e for e in events.run(ctx(), GetEventsInput()).events}["Hackathon 2026"]
    assert ev.already_registered and ev.seats_left == 18


def test_run_is_idempotent_no_duplicates(reg):
    tool, _, store = reg
    tool.run(ctx(), RegisterEventInput(event_id="EV-101"))
    again = tool.run(ctx(), RegisterEventInput(event_id="EV-101"))
    assert again.status == "already_registered" and store.count("EV-101") == 1


def test_run_rechecks_capacity_last_seat_race():
    store = RegistrationStore()
    tool = RegisterEvent(store)
    # EV-103 has capacity 2 and is already full in the data, so use a nearly-full copy:
    assert store.add_if_seat("S1", "X", base_taken=1, capacity=2) is True
    assert store.add_if_seat("S2", "X", base_taken=1, capacity=2) is False


def test_run_other_batch_event_not_registrable(reg):
    tool, _, store = reg
    out = tool.run(ctx(), RegisterEventInput(event_id="EV-107"))
    assert out.status == "not_found" and store.count("EV-107") == 0


def test_run_rejects_after_deadline():
    late = dt.datetime(2026, 11, 11, 9, 0, tzinfo=IST)
    out = RegisterEvent().run(ctx(now=late), RegisterEventInput(event_id="EV-101"))
    assert out.status == "closed"


def test_register_schema_has_no_confirmed_field():
    assert "confirmed" not in RegisterEventInput.model_fields
    assert RegisterEvent.requires_confirmation is True


# ---------------- catalog
@pytest.mark.parametrize("text,course", [
    ("dbms exam", "Database Systems"), ("OS notes", "Operating Systems"),
    ("database lab record", "Database Lab"), ("computer networks", "Computer Networks"),
    ("python", "Python Lab"), ("kya hai se", None), ("hello", None),
])
def test_normalize_course(text, course):
    assert normalize_course(text) == course
