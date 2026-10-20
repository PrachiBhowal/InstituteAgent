from __future__ import annotations

import datetime as dt
from dataclasses import dataclass
from typing import Any, ClassVar, Type

from pydantic import BaseModel


@dataclass(frozen=True)
class ToolContext:
    """Injected server-side. The model can never override these."""

    student_id: str
    batch_id: str
    now: dt.datetime  # timezone-aware, institute timezone


class Tool:
    name: ClassVar[str]
    description: ClassVar[str]
    input_model: ClassVar[Type[BaseModel]]

    def run(self, ctx: ToolContext, args: BaseModel) -> BaseModel:  # pragma: no cover
        raise NotImplementedError

    @classmethod
    def spec(cls) -> dict[str, Any]:
        """JSON-schema spec handed to the LLM for tool calling."""
        return {
            "name": cls.name,
            "description": cls.description,
            "parameters": cls.input_model.model_json_schema(),
        }
