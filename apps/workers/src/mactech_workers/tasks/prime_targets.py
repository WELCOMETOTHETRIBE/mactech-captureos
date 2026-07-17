"""Prime-target discovery worker (Slice 7).

For a sub-lane opportunity, find the companies MacTech would team under by
querying USASpending (keyless) for recent awardees of like work (same NAICS,
same awarding agency), ranking them, and persisting prime_targets +
opportunity_prime_targets. Populating these lets the decision engine promote
SUB_TO_PRIME_NOT_YET_IDENTIFIED to SUB_TO_IDENTIFIED_PRIME.
"""

from __future__ import annotations

import asyncio
import logging
from datetime import UTC, date, datetime, timedelta
from typing import Any
from uuid import UUID

from mactech_db import async_session_factory
from mactech_db.models import (
    OpportunityPrimeTarget,
    OpportunityRaw,
    PrimeTarget,
    Tenant,
)
from mactech_integrations.usaspending import UsaSpendingClient
from mactech_intelligence.prime_targets import AwardRow, rank_prime_targets
from sqlalchemy import delete, select, text
from sqlalchemy.dialects.postgresql import insert as pg_insert

from mactech_workers.celery_app import celery_app
from mactech_workers.tasks.enrich import _normalize_agency

log = logging.getLogger(__name__)

# Minimum award size to count a firm as a plausible prime, by work type.
_CONSTRUCTION_NAICS = frozenset({"236220", "237130", "237310", "237990", "238210", "562910"})
_CONSTRUCTION_MIN = 1_000_000
_SERVICES_MIN = 100_000
_LOOKBACK_MONTHS = 36
_OUTREACH_BUFFER_DAYS = 7
_CONTACT_ROLE = "capture manager / small-business liaison officer"


def _agency_for(opp: OpportunityRaw) -> str | None:
    raw = opp.raw_payload or {}
    path = raw.get("fullParentPathName") or opp.agency
    return _normalize_agency(path)


def _dedupe_key(uei: str | None, name: str | None) -> str:
    return (uei or (name or "").strip().upper())[:255]


async def _upsert_prime_target(session, cand) -> UUID:
    key = _dedupe_key(cand.uei, cand.name)
    now = datetime.now(UTC)
    values = {
        "dedupe_key": key,
        "uei": cand.uei,
        "name": cand.name[:512],
        "target_type": cand.target_type,
        "agencies": cand.agencies,
        "naics_codes": cand.naics_codes or None,
        "recent_award_ids": cand.recent_award_ids,
        "total_recent_award_amount": cand.total_recent_award_amount,
        "award_count": cand.award_count,
        "source": "usaspending",
        "refreshed_at": now,
    }
    await session.execute(
        pg_insert(PrimeTarget)
        .values(**values)
        .on_conflict_do_update(
            constraint="uq_prime_targets_dedupe_key",
            set_={k: values[k] for k in values if k != "dedupe_key"},
        )
    )
    return (
        await session.execute(
            select(PrimeTarget.id).where(PrimeTarget.dedupe_key == key)
        )
    ).scalar_one()


async def find_for_opportunity(tenant_id: UUID, opp: OpportunityRaw) -> dict[str, Any]:
    if not opp.naics_code:
        return {"status": "skipped", "reason": "no_naics", "found": 0}

    is_construction = opp.naics_code in _CONSTRUCTION_NAICS
    amount_min = _CONSTRUCTION_MIN if is_construction else _SERVICES_MIN
    agency = _agency_for(opp)
    end = date.today()
    start = end - timedelta(days=30 * _LOOKBACK_MONTHS)

    async with UsaSpendingClient() as us:
        page = await us.search_awards(
            naics_codes=[opp.naics_code],
            awarding_agency_name=agency,
            award_amount_min=amount_min,
            time_period_start=start,
            time_period_end=end,
            limit=50,
        )

    awards = [
        AwardRow(
            recipient_name=r.recipient_name,
            recipient_uei=r.recipient_uei,
            award_id=r.award_id_field or r.generated_internal_id,
            award_amount=float(r.award_amount) if r.award_amount is not None else None,
            awarding_agency=r.awarding_agency,
            naics_code=(r.naics_field or {}).get("code") if r.naics_field else opp.naics_code,
        )
        for r in page.results
    ]
    candidates = rank_prime_targets(awards, recommended_contact_role=_CONTACT_ROLE, limit=8)

    outreach = None
    if opp.response_deadline is not None:
        outreach = opp.response_deadline - timedelta(days=_OUTREACH_BUFFER_DAYS)

    session_factory = async_session_factory()
    async with session_factory() as session, session.begin():
        # Replace this opp's links so re-runs are idempotent.
        await session.execute(
            delete(OpportunityPrimeTarget).where(
                OpportunityPrimeTarget.tenant_id == tenant_id,
                OpportunityPrimeTarget.opportunity_id == opp.id,
            )
        )
        for rank, cand in enumerate(candidates):
            pt_id = await _upsert_prime_target(session, cand)
            session.add(
                OpportunityPrimeTarget(
                    tenant_id=tenant_id,
                    opportunity_id=opp.id,
                    prime_target_id=pt_id,
                    target_type=cand.target_type,
                    rank=rank,
                    why_target=cand.why_target,
                    recommended_contact_role=cand.recommended_contact_role,
                    outreach_deadline=outreach,
                    confidence=cand.confidence,
                    evidence=cand.evidence,
                )
            )

    return {"status": "ok", "found": len(candidates), "names": [c.name for c in candidates[:5]]}


async def find_batch(tenant_slug: str, *, limit: int = 30) -> dict[str, Any]:
    """Find primes for SUB-lane opportunities that have none yet."""
    session_factory = async_session_factory()
    async with session_factory() as session:
        tenant = (
            await session.execute(select(Tenant).where(Tenant.slug == tenant_slug))
        ).scalar_one_or_none()
        if tenant is None:
            return {"status": "error", "reason": "tenant_not_found"}
        rows = (
            await session.execute(
                text(
                    """
                    select o.id
                    from opportunity_decision_vectors dv
                    join opportunities_raw o on o.id = dv.opportunity_id
                    left join opportunity_prime_targets opt
                      on opt.opportunity_id = o.id and opt.tenant_id = dv.tenant_id
                    where dv.tenant_id = :t
                      and dv.pursuit_lane like 'SUB%'
                      and opt.id is null
                    group by o.id
                    limit :n
                    """
                ),
                {"t": str(tenant.id), "n": limit},
            )
        ).scalars().all()

    processed = 0
    total_found = 0
    for opp_id in rows:
        async with session_factory() as session:
            opp = (
                await session.execute(select(OpportunityRaw).where(OpportunityRaw.id == opp_id))
            ).scalar_one()
        try:
            res = await find_for_opportunity(tenant.id, opp)
            processed += 1
            total_found += res.get("found", 0)
            # Recompute the decision so the lane can flip to IDENTIFIED.
            celery_app.send_task(
                "mactech.decision.compute_one", args=[tenant_slug, str(opp_id)]
            )
        except Exception as exc:
            log.warning("prime_targets find failed for %s: %s", opp_id, exc)
    return {"status": "ok", "opportunities": processed, "prime_targets_found": total_found}


@celery_app.task(name="mactech.prime_targets.find_batch")
def find_batch_task(tenant_slug: str, limit: int = 30) -> dict[str, Any]:
    return asyncio.run(find_batch(tenant_slug, limit=limit))


@celery_app.task(name="mactech.prime_targets.find_one")
def find_one_task(tenant_slug: str, opportunity_id: str) -> dict[str, Any]:
    async def _run() -> dict[str, Any]:
        session_factory = async_session_factory()
        async with session_factory() as session:
            tenant = (
                await session.execute(select(Tenant).where(Tenant.slug == tenant_slug))
            ).scalar_one()
            opp = (
                await session.execute(
                    select(OpportunityRaw).where(OpportunityRaw.id == UUID(opportunity_id))
                )
            ).scalar_one()
        return await find_for_opportunity(tenant.id, opp)

    return asyncio.run(_run())
