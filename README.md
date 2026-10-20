# Institute Agent (Person B), Weeks 2-3

FastAPI agent service: router (rules -> classifier -> LLM), tool layer, orchestrator.

## Run
```
pip install -r requirements.txt
cp .env.example .env        # add LLM_API_KEY later; works without it (mock mode)
uvicorn app.main:app --reload
pytest -q
python -m eval.run_eval
```
Try it:
```
curl -X POST localhost:8000/chat -H 'content-type: application/json' \
  -d '{"message":"what is my schedule today","student_id":"S1","batch_id":"BATCH-A"}'
```

## Turning on the real LLM
In `.env`: `LLM_PROVIDER=openai_compatible`, `LLM_BASE_URL`, `LLM_API_KEY`, `LLM_MODEL_MAIN`.
Without these the service runs in mock mode: rules and classifier work, unknown queries get the fallback.

## Layout
- `app/router/` rules.py (stage 1), classifier.py (stage 2), router.py, dates.py
- `app/tools/` base.py, get_schedule.py (STUB, mock data), registry.py
- `app/llm/adapter.py` single place for all LLM calls (+ token logging)
- `app/orchestrator.py` routing -> tool/LLM -> composed answer or fallback
- `eval/` labelled queries + scorer

## Tools (Week 3)
get_schedule, get_holidays, get_exams, get_session_plan, get_assignments, get_events (read);
register_event (write). All are mock-backed (`app/mock_data/*.json`), swap each `run()` for Person A's API.

## Confirm-before-write
`register_event.prepare()` resolves the event and checks capacity/deadline/duplicates, changing nothing.
The orchestrator stores a pending action (5 min TTL, keyed by student + session) and asks Yes/No.
Only an explicit yes runs `register_event.run()`, which re-checks capacity. The LLM can request
a write but never perform one; the tool schema has no `confirmed` field.

## Rules the tools enforce (Person A's API must match)
Published items only (drafts never shown), own batch only, `updated_at` + `updated_by_role` on every response.
