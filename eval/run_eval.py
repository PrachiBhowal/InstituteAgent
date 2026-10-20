"""Score the router against labelled queries. Run: python -m eval.run_eval"""
import datetime as dt
import json
from pathlib import Path

from app.router.router import Router

router = Router()
today = dt.date(2026, 10, 20)
rows = [json.loads(l) for l in (Path(__file__).parent / "seed_queries.jsonl").read_text().splitlines() if l]

ok, by_stage, misses = 0, {}, []
for r in rows:
    d = router.route(r["q"], today)
    by_stage[d.stage] = by_stage.get(d.stage, 0) + 1
    if d.tool == r["tool"]:
        ok += 1
    else:
        misses.append((r["q"], r["tool"], d.tool, d.confidence))

print(f"routing accuracy: {ok}/{len(rows)}  stages: {by_stage}")
for m in misses:
    print("  MISS:", m)
print("(a miss with expected tool + got None goes to the LLM stage; not an error)")
