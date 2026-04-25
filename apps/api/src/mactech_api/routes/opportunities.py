"""Opportunity read APIs.

Phase 2 Week 6 endpoints:
  GET /opportunities/{id}           single-opp full detail (authenticated;
                                    requires Clerk session). Returns the
                                    rich payload the dashboard's
                                    /opportunities/[id] page renders:
                                    header + description + incumbent +
                                    exclusions + score + capability matches
                                    + scoring breakdown.
  GET /digest/{founder-slug}        today's top-N for that founder
                                    (authenticated). Same as before.

The previous unauthenticated /opportunities/{id}/enriched is kept as a
thin redirect so any bookmarked links still resolve.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Annotated, Any
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import RedirectResponse
from pydantic import BaseModel, ConfigDict
from sqlalchemy import select, text

from mactech_api.auth import RequestContext, get_request_context
from mactech_db.models import (
    ExclusionsCache,
    Founder,
    OpportunityEnriched,
    OpportunityRaw,
    OpportunityScore,
)

router = APIRouter(tags=["opportunities"])

EXCLUSION_TTL = timedelta(hours=24)


class _Out(BaseModel):
    model_config = ConfigDict(from_attributes=True)


class ExclusionBlock(_Out):
    uei: str
    is_excluded: bool
    checked_at: str
    cache_status: str  # 'fresh' | 'stale'


class IncumbentBlock(_Out):
    uei: str | None
    name: str | None
    contract_id: str | None
    contract_end_date: str | None
    contract_amount: float | None
    exclusions: ExclusionBlock | None


class ScoreBlock(_Out):
    score: int
    breakdown: dict[str, int]
    assigned_founder_slug: str | None
    why_it_matters: str | None
    why_it_matters_model: str | None
    scored_at: str | None


class OpportunityHeader(_Out):
    id: str
    notice_id: str
    title: str
    notice_type: str | None
    set_aside: str | None
    set_aside_description: str | None
    naics_code: str | None
    agency: str | None
    solicitation_number: str | None
    posted_at: str | None
    response_deadline: str | None
    days_until_deadline: int | None
    sam_link: str | None
    additional_info_link: str | None


class DescriptionBlock(_Out):
    text: str | None
    source_url: str | None
    fetch_status: str  # 'fetched' | 'pending' | 'unavailable'


class CapabilityMatch(_Out):
    id: str
    title: str
    summary: str
    similarity: float  # 0..1 cosine


class OpportunityDetail(_Out):
    opportunity: OpportunityHeader
    description: DescriptionBlock
    incumbent: IncumbentBlock | None
    score: ScoreBlock | None
    capability_matches: list[CapabilityMatch]
    enrichment_notes: str | None
    enriched_at: str | None
    sam_resource_links: list[str]


class DigestItem(_Out):
    opportunity: OpportunityHeader
    score: int
    breakdown: dict[str, int]
    why_it_matters: str | None
    incumbent_summary: str | None
    detail_url: str


class FounderDigest(_Out):
    founder_slug: str
    founder_name: str
    founder_pillar: str
    items_count: int
    items: list[DigestItem]
    rendered_at: str


def _opp_header(opp: OpportunityRaw) -> OpportunityHeader:
    raw: dict[str, Any] = opp.raw_payload or {}
    days = None
    if opp.response_deadline:
        delta = opp.response_deadline - datetime.now(timezone.utc)
        days = int(delta.total_seconds() / 86400)
    return OpportunityHeader(
        id=str(opp.id),
        notice_id=opp.source_id,
        title=opp.title,
        notice_type=opp.notice_type,
        set_aside=opp.set_aside,
        set_aside_description=raw.get("typeOfSetAsideDescription"),
        naics_code=opp.naics_code,
        agency=opp.agency,
        solicitation_number=opp.solicitation_number,
        posted_at=opp.posted_at.isoformat() if opp.posted_at else None,
        response_deadline=(
            opp.response_deadline.isoformat() if opp.response_deadline else None
        ),
        days_until_deadline=days,
        sam_link=raw.get("uiLink"),
        additional_info_link=raw.get("additionalInfoLink"),
    )


def _incumbent_one_liner(enr: OpportunityEnriched | None) -> str | None:
    if enr is None or not enr.incumbent_name:
        return None
    parts = [enr.incumbent_name]
    if enr.incumbent_award_amount is not None:
        parts.append(f"${float(enr.incumbent_award_amount):,.0f} prior obligations")
    return " — ".join(parts)


@router.get("/opportunities/{opportunity_id}", response_model=OpportunityDetail)
async def get_opportunity_detail(
    opportunity_id: UUID,
    ctx: Annotated[RequestContext, Depends(get_request_context)],
) -> OpportunityDetail:
    session = ctx.session
    tenant_id = ctx.tenant.id

    opp = (
        await session.execute(
            select(OpportunityRaw).where(OpportunityRaw.id == opportunity_id)
        )
    ).scalar_one_or_none()
    if opp is None:
        raise HTTPException(status_code=404, detail="opportunity not found")

    enr = (
        await session.execute(
            select(OpportunityEnriched).where(
                OpportunityEnriched.opportunity_id == opportunity_id
            )
        )
    ).scalar_one_or_none()

    excl_block: ExclusionBlock | None = None
    if enr and enr.incumbent_uei:
        excl_row = (
            await session.execute(
                select(ExclusionsCache).where(ExclusionsCache.uei == enr.incumbent_uei)
            )
        ).scalar_one_or_none()
        if excl_row is not None:
            age = datetime.now(timezone.utc) - excl_row.checked_at
            excl_block = ExclusionBlock(
                uei=excl_row.uei,
                is_excluded=excl_row.is_excluded,
                checked_at=excl_row.checked_at.isoformat(),
                cache_status="fresh" if age <= EXCLUSION_TTL else "stale",
            )

    incumbent_block: IncumbentBlock | None = None
    if enr and (enr.incumbent_uei or enr.incumbent_name):
        incumbent_block = IncumbentBlock(
            uei=enr.incumbent_uei,
            name=enr.incumbent_name,
            contract_id=enr.incumbent_contract_id,
            contract_end_date=(
                enr.incumbent_end_date.isoformat() if enr.incumbent_end_date else None
            ),
            contract_amount=(
                float(enr.incumbent_award_amount)
                if enr.incumbent_award_amount is not None
                else None
            ),
            exclusions=excl_block,
        )

    # Score block — joined to the active tenant.
    score_block: ScoreBlock | None = None
    sc = (
        await session.execute(
            select(OpportunityScore, Founder.slug)
            .outerjoin(Founder, Founder.id == OpportunityScore.assigned_founder_id)
            .where(
                OpportunityScore.tenant_id == tenant_id,
                OpportunityScore.opportunity_id == opportunity_id,
            )
        )
    ).one_or_none()
    if sc is not None:
        score_row, founder_slug = sc
        score_block = ScoreBlock(
            score=score_row.score,
            breakdown=score_row.score_breakdown,
            assigned_founder_slug=founder_slug,
            why_it_matters=score_row.why_it_matters,
            why_it_matters_model=score_row.why_it_matters_model,
            scored_at=score_row.scored_at.isoformat(),
        )

    # Capability matches via pgvector cosine similarity. similarity = 1 - distance.
    matches_rows = (
        await session.execute(
            text(
                """
                select c.id::text, c.title, c.summary,
                       1 - (o.embedding <=> c.embedding) as similarity
                from opportunities_raw o, capability_statements c
                where o.id = :opp_id
                  and c.tenant_id = :tenant_id
                  and o.embedding is not null
                  and c.embedding is not null
                order by similarity desc
                limit 5
                """
            ),
            {"opp_id": str(opportunity_id), "tenant_id": str(tenant_id)},
        )
    ).all()
    capability_matches = [
        CapabilityMatch(
            id=r[0],
            title=r[1],
            summary=r[2],
            similarity=float(r[3]),
        )
        for r in matches_rows
    ]

    # Description block.
    raw: dict[str, Any] = opp.raw_payload or {}
    if opp.description_text:
        desc = DescriptionBlock(
            text=opp.description_text,
            source_url=opp.description_url,
            fetch_status="fetched",
        )
    elif opp.description_url:
        desc = DescriptionBlock(
            text=None,
            source_url=opp.description_url,
            fetch_status="pending",
        )
    else:
        desc = DescriptionBlock(text=None, source_url=None, fetch_status="unavailable")

    return OpportunityDetail(
        opportunity=_opp_header(opp),
        description=desc,
        incumbent=incumbent_block,
        score=score_block,
        capability_matches=capability_matches,
        enrichment_notes=enr.naics_match_notes if enr else None,
        enriched_at=enr.enriched_at.isoformat() if enr else None,
        sam_resource_links=raw.get("resourceLinks") or [],
    )


@router.get("/opportunities/{opportunity_id}/enriched", include_in_schema=False)
async def enriched_redirect(opportunity_id: UUID) -> RedirectResponse:
    """Backward-compat for the Phase 1 URL."""
    return RedirectResponse(url=f"/opportunities/{opportunity_id}", status_code=308)


@router.get("/digest/{founder_slug}", response_model=FounderDigest)
async def get_founder_digest(
    founder_slug: str,
    ctx: Annotated[RequestContext, Depends(get_request_context)],
    limit: int = 5,
) -> FounderDigest:
    if limit < 1 or limit > 50:
        raise HTTPException(status_code=400, detail="limit must be between 1 and 50")

    session = ctx.session
    tenant_id = ctx.tenant.id

    founder = (
        await session.execute(select(Founder).where(Founder.slug == founder_slug))
    ).scalar_one_or_none()
    if founder is None:
        raise HTTPException(status_code=404, detail="founder not found")

    rows = (
        await session.execute(
            select(OpportunityScore, OpportunityRaw, OpportunityEnriched)
            .join(OpportunityRaw, OpportunityRaw.id == OpportunityScore.opportunity_id)
            .outerjoin(
                OpportunityEnriched,
                OpportunityEnriched.opportunity_id == OpportunityRaw.id,
            )
            .where(
                OpportunityScore.tenant_id == tenant_id,
                OpportunityScore.assigned_founder_id == founder.id,
            )
            .order_by(OpportunityScore.score.desc())
            .limit(limit)
        )
    ).all()

    items: list[DigestItem] = []
    for sc, opp, enr in rows:
        items.append(
            DigestItem(
                opportunity=_opp_header(opp),
                score=sc.score,
                breakdown=sc.score_breakdown,
                why_it_matters=sc.why_it_matters,
                incumbent_summary=_incumbent_one_liner(enr),
                detail_url=f"/opportunities/{opp.id}",
            )
        )

    return FounderDigest(
        founder_slug=founder.slug,
        founder_name=founder.full_name,
        founder_pillar=founder.pillar,
        items_count=len(items),
        items=items,
        rendered_at=datetime.now(timezone.utc).isoformat(),
    )
