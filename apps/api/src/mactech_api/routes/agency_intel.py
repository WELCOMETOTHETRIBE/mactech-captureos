"""Agency-level NAICS spending intel.

Phase 3 Week 12 (UX Sprint 5). Backs the "Agency intel" card on the
opportunity detail page.

Endpoint:
  GET /opportunities/{id}/agency-intel

Behaviour:
  - Look up cached row by (agency_name, naics_code, lookback_days).
  - If row is fresh (≤7 days), return immediately.
  - If stale or missing, fire a USASpending query, persist, and return.
  - On lookup failure, persist a failure row to avoid retry storms; the
    record is invalidated after 24 hours so transient failures self-heal.
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from statistics import median
from typing import Annotated, Any
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, ConfigDict
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from mactech_api.auth import RequestContext, get_request_context
from mactech_db.models import AgencyNaicsIntel, OpportunityRaw
from mactech_integrations.usaspending import UsaSpendingClient
from mactech_integrations.usaspending.client import (
    UsaSpendingError,
    UsaSpendingRateLimitError,
)

log = logging.getLogger(__name__)
router = APIRouter(tags=["agency-intel"])

LOOKBACK_DAYS = 365
CACHE_TTL_DAYS = 7
FAILURE_TTL_DAYS = 1
SAMPLE_LIMIT = 100  # how many awards we pull to compute aggregates


class _Out(BaseModel):
    model_config = ConfigDict(from_attributes=True)


class TopRecipient(_Out):
    name: str
    uei: str | None
    total: float
    award_count: int


class AgencyIntelOut(_Out):
    agency_name: str
    naics_code: str
    lookback_days: int
    award_count: int
    total_obligated: float | None
    avg_award_value: float | None
    median_award_value: float | None
    top_recipients: list[TopRecipient]
    sample_size: int | None
    refreshed_at: str
    cache_age_hours: float
    is_fresh: bool
    lookup_failed: bool
    failure_note: str | None


def _normalize_agency(name: str) -> str:
    """USASpending matches toptier names verbatim. SAM gives us deeper
    paths like 'DEPT OF VETERANS AFFAIRS.VETERANS HEALTH ADMINISTRATION'
    or full names with extra punctuation. Take the first dot-separated
    chunk and uppercase it.
    """
    if not name:
        return ""
    head = name.split(".", 1)[0].strip()
    return head.upper()


def _resolve_agency_for_lookup(opp: OpportunityRaw) -> str:
    raw = (opp.agency or "").strip()
    if not raw:
        return ""
    # Many SAM agency strings are already uppercase toptier names; keep
    # the first dot-separated segment.
    return raw.split(".", 1)[0].strip()


async def _fetch_from_usaspending(
    agency_name: str, naics_code: str, lookback_days: int
) -> tuple[list[dict[str, Any]], int]:
    """Returns (rows, sample_size_pulled). Each row is a flat dict."""
    end = datetime.now(timezone.utc).date()
    start = end - timedelta(days=lookback_days)
    rows: list[dict[str, Any]] = []
    async with UsaSpendingClient() as client:
        page = await client.search_awards(
            naics_codes=[naics_code],
            awarding_agency_name=agency_name,
            time_period_start=start,
            time_period_end=end,
            award_amount_min=1,
            limit=SAMPLE_LIMIT,
            page=1,
        )
    for r in page.results:
        amount = float(r.award_amount) if r.award_amount is not None else 0.0
        rows.append(
            {
                "recipient_name": r.recipient_name or "(unknown)",
                "recipient_uei": r.recipient_uei,
                "amount": amount,
            }
        )
    return rows, len(rows)


def _aggregate(rows: list[dict[str, Any]]) -> dict[str, Any]:
    if not rows:
        return {
            "award_count": 0,
            "total_obligated": None,
            "avg_award_value": None,
            "median_award_value": None,
            "top_recipients": [],
        }

    amounts = [r["amount"] for r in rows if r["amount"] > 0]
    total = sum(amounts) if amounts else 0.0
    avg = (total / len(amounts)) if amounts else None
    med = float(median(amounts)) if amounts else None

    by_recipient: dict[str, dict[str, Any]] = {}
    for r in rows:
        name = r["recipient_name"] or "(unknown)"
        if name not in by_recipient:
            by_recipient[name] = {
                "name": name,
                "uei": r["recipient_uei"],
                "total": 0.0,
                "award_count": 0,
            }
        by_recipient[name]["total"] += r["amount"] or 0.0
        by_recipient[name]["award_count"] += 1

    top = sorted(by_recipient.values(), key=lambda x: x["total"], reverse=True)[:5]

    return {
        "award_count": len(rows),
        "total_obligated": float(total) if amounts else None,
        "avg_award_value": float(avg) if avg is not None else None,
        "median_award_value": med,
        "top_recipients": top,
    }


def _to_out(row: AgencyNaicsIntel) -> AgencyIntelOut:
    age = datetime.now(timezone.utc) - row.refreshed_at
    age_hours = age.total_seconds() / 3600
    fresh_threshold = (
        FAILURE_TTL_DAYS * 24 if row.lookup_failed else CACHE_TTL_DAYS * 24
    )
    is_fresh = age_hours <= fresh_threshold
    top: list[TopRecipient] = []
    if row.top_recipients:
        for tr in row.top_recipients:
            if isinstance(tr, dict):
                try:
                    top.append(
                        TopRecipient(
                            name=str(tr.get("name") or "(unknown)"),
                            uei=tr.get("uei") if isinstance(tr.get("uei"), str) else None,
                            total=float(tr.get("total") or 0),
                            award_count=int(tr.get("award_count") or 0),
                        )
                    )
                except (TypeError, ValueError):
                    continue
    return AgencyIntelOut(
        agency_name=row.agency_name,
        naics_code=row.naics_code,
        lookback_days=row.lookback_days,
        award_count=row.award_count,
        total_obligated=float(row.total_obligated) if row.total_obligated is not None else None,
        avg_award_value=float(row.avg_award_value) if row.avg_award_value is not None else None,
        median_award_value=(
            float(row.median_award_value) if row.median_award_value is not None else None
        ),
        top_recipients=top,
        sample_size=row.sample_size,
        refreshed_at=row.refreshed_at.isoformat(),
        cache_age_hours=age_hours,
        is_fresh=is_fresh,
        lookup_failed=row.lookup_failed,
        failure_note=row.failure_note,
    )


@router.get(
    "/opportunities/{opportunity_id}/agency-intel",
    response_model=AgencyIntelOut,
)
async def get_agency_intel(
    opportunity_id: UUID,
    ctx: Annotated[RequestContext, Depends(get_request_context)],
) -> AgencyIntelOut:
    opp = (
        await ctx.session.execute(
            select(OpportunityRaw).where(OpportunityRaw.id == opportunity_id)
        )
    ).scalar_one_or_none()
    if opp is None:
        raise HTTPException(status_code=404, detail="opportunity not found")

    agency_name = _resolve_agency_for_lookup(opp)
    naics = (opp.naics_code or "").strip()
    if not agency_name or not naics:
        raise HTTPException(
            status_code=409,
            detail=(
                "this opportunity is missing agency name or NAICS code; "
                "agency intel needs both."
            ),
        )

    cached = (
        await ctx.session.execute(
            select(AgencyNaicsIntel).where(
                AgencyNaicsIntel.agency_name == agency_name,
                AgencyNaicsIntel.naics_code == naics,
                AgencyNaicsIntel.lookback_days == LOOKBACK_DAYS,
            )
        )
    ).scalar_one_or_none()

    if cached is not None:
        out = _to_out(cached)
        if out.is_fresh:
            return out
        # Fall through to refresh; on failure we return the stale value.

    # Fetch fresh.
    try:
        rows, sample_size = await _fetch_from_usaspending(
            agency_name, naics, LOOKBACK_DAYS
        )
        agg = _aggregate(rows)
        failure_note = None
        lookup_failed = False
    except UsaSpendingRateLimitError as exc:
        log.warning("usaspending rate limited: %s", exc)
        if cached is not None:
            return _to_out(cached)
        raise HTTPException(
            status_code=503,
            detail="USASpending is rate-limiting us. Try again in a minute.",
        ) from exc
    except UsaSpendingError as exc:
        log.warning("usaspending error: %s", exc)
        agg = {
            "award_count": 0,
            "total_obligated": None,
            "avg_award_value": None,
            "median_award_value": None,
            "top_recipients": [],
        }
        sample_size = 0
        failure_note = f"USASpending error: {exc}"[:255]
        lookup_failed = True
    except Exception as exc:
        log.exception("agency intel unexpected error: %s", exc)
        if cached is not None:
            return _to_out(cached)
        raise HTTPException(
            status_code=502, detail=f"agency intel failed: {exc.__class__.__name__}"
        ) from exc

    # Upsert.
    if cached is None:
        row = AgencyNaicsIntel(
            agency_name=agency_name,
            naics_code=naics,
            lookback_days=LOOKBACK_DAYS,
            award_count=agg["award_count"],
            total_obligated=(
                Decimal(str(agg["total_obligated"]))
                if agg["total_obligated"] is not None
                else None
            ),
            avg_award_value=(
                Decimal(str(agg["avg_award_value"]))
                if agg["avg_award_value"] is not None
                else None
            ),
            median_award_value=(
                Decimal(str(agg["median_award_value"]))
                if agg["median_award_value"] is not None
                else None
            ),
            top_recipients=agg["top_recipients"],
            sample_size=sample_size,
            lookup_failed=lookup_failed,
            failure_note=failure_note,
            refreshed_at=datetime.now(timezone.utc),
        )
        ctx.session.add(row)
        try:
            await ctx.session.flush()
        except IntegrityError:
            # Concurrent refresh — re-read.
            await ctx.session.rollback()
            row = (
                await ctx.session.execute(
                    select(AgencyNaicsIntel).where(
                        AgencyNaicsIntel.agency_name == agency_name,
                        AgencyNaicsIntel.naics_code == naics,
                        AgencyNaicsIntel.lookback_days == LOOKBACK_DAYS,
                    )
                )
            ).scalar_one()
    else:
        cached.award_count = agg["award_count"]
        cached.total_obligated = (
            Decimal(str(agg["total_obligated"]))
            if agg["total_obligated"] is not None
            else None
        )
        cached.avg_award_value = (
            Decimal(str(agg["avg_award_value"]))
            if agg["avg_award_value"] is not None
            else None
        )
        cached.median_award_value = (
            Decimal(str(agg["median_award_value"]))
            if agg["median_award_value"] is not None
            else None
        )
        cached.top_recipients = agg["top_recipients"]
        cached.sample_size = sample_size
        cached.lookup_failed = lookup_failed
        cached.failure_note = failure_note
        cached.refreshed_at = datetime.now(timezone.utc)
        await ctx.session.flush()
        row = cached

    # Suppress unused-name parameter
    _ = ctx.tenant
    return _to_out(row)


# Suppress unused-import false positive; reserved for stale-while-revalidate
# follow-up that uses the normalized name.
_ = _normalize_agency
