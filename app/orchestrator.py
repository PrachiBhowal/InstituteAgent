from __future__ import annotations

import datetime as dt
import json
import logging
import time
from typing import Callable, Optional
from zoneinfo import ZoneInfo

from pydantic import ValidationError

from app import composer
from app.config import Settings
from app.llm.adapter import LLMAdapter
from app.prompts import SYSTEM_PROMPT
from app.router.router import Router
from app.schemas import (ChatRequest, ChatResponse, GetScheduleOutput,
                         RouteDecision, Source)
from app.tools.base import ToolContext
from app.tools.registry import ToolRegistry

log = logging.getLogger("agent.orchestrator")


class Orchestrator:
    def __init__(self, settings: Settings, router: Router, registry: ToolRegistry,
                 llm: LLMAdapter, clock: Optional[Callable[[], dt.datetime]] = None):
        self.s, self.router, self.registry, self.llm = settings, router, registry, llm
        tz = ZoneInfo(settings.institute_tz)
        self.clock = clock or (lambda: dt.datetime.now(tz))

    # ---------- public ----------
    def handle(self, req: ChatRequest) -> ChatResponse:
        t0 = time.perf_counter()
        now = self.clock()
        ctx = ToolContext(student_id=req.student_id, batch_id=req.batch_id, now=now)

        decision = self.router.route(req.message, now.date())
        resp = self._dispatch(req, ctx, decision)

        log.info(
            "chat stage=%s intent=%s tool=%s conf=%s fallback=%s latency_ms=%d",
            resp.route.stage, resp.route.intent, resp.route.tool,
            resp.route.confidence, resp.fallback, (time.perf_counter() - t0) * 1000,
        )
        return resp

    # ---------- internals ----------
    def _dispatch(self, req, ctx, decision: RouteDecision) -> ChatResponse:
        if decision.clarification:
            return composer.clarify(decision.clarification, decision)

        if decision.tool:
            if not self.registry.has(decision.tool):
                # Intent understood, tool not built yet (Week 3+).
                return composer.fallback(
                    self.s, decision, "I can't look that up yet.")
            return self._run_direct(ctx, decision)

        return self._run_llm(req, ctx, decision)

    def _run_direct(self, ctx: ToolContext, d: RouteDecision) -> ChatResponse:
        tool = self.registry.get(d.tool)
        try:
            args = tool.input_model.model_validate(d.params)
            out = tool.run(ctx, args)
        except (ValidationError, Exception) as exc:  # tool error never reaches the student raw
            log.warning("tool_error tool=%s err=%s", d.tool, exc)
            return composer.fallback(self.s, d)
        if isinstance(out, GetScheduleOutput):
            return composer.schedule_answer(out, ctx.batch_id, bool(d.params.get("next_class")), d)
        return composer.fallback(self.s, d)

    def _run_llm(self, req: ChatRequest, ctx: ToolContext, base: RouteDecision) -> ChatResponse:
        route = RouteDecision(intent="llm", confidence=base.confidence, stage="llm")
        if not self.llm.available:
            return composer.fallback(self.s, base)

        messages = [
            {"role": "system", "content": SYSTEM_PROMPT.format(
                institute_name=self.s.institute_name, batch_id=ctx.batch_id,
                today=ctx.now.date().isoformat(), weekday=ctx.now.strftime("%A"),
                tz=self.s.institute_tz)},
            {"role": "user", "content": req.message},
        ]
        source: Optional[Source] = None
        calls_made = 0
        try:
            while True:
                result = self.llm.complete(messages, self.registry.specs())
                if not result.tool_calls:
                    if not result.text.strip():
                        return composer.fallback(self.s, route)
                    return ChatResponse(answer=result.text.strip(), source=source, route=route)

                messages.append({
                    "role": "assistant", "content": None,
                    "tool_calls": [{"id": c.id, "type": "function",
                                    "function": {"name": c.name,
                                                 "arguments": json.dumps(c.arguments)}}
                                   for c in result.tool_calls],
                })
                for call in result.tool_calls:
                    calls_made += 1
                    if calls_made > self.s.max_tool_calls:
                        return composer.fallback(self.s, route)
                    tool = self.registry.get(call.name)
                    if tool is None:
                        payload = {"error": "unknown tool"}
                    else:
                        out = tool.run(ctx, tool.input_model.model_validate(call.arguments))
                        payload = json.loads(out.model_dump_json())
                        route.tool = call.name
                        if hasattr(out, "updated_at"):
                            source = Source(label=call.name, updated_at=out.updated_at,
                                            updated_by_role=getattr(out, "updated_by_role", None))
                    messages.append({"role": "tool", "tool_call_id": call.id,
                                     "content": json.dumps(payload)})
        except Exception as exc:
            log.warning("llm_path_error err=%s", exc)
            return composer.fallback(self.s, route)
