import datetime as dt

import pytest

from app.router.dates import resolve_date
from app.router.router import Router

TODAY = dt.date(2026, 10, 20)  # Tuesday
router = Router()


@pytest.mark.parametrize("text,date", [
    ("what's my schedule today", "2026-10-20"),
    ("tomorrow's classes", "2026-10-21"),
    ("friday timetable", "2026-10-23"),
    ("mera aaj ka time table", "2026-10-20"),
    ("timetable", "2026-10-20"),          # no date -> today
])
def test_rules_schedule(text, date):
    d = router.route(text, TODAY)
    assert (d.stage, d.tool) == ("rules", "get_schedule")
    assert d.params["date"] == date and d.confidence >= 0.9


def test_next_class():
    d = router.route("when is my next class?", TODAY)
    assert d.tool == "get_schedule" and d.params == {"next_class": True}


def test_exam_schedule_is_exam_not_timetable():
    assert router.route("exam schedule please", TODAY).tool == "get_exams"


def test_other_intents_recognised():
    assert router.route("any holidays this month", TODAY).tool == "get_holidays"
    assert router.route("what's due this week", TODAY).tool == "get_assignments"
    assert router.route("any hackathon coming", TODAY).tool == "get_events"
    d = router.route("any circular about fees", TODAY)
    assert d.tool == "search_notices" and d.params["query"]


def test_hinglish_kal_asks_clarification():
    d = router.route("kal ka timetable", TODAY)
    assert d.clarification and "yesterday or tomorrow" in d.clarification


def test_classifier_catches_paraphrase_rules_miss():
    d = router.route("which subjects do we have on thursday", TODAY)
    assert d.stage == "classifier" and d.tool == "get_schedule"
    assert d.params["date"] == "2026-10-22"


def test_unknown_goes_to_llm_stage():
    d = router.route("tell me a joke about pigeons", TODAY)
    assert d.tool is None and d.intent == "unknown"


def test_next_weekday_strict():
    assert resolve_date("next tuesday", TODAY).date == dt.date(2026, 10, 27)
    assert resolve_date("tuesday", TODAY).date == TODAY
