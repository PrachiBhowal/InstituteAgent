from __future__ import annotations

import logging

from fastapi import FastAPI

from app.config import get_settings
from app.llm.adapter import LLMAdapter
from app.orchestrator import Orchestrator
from app.router.router import Router
from app.schemas import ChatRequest, ChatResponse
from app.tools.registry import ToolRegistry

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(message)s")


def create_app(orchestrator: Orchestrator | None = None) -> FastAPI:
    app = FastAPI(title="Institute Agent")
    s = get_settings()
    orch = orchestrator or Orchestrator(
        s, Router(s.classifier_threshold), ToolRegistry(), LLMAdapter(s))

    @app.get("/health")
    def health():
        return {"status": "ok", "llm_configured": orch.llm.available}

    @app.post("/chat", response_model=ChatResponse)
    def chat(req: ChatRequest) -> ChatResponse:
        return orch.handle(req)

    return app


app = create_app()
