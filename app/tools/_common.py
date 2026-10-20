"""Helpers shared by the mock-backed tools.

Week 3 swap: each tool replaces its `load()` + filtering with a call to
Person A's API. Visibility rules (published only, own batch only) must then be
enforced by that API; keeping them here documents the contract we expect.
"""
from __future__ import annotations

import datetime as dt
import json
from pathlib import Path
from typing import Optional

from app.tools.base import ToolContext

_DIR = Path(__file__).resolve().parent.parent / "mock_data"


def load(name: str) -> dict:
    return json.loads((_DIR / f"{name}.json").read_text())


def stamp(meta: dict) -> tuple[dt.datetime, str]:
    return dt.datetime.fromisoformat(meta["updated_at"]), meta["updated_by_role"]


def visible(items: list[dict], batch_id: str) -> list[dict]:
    """Only published items for this student's batch (or institute-wide)."""
    out = []
    for i in items:
        if i.get("status", "published") != "published":
            continue                      # never expose confirm-before-publish items
        if "batch_id" in i and i["batch_id"] not in (batch_id, "ALL"):
            continue
        if "audience" in i and not ({"ALL", batch_id} & set(i["audience"])):
            continue
        out.append(i)
    return out


def resolve_range(from_date: Optional[dt.date], to_date: Optional[dt.date],
                  ctx: ToolContext, default_days: int) -> tuple[dt.date, dt.date]:
    start = from_date or ctx.now.date()
    end = to_date or (start + dt.timedelta(days=default_days - 1))   # N days incl. start
    if end < start:
        start, end = end, start
    return start, end
