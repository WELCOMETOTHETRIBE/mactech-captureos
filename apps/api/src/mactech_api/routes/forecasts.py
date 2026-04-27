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
from datetime import UTC, date, datetime, timedelta
from typing import Annotated

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, ConfigDict
from sqlalchemy import cast, func, or_, select, text
from sqlalchemy.dialects.postgresql import JSONB

from mactech_api.auth import RequestContext, get_request_context
from mactech_db.models import (
    AwardHistory,
    Founder,
    ForecastRaw,
    IncumbentSignal,
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
    assigned_founder_name: str | None
    assigned_founder_pillar: str | None
    incumbent_total_obligations: float | None
    incumbent_award_count: int | None
    incumbent_distress_score: int | None
    incumbent_distress_summary: str | None
    incumbent_sec_ticker: str | None
    incumbent_filings_last_90d: int | None


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
    # DOE uses verbose strings ("Service Disabled Veteran Owned Small
    # Business Set-Aside"); APFS uses short forms ("True", "SB",
    # "SDVOSB"). Both feed into a scorer that expects SAM-style codes.
    # Order matters: the SDVOSB check must precede the small-business
    # check because the verbose SDVOSB string contains "small business".
    if set_aside:
        sl = set_aside.lower()
        if (
            "sdvosb" in sl
            or "service disabled veteran" in sl
            or "service-disabled veteran" in sl
        ):
            set_aside = "SDVOSBC"
        elif "vosb" in sl or "veteran owned" in sl or "veteran-owned" in sl:
            # Non-SDVOSB veteran-owned still gets the small-biz code so
            # the scorer recognizes it as a meaningful set-aside.
            set_aside = "VSA"
        elif (
            sl == "true"
            or sl == "sb"
            or "small business set-aside" in sl
            or "total small business" in sl
            or sl == "small business"
        ):
            set_aside = "SBA"
        elif "8(a)" in sl or sl == "8a" or "hubzone" in sl or "wosb" in sl:
            # MacTech is SDVOSB, not 8(a)/HUBZone/WOSB-eligible — drop
            # the set_aside so we don't incorrectly score these as
            # "fit" small-biz set-asides.
            set_aside = None

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


def _forecast_specific_boost(fc: ForecastRaw) -> tuple[int, dict[str, int]]:
    """Forecasts have signal SAM opportunities don't: an expected
    solicitation date and a current contract POP-end date. Both inform
    "how urgent is this." Boost up to +20 points beyond the base
    OpportunityFacts score so the watchlist surfaces near-term work.

    Components (additive, capped at 20):
      - recompete_urgency: POP_end ≤ 6mo → +10, ≤ 12mo → +7, ≤ 24mo → +3
      - solicitation_imminent: RFP expected ≤ 3mo → +6, ≤ 6mo → +4
      - high_value_in_sweet_spot: value_high ≥ $5M (in sweet spot) → +4
    """
    today = date.today()
    breakdown: dict[str, int] = {}

    if fc.period_of_performance_end:
        days = (fc.period_of_performance_end - today).days
        if 0 <= days <= 180:
            breakdown["recompete_urgency"] = 10
        elif 180 < days <= 365:
            breakdown["recompete_urgency"] = 7
        elif 365 < days <= 730:
            breakdown["recompete_urgency"] = 3
        else:
            breakdown["recompete_urgency"] = 0
    else:
        breakdown["recompete_urgency"] = 0

    if fc.expected_solicitation_date:
        days = (fc.expected_solicitation_date - today).days
        if 0 <= days <= 90:
            breakdown["solicitation_imminent"] = 6
        elif 90 < days <= 180:
            breakdown["solicitation_imminent"] = 4
        else:
            breakdown["solicitation_imminent"] = 0
    else:
        breakdown["solicitation_imminent"] = 0

    if (
        fc.estimated_value_high is not None
        and fc.estimated_value_high >= 5_000_000
        and fc.estimated_value_high <= 50_000_000
    ):
        breakdown["high_value_in_sweet_spot"] = 4
    else:
        breakdown["high_value_in_sweet_spot"] = 0

    total = min(20, sum(breakdown.values()))
    return total, breakdown


def _to_out(
    fc: ForecastRaw,
    *,
    target_set: set[str],
    scoring_ctx: ScoringContext,
    founder_index: dict[str, tuple[str, str]],
    intel_index: dict[str, dict] | None = None,
) -> ForecastOut:
    naics_set = set(fc.naics_codes or [])
    if fc.naics_code:
        naics_set.add(fc.naics_code)
    matches = bool(target_set) and bool(naics_set & target_set)

    facts = _forecast_to_facts(fc)
    base = score_opportunity(facts, scoring_ctx)
    boost, boost_breakdown = _forecast_specific_boost(fc)
    final_score = min(100, base.score + boost)
    breakdown = {**dict(base.breakdown), **boost_breakdown}
    # Replace base reference with adjusted result for the rest of the
    # function — keeps the existing _to_out body unchanged.
    from dataclasses import replace
    result = replace(base, score=final_score, breakdown=breakdown)

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
        assigned_founder_name=(
            founder_index.get(result.assigned_founder_slug or "", (None, None))[0]
        ),
        assigned_founder_pillar=(
            founder_index.get(result.assigned_founder_slug or "", (None, None))[1]
        ),
        incumbent_total_obligations=(
            (intel_index or {}).get(fc.incumbent_name or "", {}).get(
                "total_obligations"
            )
        ),
        incumbent_award_count=(
            (intel_index or {}).get(fc.incumbent_name or "", {}).get("award_count")
        ),
        incumbent_distress_score=(
            (intel_index or {}).get(fc.incumbent_name or "", {}).get(
                "distress_score"
            )
        ),
        incumbent_distress_summary=(
            (intel_index or {}).get(fc.incumbent_name or "", {}).get(
                "distress_summary"
            )
        ),
        incumbent_sec_ticker=(
            (intel_index or {}).get(fc.incumbent_name or "", {}).get("sec_ticker")
        ),
        incumbent_filings_last_90d=(
            (intel_index or {}).get(fc.incumbent_name or "", {}).get(
                "filings_last_90d"
            )
        ),
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


async def _build_founder_index(ctx: RequestContext) -> dict[str, tuple[str, str]]:
    """slug → (full_name, pillar) so the API can echo back which founder
    owns each forecast's NAICS — without the web layer making N queries."""
    rows = (
        await ctx.session.execute(
            select(Founder.slug, Founder.full_name, Founder.pillar).where(
                Founder.tenant_id == ctx.tenant.id
            )
        )
    ).all()
    return {r.slug: (r.full_name, r.pillar) for r in rows}


async def _build_incumbent_intel_index(
    ctx: RequestContext, incumbent_names: list[str]
) -> dict[str, dict]:
    """Batch lookup: for every incumbent_name on a forecast, pull their
    USASpending federal-footprint + EDGAR distress signal in one round
    trip. Returns a dict keyed by the original name string.

    USASpending side is matched via pg_trgm similarity on
    awards_history.recipient_name. EDGAR side is matched on
    incumbent_signals.normalized_name (which is computed by the worker
    using the same normalize fn we use here).
    """
    if not incumbent_names:
        return {}

    # Dedupe + lowercase the candidates.
    seen: dict[str, str] = {}
    for n in incumbent_names:
        key = (n or "").strip()
        if key:
            seen[key] = _normalize_incumbent_name(key)
    if not seen:
        return {}

    # USASpending: total obligations + award count per incumbent name.
    # Use pg_trgm word_similarity to tolerate the case difference between
    # forecast feeds (DOE uppercase, DHS mixed) and awards_history.
    awards_rows = (
        await ctx.session.execute(
            select(
                AwardHistory.recipient_name,
                func.sum(AwardHistory.obligated_amount).label("total"),
                func.count(AwardHistory.id).label("award_count"),
            )
            .where(
                AwardHistory.recipient_name.is_not(None),
                func.lower(AwardHistory.recipient_name).in_(
                    [n.lower() for n in seen.keys()]
                ),
            )
            .group_by(AwardHistory.recipient_name)
        )
    ).all()
    awards_lookup: dict[str, tuple[float, int]] = {}
    for r in awards_rows:
        awards_lookup[r.recipient_name.lower()] = (
            float(r.total) if r.total is not None else 0.0,
            int(r.award_count or 0),
        )

    # EDGAR signals — match on normalized_name.
    normalized_set = set(seen.values())
    signals_rows = (
        await ctx.session.execute(
            select(IncumbentSignal).where(
                IncumbentSignal.normalized_name.in_(list(normalized_set))
            )
        )
    ).scalars().all()
    signals_lookup: dict[str, IncumbentSignal] = {
        s.normalized_name: s for s in signals_rows
    }

    out: dict[str, dict] = {}
    for original, normalized in seen.items():
        awards = awards_lookup.get(original.lower())
        sig = signals_lookup.get(normalized)
        out[original] = {
            "total_obligations": awards[0] if awards else None,
            "award_count": awards[1] if awards else None,
            "distress_score": sig.distress_score if sig else None,
            "distress_summary": sig.distress_summary if sig else None,
            "sec_ticker": sig.sec_ticker if sig else None,
            "filings_last_90d": sig.filings_last_90d_count if sig else None,
        }
    return out


def _normalize_incumbent_name(name: str) -> str:
    """Match worker's normalize_name (edgar_signals._normalize_name)."""
    import re as _re

    s = name.lower()
    s = _re.sub(r"[,\.\(\)\[\]&]+", " ", s)
    suffixes = (
        r"\b(inc|incorporated|llc|ltd|limited|corp|corporation|co|company|"
        r"holdings|group|technologies|technology|services|solutions|"
        r"systems|federal|government)\b"
    )
    s = _re.sub(suffixes, "", s)
    s = _re.sub(r"\s+", " ", s).strip()
    return s


_SET_ASIDE_SCOPE_TO_NORMALIZED = {
    "sdvosb": {"SDVOSBC"},
    "sb": {"SBA", "SDVOSBC", "VSA"},  # any small-biz family
    "all": None,
}


def _matches_set_aside_scope(
    fc: ForecastRaw, scope: str, normalized_lookup
) -> bool:
    """Filter forecasts by the requested set-aside scope. We re-run the
    same normalization the scorer uses so the scope filter is consistent
    with how rows are scored."""
    allowed = _SET_ASIDE_SCOPE_TO_NORMALIZED.get(scope.lower())
    if allowed is None:
        return True
    facts = normalized_lookup(fc)
    return facts.set_aside in allowed


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
    founder_index = await _build_founder_index(ctx)

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
    intel_index = await _build_incumbent_intel_index(
        ctx, [r.incumbent_name for r in rows if r.incumbent_name]
    )
    items = [
        _to_out(
            r,
            target_set=target_set,
            scoring_ctx=scoring_ctx,
            founder_index=founder_index,
            intel_index=intel_index,
        )
        for r in rows
    ]
    items.sort(
        key=lambda x: (-x.score, x.expected_solicitation_date or "9999")
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
    agency: Annotated[
        str | None,
        Query(description="Restrict to a single agency code (e.g. 'DHS', 'DOE')"),
    ] = None,
    set_aside_scope: Annotated[
        str,
        Query(
            description="'sdvosb' (only SDVOSB-set-aside), 'sb' (any small-biz family), 'all' (default)"
        ),
    ] = "all",
    pop_window_months: Annotated[
        int | None,
        Query(
            ge=1,
            le=60,
            description="Restrict to recompetes whose POP ends within N months",
        ),
    ] = None,
    assigned_founder: Annotated[
        str | None,
        Query(description="Restrict to forecasts auto-assigned to this founder slug"),
    ] = None,
    mine_only: Annotated[
        bool,
        Query(
            description="When true, restrict to the calling founder's NAICS lane"
        ),
    ] = False,
) -> ForecastsResponse:
    """Forecasts with a named incumbent — the recompete watchlist.

    Per docs/APIFY_STRATEGY.md §3.3, the strongest single differentiator
    against GovWin is showing up to a recompete with the incumbent's
    weak spots already identified. This endpoint surfaces every
    forecast where we know who currently holds the contract, ranked
    by fit score, with optional filters for agency / set-aside /
    POP-end window / per-founder lane.
    """
    target_naics = list(ctx.tenant.target_naics or [])
    target_set = set(target_naics)
    scoring_ctx = await _build_scoring_context(ctx)
    founder_index = await _build_founder_index(ctx)

    # `mine_only` resolves to the calling founder's slug when one is
    # linked. Frontends use this for the "Your recompetes" tile.
    if mine_only and ctx.founder is not None and not assigned_founder:
        assigned_founder = ctx.founder.slug

    sub = _deduped_subquery()
    stmt = select(ForecastRaw).where(
        ForecastRaw.id.in_(select(sub.c.id)),
        ForecastRaw.incumbent_name.is_not(None),
        func.length(func.trim(ForecastRaw.incumbent_name)) > 0,
    )
    if naics_filter and target_set:
        stmt = _apply_naics_filter(stmt, target_set)
    if agency:
        stmt = stmt.where(ForecastRaw.agency == agency.upper())
    if pop_window_months is not None:
        from datetime import timedelta as _td
        end_max = datetime.now(UTC).date() + _td(days=pop_window_months * 30)
        stmt = stmt.where(
            ForecastRaw.period_of_performance_end.is_not(None),
            ForecastRaw.period_of_performance_end <= end_max,
            ForecastRaw.period_of_performance_end >= datetime.now(UTC).date(),
        )

    stmt = stmt.order_by(
        ForecastRaw.estimated_value_high.desc().nulls_last(),
        ForecastRaw.last_seen_at.desc(),
    ).limit(limit)

    rows = (await ctx.session.execute(stmt)).scalars().all()
    intel_index = await _build_incumbent_intel_index(
        ctx, [r.incumbent_name for r in rows if r.incumbent_name]
    )
    items = [
        _to_out(
            r,
            target_set=target_set,
            scoring_ctx=scoring_ctx,
            founder_index=founder_index,
            intel_index=intel_index,
        )
        for r in rows
    ]

    # Set-aside scope filter (post-scoring so it operates on normalized
    # codes instead of raw verbose strings).
    allowed = _SET_ASIDE_SCOPE_TO_NORMALIZED.get(set_aside_scope.lower())
    if allowed is not None:
        items = [
            i for i in items
            if _forecast_to_facts_set_aside(i.set_aside) in allowed
        ]

    # Founder filter — assigned_founder is the result of NAICS routing.
    if assigned_founder:
        items = [
            i for i in items if i.assigned_founder_slug == assigned_founder
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


def _forecast_to_facts_set_aside(raw: str | None) -> str | None:
    """Compact mirror of the SDVOSB normalization used inside
    _forecast_to_facts. Used by the /recompetes set_aside_scope filter."""
    if not raw:
        return None
    sl = raw.lower()
    if (
        "sdvosb" in sl
        or "service disabled veteran" in sl
        or "service-disabled veteran" in sl
    ):
        return "SDVOSBC"
    if "vosb" in sl or "veteran owned" in sl or "veteran-owned" in sl:
        return "VSA"
    if (
        sl == "true"
        or sl == "sb"
        or "small business set-aside" in sl
        or "total small business" in sl
        or sl == "small business"
    ):
        return "SBA"
    if "8(a)" in sl or sl == "8a" or "hubzone" in sl or "wosb" in sl:
        return None
    return raw
