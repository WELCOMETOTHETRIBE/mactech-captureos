"""Opportunity read APIs.

Phase 1 Week 3 surfaces only the enriched-view endpoint required by the
roadmap demo: GET /opportunities/{id}/enriched. List/search endpoints
arrive in Phase 2 Week 6 alongside the dashboard.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any
from uuid import UUID

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, ConfigDict
from sqlalchemy import select

from mactech_db import async_session_factory
from mactech_db.models import (
    ExclusionsCache,
    OpportunityEnriched,
    OpportunityRaw,
)

router = APIRouter(prefix="/opportunities", tags=["opportunities"])

EXCLUSION_TTL = timedelta(hours=24)


class _Out(BaseModel):
    model_config = ConfigDict(from_attributes=True)


class IncumbentBlock(_Out):
    uei: str | None
    name: str | None
    contract_id: str | None
    contract_end_date: str | None
    contract_amount: float | None
    exclusions: ExclusionBlock | None  # forward ref


class ExclusionBlock(_Out):
    uei: str
    is_excluded: bool
    checked_at: str
    cache_status: str  # 'fresh' | 'stale'


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
    enrichment_notes: str | None
    enriched_at: str | None


IncumbentBlock.model_rebuild()


@router.get("/{opportunity_id}/enriched", response_model=EnrichedOpportunity)
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

    raw: dict[str, Any] = opp.raw_payload or {}
    return EnrichedOpportunity(
        opportunity=OpportunityHeader(
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
        ),
        incumbent=incumbent_block,
        enrichment_notes=enr.naics_match_notes if enr else None,
        enriched_at=enr.enriched_at.isoformat() if enr else None,
    )
