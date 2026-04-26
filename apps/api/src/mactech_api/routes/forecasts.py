"""Forecasts feed — agency procurement forecasts (pre-SAM intent).

Sprint 20 + 21. Tenant-shared (forecasts are public-data signal).
Filters by tenant.target_naics, dedups across source URLs, and scores
on read using the same scoring engine as opportunities so the founder
sees the same ranking semantics in both feeds.

  GET /forecasts?upcoming_only=true&naics_filter=true&limit=100
  GET /recompetes  — forecasts with named incumbents, sorted by score
"""

from __future__ import annotations

import logging
from datetime import UTC, datetime
from typing import Annotated

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, ConfigDict
from sqlalchemy import cast, func, or_, select, text
from sqlalchemy.dialects.postgresql import JSONB

from mactech_api.auth import RequestContext, get_request_context
from mactech_db.models import (
    Founder,
    ForecastRaw,
    NaicsCode,
    SavedSearch,
)
from mactech_intelligence import (
    OpportunityFacts,
    ScoringContext,
    score_opportunity,
)

log = logging.getLogger(__name__)
router = APIRouter(tags=["forecasts"])


class _Out(BaseModel):
    model_config = ConfigDict(from_attributes=True)


class ForecastOut(_Out):
    id: str
    title: str
    agency: str | None
    contracting_office: str | None
    description: str | None
    naics_code: str | None
    naics_codes: list[str]
    set_aside: str | None
    contract_type: str | None
    estimated_value_low: float | None
    estimated_value_high: float | None
    estimated_value_text: str | None
    expected_solicitation_date: str | None
    expected_award_date: str | None
    period_of_performance_end: str | None
    incumbent_name: str | None
    incumbent_contract_number: str | None
    poc_name: str | None
    poc_email: str | None
    source_url: str
    source_host: str | None
    last_seen_at: str
    matches_target_naics: bool
    score: int
    score_breakdown: dict[str, int]
    assigned_founder_slug: str | None


class ForecastsResponse(_Out):
    total: int
    items: list[ForecastOut]
    target_naics_filter: bool
    target_naics: list[str]


# ── Scoring helpers ─────────────────────────────────────────────────


async def _build_scoring_context(ctx: RequestContext) -> ScoringContext:
    """Mirror score.py's _build_context but inline + simplified for the
    request path. Pulls primary/secondary NAICS, keywords, and the
    founder routing map."""
    tenant = ctx.tenant
    target = list(tenant.target_naics or [])
    if target:
        primary = target
        secondary: list[str] = []
    else:
        primary = (
            await ctx.session.execute(
                select(NaicsCode.code).where(NaicsCode.mactech_tier == "primary")
            )
        ).scalars().all()
        secondary = (
            await ctx.session.execute(
                select(NaicsCode.code).where(
                    NaicsCode.mactech_tier == "secondary"
                )
            )
        ).scalars().all()

    searches = (
        await ctx.session.execute(
            select(SavedSearch).where(SavedSearch.tenant_id == tenant.id)
        )
    ).scalars().all()
    keywords: list[str] = []
    seen: set[str] = set()
    for s in searches:
        for k in (s.filters or {}).get("keywords", []) or []:
            kl = k.strip().lower()
            if kl and kl not in seen:
                seen.add(kl)
                keywords.append(k.strip())

    routing_rows = (
        await ctx.session.execute(
            text(
                "select fnm.naics_code, f.slug "
                "from founder_naics_matrix fnm "
                "join founders f on f.id = fnm.founder_id"
            )
        )
    ).all()
    naics_to_founder: dict[str, str] = {}
    for code, slug in routing_rows:
        naics_to_founder.setdefault(code, slug)

    return ScoringContext(
        primary_naics=set(primary),
        secondary_naics=set(secondary),
        keywords=keywords,
        set_aside_sdvosb={"SDVOSBC", "SDVOSBS", "VSA", "VSS"},
        set_aside_small_biz={"SBA", "SBP", "SB"},
        sweet_spot_min=100_000,
        sweet_spot_max=10_000_000,
        naics_to_founder_slug=naics_to_founder,
    )


def _forecast_to_facts(fc: ForecastRaw) -> OpportunityFacts:
    """Adapt a ForecastRaw into the OpportunityFacts shape the scorer
    consumes. Forecasts don't have all fields (no posted_at, no
    incumbent UEI, no exclusion check) — the scorer handles None cleanly.
    """
    set_aside = fc.set_aside
    # DOE uses verbose strings; SAM/SCORER expects codes. Map a few
    # common DOE/APFS forms back to codes the scorer recognizes.
    if set_aside:
        sl = set_aside.lower()
        if "sdvosb" in sl:
            set_aside = "SDVOSBC"
        elif sl == "true" or "small business" in sl:
            set_aside = "SBA"
        elif sl == "sb":
            set_aside = "SBA"

    return OpportunityFacts(
        naics_code=fc.naics_code,
        set_aside=set_aside,
        # Use last_seen_at as a freshness proxy. Fresh forecasts (we just
        # discovered them) get the freshness component the same way new
        # opps do.
        posted_at=fc.last_seen_at,
        title=fc.title,
        description_text=fc.description,
        estimated_value_low=fc.estimated_value_low,
        estimated_value_high=fc.estimated_value_high,
        incumbent_uei=None,
        incumbent_end_date=fc.period_of_performance_end,
        incumbent_excluded=None,
        has_capability_match=False,
        has_capability_match_score=0,
    )


def _to_out(
    fc: ForecastRaw, *, target_set: set[str], scoring_ctx: ScoringContext
) -> ForecastOut:
    naics_set = set(fc.naics_codes or [])
    if fc.naics_code:
        naics_set.add(fc.naics_code)
    matches = bool(target_set) and bool(naics_set & target_set)

    facts = _forecast_to_facts(fc)
    result = score_opportunity(facts, scoring_ctx)

    return ForecastOut(
        id=str(fc.id),
        title=fc.title,
        agency=fc.agency,
        contracting_office=fc.contracting_office,
        description=fc.description,
        naics_code=fc.naics_code,
        naics_codes=list(fc.naics_codes or []),
        set_aside=fc.set_aside,
        contract_type=fc.contract_type,
        estimated_value_low=(
            float(fc.estimated_value_low)
            if fc.estimated_value_low is not None
            else None
        ),
        estimated_value_high=(
            float(fc.estimated_value_high)
            if fc.estimated_value_high is not None
            else None
        ),
        estimated_value_text=fc.estimated_value_text,
        expected_solicitation_date=(
            fc.expected_solicitation_date.isoformat()
            if fc.expected_solicitation_date
            else None
        ),
        expected_award_date=(
            fc.expected_award_date.isoformat()
            if fc.expected_award_date
            else None
        ),
        period_of_performance_end=(
            fc.period_of_performance_end.isoformat()
            if fc.period_of_performance_end
            else None
        ),
        incumbent_name=fc.incumbent_name,
        incumbent_contract_number=fc.incumbent_contract_number,
        poc_name=fc.poc_name,
        poc_email=fc.poc_email,
        source_url=fc.source_url,
        source_host=fc.source_host,
        last_seen_at=fc.last_seen_at.isoformat(),
        matches_target_naics=matches,
        score=result.score,
        score_breakdown=dict(result.breakdown),
        assigned_founder_slug=result.assigned_founder_slug,
    )


# ── Endpoints ────────────────────────────────────────────────────────


def _deduped_subquery():
    """DISTINCT ON (lower(title), expected_solicitation_date) with the
    most-complete row winning — same shape as /events dedup."""
    title_l = func.lower(ForecastRaw.title)
    sub = (
        select(ForecastRaw)
        .distinct(title_l, ForecastRaw.expected_solicitation_date)
        .order_by(
            title_l,
            ForecastRaw.expected_solicitation_date,
            ForecastRaw.naics_code.is_(None),
            ForecastRaw.estimated_value_high.is_(None),
            ForecastRaw.poc_email.is_(None),
            ForecastRaw.agency.is_(None),
            ForecastRaw.last_seen_at.desc(),
        )
        .subquery()
    )
    return sub


def _apply_naics_filter(stmt, target_set: set[str]):
    return stmt.where(
        or_(
            ForecastRaw.naics_code.in_(list(target_set)),
            cast(ForecastRaw.naics_codes, JSONB).op("?|")(list(target_set)),
        )
    )


@router.get("/forecasts", response_model=ForecastsResponse)
async def list_forecasts(
    ctx: Annotated[RequestContext, Depends(get_request_context)],
    upcoming_only: Annotated[bool, Query()] = True,
    limit: Annotated[int, Query(ge=1, le=400)] = 200,
    naics_filter: Annotated[
        bool, Query(description="Restrict to forecasts matching tenant.target_naics")
    ] = True,
) -> ForecastsResponse:
    target_naics = list(ctx.tenant.target_naics or [])
    target_set = set(target_naics)
    scoring_ctx = await _build_scoring_context(ctx)

    sub = _deduped_subquery()
    stmt = select(ForecastRaw).where(ForecastRaw.id.in_(select(sub.c.id)))

    if upcoming_only:
        now_d = datetime.now(UTC).date()
        stmt = stmt.where(
            (ForecastRaw.expected_solicitation_date >= now_d)
            | (ForecastRaw.expected_solicitation_date.is_(None))
        )
    if naics_filter and target_set:
        stmt = _apply_naics_filter(stmt, target_set)

    stmt = stmt.order_by(
        ForecastRaw.expected_solicitation_date.asc().nulls_last(),
        ForecastRaw.last_seen_at.desc(),
    ).limit(limit)

    rows = (await ctx.session.execute(stmt)).scalars().all()
    items = [
        _to_out(r, target_set=target_set, scoring_ctx=scoring_ctx) for r in rows
    ]
    # Sort by score descending so the highest-fit forecasts surface
    # first; preserve the date sub-ordering as a tiebreaker.
    items.sort(
        key=lambda x: (
            -x.score,
            x.expected_solicitation_date or "9999",
        )
    )
    return ForecastsResponse(
        total=len(items),
        items=items,
        target_naics_filter=bool(naics_filter and target_set),
        target_naics=target_naics,
    )


@router.get("/recompetes", response_model=ForecastsResponse)
async def list_recompetes(
    ctx: Annotated[RequestContext, Depends(get_request_context)],
    naics_filter: Annotated[bool, Query()] = True,
    limit: Annotated[int, Query(ge=1, le=400)] = 200,
) -> ForecastsResponse:
    """Forecasts with a named incumbent — the recompete watchlist.

    Per docs/APIFY_STRATEGY.md §3.3, the strongest single differentiator
    against GovWin is showing up to a recompete with the incumbent's
    weak spots already identified. This endpoint surfaces every
    forecast where we know who currently holds the contract, ranked
    by fit score.
    """
    target_naics = list(ctx.tenant.target_naics or [])
    target_set = set(target_naics)
    scoring_ctx = await _build_scoring_context(ctx)

    sub = _deduped_subquery()
    stmt = select(ForecastRaw).where(
        ForecastRaw.id.in_(select(sub.c.id)),
        ForecastRaw.incumbent_name.is_not(None),
        func.length(func.trim(ForecastRaw.incumbent_name)) > 0,
    )
    if naics_filter and target_set:
        stmt = _apply_naics_filter(stmt, target_set)

    stmt = stmt.order_by(
        ForecastRaw.estimated_value_high.desc().nulls_last(),
        ForecastRaw.last_seen_at.desc(),
    ).limit(limit)

    rows = (await ctx.session.execute(stmt)).scalars().all()
    items = [
        _to_out(r, target_set=target_set, scoring_ctx=scoring_ctx) for r in rows
    ]
    # Recompetes ordered by score first, then high estimated value, then
    # nearest expiry — in that order of intent ("high-fit, expensive,
    # expiring soon").
    items.sort(
        key=lambda x: (
            -x.score,
            -(x.estimated_value_high or 0),
            x.period_of_performance_end or "9999",
        )
    )
    return ForecastsResponse(
        total=len(items),
        items=items,
        target_naics_filter=bool(naics_filter and target_set),
        target_naics=target_naics,
    )


# Suppress unused-import (Founder reserved for future per-founder
# pillar joins on assigned_founder_slug)
_ = Founder
