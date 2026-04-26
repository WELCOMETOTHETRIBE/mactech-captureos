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

Phase 3 Week 16 adds `complete_stream()` for SSE-style live Q&A.
"""

from __future__ import annotations

import logging
import os
from collections.abc import AsyncIterator
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

    async def complete_stream(
        self,
        *,
        system: str,
        user: str,
        complexity: Complexity | None = None,
        max_tokens: int = 600,
        purpose: str | None = None,
    ) -> AsyncIterator[StreamChunk]:
        """Stream the model's reply as it composes.

        Yields a sequence of `StreamChunk(kind="delta", text=...)` events
        followed by exactly one `StreamChunk(kind="final", ...)` carrying
        the assembled text + token usage. Callers who only need the live
        text consume `kind == "delta"` and ignore the final.

        Wraps Anthropic's `messages.stream` context manager — the SDK
        handles SSE parsing, retries, and cleanup; we surface a small,
        loop-friendly view that doesn't leak the SDK's API surface to
        downstream callers.
        """
        model = _model_for(complexity or self._default_complexity)
        async with self._client.messages.stream(
            model=model,
            max_tokens=max_tokens,
            system=system,
            messages=[{"role": "user", "content": user}],
        ) as stream:
            text_parts: list[str] = []
            async for event in stream:
                # Anthropic emits `content_block_delta` events with a
                # text_delta block carrying the actual text. Other event
                # types (message_start, content_block_start, message_stop,
                # ...) are ignored here.
                if getattr(event, "type", None) == "content_block_delta":
                    delta = getattr(event, "delta", None)
                    if delta is not None and getattr(delta, "type", None) == "text_delta":
                        chunk_text = getattr(delta, "text", "")
                        if chunk_text:
                            text_parts.append(chunk_text)
                            yield StreamChunk(kind="delta", text=chunk_text)
            final: Message = await stream.get_final_message()
        yield StreamChunk(
            kind="final",
            text="".join(text_parts).strip(),
            model=final.model,
            input_tokens=final.usage.input_tokens,
            output_tokens=final.usage.output_tokens,
            stop_reason=final.stop_reason,
            purpose=purpose,
        )


@dataclass(frozen=True)
class StreamChunk:
    kind: Literal["delta", "final"]
    text: str
    model: str | None = None
    input_tokens: int | None = None
    output_tokens: int | None = None
    stop_reason: str | None = None
    purpose: str | None = None
