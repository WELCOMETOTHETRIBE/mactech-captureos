"""Opportunity read APIs.

Phase 1 endpoints:
  GET /opportunities/{id}/enriched   single-opp incumbent + exclusions + score
  GET /digest/{founder-slug}         today's top-5 for that founder

List/search endpoints arrive in Phase 2 Week 6 alongside the dashboard.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any
from uuid import UUID

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, ConfigDict
from sqlalchemy import select

from mactech_api.settings import settings
from mactech_db import async_session_factory
from mactech_db.models import (
    ExclusionsCache,
    Founder,
    OpportunityEnriched,
    OpportunityRaw,
    OpportunityScore,
    Tenant,
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
    naics_code: str | None
    agency: str | None
    posted_at: str | None
    response_deadline: str | None
    sam_link: str | None


class EnrichedOpportunity(_Out):
    opportunity: OpportunityHeader
    incumbent: IncumbentBlock | None
    score: ScoreBlock | None
    enrichment_notes: str | None
    enriched_at: str | None


class DigestItem(_Out):
    opportunity: OpportunityHeader
    score: int
    breakdown: dict[str, int]
    why_it_matters: str | None
    incumbent_summary: str | None  # 1-line "Dell Federal — $1.7B in VA cyber"
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
    return OpportunityHeader(
        id=str(opp.id),
        notice_id=opp.source_id,
        title=opp.title,
        notice_type=opp.notice_type,
        set_aside=opp.set_aside,
        naics_code=opp.naics_code,
        agency=opp.agency,
        posted_at=opp.posted_at.isoformat() if opp.posted_at else None,
        response_deadline=(
            opp.response_deadline.isoformat() if opp.response_deadline else None
        ),
        sam_link=raw.get("uiLink"),
    )


def _incumbent_summary(enr: OpportunityEnriched | None) -> str | None:
    if enr is None or not enr.incumbent_name:
        return None
    parts = [enr.incumbent_name]
    if enr.incumbent_award_amount is not None:
        parts.append(f"${float(enr.incumbent_award_amount):,.0f} prior obligations")
    return " — ".join(parts)


@router.get("/opportunities/{opportunity_id}/enriched", response_model=EnrichedOpportunity)
async def get_enriched_opportunity(opportunity_id: UUID) -> EnrichedOpportunity:
    session_factory = async_session_factory()
    async with session_factory() as session:
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
                    select(ExclusionsCache).where(
                        ExclusionsCache.uei == enr.incumbent_uei
                    )
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

        # Score block — joined to the MacTech tenant.
        tenant = (
            await session.execute(
                select(Tenant).where(Tenant.slug == settings.mactech_tenant_slug)
            )
        ).scalar_one_or_none()
        score_block: ScoreBlock | None = None
        if tenant is not None:
            sc = (
                await session.execute(
                    select(OpportunityScore, Founder.slug)
                    .outerjoin(Founder, Founder.id == OpportunityScore.assigned_founder_id)
                    .where(
                        OpportunityScore.tenant_id == tenant.id,
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

    return EnrichedOpportunity(
        opportunity=_opp_header(opp),
        incumbent=incumbent_block,
        score=score_block,
        enrichment_notes=enr.naics_match_notes if enr else None,
        enriched_at=enr.enriched_at.isoformat() if enr else None,
    )


@router.get("/digest/{founder_slug}", response_model=FounderDigest)
async def get_founder_digest(founder_slug: str, limit: int = 5) -> FounderDigest:
    if limit < 1 or limit > 50:
        raise HTTPException(status_code=400, detail="limit must be between 1 and 50")

    session_factory = async_session_factory()
    async with session_factory() as session:
        founder = (
            await session.execute(select(Founder).where(Founder.slug == founder_slug))
        ).scalar_one_or_none()
        if founder is None:
            raise HTTPException(status_code=404, detail="founder not found")

        tenant = (
            await session.execute(
                select(Tenant).where(Tenant.slug == settings.mactech_tenant_slug)
            )
        ).scalar_one()

        rows = (
            await session.execute(
                select(OpportunityScore, OpportunityRaw, OpportunityEnriched)
                .join(OpportunityRaw, OpportunityRaw.id == OpportunityScore.opportunity_id)
                .outerjoin(
                    OpportunityEnriched,
                    OpportunityEnriched.opportunity_id == OpportunityRaw.id,
                )
                .where(
                    OpportunityScore.tenant_id == tenant.id,
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
                incumbent_summary=_incumbent_summary(enr),
                detail_url=f"/opportunities/{opp.id}/enriched",
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
