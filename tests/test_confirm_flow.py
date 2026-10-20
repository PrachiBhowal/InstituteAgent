import datetime as dt

from fastapi.testclient import TestClient

from app.config import Settings
from app.llm.adapter import LLMAdapter, LLMResult, ToolCall
from app.main import create_app
from app.orchestrator import Orchestrator, confirmation_of
from app.router.router import Router
from app.tools.registry import ToolRegistry
from tests.conftest import NOW, ScriptedProvider


class Clock:
    def __init__(self):
        self.now = NOW

    def __call__(self):
        return self.now


def build(provider=None):
    s = Settings(llm_provider="mock", admin_contact_email="admin@test.edu")
    clock = Clock()
    llm = LLMAdapter(s, provider=provider) if provider else LLMAdapter(s)
    orch = Orchestrator(s, Router(s.classifier_threshold), ToolRegistry(), llm, clock=clock)
    return orch, clock, TestClient(create_app(orch))


def say(client, msg, student="S1", session="sess1", batch="BATCH-A"):
    r = client.post("/chat", json={"message": msg, "student_id": student,
                                   "batch_id": batch, "session_id": session})
    assert r.status_code == 200
    return r.json()


def seats_for(client, title="Hackathon 2026", student="S9"):
    j = say(client, "any events this month", student=student, session="viewer")
    j2 = say(client, "events in november", student=student, session="viewer")
    for card in j["cards"] + j2["cards"]:
        for it in card["items"]:
            if it["title"] == title:
                return it["seats_left"], it["already_registered"]


def test_register_asks_for_confirmation_and_changes_nothing():
    _, _, c = build()
    j = say(c, "register me for the hackathon")
    assert "Hackathon 2026" in j["answer"] and "Yes" in j["answer"]
    assert j["quick_replies"] == ["Yes", "No"]
    assert j["pending_action"]["tool"] == "register_event"
    assert seats_for(c) == (19, False)               # nothing registered yet


def test_yes_registers():
    _, _, c = build()
    say(c, "register me for the hackathon")
    j = say(c, "yes")
    assert "registered for Hackathon 2026" in j["answer"]
    assert seats_for(c, student="S1") == (18, True)


def test_hinglish_haan_confirms():
    _, _, c = build()
    say(c, "register me for the hackathon")
    assert "registered" in say(c, "haan")["answer"]


def test_no_cancels():
    _, _, c = build()
    say(c, "register me for the hackathon")
    assert "cancelled" in say(c, "no")["answer"]
    assert seats_for(c) == (19, False)
    assert "registered" not in say(c, "yes")["answer"]   # nothing left to confirm


def test_unrelated_message_drops_pending():
    _, _, c = build()
    say(c, "register me for the hackathon")
    say(c, "what's my schedule today")                  # new topic
    j = say(c, "yes")                                   # must NOT register
    assert "registered" not in j["answer"]
    assert seats_for(c) == (19, False)


def test_confirmation_expires_after_ttl():
    _, clock, c = build()
    say(c, "register me for the hackathon")
    clock.now = NOW + dt.timedelta(minutes=6)
    assert "registered" not in say(c, "yes")["answer"]
    assert seats_for(c) == (19, False)


def test_other_student_cannot_confirm():
    _, _, c = build()
    say(c, "register me for the hackathon", student="S1", session="a")
    j = say(c, "yes", student="S2", session="a")
    assert "registered" not in j["answer"]
    assert seats_for(c, student="S1") == (19, False)


def test_other_session_cannot_confirm():
    _, _, c = build()
    say(c, "register me for the hackathon", session="a")
    assert "registered" not in say(c, "yes", session="b")["answer"]


def test_double_confirm_does_not_double_register():
    _, _, c = build()
    say(c, "register me for the hackathon")
    say(c, "yes")
    say(c, "yes")
    j = say(c, "register me for the hackathon")
    assert "already registered" in j["answer"] and not j.get("pending_action")
    assert seats_for(c, student="S1") == (18, True)


def test_ambiguous_event_asks_which_with_quick_replies():
    _, _, c = build()
    j = say(c, "register me for the workshop")
    assert "Which event" in j["answer"] and j["pending_action"] is None
    assert "Register me for Robotics Workshop" in j["quick_replies"]
    # follow the quick reply -> it's full
    assert "full" in say(c, "Register me for Robotics Workshop")["answer"]


def test_full_and_closed_events_never_reach_confirm():
    _, _, c = build()
    for q, w in [("register me for the robotics workshop", "full"),
                 ("register me for open source day", "closed")]:
        j = say(c, q)
        assert w in j["answer"] and j["pending_action"] is None


def test_llm_cannot_register_without_confirmation():
    script = [LLMResult(tool_calls=[ToolCall(
        id="1", name="register_event", arguments={"event_query": "hackathon"})])]
    _, _, c = build(ScriptedProvider(script))
    j = say(c, "ugh i guess i should do something about that coding thing")
    assert j["pending_action"]["tool"] == "register_event"
    assert seats_for(c) == (19, False)                  # still nothing happened
    assert "registered for Hackathon" in say(c, "yes")["answer"]


def test_confirmation_word_parsing():
    assert confirmation_of("Yes!") is True and confirmation_of("  okay ") is True
    assert confirmation_of("No.") is False and confirmation_of("nahi") is False
    assert confirmation_of("yes but also tell me the schedule") is None
    assert confirmation_of("hackathon") is None
