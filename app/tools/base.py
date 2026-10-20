from __future__ import annotations

import datetime as dt
from dataclasses import dataclass, field
from typing import Any, ClassVar, Optional, Type

from pydantic import BaseModel


@dataclass(frozen=True)
class ToolContext:
    """Injected server-side. The model can never override these."""

    student_id: str
    batch_id: str
    now: dt.datetime  # timezone-aware, institute timezone


@dataclass
class Prepared:
    """Result of the 'prepare' step of a write tool (nothing has changed yet)."""

    ok: bool
    args: Optional[BaseModel] = None   # fully resolved args to execute on confirmation
    summary: str = ""                  # what will happen, shown to the student
    message: str = ""                  # shown instead of a prompt when ok is False
    quick_replies: list[str] = field(default_factory=list)


class Tool:
    name: ClassVar[str]
    description: ClassVar[str]
    input_model: ClassVar[Type[BaseModel]]
    # Write tools never run directly. The orchestrator calls prepare(), shows the
    # summary, and only calls run() after the student explicitly confirms.
    requires_confirmation: ClassVar[bool] = False

    def run(self, ctx: ToolContext, args: BaseModel) -> BaseModel:  # pragma: no cover
        raise NotImplementedError

    def prepare(self, ctx: ToolContext, args: BaseModel) -> Prepared:  # pragma: no cover
        raise NotImplementedError

    @classmethod
    def spec(cls) -> dict[str, Any]:
        """JSON-schema spec handed to the LLM for tool calling."""
        return {
            "name": cls.name,
            "description": cls.description,
            "parameters": cls.input_model.model_json_schema(),
        }
