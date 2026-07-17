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

from datetime import UTC, datetime, timedelta
from typing import Annotated, Any
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import RedirectResponse
from mactech_db.models import (
    CyberScopeAnalysis,
    ExclusionsCache,
    Founder,
    OpportunityDecisionVector,
    OpportunityEnriched,
    OpportunityGate,
    OpportunityPrimeTarget,
    OpportunityRaw,
    OpportunityScore,
    PrimeTarget,
    PursuitAction,
    PursuitRecommendation,
)
from pydantic import BaseModel, ConfigDict
from sqlalchemy import select, text

from mactech_api.auth import RequestContext, get_request_context

router = APIRouter(tags=["opportunities"])

# Shared by the list query, its count, and the sidebar facets so that a facet
# count never promises more rows than the list will actually show.
_NOT_EXPIRED_SQL = "(o.response_deadline is null or o.response_deadline >= now())"

# The SAM beat runs every 2h; tolerate a few missed ticks before crying stale.
_INGEST_STALE_AFTER = timedelta(hours=12)

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


class CyberScopeBlock(_Out):
    """Parallel cyber scope analysis (UFGS tiers, FRCS, hidden scope)."""

    score: int
    likelihood: str
    pursuit_model: str
    ufgs_center_of_gravity: bool
    ufgs_tier_1_hit: bool
    top_ufgs_sections: list[str]
    top_signals: list[dict[str, Any]]
    scan_pass: str
    attachments_pending: bool
    analysis_id: str | None
    analysis_url: str | None


class HighMoatBlock(_Out):
    """Parallel high-moat (UFGS 25 / FRCS cyber) score block. Null on the
    parent ScoreBlock when the tenant has no high_moat_scoring config or
    the opportunity hasn't been re-scored since the column was added."""

    score: int
    breakdown: dict[str, int]
    is_high_probability_easy_win: bool
    clause_hits: list[str]
    clearance_hits: list[str]
    role_hits: list[str]
    top_clearance: str  # 'TS_SCI' | 'TS' | 'S' | 'NONE'
    why_it_matters_seed: str | None


class ScoreBlock(_Out):
    score: int
    breakdown: dict[str, int]
    assigned_founder_slug: str | None
    why_it_matters: str | None
    why_it_matters_model: str | None
    scored_at: str | None
    high_moat: HighMoatBlock | None = None
    cyber_scope: CyberScopeBlock | None = None


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
    # Provenance of the raw text, so the UI can label it honestly: SAM notices
    # show "Original SAM text", a promoted BuildingConnected invite shows the
    # invitation email, etc. Mirrors opportunities_raw.source.
    source: str


class CapabilityMatch(_Out):
    id: str
    title: str
    summary: str
    similarity: float  # 0..1 cosine


class DecisionVectorOut(_Out):
    relevance: int
    prime_fit: int
    subcontract_fit: int
    winability: int
    deliverability: int
    strategic_value: int
    urgency: int
    evidence_completeness: int
    overall_priority: int


class GateOut(_Out):
    gate_code: str
    status: str
    severity: str
    reason_code: str | None
    detail: str | None


class DecisionBlock(_Out):
    pursuit_lane: str
    reason_codes: list[str]
    confidence: str
    lane_weight_profile: str
    needs_human_review: bool
    vector: DecisionVectorOut
    gates: list[GateOut]
    knowledge_pack_version: str | None
    formula_version: str | None
    computed_at: str | None


class PrimeTargetOut(_Out):
    name: str
    uei: str | None
    target_type: str
    confidence: str
    why_target: str | None
    recommended_contact_role: str | None
    outreach_deadline: str | None
    rank: int


class PursuitActionOut(_Out):
    sequence: int
    action: str
    owner_founder_slug: str | None
    due_at: str | None
    status: str


class PursuitPlanBlock(_Out):
    pursuit_lane: str
    executive_decision: str
    why_this_is_real: str | None
    mactech_work_package: str | None
    blocking_issues: list[str]
    prime_target_names: list[str]
    recommended_owner_slug: str | None
    decision_deadline: str | None
    response_deadline: str | None
    confidence: str
    actions: list[PursuitActionOut]


class OpportunityDetail(_Out):
    opportunity: OpportunityHeader
    description: DescriptionBlock
    incumbent: IncumbentBlock | None
    score: ScoreBlock | None
    decision: DecisionBlock | None
    pursuit_plan: PursuitPlanBlock | None
    prime_targets: list[PrimeTargetOut]
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
        delta = opp.response_deadline - datetime.now(UTC)
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


class OpportunityListItem(_Out):
    id: str
    notice_id: str
    title: str
    notice_type: str | None
    set_aside: str | None
    naics_code: str | None
    agency_short: str | None
    posted_at: str | None
    response_deadline: str | None
    days_until_deadline: int | None
    score: int | None
    why_it_matters: str | None
    incumbent_summary: str | None
    assigned_founder_slug: str | None
    # Parallel high-moat track. Null when never computed.
    high_moat_score: int | None = None
    is_sweet_spot: bool = False
    # Claude-generated one-sentence scope summary. Populated by the
    # post-score worker chain on score ≥ 60. When present, the UI
    # promotes it above the raw SAM title (which is often formatted for
    # the agency's internal system rather than human triage).
    scope_one_sentence: str | None = None
    cyber_scope_score: int | None = None
    cyber_scope_likelihood: str | None = None
    cyber_scope_pursuit_model: str | None = None
    cyber_scope_analysis_id: str | None = None
    cyber_scope_attachments_pending: bool = False


class OpportunityListResponse(_Out):
    page: int
    limit: int
    total: int
    has_next: bool
    items: list[OpportunityListItem]
    facets: dict[str, dict[str, int]]


class IngestFeed(_Out):
    source: str
    key: str
    last_run_at: datetime | None = None
    last_success_at: datetime | None = None
    last_status: str | None = None
    last_error: str | None = None


class IngestStatus(_Out):
    # 'ok' | 'degraded' | 'stale' | 'failing' | 'unknown'
    status: str
    last_success_at: datetime | None = None
    last_run_at: datetime | None = None
    sources_ok: int = 0
    sources_error: int = 0
    first_error: str | None = None
    feeds: list[IngestFeed] = []


def classify_ingest(
    ok: int,
    errored: int,
    newest_success: datetime | None,
    now: datetime,
) -> str:
    """Roll per-source ingest state up into one feed verdict.

    Ordering matters: 'failing' outranks 'stale' because every-source-down is
    the actionable diagnosis, while staleness is only its symptom. A feed that
    has never once succeeded is 'unknown', not 'stale' — there is no baseline
    to be stale against.
    """
    if errored and not ok:
        return "failing"
    if newest_success is None:
        return "unknown"
    # Generous relative to the 2-hourly beat: a couple of missed ticks is
    # noise, half a day without a single success is a real outage.
    if now - newest_success > _INGEST_STALE_AFTER:
        return "stale"
    if errored:
        return "degraded"
    return "ok"


def _short_agency_path(p: str | None) -> str | None:
    if not p:
        return None
    return p.split(".")[0].strip()


def _days_until(dt: datetime | None) -> int | None:
    if dt is None:
        return None
    delta = dt - datetime.now(UTC)
    return int(delta.total_seconds() / 86400)


@router.get("/opportunities", response_model=OpportunityListResponse)
async def list_opportunities(
    ctx: Annotated[RequestContext, Depends(get_request_context)],
    page: int = 1,
    limit: int = 25,
    q: str | None = None,
    naics_code: str | None = None,
    set_aside: str | None = None,
    notice_type: str | None = None,
    agency: str | None = None,
    assigned_founder: str | None = None,
    score_min: int = 0,
    score_max: int = 100,
    high_moat_min: int | None = None,
    cyber_scope_min: int | None = None,
    cyber_scope_likelihood: str | None = None,
    sweet_spot_only: bool = False,
    include_expired: bool = False,
    sort: str = "score_desc",  # 'score_desc' | 'high_moat_desc' | 'cyber_scope_desc' | 'posted_desc' | 'deadline_asc'
) -> OpportunityListResponse:
    if limit < 1 or limit > 100:
        raise HTTPException(status_code=400, detail="limit must be 1..100")
    if page < 1:
        raise HTTPException(status_code=400, detail="page must be >=1")
    if score_min < 0 or score_max > 100 or score_min > score_max:
        raise HTTPException(status_code=400, detail="score_min/max out of range")
    if high_moat_min is not None and (high_moat_min < 0 or high_moat_min > 100):
        raise HTTPException(status_code=400, detail="high_moat_min out of range")
    if cyber_scope_min is not None and (cyber_scope_min < 0 or cyber_scope_min > 100):
        raise HTTPException(status_code=400, detail="cyber_scope_min out of range")

    session = ctx.session
    tenant_id = ctx.tenant.id
    offset = (page - 1) * limit

    # Build filters as a list of WHERE fragments + bound params, then run via
    # raw SQL — gives us the LEFT JOIN to opportunity_scores + founder slug
    # in one round-trip with full filtering.
    where_parts: list[str] = []
    params: dict[str, Any] = {"tenant_id": str(tenant_id)}

    # A notice whose response deadline has passed can't be bid, so it stays out
    # of the default view. Null deadlines are kept: unknown is not the same as
    # closed, and sources (e.g. buildingconnected) often omit the field.
    if not include_expired:
        where_parts.append(_NOT_EXPIRED_SQL)

    if q:
        where_parts.append("o.title ilike '%' || :q || '%'")
        params["q"] = q
    if naics_code:
        where_parts.append("o.naics_code = :naics")
        params["naics"] = naics_code
    if set_aside:
        where_parts.append("o.set_aside = :sa")
        params["sa"] = set_aside
    if notice_type:
        where_parts.append("o.notice_type = :nt")
        params["nt"] = notice_type
    if agency:
        where_parts.append("o.agency ilike '%' || :ag || '%'")
        params["ag"] = agency
    if assigned_founder:
        where_parts.append(
            "(select f.slug from founders f where f.id = s.assigned_founder_id) = :af"
        )
        params["af"] = assigned_founder
    where_parts.append(
        "(s.score is null or (s.score >= :smin and s.score <= :smax))"
    )
    params["smin"] = score_min
    params["smax"] = score_max
    if high_moat_min is not None:
        where_parts.append("s.high_moat_score >= :hm_min")
        params["hm_min"] = high_moat_min
    if sweet_spot_only:
        where_parts.append(
            "(s.high_moat_flags->>'is_high_probability_easy_win')::bool = true"
        )
    if cyber_scope_min is not None:
        where_parts.append("s.cyber_scope_score >= :cs_min")
        params["cs_min"] = cyber_scope_min
    if cyber_scope_likelihood:
        levels = [x.strip().upper() for x in cyber_scope_likelihood.split(",") if x.strip()]
        if levels:
            where_parts.append("s.cyber_scope_likelihood = any(:cs_likelihood)")
            params["cs_likelihood"] = levels

    where_sql = " and ".join(where_parts) if where_parts else "true"

    sort_sql = {
        "score_desc": "s.score desc nulls last, o.posted_at desc nulls last",
        "high_moat_desc": "s.high_moat_score desc nulls last, o.posted_at desc nulls last",
        "cyber_scope_desc": "s.cyber_scope_score desc nulls last, o.posted_at desc nulls last",
        "posted_desc": "o.posted_at desc nulls last",
        "deadline_asc": "o.response_deadline asc nulls last",
    }.get(sort, "s.score desc nulls last, o.posted_at desc nulls last")

    rows_q = text(
        f"""
        select
            o.id::text, o.source_id, o.title, o.notice_type, o.set_aside,
            o.naics_code, o.agency, o.posted_at, o.response_deadline,
            s.score, s.why_it_matters,
            e.incumbent_name, e.incumbent_award_amount,
            (select f.slug from founders f where f.id = s.assigned_founder_id)
              as assigned_founder_slug,
            s.high_moat_score,
            (s.high_moat_flags->>'is_high_probability_easy_win')::bool
              as is_sweet_spot,
            b.scope_one_sentence,
            s.cyber_scope_score,
            s.cyber_scope_likelihood,
            s.cyber_scope_pursuit_model,
            csa.id::text as cyber_scope_analysis_id,
            (csa.id is not null
              and csa.scan_pass = 'description_only'
              and (o.attachment_text is null or o.attachment_text = ''))
              as cyber_scope_attachments_pending
        from opportunities_raw o
        left join opportunity_scores s
          on s.opportunity_id = o.id and s.tenant_id = :tenant_id
        left join opportunities_enriched e on e.opportunity_id = o.id
        left join opportunity_briefs b
          on b.opportunity_id = o.id and b.tenant_id = :tenant_id
        left join cyber_scope_analyses csa
          on csa.opportunity_id = o.id and csa.tenant_id = :tenant_id
        where {where_sql}
        order by {sort_sql}
        limit :limit offset :offset
        """
    )
    count_q = text(
        f"""
        select count(*) from opportunities_raw o
        left join opportunity_scores s
          on s.opportunity_id = o.id and s.tenant_id = :tenant_id
        where {where_sql}
        """
    )

    items_rows = (
        await session.execute(rows_q, {**params, "limit": limit, "offset": offset})
    ).all()
    total = (await session.execute(count_q, params)).scalar_one()

    items: list[OpportunityListItem] = []
    for r in items_rows:
        incumbent_summary: str | None = None
        if r[11]:  # incumbent_name
            parts = [r[11]]
            if r[12] is not None:  # incumbent_award_amount
                parts.append(f"${float(r[12]):,.0f} prior obligations")
            incumbent_summary = " — ".join(parts)
        items.append(
            OpportunityListItem(
                id=r[0],
                notice_id=r[1],
                title=r[2],
                notice_type=r[3],
                set_aside=r[4],
                naics_code=r[5],
                agency_short=_short_agency_path(r[6]),
                posted_at=r[7].isoformat() if r[7] else None,
                response_deadline=r[8].isoformat() if r[8] else None,
                days_until_deadline=_days_until(r[8]),
                score=int(r[9]) if r[9] is not None else None,
                why_it_matters=r[10],
                incumbent_summary=incumbent_summary,
                assigned_founder_slug=r[13],
                high_moat_score=int(r[14]) if r[14] is not None else None,
                is_sweet_spot=bool(r[15]) if r[15] is not None else False,
                scope_one_sentence=r[16],
                cyber_scope_score=int(r[17]) if r[17] is not None else None,
                cyber_scope_likelihood=r[18],
                cyber_scope_pursuit_model=r[19],
                cyber_scope_analysis_id=r[20],
                cyber_scope_attachments_pending=bool(r[21]) if r[21] else False,
            )
        )

    # Facets — counts of values within the unfiltered tenant view, useful for
    # the sidebar filters. Cheap: aggregations on already-indexed columns.
    # They honour include_expired for the same reason the list does: a sidebar
    # reading "Set-aside: SDVOSB (412)" that filters down to 9 live notices is
    # worse than no count at all.
    facet_where = "true" if include_expired else _NOT_EXPIRED_SQL
    facets: dict[str, dict[str, int]] = {
        "set_asides": {},
        "notice_types": {},
        "naics": {},
        "assigned_founder": {},
    }
    set_aside_counts = (
        await session.execute(
            text(
                "select coalesce(o.set_aside, 'NONE'), count(*) "
                f"from opportunities_raw o where {facet_where} "
                "group by 1 order by 2 desc limit 20"
            )
        )
    ).all()
    facets["set_asides"] = {r[0]: r[1] for r in set_aside_counts}

    notice_type_counts = (
        await session.execute(
            text(
                "select coalesce(o.notice_type, 'unknown'), count(*) "
                f"from opportunities_raw o where {facet_where} "
                "group by 1 order by 2 desc"
            )
        )
    ).all()
    facets["notice_types"] = {r[0]: r[1] for r in notice_type_counts}

    naics_counts = (
        await session.execute(
            text(
                "select o.naics_code, count(*) from opportunities_raw o "
                f"where o.naics_code is not null and {facet_where} "
                "group by 1 order by 2 desc limit 25"
            )
        )
    ).all()
    facets["naics"] = {r[0]: r[1] for r in naics_counts}

    founder_counts = (
        await session.execute(
            text(
                f"""
                select f.slug, count(*)
                from opportunity_scores s
                join founders f on f.id = s.assigned_founder_id
                join opportunities_raw o on o.id = s.opportunity_id
                where s.tenant_id = :t and s.score >= 60 and {facet_where}
                group by f.slug order by 2 desc
                """
            ),
            {"t": str(tenant_id)},
        )
    ).all()
    facets["assigned_founder"] = {r[0]: r[1] for r in founder_counts}

    return OpportunityListResponse(
        page=page,
        limit=limit,
        total=int(total),
        has_next=offset + limit < int(total),
        items=items,
        facets=facets,
    )


# Registered before /opportunities/{opportunity_id} so the literal path wins
# the match — otherwise FastAPI tries to parse "ingest-status" as a UUID.
@router.get("/opportunities/ingest-status", response_model=IngestStatus)
async def get_ingest_status(
    ctx: Annotated[RequestContext, Depends(get_request_context)],
) -> IngestStatus:
    """Health of the opportunity feed, keyed on last *success*.

    Deliberately reports last_success_at rather than last_run_at: a run that
    401s still stamps last_run_at, so a "last ingest" built on last_run_at
    reads healthy while the feed is dead. That is precisely how a 19-day
    SAM.gov outage went unnoticed in June 2026.
    """
    rows = (
        await ctx.session.execute(
            text(
                """
                select source, key, last_run_at, last_success_at,
                       last_status, last_error
                from ingestion_state
                """
            )
        )
    ).all()

    if not rows:
        return IngestStatus(
            status="unknown", sources_ok=0, sources_error=0, feeds=[]
        )

    now = datetime.now(UTC)
    feeds: list[IngestFeed] = []
    for r in rows:
        feeds.append(
            IngestFeed(
                source=r[0],
                key=r[1],
                last_run_at=r[2],
                last_success_at=r[3],
                last_status=r[4],
                last_error=(r[5][:200] if r[5] else None),
            )
        )

    ok = sum(1 for f in feeds if f.last_status == "ok")
    errored = sum(1 for f in feeds if f.last_status == "error")
    successes = [f.last_success_at for f in feeds if f.last_success_at]
    newest_success = max(successes) if successes else None
    status = classify_ingest(ok, errored, newest_success, now)

    return IngestStatus(
        status=status,
        last_success_at=newest_success,
        last_run_at=max((f.last_run_at for f in feeds if f.last_run_at), default=None),
        sources_ok=ok,
        sources_error=errored,
        first_error=next((f.last_error for f in feeds if f.last_error), None),
        feeds=sorted(feeds, key=lambda f: (f.source, f.key)),
    )


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
            age = datetime.now(UTC) - excl_row.checked_at
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
        hm_block: HighMoatBlock | None = None
        if score_row.high_moat_score is not None:
            flags = score_row.high_moat_flags or {}
            hm_block = HighMoatBlock(
                score=score_row.high_moat_score,
                breakdown=score_row.high_moat_breakdown or {},
                is_high_probability_easy_win=bool(
                    flags.get("is_high_probability_easy_win")
                ),
                clause_hits=list(flags.get("clause_hits") or []),
                clearance_hits=list(flags.get("clearance_hits") or []),
                role_hits=list(flags.get("role_hits") or []),
                top_clearance=str(flags.get("top_clearance") or "NONE"),
                why_it_matters_seed=flags.get("why_it_matters_seed"),
            )
        cs_block: CyberScopeBlock | None = None
        if score_row.cyber_scope_score is not None:
            csa_row = (
                await session.execute(
                    select(CyberScopeAnalysis).where(
                        CyberScopeAnalysis.tenant_id == tenant_id,
                        CyberScopeAnalysis.opportunity_id == opportunity_id,
                    )
                )
            ).scalar_one_or_none()
            flags = score_row.cyber_scope_flags or {}
            top_signals = (
                (csa_row.top_signals_json or [])[:5] if csa_row is not None else []
            )
            attachments_pending = bool(
                csa_row is not None
                and csa_row.scan_pass == "description_only"
                and not (opp.attachment_text and opp.attachment_text.strip())
            )
            analysis_id = str(csa_row.id) if csa_row else None
            cs_block = CyberScopeBlock(
                score=score_row.cyber_scope_score,
                likelihood=score_row.cyber_scope_likelihood or "NONE",
                pursuit_model=score_row.cyber_scope_pursuit_model or "NO_ACTION",
                ufgs_center_of_gravity=bool(flags.get("ufgs_center_of_gravity")),
                ufgs_tier_1_hit=bool(flags.get("ufgs_tier_1_hit")),
                top_ufgs_sections=list(flags.get("top_ufgs_sections") or []),
                top_signals=top_signals,
                scan_pass=csa_row.scan_pass if csa_row else "description_only",
                attachments_pending=attachments_pending,
                analysis_id=analysis_id,
                analysis_url=(
                    f"/tools/cyber-scope-parser/{analysis_id}"
                    if analysis_id
                    else None
                ),
            )
        score_block = ScoreBlock(
            score=score_row.score,
            breakdown=score_row.score_breakdown,
            assigned_founder_slug=founder_slug,
            why_it_matters=score_row.why_it_matters,
            why_it_matters_model=score_row.why_it_matters_model,
            scored_at=score_row.scored_at.isoformat(),
            high_moat=hm_block,
            cyber_scope=cs_block,
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
            source=opp.source,
        )
    elif opp.description_url:
        desc = DescriptionBlock(
            text=None,
            source_url=opp.description_url,
            fetch_status="pending",
            source=opp.source,
        )
    else:
        desc = DescriptionBlock(
            text=None, source_url=None, fetch_status="unavailable", source=opp.source
        )

    # Decision block — the authoritative pursuit lane + vector + gates.
    decision_block: DecisionBlock | None = None
    dv = (
        await session.execute(
            select(OpportunityDecisionVector).where(
                OpportunityDecisionVector.tenant_id == tenant_id,
                OpportunityDecisionVector.opportunity_id == opportunity_id,
            )
        )
    ).scalar_one_or_none()
    if dv is not None:
        gate_rows = (
            await session.execute(
                select(OpportunityGate)
                .where(
                    OpportunityGate.tenant_id == tenant_id,
                    OpportunityGate.opportunity_id == opportunity_id,
                )
                .order_by(OpportunityGate.severity, OpportunityGate.gate_code)
            )
        ).scalars().all()
        decision_block = DecisionBlock(
            pursuit_lane=dv.manual_lane_override or dv.pursuit_lane,
            reason_codes=list(dv.reason_codes or []),
            confidence=dv.confidence,
            lane_weight_profile=dv.lane_weight_profile,
            needs_human_review=dv.needs_human_review,
            vector=DecisionVectorOut(
                relevance=dv.relevance_score,
                prime_fit=dv.prime_fit_score,
                subcontract_fit=dv.subcontract_fit_score,
                winability=dv.winability_score,
                deliverability=dv.deliverability_score,
                strategic_value=dv.strategic_value_score,
                urgency=dv.urgency_score,
                evidence_completeness=dv.evidence_completeness_score,
                overall_priority=dv.overall_priority_score,
            ),
            gates=[
                GateOut(
                    gate_code=g.gate_code,
                    status=g.status,
                    severity=g.severity,
                    reason_code=g.reason_code,
                    detail=g.detail,
                )
                for g in gate_rows
            ],
            knowledge_pack_version=dv.knowledge_pack_version,
            formula_version=dv.formula_version,
            computed_at=dv.computed_at.isoformat() if dv.computed_at else None,
        )

    # Prime targets (ranked) for this notice.
    pt_rows = (
        await session.execute(
            select(OpportunityPrimeTarget, PrimeTarget)
            .join(PrimeTarget, PrimeTarget.id == OpportunityPrimeTarget.prime_target_id)
            .where(
                OpportunityPrimeTarget.tenant_id == tenant_id,
                OpportunityPrimeTarget.opportunity_id == opportunity_id,
            )
            .order_by(OpportunityPrimeTarget.rank)
        )
    ).all()
    prime_targets = [
        PrimeTargetOut(
            name=pt.name,
            uei=pt.uei,
            target_type=link.target_type,
            confidence=link.confidence,
            why_target=link.why_target,
            recommended_contact_role=link.recommended_contact_role,
            outreach_deadline=link.outreach_deadline.isoformat() if link.outreach_deadline else None,
            rank=link.rank,
        )
        for link, pt in pt_rows
    ]

    # Pursuit plan + dated actions.
    pursuit_plan_block: PursuitPlanBlock | None = None
    rec = (
        await session.execute(
            select(PursuitRecommendation).where(
                PursuitRecommendation.tenant_id == tenant_id,
                PursuitRecommendation.opportunity_id == opportunity_id,
            )
        )
    ).scalar_one_or_none()
    if rec is not None:
        action_rows = (
            await session.execute(
                select(PursuitAction)
                .where(PursuitAction.recommendation_id == rec.id)
                .order_by(PursuitAction.sequence)
            )
        ).scalars().all()
        pursuit_plan_block = PursuitPlanBlock(
            pursuit_lane=rec.pursuit_lane,
            executive_decision=rec.executive_decision,
            why_this_is_real=rec.why_this_is_real,
            mactech_work_package=rec.mactech_work_package,
            blocking_issues=list(rec.blocking_issues or []),
            prime_target_names=list(rec.prime_target_names or []),
            recommended_owner_slug=rec.recommended_owner_slug,
            decision_deadline=rec.decision_deadline.isoformat() if rec.decision_deadline else None,
            response_deadline=rec.response_deadline.isoformat() if rec.response_deadline else None,
            confidence=rec.confidence,
            actions=[
                PursuitActionOut(
                    sequence=a.sequence,
                    action=a.action,
                    owner_founder_slug=a.owner_founder_slug,
                    due_at=a.due_at.isoformat() if a.due_at else None,
                    status=a.status,
                )
                for a in action_rows
            ],
        )

    return OpportunityDetail(
        opportunity=_opp_header(opp),
        description=desc,
        incumbent=incumbent_block,
        score=score_block,
        decision=decision_block,
        pursuit_plan=pursuit_plan_block,
        prime_targets=prime_targets,
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
        await session.execute(
            select(Founder).where(
                Founder.tenant_id == tenant_id,
                Founder.slug == founder_slug,
            )
        )
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
        rendered_at=datetime.now(UTC).isoformat(),
    )
