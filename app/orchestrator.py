from __future__ import annotations

import datetime as dt
import json
import logging
import re
import time
from dataclasses import dataclass
from typing import Callable, Optional
from zoneinfo import ZoneInfo

from pydantic import BaseModel

from app import composer
from app.config import Settings
from app.llm.adapter import LLMAdapter
from app.prompts import SYSTEM_PROMPT
from app.router.router import Router
from app.schemas import (ChatRequest, ChatResponse, PendingInfo, RouteDecision, Source)
from app.tools.base import Tool, ToolContext
from app.tools.registry import ToolRegistry

log = logging.getLogger("agent.orchestrator")

_YES = {"yes", "y", "yeah", "yep", "yup", "ok", "okay", "confirm", "confirmed", "sure",
        "go ahead", "do it", "haan", "han", "ha", "haa", "kar do", "theek hai"}
_NO = {"no", "n", "nope", "cancel", "stop", "nahi", "nahin", "mat karo", "never mind", "nevermind"}


def confirmation_of(text: str) -> Optional[bool]:
    """True = yes, False = no, None = something else (treated as a new question)."""
    t = re.sub(r"[^a-z ]+", "", text.lower()).strip()
    if t in _YES:
        return True
    if t in _NO:
        return False
    return None


@dataclass
class PendingAction:
    tool: Tool
    args: BaseModel          # fully resolved by tool.prepare()
    expires_at: dt.datetime


class Orchestrator:
    def __init__(self, settings: Settings, router: Router, registry: ToolRegistry,
                 llm: LLMAdapter, clock: Optional[Callable[[], dt.datetime]] = None):
        self.s, self.router, self.registry, self.llm = settings, router, registry, llm
        tz = ZoneInfo(settings.institute_tz)
        self.clock = clock or (lambda: dt.datetime.now(tz))
        # Keyed by (student_id, session_id). In production use Redis with a TTL.
        self.pending: dict[tuple[str, str], PendingAction] = {}

    # ---------- public ----------
    def handle(self, req: ChatRequest) -> ChatResponse:
        t0 = time.perf_counter()
        now = self.clock()
        ctx = ToolContext(student_id=req.student_id, batch_id=req.batch_id, now=now)

        resp = self._handle_pending(req, ctx)
        if resp is None:
            decision = self.router.route(req.message, now.date())
            resp = self._dispatch(req, ctx, decision)

        log.info(
            "chat stage=%s intent=%s tool=%s conf=%s fallback=%s latency_ms=%d",
            resp.route.stage, resp.route.intent, resp.route.tool,
            resp.route.confidence, resp.fallback, (time.perf_counter() - t0) * 1000,
        )
        return resp

    # ---------- confirm step ----------
    def _handle_pending(self, req: ChatRequest, ctx: ToolContext) -> Optional[ChatResponse]:
        # Any reply consumes the pending action: yes runs it, no cancels it,
        # anything else drops it and is handled as a fresh question.
        pend = self.pending.pop((req.student_id, req.session_id), None)
        if pend is None or ctx.now > pend.expires_at:
            return None
        answer = confirmation_of(req.message)
        route = RouteDecision(intent=pend.tool.name, tool=pend.tool.name,
                              confidence=1.0, stage="rules")
        if answer is None:
            return None
        if answer is False:
            return ChatResponse(answer="Okay, I've cancelled that.", route=route)
        try:
            out = pend.tool.run(ctx, pend.args)
        except Exception as exc:
            log.warning("confirmed_tool_error tool=%s err=%s", pend.tool.name, exc)
            return composer.fallback(self.s, route)
        return composer.answer_for(out, ctx.batch_id, route) or composer.fallback(self.s, route)

    def _propose(self, ctx: ToolContext, req: ChatRequest, tool: Tool,
                 args: BaseModel, route: RouteDecision) -> ChatResponse:
        """Step 1 of a write: nothing changes until the student says yes."""
        prep = tool.prepare(ctx, args)
        if not prep.ok:
            return ChatResponse(answer=prep.message, quick_replies=prep.quick_replies, route=route)
        expires = ctx.now + dt.timedelta(seconds=self.s.pending_ttl_seconds)
        self.pending[(req.student_id, req.session_id)] = PendingAction(tool, prep.args, expires)
        return ChatResponse(
            answer=f"{prep.summary}\nReply Yes to confirm or No to cancel.",
            quick_replies=["Yes", "No"],
            pending_action=PendingInfo(tool=tool.name, expires_at=expires),
            route=route,
        )

    # ---------- routing ----------
    def _dispatch(self, req, ctx, decision: RouteDecision) -> ChatResponse:
        if decision.clarification:
            return composer.clarify(decision.clarification, decision)
        if decision.tool:
            if not self.registry.has(decision.tool):
                return composer.fallback(self.s, decision, "I can't look that up yet.")
            return self._run_direct(req, ctx, decision)
        return self._run_llm(req, ctx, decision)

    def _run_direct(self, req, ctx: ToolContext, d: RouteDecision) -> ChatResponse:
        tool = self.registry.get(d.tool)
        try:
            args = tool.input_model.model_validate(d.params)
            if tool.requires_confirmation:
                return self._propose(ctx, req, tool, args, d)
            out = tool.run(ctx, args)
        except Exception as exc:  # tool errors never reach the student raw
            log.warning("tool_error tool=%s err=%s", d.tool, exc)
            return composer.fallback(self.s, d)
        return composer.answer_for(out, ctx.batch_id, d) or composer.fallback(self.s, d)

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
                        args = tool.input_model.model_validate(call.arguments)
                        route.tool = call.name
                        if tool.requires_confirmation:
                            # The model can ask for a write, never perform it.
                            return self._propose(ctx, req, tool, args, route)
                        out = tool.run(ctx, args)
                        payload = json.loads(out.model_dump_json())
                        if hasattr(out, "updated_at"):
                            source = Source(label=call.name, updated_at=out.updated_at,
                                            updated_by_role=getattr(out, "updated_by_role", None))
                    messages.append({"role": "tool", "tool_call_id": call.id,
                                     "content": json.dumps(payload)})
        except Exception as exc:
            log.warning("llm_path_error err=%s", exc)
            return composer.fallback(self.s, route)
