"""Structured plain-English brief extraction.

Phase 3 Week 11 (UX Sprint 4). Takes a SAM.gov opportunity description
(can be 1–10 pages of dense PWS text) plus the opportunity's metadata
and returns four short structured sections that replace the raw `<pre>`
on the detail page:

  - scope_one_sentence: what the agency is buying, in plain English
  - must_have_requirements: explicit reqs (≤6 bullets)
  - nice_to_have: preferences / evaluation criteria (≤4 bullets)
  - red_flags_for_small_biz: things that hurt a 4-person SDVOSB (≤4 bullets)
  - suggested_team_roles: kinds of teammates to add (≤4 bullets)

Generation is **lazy** (button on first detail page view, not auto on
ingest) so the worker cost stays bounded as the corpus grows past 1k opps.
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from mactech_intelligence.llm import AnthropicLLMClient, LLMResponse

log = logging.getLogger(__name__)

PROMPT_PATH = Path(__file__).parent / "prompts" / "extract_brief.md"
PROMPT_VERSION = "v1"
DEFAULT_MAX_TOKENS = 1200
MAX_DESCRIPTION_CHARS = 12000  # Sonnet handles more, but bound for cost.


@dataclass(frozen=True)
class ExtractBriefInput:
    title: str
    agency: str | None
    notice_type: str | None
    set_aside: str | None
    naics_code: str | None
    posted_at: datetime | None
    response_deadline: datetime | None
    description: str


@dataclass(frozen=True)
class StructuredBrief:
    scope_one_sentence: str
    must_have_requirements: list[str]
    nice_to_have: list[str]
    red_flags_for_small_biz: list[str]
    suggested_team_roles: list[str]
    response: LLMResponse
    description_chars: int


class BriefExtractionError(RuntimeError):
    """Raised when the LLM output isn't valid structured JSON."""


def _build_user_message(inp: ExtractBriefInput) -> str:
    desc = inp.description.strip()
    truncated = len(desc) > MAX_DESCRIPTION_CHARS
    if truncated:
        desc = desc[:MAX_DESCRIPTION_CHARS]
    parts = [
        f"Title: {inp.title}",
        f"Agency: {inp.agency or '(unspecified)'}",
        f"Notice type: {inp.notice_type or '(unspecified)'}",
        f"Set-aside: {inp.set_aside or 'unrestricted'}",
        f"NAICS: {inp.naics_code or '(unspecified)'}",
        f"Posted: {inp.posted_at.date().isoformat() if inp.posted_at else '(unspecified)'}",
        f"Response deadline: {inp.response_deadline.date().isoformat() if inp.response_deadline else '(unspecified)'}",
        "",
        "Description:",
        desc,
    ]
    if truncated:
        parts.append(
            f"\n[Note: description truncated at {MAX_DESCRIPTION_CHARS} chars; "
            f"original was {len(inp.description)} chars.]"
        )
    parts.append("\nRespond with the JSON object only.")
    return "\n".join(parts)


def _strip_code_fence(text: str) -> str:
    """Some models wrap JSON in ```json ... ```. Strip if present."""
    text = text.strip()
    if text.startswith("```"):
        # Find first newline, drop the fence start.
        nl = text.find("\n")
        if nl > 0:
            text = text[nl + 1 :]
        if text.endswith("```"):
            text = text[:-3]
    return text.strip()


def _ensure_str_list(v: object, field_name: str, max_len: int = 6) -> list[str]:
    if v is None:
        return []
    if not isinstance(v, list):
        raise BriefExtractionError(f"{field_name} not a list: {type(v).__name__}")
    out: list[str] = []
    for item in v[:max_len]:
        if isinstance(item, str):
            s = item.strip()
            if s:
                out.append(s)
        elif item is None:
            continue
        else:
            out.append(str(item))
    return out


async def extract_structured_brief(
    client: AnthropicLLMClient,
    inp: ExtractBriefInput,
    *,
    max_tokens: int = DEFAULT_MAX_TOKENS,
) -> StructuredBrief:
    system_prompt = PROMPT_PATH.read_text().strip()
    user_message = _build_user_message(inp)
    response = await client.complete(
        system=system_prompt,
        user=user_message,
        complexity="smart",
        max_tokens=max_tokens,
        purpose=f"extract_brief:{PROMPT_VERSION}",
    )

    raw = _strip_code_fence(response.text)
    try:
        data = json.loads(raw)
    except json.JSONDecodeError as exc:
        log.warning(
            "extract_brief got non-JSON output (first 200 chars): %s",
            raw[:200],
        )
        raise BriefExtractionError(f"model output is not valid JSON: {exc.msg}") from exc
    if not isinstance(data, dict):
        raise BriefExtractionError(f"top-level JSON is not an object: {type(data).__name__}")

    scope = data.get("scope_one_sentence")
    if not isinstance(scope, str) or not scope.strip():
        raise BriefExtractionError("missing or empty 'scope_one_sentence' field in extracted brief")

    return StructuredBrief(
        scope_one_sentence=scope.strip(),
        must_have_requirements=_ensure_str_list(
            data.get("must_have_requirements"), "must_have_requirements", max_len=6
        ),
        nice_to_have=_ensure_str_list(data.get("nice_to_have"), "nice_to_have", max_len=4),
        red_flags_for_small_biz=_ensure_str_list(
            data.get("red_flags_for_small_biz"), "red_flags_for_small_biz", max_len=4
        ),
        suggested_team_roles=_ensure_str_list(
            data.get("suggested_team_roles"), "suggested_team_roles", max_len=4
        ),
        response=response,
        description_chars=len(inp.description),
    )
