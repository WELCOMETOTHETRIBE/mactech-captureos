"""Past-performance field extraction from raw document text.

Phase 3 Week 13 (UX Sprint 6). Backs the PDF upload flow on /library:
PDF text in → structured JSON for the past_performance table out.

The web side parses the PDF (PyMuPDF) and posts the extracted text;
the API calls Claude Sonnet with a strict JSON schema.
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path

from mactech_intelligence.llm import AnthropicLLMClient, LLMResponse

log = logging.getLogger(__name__)

PROMPT_PATH = Path(__file__).parent / "prompts" / "extract_past_performance.md"
PROMPT_VERSION = "v1"
DEFAULT_MAX_TOKENS = 1500
MAX_TEXT_CHARS = 25_000


class PastPerformanceExtractionError(RuntimeError):
    pass


@dataclass(frozen=True)
class ExtractedPastPerformance:
    title: str
    customer_agency: str | None
    customer_office: str | None
    contract_number: str | None
    role: str
    period_start: date | None
    period_end: date | None
    contract_value: float | None
    naics_code: str | None
    summary: str
    keywords: list[str] = field(default_factory=list)
    response: LLMResponse | None = None
    text_chars: int = 0


def _strip_code_fence(text: str) -> str:
    text = text.strip()
    if text.startswith("```"):
        nl = text.find("\n")
        if nl > 0:
            text = text[nl + 1 :]
        if text.endswith("```"):
            text = text[:-3]
    return text.strip()


def _parse_date(v: object) -> date | None:
    if not v or not isinstance(v, str):
        return None
    try:
        return date.fromisoformat(v[:10])
    except ValueError:
        return None


def _parse_float(v: object) -> float | None:
    if v is None:
        return None
    if isinstance(v, (int, float)):
        return float(v)
    if isinstance(v, str):
        cleaned = v.replace("$", "").replace(",", "").strip()
        try:
            return float(cleaned)
        except ValueError:
            return None
    return None


def _coerce_keywords(v: object) -> list[str]:
    if not isinstance(v, list):
        return []
    out: list[str] = []
    for item in v[:8]:
        if isinstance(item, str):
            s = item.strip()
            if s:
                out.append(s[:60])
    return out


VALID_ROLES = {"prime", "sub", "joint_venture", "individual"}


async def extract_past_performance(
    client: AnthropicLLMClient,
    text: str,
    *,
    max_tokens: int = DEFAULT_MAX_TOKENS,
) -> ExtractedPastPerformance:
    text = (text or "").strip()
    if len(text) < 30:
        raise PastPerformanceExtractionError(
            "document text is too short to extract anything meaningful "
            f"({len(text)} chars). Try a richer source document."
        )
    truncated = len(text) > MAX_TEXT_CHARS
    body = text[:MAX_TEXT_CHARS] if truncated else text

    system_prompt = PROMPT_PATH.read_text().strip()
    user_message = (
        "Extract the structured past-performance JSON from the document below. "
        "Return JSON only.\n\n"
        f"Document text ({'truncated' if truncated else 'full'}, "
        f"{len(body)} chars):\n\n{body}"
    )
    response = await client.complete(
        system=system_prompt,
        user=user_message,
        complexity="smart",
        max_tokens=max_tokens,
        purpose=f"extract_past_performance:{PROMPT_VERSION}",
    )

    raw = _strip_code_fence(response.text)
    try:
        data = json.loads(raw)
    except json.JSONDecodeError as exc:
        log.warning(
            "extract_past_performance got non-JSON output (first 200 chars): %s",
            raw[:200],
        )
        raise PastPerformanceExtractionError(f"model output is not valid JSON: {exc.msg}") from exc
    if not isinstance(data, dict):
        raise PastPerformanceExtractionError(
            f"top-level JSON is not an object: {type(data).__name__}"
        )

    title = data.get("title")
    if not isinstance(title, str) or not title.strip():
        raise PastPerformanceExtractionError("missing or empty 'title' field")

    summary = data.get("summary")
    if not isinstance(summary, str) or not summary.strip():
        raise PastPerformanceExtractionError("missing or empty 'summary' field")

    role = data.get("role") or "prime"
    if not isinstance(role, str) or role not in VALID_ROLES:
        role = "prime"

    return ExtractedPastPerformance(
        title=title.strip()[:255],
        customer_agency=(
            data.get("customer_agency").strip()[:255]
            if isinstance(data.get("customer_agency"), str) and data.get("customer_agency").strip()
            else None
        ),
        customer_office=(
            data.get("customer_office").strip()[:255]
            if isinstance(data.get("customer_office"), str) and data.get("customer_office").strip()
            else None
        ),
        contract_number=(
            data.get("contract_number").strip()[:64]
            if isinstance(data.get("contract_number"), str) and data.get("contract_number").strip()
            else None
        ),
        role=role,
        period_start=_parse_date(data.get("period_start")),
        period_end=_parse_date(data.get("period_end")),
        contract_value=_parse_float(data.get("contract_value")),
        naics_code=(
            str(data.get("naics_code")).strip()[:8]
            if data.get("naics_code") not in (None, "")
            else None
        ),
        summary=summary.strip(),
        keywords=_coerce_keywords(data.get("keywords")),
        response=response,
        text_chars=len(text),
    )
