"""Opportunity enrichment.

Per docs/USASPENDING_API.md §6 Chain 1:
  Style-A SAM opportunity → USASpending spending_by_award filtered by NAICS
  + awarding agency + last 24 months → top result by Period of Performance
  Current End Date desc whose end-date straddles or precedes the new opp's
  posted date is the incumbent.

Then per docs/SAM_GOV_API.md §4 Chain 4: take the incumbent UEI, query
SAM Exclusions, cache result.

Output:
  - opportunities_enriched row (1:1 with opportunities_raw)
  - exclusions_cache row keyed by UEI
  - optionally a small set of awards_history rows for the top candidates

Phase 1 Week 3 strategy: enrich opportunities lazily — the enrichment
beat task scans unenriched opps every 30 minutes and processes a small
batch. Manual enqueue via mactech.enrich.opportunity is also exposed.
"""

from __future__ import annotations

import asyncio
import logging
import os
from dataclasses import asdict, dataclass
from datetime import UTC, date, datetime, timedelta
from typing import Any
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from mactech_db import async_session_factory
from mactech_db.models import (
    AwardHistory,
    ExclusionsCache,
    OpportunityEnriched,
    OpportunityRaw,
)
from mactech_integrations.sam_gov import SamExclusionsClient
from mactech_integrations.usaspending import (
    AwardSearchResult,
    UsaSpendingClient,
)
from mactech_workers.celery_app import celery_app

log = logging.getLogger(__name__)

EXCLUSION_TTL = timedelta(hours=24)
INCUMBENT_LOOKBACK = timedelta(days=730)  # 24 months
AWARD_TYPE_CODES = ["A", "B", "C", "D"]  # contracts only


@dataclass
class EnrichStats:
    opportunity_id: str
    incumbent_uei: str | None
    incumbent_name: str | None
    incumbent_end_date: str | None
    incumbent_award_amount: float | None
    candidates_scanned: int
    excluded: bool | None
    duration_ms: int


async def enrich_opportunity(opportunity_id: UUID | str) -> EnrichStats:
    started = datetime.now(UTC)
    opp_uuid = UUID(str(opportunity_id))

    sam_key = os.environ.get("SAM_API_KEY", "")
    if not sam_key:
        raise RuntimeError("SAM_API_KEY not set; required for exclusions check")

    session_factory = async_session_factory()
    candidates_scanned = 0
    incumbent: AwardSearchResult | None = None
    is_excluded: bool | None = None

    async with session_factory() as session:
        async with session.begin():
            opp = (
                await session.execute(
                    select(OpportunityRaw).where(OpportunityRaw.id == opp_uuid)
                )
            ).scalar_one_or_none()
            if opp is None:
                raise ValueError(f"opportunity {opp_uuid} not found")

            posted = opp.posted_at.date() if opp.posted_at else datetime.now(UTC).date()
            agency_name = _normalize_agency(opp.agency)
            naics = opp.naics_code

            if naics and agency_name:
                async with UsaSpendingClient() as us:
                    page = await us.search_awards(
                        naics_codes=[naics],
                        awarding_agency_name=agency_name,
                        time_period_start=posted - INCUMBENT_LOOKBACK,
                        time_period_end=posted,
                        award_type_codes=AWARD_TYPE_CODES,
                        # USASpending only allows sorting by a small set of
                        # keys (Award ID, Recipient Name, Award Amount, Action
                        # Date, ...). PoP dates are response-only. Pull the
                        # top 25 by Award Amount and re-rank by end-date in
                        # Python — the largest contracts in the same NAICS
                        # + agency are nearly always the right candidate pool.
                        sort="Award Amount",
                        order="desc",
                        limit=25,
                    )
                candidates_scanned = len(page.results)
                # Prefer candidates still active (end-date >= posted), most
                # recently ending first. If none are active, fall back to
                # the most-recently-expired contract.
                still_active = sorted(
                    [
                        r
                        for r in page.results
                        if r.period_of_performance_current_end_date
                        and r.period_of_performance_current_end_date >= posted
                    ],
                    key=lambda r: r.period_of_performance_current_end_date,  # type: ignore[arg-type,return-value]
                    reverse=True,
                )
                expired = sorted(
                    [
                        r
                        for r in page.results
                        if r.period_of_performance_current_end_date
                        and r.period_of_performance_current_end_date < posted
                    ],
                    key=lambda r: r.period_of_performance_current_end_date,  # type: ignore[arg-type,return-value]
                    reverse=True,
                )
                pool = still_active or expired
                if pool:
                    incumbent = pool[0]

            # Persist any candidate awards we saw — they are useful intel
            # regardless of whether they were the chosen incumbent.
            for cand in (page.results if naics and agency_name else []):
                if not cand.generated_internal_id:
                    continue
                await _upsert_award_history(session, cand, naics_code=naics)

            # Run exclusions check on the incumbent UEI if we found one.
            exclusion_details: dict[str, Any] | None = None
            if incumbent and incumbent.recipient_uei:
                cached = await _read_exclusion_cache(session, incumbent.recipient_uei)
                if cached is not None:
                    is_excluded = cached.is_excluded
                    exclusion_details = cached.exclusion_details
                else:
                    async with SamExclusionsClient(api_key=sam_key) as ex:
                        result = await ex.check_uei(incumbent.recipient_uei)
                    is_excluded = result.is_excluded
                    exclusion_details = result.raw
                    await _write_exclusion_cache(
                        session,
                        uei=incumbent.recipient_uei,
                        is_excluded=is_excluded,
                        details=exclusion_details,
                    )

            await _upsert_enrichment(
                session,
                opp_id=opp_uuid,
                incumbent=incumbent,
                naics=naics,
                agency_name=agency_name,
            )

    duration_ms = int((datetime.now(UTC) - started).total_seconds() * 1000)
    return EnrichStats(
        opportunity_id=str(opp_uuid),
        incumbent_uei=incumbent.recipient_uei if incumbent else None,
        incumbent_name=incumbent.recipient_name if incumbent else None,
        incumbent_end_date=(
            incumbent.period_of_performance_current_end_date.isoformat()
            if incumbent and incumbent.period_of_performance_current_end_date
            else None
        ),
        incumbent_award_amount=(
            float(incumbent.award_amount)
            if incumbent and incumbent.award_amount is not None
            else None
        ),
        candidates_scanned=candidates_scanned,
        excluded=is_excluded,
        duration_ms=duration_ms,
    )


async def enrich_unenriched_batch(*, batch_size: int = 25) -> dict[str, Any]:
    """Find opportunities that don't have a corresponding enrichment row, enrich them."""
    session_factory = async_session_factory()
    async with session_factory() as session:
        rows = (
            await session.execute(
                select(OpportunityRaw.id)
                .outerjoin(
                    OpportunityEnriched,
                    OpportunityEnriched.opportunity_id == OpportunityRaw.id,
                )
                .where(OpportunityEnriched.id.is_(None))
                .where(OpportunityRaw.naics_code.is_not(None))
                .order_by(OpportunityRaw.posted_at.desc().nulls_last())
                .limit(batch_size)
            )
        ).scalars().all()

    log.info("enriching batch of %d opportunities", len(rows))
    results = []
    for opp_id in rows:
        try:
            stats = await enrich_opportunity(opp_id)
            results.append(asdict(stats))
            log.info(
                "enriched %s: incumbent=%s end=%s excluded=%s",
                opp_id,
                stats.incumbent_uei,
                stats.incumbent_end_date,
                stats.excluded,
            )
        except Exception as exc:
            log.exception("enrich %s failed: %s", opp_id, exc)
    return {"processed": len(results), "results": results}


def _normalize_agency(agency_path: str | None) -> str | None:
    """SAM returns 'fullParentPathName' with dotted hierarchy; USASpending
    needs the toptier-only canonical name. Take the first segment and
    title-case common DoD spellings.
    """
    if not agency_path:
        return None
    top = agency_path.split(".")[0].strip()
    # Map a few common short forms back to USASpending toptier canonical
    # names. Extend as enrichment failures surface in production.
    mapping = {
        "DEPT OF DEFENSE": "Department of Defense",
        "DEPARTMENT OF DEFENSE": "Department of Defense",
        "VETERANS AFFAIRS, DEPARTMENT OF": "Department of Veterans Affairs",
        "DEPARTMENT OF VETERANS AFFAIRS": "Department of Veterans Affairs",
        "HEALTH AND HUMAN SERVICES, DEPARTMENT OF": "Department of Health and Human Services",
        "INTERIOR, DEPARTMENT OF THE": "Department of the Interior",
        "HOMELAND SECURITY, DEPARTMENT OF": "Department of Homeland Security",
        "GENERAL SERVICES ADMINISTRATION": "General Services Administration",
        "TRANSPORTATION, DEPARTMENT OF": "Department of Transportation",
        "ENERGY, DEPARTMENT OF": "Department of Energy",
        "STATE, DEPARTMENT OF": "Department of State",
        "TREASURY, DEPARTMENT OF THE": "Department of the Treasury",
        "JUSTICE, DEPARTMENT OF": "Department of Justice",
        "AGRICULTURE, DEPARTMENT OF": "Department of Agriculture",
        "COMMERCE, DEPARTMENT OF": "Department of Commerce",
        "EDUCATION, DEPARTMENT OF": "Department of Education",
        "LABOR, DEPARTMENT OF": "Department of Labor",
        "ENVIRONMENTAL PROTECTION AGENCY": "Environmental Protection Agency",
        "SOCIAL SECURITY ADMINISTRATION": "Social Security Administration",
        "SENATE, THE": None,  # No USASpending equivalent
        "HOUSE OF REPRESENTATIVES, THE": None,
    }
    return mapping.get(top.upper(), top)


async def _read_exclusion_cache(
    session: AsyncSession, uei: str
) -> ExclusionsCache | None:
    row = (
        await session.execute(
            select(ExclusionsCache).where(ExclusionsCache.uei == uei)
        )
    ).scalar_one_or_none()
    if row is None:
        return None
    if datetime.now(UTC) - row.checked_at > EXCLUSION_TTL:
        return None
    return row


async def _write_exclusion_cache(
    session: AsyncSession,
    *,
    uei: str,
    is_excluded: bool,
    details: dict[str, Any] | None,
) -> None:
    stmt = (
        pg_insert(ExclusionsCache)
        .values(
            uei=uei,
            is_excluded=is_excluded,
            exclusion_details=details,
            checked_at=datetime.now(UTC),
        )
        .on_conflict_do_update(
            index_elements=["uei"],
            set_={
                "is_excluded": is_excluded,
                "exclusion_details": details,
                "checked_at": datetime.now(UTC),
            },
        )
    )
    await session.execute(stmt)


async def _upsert_award_history(
    session: AsyncSession,
    award: AwardSearchResult,
    *,
    naics_code: str | None,
) -> None:
    if not award.generated_internal_id:
        return
    stmt = (
        pg_insert(AwardHistory)
        .values(
            source="usaspending",
            award_id=award.generated_internal_id,
            piid=award.award_id_field,
            recipient_uei=award.recipient_uei,
            recipient_name=award.recipient_name,
            awarding_agency=award.awarding_agency,
            awarding_subagency=award.awarding_subagency,
            naics_code=naics_code,
            award_type=award.contract_award_type,
            obligated_amount=award.award_amount,
            period_of_performance_start=award.period_of_performance_start_date,
            period_of_performance_current_end=award.period_of_performance_current_end_date,
            description=award.description,
            raw_payload=award.model_dump(mode="json", by_alias=True),
        )
        .on_conflict_do_update(
            index_elements=["source", "award_id"],
            set_={
                "recipient_uei": award.recipient_uei,
                "recipient_name": award.recipient_name,
                "awarding_agency": award.awarding_agency,
                "awarding_subagency": award.awarding_subagency,
                "obligated_amount": award.award_amount,
                "period_of_performance_current_end": award.period_of_performance_current_end_date,
                "description": award.description,
                "raw_payload": award.model_dump(mode="json", by_alias=True),
            },
        )
    )
    await session.execute(stmt)


async def _upsert_enrichment(
    session: AsyncSession,
    *,
    opp_id: UUID,
    incumbent: AwardSearchResult | None,
    naics: str | None,
    agency_name: str | None,
) -> None:
    notes_parts: list[str] = []
    if not naics:
        notes_parts.append("no naics on opportunity")
    if not agency_name:
        notes_parts.append("agency not mappable to usaspending toptier")
    if naics and agency_name and not incumbent:
        notes_parts.append("no contract-type award found in last 24 months")
    notes = "; ".join(notes_parts) or None

    values: dict[str, Any] = {
        "opportunity_id": opp_id,
        "incumbent_uei": incumbent.recipient_uei if incumbent else None,
        "incumbent_name": incumbent.recipient_name if incumbent else None,
        "incumbent_contract_id": incumbent.generated_internal_id if incumbent else None,
        "incumbent_end_date": (
            incumbent.period_of_performance_current_end_date if incumbent else None
        ),
        "incumbent_award_amount": (
            incumbent.award_amount if incumbent else None
        ),
        "naics_match_notes": notes,
        "source": "usaspending",
        "enriched_at": datetime.now(UTC),
        "updated_at": datetime.now(UTC),
    }
    stmt = (
        pg_insert(OpportunityEnriched)
        .values(**values)
        .on_conflict_do_update(
            index_elements=["opportunity_id"],
            set_={
                "incumbent_uei": values["incumbent_uei"],
                "incumbent_name": values["incumbent_name"],
                "incumbent_contract_id": values["incumbent_contract_id"],
                "incumbent_end_date": values["incumbent_end_date"],
                "incumbent_award_amount": values["incumbent_award_amount"],
                "naics_match_notes": values["naics_match_notes"],
                "source": values["source"],
                "enriched_at": values["enriched_at"],
                "updated_at": values["updated_at"],
            },
        )
    )
    await session.execute(stmt)


# --- Celery task wrappers ---


@celery_app.task(name="mactech.enrich.opportunity")
def enrich_opportunity_task(opportunity_id: str) -> dict[str, Any]:
    return asdict(asyncio.run(enrich_opportunity(opportunity_id)))


@celery_app.task(name="mactech.enrich.batch")
def enrich_unenriched_batch_task(batch_size: int = 25) -> dict[str, Any]:
    return asyncio.run(enrich_unenriched_batch(batch_size=batch_size))
