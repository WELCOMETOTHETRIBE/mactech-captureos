"""Plain-English structured brief for an opportunity.

Phase 3 Week 11 (UX Sprint 4). Replaces the raw SAM <pre> on the detail
page with five short structured sections.

  GET  /opportunities/{id}/brief        return cached brief or 404
  POST /opportunities/{id}/brief        generate (or regenerate)
  DELETE /opportunities/{id}/brief      throw out the cached brief

Generation is lazy — front-end shows a "Generate brief" button on first
view. Worker auto-extraction at ingest is intentionally deferred until
the corpus grows past hundreds-of-thousands of opps.
"""

from __future__ import annotations

import logging
import os
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, ConfigDict
from sqlalchemy import select

from mactech_api.auth import RequestContext, get_request_context
from mactech_db.models import OpportunityBrief, OpportunityRaw
from mactech_intelligence import (
    AnthropicLLMClient,
    BriefExtractionError,
    ExtractBriefInput,
    extract_structured_brief,
)
from mactech_intelligence.extract_brief import PROMPT_VERSION

log = logging.getLogger(__name__)
router = APIRouter(tags=["brief"])


class _Out(BaseModel):
    model_config = ConfigDict(from_attributes=True)


class BriefOut(_Out):
    id: str
    opportunity_id: str
    scope_one_sentence: str
    must_have_requirements: list[str]
    nice_to_have: list[str]
    red_flags_for_small_biz: list[str]
    suggested_team_roles: list[str]
    model: str | None
    prompt_version: str | None
    input_tokens: int | None
    output_tokens: int | None
    description_chars: int | None
    created_at: str
    updated_at: str


def _to_out(b: OpportunityBrief) -> BriefOut:
    return BriefOut(
        id=str(b.id),
        opportunity_id=str(b.opportunity_id),
        scope_one_sentence=b.scope_one_sentence,
        must_have_requirements=list(b.must_have_requirements or []),
        nice_to_have=list(b.nice_to_have or []),
        red_flags_for_small_biz=list(b.red_flags_for_small_biz or []),
        suggested_team_roles=list(b.suggested_team_roles or []),
        model=b.model,
        prompt_version=b.prompt_version,
        input_tokens=b.input_tokens,
        output_tokens=b.output_tokens,
        description_chars=b.description_chars,
        created_at=b.created_at.isoformat(),
        updated_at=b.updated_at.isoformat(),
    )


@router.get("/opportunities/{opportunity_id}/brief", response_model=BriefOut)
async def get_brief(
    opportunity_id: UUID,
    ctx: Annotated[RequestContext, Depends(get_request_context)],
) -> BriefOut:
    b = (
        await ctx.session.execute(
            select(OpportunityBrief).where(
                OpportunityBrief.tenant_id == ctx.tenant.id,
                OpportunityBrief.opportunity_id == opportunity_id,
            )
        )
    ).scalar_one_or_none()
    if b is None:
        raise HTTPException(status_code=404, detail="no brief generated yet")
    return _to_out(b)


@router.post(
    "/opportunities/{opportunity_id}/brief",
    response_model=BriefOut,
    status_code=status.HTTP_201_CREATED,
)
async def generate_brief(
    opportunity_id: UUID,
    ctx: Annotated[RequestContext, Depends(get_request_context)],
) -> BriefOut:
    api_key = os.environ.get("ANTHROPIC_API_KEY", "")
    if not api_key:
        raise HTTPException(
            status_code=503,
            detail="ANTHROPIC_API_KEY not configured on the API service.",
        )

    opp = (
        await ctx.session.execute(
            select(OpportunityRaw).where(OpportunityRaw.id == opportunity_id)
        )
    ).scalar_one_or_none()
    if opp is None:
        raise HTTPException(status_code=404, detail="opportunity not found")

    description = opp.description_text or ""
    if not description.strip():
        raise HTTPException(
            status_code=409,
            detail=(
                "opportunity has no description text on file yet. The "
                "fetch_descriptions worker pulls it on the next 30-minute "
                "tick — try again then."
            ),
        )

    inp = ExtractBriefInput(
        title=opp.title,
        agency=opp.agency,
        notice_type=opp.notice_type,
        set_aside=opp.set_aside,
        naics_code=opp.naics_code,
        posted_at=opp.posted_at,
        response_deadline=opp.response_deadline,
        description=description,
    )

    client = AnthropicLLMClient(api_key=api_key)
    try:
        result = await extract_structured_brief(client, inp)
    except BriefExtractionError as exc:
        log.warning("extract_brief produced bad JSON: %s", exc)
        raise HTTPException(
            status_code=502,
            detail=f"brief extraction failed: {exc}",
        ) from exc
    except Exception as exc:
        log.exception("extract_brief failed: %s", exc)
        raise HTTPException(
            status_code=502,
            detail=f"Anthropic call failed: {exc.__class__.__name__}",
        ) from exc

    # Upsert: keep one row per (tenant, opp).
    existing = (
        await ctx.session.execute(
            select(OpportunityBrief).where(
                OpportunityBrief.tenant_id == ctx.tenant.id,
                OpportunityBrief.opportunity_id == opportunity_id,
            )
        )
    ).scalar_one_or_none()

    if existing is None:
        b = OpportunityBrief(
            tenant_id=ctx.tenant.id,
            opportunity_id=opportunity_id,
            scope_one_sentence=result.scope_one_sentence,
            must_have_requirements=result.must_have_requirements,
            nice_to_have=result.nice_to_have,
            red_flags_for_small_biz=result.red_flags_for_small_biz,
            suggested_team_roles=result.suggested_team_roles,
            model=result.response.model,
            prompt_version=PROMPT_VERSION,
            input_tokens=result.response.input_tokens,
            output_tokens=result.response.output_tokens,
            description_chars=result.description_chars,
        )
        ctx.session.add(b)
    else:
        existing.scope_one_sentence = result.scope_one_sentence
        existing.must_have_requirements = result.must_have_requirements
        existing.nice_to_have = result.nice_to_have
        existing.red_flags_for_small_biz = result.red_flags_for_small_biz
        existing.suggested_team_roles = result.suggested_team_roles
        existing.model = result.response.model
        existing.prompt_version = PROMPT_VERSION
        existing.input_tokens = result.response.input_tokens
        existing.output_tokens = result.response.output_tokens
        existing.description_chars = result.description_chars
        b = existing

    await ctx.session.flush()
    return _to_out(b)


@router.delete(
    "/opportunities/{opportunity_id}/brief",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def delete_brief(
    opportunity_id: UUID,
    ctx: Annotated[RequestContext, Depends(get_request_context)],
) -> None:
    b = (
        await ctx.session.execute(
            select(OpportunityBrief).where(
                OpportunityBrief.tenant_id == ctx.tenant.id,
                OpportunityBrief.opportunity_id == opportunity_id,
            )
        )
    ).scalar_one_or_none()
    if b is None:
        raise HTTPException(status_code=404, detail="no brief to delete")
    await ctx.session.delete(b)
    await ctx.session.flush()
