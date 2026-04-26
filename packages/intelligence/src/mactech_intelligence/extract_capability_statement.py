"""Capability statement field extraction from raw document text.

Phase 3 Week 14 (UX Sprint 7). Backs the PDF upload flow on /library
for capability statements. PDF text in → structured JSON for the
capability_statements table out.
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from pathlib import Path

from mactech_intelligence.llm import AnthropicLLMClient, LLMResponse

log = logging.getLogger(__name__)

PROMPT_PATH = Path(__file__).parent / "prompts" / "extract_capability_statement.md"
PROMPT_VERSION = "v1"
DEFAULT_MAX_TOKENS = 1500
MAX_TEXT_CHARS = 25_000


class CapabilityExtractionError(RuntimeError):
    pass


@dataclass(frozen=True)
class ExtractedCapabilityStatement:
    title: str
    summary: str
    keywords: list[str] = field(default_factory=list)
    related_naics: list[str] = field(default_factory=list)
    related_founder_slugs: list[str] = field(default_factory=list)
    response: LLMResponse | None = None
    text_chars: int = 0


def _strip_code_fence(text: str) -> str:
    text = text.strip()
    if text.startswith("```"):
        nl = text.find("\n")
        if nl > 0:
            text = text[nl + 1 :]
        if text.endswith("```"):
            text = text[: -3]
    return text.strip()


def _coerce_str_list(v: object, max_len: int, max_item_chars: int = 60) -> list[str]:
    if not isinstance(v, list):
        return []
    out: list[str] = []
    for item in v[:max_len]:
        if isinstance(item, str):
            s = item.strip()
            if s:
                out.append(s[:max_item_chars])
    return out


async def extract_capability_statement(
    client: AnthropicLLMClient,
    text: str,
    *,
    max_tokens: int = DEFAULT_MAX_TOKENS,
) -> ExtractedCapabilityStatement:
    text = (text or "").strip()
    if len(text) < 30:
        raise CapabilityExtractionError(
            f"document text is too short ({len(text)} chars) to extract anything meaningful"
        )
    truncated = len(text) > MAX_TEXT_CHARS
    body = text[:MAX_TEXT_CHARS] if truncated else text

    system_prompt = PROMPT_PATH.read_text().strip()
    user_message = (
        "Extract the structured capability statement JSON from the document below. "
        "Return JSON only.\n\n"
        f"Document text ({'truncated' if truncated else 'full'}, "
        f"{len(body)} chars):\n\n{body}"
    )
    response = await client.complete(
        system=system_prompt,
        user=user_message,
        complexity="smart",
        max_tokens=max_tokens,
        purpose=f"extract_capability_statement:{PROMPT_VERSION}",
    )

    raw = _strip_code_fence(response.text)
    try:
        data = json.loads(raw)
    except json.JSONDecodeError as exc:
        log.warning(
            "extract_capability_statement got non-JSON output (first 200 chars): %s",
            raw[:200],
        )
        raise CapabilityExtractionError(
            f"model output is not valid JSON: {exc.msg}"
        ) from exc
    if not isinstance(data, dict):
        raise CapabilityExtractionError(
            f"top-level JSON is not an object: {type(data).__name__}"
        )

    title = data.get("title")
    if not isinstance(title, str) or not title.strip():
        raise CapabilityExtractionError("missing or empty 'title' field")
    summary = data.get("summary")
    if not isinstance(summary, str) or not summary.strip():
        raise CapabilityExtractionError("missing or empty 'summary' field")

    return ExtractedCapabilityStatement(
        title=title.strip()[:255],
        summary=summary.strip(),
        keywords=_coerce_str_list(data.get("keywords"), max_len=10),
        related_naics=_coerce_str_list(
            data.get("related_naics"), max_len=6, max_item_chars=8
        ),
        related_founder_slugs=_coerce_str_list(
            data.get("related_founder_slugs"), max_len=4
        ),
        response=response,
        text_chars=len(text),
    )
