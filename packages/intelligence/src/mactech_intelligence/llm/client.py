"""LLM client abstraction (Mode C — Anthropic commercial API).

Per docs/AGENT_ARCHITECTURE.md, Phase 1 routes all MacTech LLM traffic
through `AnthropicLLMClient` with a single platform API key. Mode A
(Agent SDK on subscription) is deferred to Phase 5; the client surface
here is what Phase 1 callers depend on.

Model selection per docs/DATA_SOURCES.md §4.1:
  - claude-haiku-4-5-20251001  high-volume scoring + classification
  - claude-sonnet-4-6          drafting (Sources Sought, compliance matrices)
  - claude-opus-4-7            deep reasoning, rare

Phase 1 only uses Haiku (scoring) + Sonnet (drafting). The `complexity`
parameter on `complete()` maps to a model selection.
"""

from __future__ import annotations

import logging
import os
from dataclasses import dataclass
from typing import Final, Literal

from anthropic import AsyncAnthropic
from anthropic.types import Message

log = logging.getLogger(__name__)

MODEL_FAST: Final = "claude-haiku-4-5-20251001"
MODEL_SMART: Final = "claude-sonnet-4-6"
MODEL_DEEP: Final = "claude-opus-4-7"

Complexity = Literal["fast", "smart", "deep"]


def _model_for(complexity: Complexity) -> str:
    return {"fast": MODEL_FAST, "smart": MODEL_SMART, "deep": MODEL_DEEP}[complexity]


@dataclass(frozen=True)
class LLMResponse:
    text: str
    model: str
    input_tokens: int
    output_tokens: int
    stop_reason: str | None
    purpose: str | None = None


class AnthropicLLMClient:
    def __init__(
        self,
        *,
        api_key: str | None = None,
        default_complexity: Complexity = "fast",
    ) -> None:
        api_key = api_key or os.environ.get("ANTHROPIC_API_KEY")
        if not api_key:
            raise RuntimeError("ANTHROPIC_API_KEY not set")
        self._client = AsyncAnthropic(api_key=api_key)
        self._default_complexity: Complexity = default_complexity

    async def complete(
        self,
        *,
        system: str,
        user: str,
        complexity: Complexity | None = None,
        max_tokens: int = 600,
        purpose: str | None = None,
    ) -> LLMResponse:
        model = _model_for(complexity or self._default_complexity)
        message: Message = await self._client.messages.create(
            model=model,
            max_tokens=max_tokens,
            system=system,
            messages=[{"role": "user", "content": user}],
        )
        text_parts: list[str] = []
        for block in message.content:
            if getattr(block, "type", None) == "text":
                text_parts.append(getattr(block, "text", ""))
        return LLMResponse(
            text="".join(text_parts).strip(),
            model=message.model,
            input_tokens=message.usage.input_tokens,
            output_tokens=message.usage.output_tokens,
            stop_reason=message.stop_reason,
            purpose=purpose,
        )
