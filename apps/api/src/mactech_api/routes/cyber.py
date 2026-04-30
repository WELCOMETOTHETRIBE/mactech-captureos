"""Cyber summary per opportunity.

Section C.8/C.10 + B.6 of CaptureOS_Requirements.md. Reads the opportunity's
description (and brief, when available) for FAR/DFARS clauses and CMMC
level mentions, pulls the tenant's current cyber posture from the SPRS
columns (already synced from Codex by the daily refresh task), and
returns a sufficiency assessment.

Endpoint:

  GET /opportunities/{id}/cyber-summary
      Returns clauses_identified, cmmc_level_required, handles_*,
      posture_snapshot, and sufficiency. Inline regex extraction — no
      external calls. Cheap, safe to call on every page load.
"""

from __future__ import annotations

import logging
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, ConfigDict
from sqlalchemy import select

from mactech_api.auth import RequestContext, get_request_context
from mactech_db.models import OpportunityBrief, OpportunityRaw
from mactech_intelligence.capture_package_builder import (
    CLAUSE_PATTERN,
    CMMC_LEVEL_PATTERN,
)

log = logging.getLogger(__name__)
router = APIRouter(tags=["cyber"])


class _Out(BaseModel):
    model_config = ConfigDict(from_attributes=True)


class CyberPostureSummaryOut(_Out):
    sprs_score: int | None
    sprs_max: int
    sprs_assessment_date: str | None
    sprs_source_url: str | None
    sprs_synced_at: str | None


class CyberSummaryOut(_Out):
    opportunity_id: str
    clauses_identified: list[str]
    cmmc_level_required: str | None
    handles_cui: bool
    handles_fci: bool
    handles_itar: bool
    posture: CyberPostureSummaryOut
    sufficiency: str  # "sufficient" | "gap" | "unknown"
    sufficiency_notes: str | None


def _build_haystack(opp: OpportunityRaw, brief: OpportunityBrief | None) -> str:
    parts: list[str] = []
    if opp.description_text:
        parts.append(opp.description_text)
    if brief is not None:
        if brief.scope_one_sentence:
            parts.append(brief.scope_one_sentence)
        parts.extend(brief.must_have_requirements or [])
        parts.extend(brief.nice_to_have or [])
    return "\n".join(p for p in parts if p)


def _assess_sufficiency(
    *,
    sprs_score: int | None,
    sprs_max: int,
    cmmc_required: str | None,
    clauses: list[str],
) -> tuple[str, str | None]:
    # No cyber asks at all → unknown is fine.
    if not clauses and not cmmc_required:
        return "unknown", None

    # We need a posture to make any claim of sufficiency.
    if sprs_score is None:
        return (
            "unknown",
            "Solicitation cites cyber clauses but no SPRS score is on file. "
            "Confirm posture in Codex before bidding.",
        )

    # DFARS 7012 territory — require an SPRS score and a non-trivial one.
    has_dfars_7012 = any("252.204-7012" in c for c in clauses)
    if has_dfars_7012 and sprs_score < 0:
        return (
            "gap",
            f"DFARS 252.204-7012 cited; current SPRS score {sprs_score}/{sprs_max} "
            "is negative. Remediate before bidding.",
        )

    if cmmc_required:
        # We don't currently store the tenant's *current* CMMC level (Codex
        # publishes it as a separate field that's not yet in our schema). We
        # can't auto-compare without it; surface as unknown but flag the
        # requirement clearly.
        return (
            "unknown",
            f"Solicitation requires {cmmc_required}. CaptureOS does not yet "
            "mirror your current CMMC level from Codex — confirm directly "
            "before bidding.",
        )

    return "sufficient", None


@router.get(
    "/opportunities/{opportunity_id}/cyber-summary",
    response_model=CyberSummaryOut,
)
async def get_cyber_summary(
    opportunity_id: UUID,
    ctx: Annotated[RequestContext, Depends(get_request_context)],
) -> CyberSummaryOut:
    opp = (
        await ctx.session.execute(
            select(OpportunityRaw).where(OpportunityRaw.id == opportunity_id)
        )
    ).scalar_one_or_none()
    if opp is None:
        raise HTTPException(status_code=404, detail="opportunity not found")

    brief = (
        await ctx.session.execute(
            select(OpportunityBrief).where(
                OpportunityBrief.tenant_id == ctx.tenant.id,
                OpportunityBrief.opportunity_id == opportunity_id,
            )
        )
    ).scalar_one_or_none()

    haystack = _build_haystack(opp, brief)
    clauses = sorted(
        {m.upper().replace("  ", " ") for m in CLAUSE_PATTERN.findall(haystack)}
    )
    cmmc_match = CMMC_LEVEL_PATTERN.search(haystack)
    cmmc_required = f"Level {cmmc_match.group(1)}" if cmmc_match else None

    handles_cui = "CUI" in haystack or "Controlled Unclassified Information" in haystack
    handles_fci = "FCI" in haystack or "Federal Contract Information" in haystack
    handles_itar = "ITAR" in haystack

    sufficiency, notes = _assess_sufficiency(
        sprs_score=ctx.tenant.sprs_score,
        sprs_max=ctx.tenant.sprs_max,
        cmmc_required=cmmc_required,
        clauses=clauses,
    )

    posture = CyberPostureSummaryOut(
        sprs_score=ctx.tenant.sprs_score,
        sprs_max=ctx.tenant.sprs_max,
        sprs_assessment_date=(
            ctx.tenant.sprs_assessment_date.isoformat()
            if ctx.tenant.sprs_assessment_date
            else None
        ),
        sprs_source_url=ctx.tenant.sprs_source_url,
        sprs_synced_at=(
            ctx.tenant.sprs_synced_at.isoformat()
            if ctx.tenant.sprs_synced_at
            else None
        ),
    )

    return CyberSummaryOut(
        opportunity_id=str(opportunity_id),
        clauses_identified=clauses,
        cmmc_level_required=cmmc_required,
        handles_cui=handles_cui,
        handles_fci=handles_fci,
        handles_itar=handles_itar,
        posture=posture,
        sufficiency=sufficiency,
        sufficiency_notes=notes,
    )
