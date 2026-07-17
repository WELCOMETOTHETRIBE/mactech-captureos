"""LLM work-package adjudication (Slice 5).

Feeds the ranked evidence (not the raw document) to the LLM and asks it to
decompose the opportunity into bounded work packages, each citing evidence IDs.
The response is parsed to ``AdjudicationResult`` and then run through
``validate_evidence_ids`` so hallucinated citations (and the packages that rest
only on them) are dropped before anything is persisted.
"""

from __future__ import annotations

import json
import logging

from mactech_intelligence.decision.evidence import EvidenceItem, evidence_id_set
from mactech_intelligence.llm import AnthropicLLMClient
from mactech_intelligence.schemas.adjudication import (
    AdjudicationResult,
    validate_evidence_ids,
)

log = logging.getLogger(__name__)

PROMPT_VERSION = "wp-1.0.0"

_SYSTEM = """You are a federal capture analyst for MacTech Solutions, an SDVOSB \
specializing in cybersecurity, RMF/CMMC, and FRCS/OT control-system security.

Decompose the opportunity into bounded WORK PACKAGES MacTech could own — favor \
the cyber/RMF/FRCS scope, not general construction. Rules:
- Cite ONLY evidence_ids from the EVIDENCE list you are given. Never invent an id.
- Every work package MUST reference at least one evidence_id.
- Do not invent contract values, companies, deadlines, or certifications.
- mactech_role is one of: prime, sub, advisor, teammate, required_hire, not_fit.
Return ONLY minified JSON, no prose, matching exactly:
{"customer_need":"","summary":"","work_packages":[{"title":"","scope_category":"",\
"description":"","deliverables":[],"required_roles":[],"required_credentials":[],\
"mactech_role":"sub","confidence":"low","evidence_ids":[]}]}"""


def _build_user_prompt(title: str, evidence: list[EvidenceItem]) -> str:
    lines = [f"OPPORTUNITY TITLE: {title}", "", "EVIDENCE (cite these ids only):"]
    for e in evidence:
        lines.append(f'- {e.evidence_id} [{e.family}] {e.canonical_name}: "{e.snippet}"')
    lines.append("")
    lines.append("Return the JSON now.")
    return "\n".join(lines)


def _extract_json(text: str) -> str:
    t = text.strip()
    if t.startswith("```"):
        t = t.split("```", 2)[1]
        if t.startswith("json"):
            t = t[4:]
    start, end = t.find("{"), t.rfind("}")
    return t[start : end + 1] if start != -1 and end != -1 else t


async def adjudicate_work_packages(
    *,
    title: str,
    evidence: list[EvidenceItem],
    client: AnthropicLLMClient,
) -> tuple[AdjudicationResult, list[str]]:
    """Returns (validated result, rejected evidence ids). Raises on an empty or
    unparseable model response."""
    if not evidence:
        return AdjudicationResult(prompt_version=PROMPT_VERSION), []

    resp = await client.complete(
        system=_SYSTEM,
        user=_build_user_prompt(title, evidence),
        complexity="smart",
        max_tokens=1500,
    )
    raw = _extract_json(resp.text)
    data = json.loads(raw)
    result = AdjudicationResult.model_validate(data)
    result = result.model_copy(update={"prompt_version": PROMPT_VERSION})

    cleaned, rejected = validate_evidence_ids(result, evidence_id_set(evidence))
    if rejected:
        log.info("adjudication dropped %d hallucinated evidence ids", len(rejected))
    return cleaned, rejected
