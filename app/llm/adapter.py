"""Single entry point for all LLM calls. Swap provider/model via .env only."""
from __future__ import annotations

import json
import logging
from typing import Any, Optional, Protocol

import httpx
from pydantic import BaseModel, Field

from app.config import Settings

log = logging.getLogger("agent.llm")


class ToolCall(BaseModel):
    id: str
    name: str
    arguments: dict[str, Any] = Field(default_factory=dict)


class LLMResult(BaseModel):
    text: str = ""
    tool_calls: list[ToolCall] = Field(default_factory=list)
    prompt_tokens: int = 0
    completion_tokens: int = 0


class LLMProvider(Protocol):
    def complete(
        self, messages: list[dict], tools: list[dict], model: str
    ) -> LLMResult: ...


class MockProvider:
    """No network. Used until LLM_API_KEY is configured, and in CI."""

    available = False

    def complete(self, messages, tools, model) -> LLMResult:
        return LLMResult(text="")


class OpenAICompatibleProvider:
    """Works with any provider exposing an OpenAI-style /chat/completions API."""

    available = True

    def __init__(self, api_key: str, base_url: str, timeout: float = 20.0):
        self._client = httpx.Client(
            base_url=base_url.rstrip("/"),
            headers={"Authorization": f"Bearer {api_key}"},
            timeout=timeout,
        )

    def complete(self, messages, tools, model) -> LLMResult:
        payload: dict[str, Any] = {"model": model, "messages": messages}
        if tools:
            payload["tools"] = [{"type": "function", "function": t} for t in tools]
        resp = self._client.post("/chat/completions", json=payload)
        resp.raise_for_status()
        data = resp.json()
        msg = data["choices"][0]["message"]
        calls = []
        for tc in msg.get("tool_calls") or []:
            calls.append(
                ToolCall(
                    id=tc["id"],
                    name=tc["function"]["name"],
                    arguments=json.loads(tc["function"].get("arguments") or "{}"),
                )
            )
        usage = data.get("usage", {})
        return LLMResult(
            text=msg.get("content") or "",
            tool_calls=calls,
            prompt_tokens=usage.get("prompt_tokens", 0),
            completion_tokens=usage.get("completion_tokens", 0),
        )


class LLMAdapter:
    def __init__(self, settings: Settings, provider: Optional[LLMProvider] = None):
        self.settings = settings
        self.provider = provider or self._build_provider(settings)

    @staticmethod
    def _build_provider(s: Settings) -> LLMProvider:
        if s.llm_provider == "openai_compatible" and s.llm_api_key and s.llm_base_url:
            return OpenAICompatibleProvider(s.llm_api_key, s.llm_base_url)
        if s.llm_provider != "mock":
            log.warning("LLM provider %r not fully configured; using mock", s.llm_provider)
        return MockProvider()

    @property
    def available(self) -> bool:
        return bool(getattr(self.provider, "available", True))

    def complete(self, messages, tools=None, fast: bool = False) -> LLMResult:
        model = self.settings.llm_model_fast if fast else self.settings.llm_model_main
        result = self.provider.complete(messages, tools or [], model)
        # Token usage is logged on every call from day one (cost control).
        log.info(
            "llm_call model=%s prompt_tokens=%s completion_tokens=%s",
            model, result.prompt_tokens, result.completion_tokens,
        )
        return result
