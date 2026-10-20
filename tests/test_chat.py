from fastapi.testclient import TestClient

from app.llm.adapter import LLMResult, ToolCall
from app.main import create_app
from tests.conftest import ScriptedProvider, make_orch

BODY = {"student_id": "S1", "batch_id": "BATCH-A"}


def chat(orch, msg):
    client = TestClient(create_app(orch))
    r = client.post("/chat", json={**BODY, "message": msg})
    assert r.status_code == 200
    return r.json()


def test_round_trip_schedule(orch):
    j = chat(orch, "what's my schedule today")
    assert "Computer Networks" in j["answer"] and "Database Systems" in j["answer"]
    assert j["cards"][0]["type"] == "schedule"
    assert j["source"]["updated_by_role"] == "teacher"
    assert j["route"]["stage"] == "rules" and not j["fallback"]


def test_next_class_answer(orch):
    j = chat(orch, "next class?")
    assert "11:30" in j["answer"] and "Database Systems" in j["answer"]


def test_no_classes_day(orch):
    j = chat(orch, "timetable for saturday")
    assert "No classes" in j["answer"]


def test_clarification_asked_once(orch):
    j = chat(orch, "kal ka timetable")
    assert "yesterday or tomorrow" in j["answer"] and not j["cards"]


def test_unbuilt_tool_falls_back_with_contact(orch):
    j = chat(orch, "any circular about fees")
    assert j["fallback"] and j["cards"][0]["type"] == "contact"
    assert j["cards"][0]["items"][0]["email"] == "admin@test.edu"


def test_unknown_with_mock_llm_falls_back(orch):
    j = chat(orch, "tell me a joke about pigeons")
    assert j["fallback"]


def test_empty_message_rejected(orch):
    client = TestClient(create_app(orch))
    assert client.post("/chat", json={**BODY, "message": ""}).status_code == 422


def test_health(orch):
    assert TestClient(create_app(orch)).get("/health").json()["llm_configured"] is False


def test_llm_tool_calling_loop(settings):
    script = [
        LLMResult(tool_calls=[ToolCall(id="1", name="get_schedule",
                                       arguments={"date": "2026-10-21", "batch_id": "HACK"})]),
        LLMResult(text="Tomorrow you have OS and Software Engineering."),
    ]
    prov = ScriptedProvider(script)
    j = chat(make_orch(settings, prov), "plan my revision around whatever is happening next")
    assert j["route"]["stage"] == "llm" and j["route"]["tool"] == "get_schedule"
    assert "Software Engineering" in j["answer"] and j["source"] is not None
    assert prov.calls == 2


def test_llm_tool_call_cap(settings):
    many = [LLMResult(tool_calls=[ToolCall(id=str(i), name="get_schedule",
            arguments={"date": "2026-10-21"})]) for i in range(10)]
    j = chat(make_orch(settings, ScriptedProvider(many)), "weird multi part question xyz")
    assert j["fallback"]


def test_llm_exception_falls_back(settings):
    class Boom:
        available = True
        def complete(self, *a, **k): raise RuntimeError("provider down")
    j = chat(make_orch(settings, Boom()), "weird question xyz")
    assert j["fallback"] and "provider down" not in j["answer"]
