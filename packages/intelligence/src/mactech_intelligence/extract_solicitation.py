"""Solicitation decoder — compliance + requirements matrix extraction.

Section C of CaptureOS_Requirements.md. Mirrors the
``extract_brief.extract_structured_brief`` pattern so behavior is
predictable and provenance tracking is consistent.

V1: operates on ``OpportunityRaw.description_text`` — typically the
SAM.gov synopsis. The matrices it produces are honest about that scope:
when the real Section L / SOW lives in attached PDFs (common), the
matrices will be partial. V2 (file ingestion + OCR) extends the same
extractor to fuller inputs without changing the schema.
"""

from __future__ import annotations

import hashlib
import json
import logging
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from mactech_db.models.solicitation_extraction import REQUIREMENT_CATEGORIES
from mactech_intelligence.llm import AnthropicLLMClient, LLMResponse

log = logging.getLogger(__name__)

PROMPT_PATH = Path(__file__).parent / "prompts" / "extract_solicitation.md"
PROMPT_VERSION = "v1"
DEFAULT_MAX_TOKENS = 4000

# Bound input cost. Section L can be long but the synopsis is usually <12k.
MAX_DESCRIPTION_CHARS = 24000

# Hard caps on output to keep the prompt's "60 + 80" instruction from
# blowing past sane proposal-team review capacity.
MAX_COMPLIANCE_ITEMS = 60
MAX_REQUIREMENT_ITEMS = 80

# Per-field length caps. Match the prompt's "≤500 chars" / "≤255 chars" rules
# so the model output that respects the prompt fits cleanly into our DB
# columns. Anything longer is truncated with an ellipsis rather than rejected.
MAX_STATEMENT_CHARS = 500
MAX_CITATION_CHARS = 255
MAX_NOTES_CHARS = 500
MAX_ITEM_ID_CHARS = 32


@dataclass(frozen=True)
class ExtractSolicitationInput:
    title: str
    agency: str | None
    notice_type: str | None
    set_aside: str | None
    naics_code: str | None
    posted_at: datetime | None
    response_deadline: datetime | None
    description: str


@dataclass(frozen=True)
class ExtractedComplianceItem:
    item_id: str
    statement: str
    section_l_citation: str | None
    pass_fail: bool
    notes: str | None


@dataclass(frozen=True)
class ExtractedRequirementItem:
    item_id: str
    statement: str
    source_citation: str | None
    category: str


@dataclass(frozen=True)
class SolicitationExtractionResult:
    compliance_items: list[ExtractedComplianceItem]
    requirement_items: list[ExtractedRequirementItem]
    response: LLMResponse
    description_chars: int
    source_text_hash: str


class SolicitationExtractionError(RuntimeError):
    """Raised when the LLM output isn't valid structured JSON."""


def _build_user_message(inp: ExtractSolicitationInput) -> str:
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
        nl = text.find("\n")
        if nl > 0:
            text = text[nl + 1 :]
        if text.endswith("```"):
            text = text[: -3]
    return text.strip()


def _truncate(value: str | None, max_len: int) -> str | None:
    if value is None:
        return None
    s = value.strip()
    if not s:
        return None
    if len(s) <= max_len:
        return s
    return s[: max_len - 1] + "…"


def _normalize_category(value: object) -> str:
    if isinstance(value, str):
        candidate = value.strip().lower()
        if candidate in REQUIREMENT_CATEGORIES:
            return candidate
    return "other"


def _coerce_compliance_item(
    raw: object, fallback_index: int
) -> ExtractedComplianceItem | None:
    if not isinstance(raw, dict):
        return None
    statement = raw.get("statement")
    if not isinstance(statement, str) or not statement.strip():
        return None
    item_id = raw.get("item_id")
    if not isinstance(item_id, str) or not item_id.strip():
        item_id = f"C-{fallback_index + 1}"
    pass_fail_raw = raw.get("pass_fail", False)
    if isinstance(pass_fail_raw, bool):
        pass_fail = pass_fail_raw
    elif isinstance(pass_fail_raw, str):
        pass_fail = pass_fail_raw.strip().lower() in ("true", "yes", "1")
    else:
        pass_fail = False

    return ExtractedComplianceItem(
        item_id=_truncate(item_id, MAX_ITEM_ID_CHARS) or f"C-{fallback_index + 1}",
        statement=_truncate(statement, MAX_STATEMENT_CHARS) or statement[:MAX_STATEMENT_CHARS],
        section_l_citation=_truncate(raw.get("section_l_citation"), MAX_CITATION_CHARS),
        pass_fail=pass_fail,
        notes=_truncate(raw.get("notes"), MAX_NOTES_CHARS),
    )


def _coerce_requirement_item(
    raw: object, fallback_index: int
) -> ExtractedRequirementItem | None:
    if not isinstance(raw, dict):
        return None
    statement = raw.get("statement")
    if not isinstance(statement, str) or not statement.strip():
        return None
    item_id = raw.get("item_id")
    if not isinstance(item_id, str) or not item_id.strip():
        item_id = f"R-{fallback_index + 1}"
    return ExtractedRequirementItem(
        item_id=_truncate(item_id, MAX_ITEM_ID_CHARS) or f"R-{fallback_index + 1}",
        statement=_truncate(statement, MAX_STATEMENT_CHARS) or statement[:MAX_STATEMENT_CHARS],
        source_citation=_truncate(raw.get("source_citation"), MAX_CITATION_CHARS),
        category=_normalize_category(raw.get("category")),
    )


def _hash_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


async def extract_solicitation(
    client: AnthropicLLMClient,
    inp: ExtractSolicitationInput,
    *,
    max_tokens: int = DEFAULT_MAX_TOKENS,
) -> SolicitationExtractionResult:
    """Run Claude on the description and return structured matrices.

    Raises ``SolicitationExtractionError`` on unparseable output.
    Network / API failures bubble up as ordinary exceptions.
    """
    system_prompt = PROMPT_PATH.read_text().strip()
    user_message = _build_user_message(inp)
    response = await client.complete(
        system=system_prompt,
        user=user_message,
        complexity="smart",
        max_tokens=max_tokens,
        purpose=f"extract_solicitation:{PROMPT_VERSION}",
    )

    raw = _strip_code_fence(response.text)
    try:
        data = json.loads(raw)
    except json.JSONDecodeError as exc:
        log.warning(
            "extract_solicitation got non-JSON output (first 200 chars): %s",
            raw[:200],
        )
        raise SolicitationExtractionError(
            f"model output is not valid JSON: {exc.msg}"
        ) from exc

    if not isinstance(data, dict):
        raise SolicitationExtractionError(
            f"top-level JSON is not an object: {type(data).__name__}"
        )

    raw_compliance = data.get("compliance_items") or []
    raw_requirements = data.get("requirement_items") or []
    if not isinstance(raw_compliance, list):
        raise SolicitationExtractionError(
            f"compliance_items not a list: {type(raw_compliance).__name__}"
        )
    if not isinstance(raw_requirements, list):
        raise SolicitationExtractionError(
            f"requirement_items not a list: {type(raw_requirements).__name__}"
        )

    compliance_items: list[ExtractedComplianceItem] = []
    seen_compliance_ids: set[str] = set()
    for idx, raw_item in enumerate(raw_compliance[:MAX_COMPLIANCE_ITEMS]):
        item = _coerce_compliance_item(raw_item, idx)
        if item is None:
            continue
        # De-duplicate by item_id within the matrix.
        unique_id = item.item_id
        suffix = 1
        while unique_id in seen_compliance_ids:
            unique_id = f"{item.item_id}-{suffix}"
            suffix += 1
        if unique_id != item.item_id:
            item = ExtractedComplianceItem(
                item_id=unique_id[:MAX_ITEM_ID_CHARS],
                statement=item.statement,
                section_l_citation=item.section_l_citation,
                pass_fail=item.pass_fail,
                notes=item.notes,
            )
        seen_compliance_ids.add(item.item_id)
        compliance_items.append(item)

    requirement_items: list[ExtractedRequirementItem] = []
    seen_requirement_ids: set[str] = set()
    for idx, raw_item in enumerate(raw_requirements[:MAX_REQUIREMENT_ITEMS]):
        item = _coerce_requirement_item(raw_item, idx)
        if item is None:
            continue
        unique_id = item.item_id
        suffix = 1
        while unique_id in seen_requirement_ids:
            unique_id = f"{item.item_id}-{suffix}"
            suffix += 1
        if unique_id != item.item_id:
            item = ExtractedRequirementItem(
                item_id=unique_id[:MAX_ITEM_ID_CHARS],
                statement=item.statement,
                source_citation=item.source_citation,
                category=item.category,
            )
        seen_requirement_ids.add(item.item_id)
        requirement_items.append(item)

    return SolicitationExtractionResult(
        compliance_items=compliance_items,
        requirement_items=requirement_items,
        response=response,
        description_chars=len(inp.description),
        source_text_hash=_hash_text(inp.description),
    )
