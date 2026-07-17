"""Phase 1 opportunity scoring.

Implements the 7-component weighted-sum from docs/SCHEMA.md §scoring,
plus founder routing using the founder_naics_matrix.

Component   Max  Phase-1 logic
NAICS match  25  primary list 25; secondary list 15;
                 future: embedding-similar 5 (returns 0 today)
Keyword      20  fraction of unique tenant keywords matched in
                 title+description_text scaled to 0..20
Set-aside    15  SDVOSB-family 15; small-biz-family 8; else 0
Value sanity 10  scaled by overlap with tenant sweet-spot range;
                 returns 5 baseline when no estimate is present
Incumbent    15  baseline 5; +5 if exclusions clean; +5 if no
weakness         active end-date (likely already-expired contract)
Founder      10  flat 10 for now; load model arrives in phase 2
availability
Freshness     5  5 if posted ≤48h ago; linear decline to 0 at 30 days

Total: 100. Output is the integer score, the breakdown dict, and the
assigned founder slug if any.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, date, datetime
from decimal import Decimal
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from mactech_intelligence.clause_detector import ClauseFindings
    from mactech_intelligence.scoring_high_moat import HighMoatConfig


@dataclass(frozen=True)
class ScoringContext:
    """Per-tenant scoring inputs. Phase 1 builds this from MacTech's
    saved_searches + tenant config; Phase 2 will pull from per-tenant
    state."""

    primary_naics: set[str]
    secondary_naics: set[str]
    keywords: list[str]  # unioned across the tenant's saved_searches
    set_aside_sdvosb: set[str]  # codes treated as SDVOSB-family
    set_aside_small_biz: set[str]  # codes treated as small-biz-family
    sweet_spot_min: int
    sweet_spot_max: int
    naics_to_founder_slug: dict[str, str]  # routing — first founder per naics
    # Optional. When set, the scoring worker will additionally compute the
    # parallel high_moat_score. Sourced from the tenant's
    # config/mactech_tenant_defaults.yml ``high_moat_scoring`` block.
    high_moat_config: HighMoatConfig | None = None


@dataclass(frozen=True)
class OpportunityFacts:
    """The opportunity-side facts the scorer needs. Decoupled from the
    ORM so the scoring engine can be unit-tested without a database."""

    naics_code: str | None
    set_aside: str | None
    posted_at: datetime | None
    title: str
    description_text: str | None
    estimated_value_low: Decimal | None
    estimated_value_high: Decimal | None
    incumbent_uei: str | None
    incumbent_end_date: date | None
    incumbent_excluded: bool | None  # None when not checked
    has_capability_match: bool  # placeholder for the embedding-similar 5pt
    has_capability_match_score: int = 0  # 0..5
    # Fields below are only consumed by the parallel high-moat scorer.
    # All None-tolerant so existing callers of score_opportunity stay
    # unchanged.
    attachment_text: str | None = None
    interested_vendors_count: int | None = None
    interested_vendors_cyber_count: int | None = None
    clause_findings: ClauseFindings | None = None
    agency: str | None = None
    subagency: str | None = None
    is_active: bool = True


@dataclass(frozen=True)
class ScoringResult:
    score: int
    breakdown: dict[str, int]
    assigned_founder_slug: str | None
    notes: list[str] = field(default_factory=list)


SDVOSB_CODES: frozenset[str] = frozenset({"SDVOSBC", "SDVOSBS", "VSA", "VSS"})
SMALL_BIZ_CODES: frozenset[str] = frozenset({"SBA", "SBP", "SB"})

FRESHNESS_FULL_HOURS = 48
FRESHNESS_ZERO_DAYS = 30


def _component_naics(opp: OpportunityFacts, ctx: ScoringContext) -> int:
    if not opp.naics_code:
        return 0
    if opp.naics_code in ctx.primary_naics:
        return 25
    if opp.naics_code in ctx.secondary_naics:
        return 15
    return 0


def _component_keywords(opp: OpportunityFacts, ctx: ScoringContext) -> int:
    if not ctx.keywords:
        return 0
    blob = " ".join(filter(None, [opp.title, opp.description_text])).lower()
    if not blob.strip():
        return 0
    seen = sum(1 for k in ctx.keywords if k.lower() in blob)
    if seen == 0:
        return 0
    fraction = min(1.0, seen / max(1, len(ctx.keywords)))
    # Most opps will only match a handful of keywords; reward the first
    # match more than the marginal one. sqrt-curve.
    curved = fraction**0.5
    return round(20 * curved)


def _component_set_aside(opp: OpportunityFacts, ctx: ScoringContext) -> int:
    if not opp.set_aside:
        return 0
    code = opp.set_aside.upper()
    if code in ctx.set_aside_sdvosb:
        return 15
    if code in ctx.set_aside_small_biz:
        return 8
    return 0


def _component_value_sanity(opp: OpportunityFacts, ctx: ScoringContext) -> int:
    low = opp.estimated_value_low
    high = opp.estimated_value_high
    if low is None and high is None:
        return 5  # baseline when SAM doesn't surface estimate
    band_low = float(low) if low is not None else float(high or 0)
    band_high = float(high) if high is not None else float(low or 0)
    sweet_low, sweet_high = ctx.sweet_spot_min, ctx.sweet_spot_max
    overlap_low = max(band_low, sweet_low)
    overlap_high = min(band_high, sweet_high)
    if overlap_high >= overlap_low:
        return 10  # any overlap with sweet spot
    # No overlap: distance from the nearest sweet-spot edge, in log scale.
    if band_high < sweet_low:
        return 3
    if band_low > sweet_high:
        return 2
    return 5


def _component_incumbent_weakness(opp: OpportunityFacts) -> int:
    score = 5  # baseline
    if opp.incumbent_excluded is False:
        # We were able to verify the incumbent is clean — small confidence boost
        # (we were able to do enrichment), not a "weakness" per se.
        score += 3
    elif opp.incumbent_excluded is True:
        # Incumbent debarred — strong indicator they will not win the recompete.
        score = 15
    if (
        opp.incumbent_end_date is not None
        and opp.posted_at is not None
        and opp.incumbent_end_date < opp.posted_at.date()
    ):
        # Incumbent contract already past its current end-date when this opp
        # posted — strong recompete signal.
        score = max(score, 12)
    return min(score, 15)


def _component_founder_availability() -> int:
    # Phase 1: every founder has theoretical capacity. The load model that
    # introduces variance lives in phase 2 alongside the pursuit pipeline.
    return 10


def _component_freshness(opp: OpportunityFacts) -> int:
    if opp.posted_at is None:
        return 0
    age = datetime.now(UTC) - opp.posted_at
    hours = age.total_seconds() / 3600
    if hours <= FRESHNESS_FULL_HOURS:
        return 5
    days = hours / 24
    if days >= FRESHNESS_ZERO_DAYS:
        return 0
    # Linear decline from 5 (at 2 days) to 0 (at 30 days).
    span = FRESHNESS_ZERO_DAYS - FRESHNESS_FULL_HOURS / 24
    elapsed = days - FRESHNESS_FULL_HOURS / 24
    return round(5 * (1 - elapsed / span))


def _component_capability_match(opp: OpportunityFacts) -> int:
    # 0..5; supplied by the upstream embedding-similarity calculation.
    return max(0, min(5, opp.has_capability_match_score))


def _route_founder(naics: str | None, ctx: ScoringContext) -> str | None:
    if naics is None:
        return None
    return ctx.naics_to_founder_slug.get(naics)


def score_opportunity(opp: OpportunityFacts, ctx: ScoringContext) -> ScoringResult:
    naics_pts = _component_naics(opp, ctx)
    keyword_pts = _component_keywords(opp, ctx)
    set_aside_pts = _component_set_aside(opp, ctx)
    value_pts = _component_value_sanity(opp, ctx)
    incumbent_pts = _component_incumbent_weakness(opp)
    founder_pts = _component_founder_availability()
    freshness_pts = _component_freshness(opp)
    capability_pts = _component_capability_match(opp)

    breakdown = {
        "naics_match": naics_pts,
        "keyword_density": keyword_pts,
        "set_aside_fit": set_aside_pts,
        "value_sanity": value_pts,
        "incumbent_weakness": incumbent_pts,
        "founder_availability": founder_pts,
        "freshness": freshness_pts,
        "capability_match": capability_pts,
    }
    score = sum(breakdown.values())
    score = max(0, min(100, score))

    notes: list[str] = []
    if not opp.naics_code:
        notes.append("opp has no NAICS")
    if not opp.set_aside:
        notes.append("opp has no set-aside")

    return ScoringResult(
        score=score,
        breakdown=breakdown,
        assigned_founder_slug=_route_founder(opp.naics_code, ctx),
        notes=notes,
    )
