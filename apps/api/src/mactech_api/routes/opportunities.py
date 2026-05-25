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


class OpportunityListResponse(_Out):
    page: int
    limit: int
    total: int
    has_next: bool
    items: list[OpportunityListItem]
    facets: dict[str, dict[str, int]]


def _short_agency_path(p: str | None) -> str | None:
    if not p:
        return None
    return p.split(".")[0].strip()


def _days_until(dt: datetime | None) -> int | None:
    if dt is None:
        return None
    delta = dt - datetime.now(timezone.utc)
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
    sweet_spot_only: bool = False,
    sort: str = "score_desc",  # 'score_desc' | 'high_moat_desc' | 'posted_desc' | 'deadline_asc'
) -> OpportunityListResponse:
    if limit < 1 or limit > 100:
        raise HTTPException(status_code=400, detail="limit must be 1..100")
    if page < 1:
        raise HTTPException(status_code=400, detail="page must be >=1")
    if score_min < 0 or score_max > 100 or score_min > score_max:
        raise HTTPException(status_code=400, detail="score_min/max out of range")
    if high_moat_min is not None and (high_moat_min < 0 or high_moat_min > 100):
        raise HTTPException(status_code=400, detail="high_moat_min out of range")

    session = ctx.session
    tenant_id = ctx.tenant.id
    offset = (page - 1) * limit

    # Build filters as a list of WHERE fragments + bound params, then run via
    # raw SQL — gives us the LEFT JOIN to opportunity_scores + founder slug
    # in one round-trip with full filtering.
    where_parts: list[str] = []
    params: dict[str, Any] = {"tenant_id": str(tenant_id)}

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

    where_sql = " and ".join(where_parts) if where_parts else "true"

    sort_sql = {
        "score_desc": "s.score desc nulls last, o.posted_at desc nulls last",
        "high_moat_desc": "s.high_moat_score desc nulls last, o.posted_at desc nulls last",
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
            b.scope_one_sentence
        from opportunities_raw o
        left join opportunity_scores s
          on s.opportunity_id = o.id and s.tenant_id = :tenant_id
        left join opportunities_enriched e on e.opportunity_id = o.id
        left join opportunity_briefs b
          on b.opportunity_id = o.id and b.tenant_id = :tenant_id
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
            )
        )

    # Facets — counts of values within the unfiltered tenant view, useful for
    # the sidebar filters. Cheap: aggregations on already-indexed columns.
    facets: dict[str, dict[str, int]] = {
        "set_asides": {},
        "notice_types": {},
        "naics": {},
        "assigned_founder": {},
    }
    set_aside_counts = (
        await session.execute(
            text(
                "select coalesce(set_aside, 'NONE'), count(*) "
                "from opportunities_raw group by 1 order by 2 desc limit 20"
            )
        )
    ).all()
    facets["set_asides"] = {r[0]: r[1] for r in set_aside_counts}

    notice_type_counts = (
        await session.execute(
            text(
                "select coalesce(notice_type, 'unknown'), count(*) "
                "from opportunities_raw group by 1 order by 2 desc"
            )
        )
    ).all()
    facets["notice_types"] = {r[0]: r[1] for r in notice_type_counts}

    naics_counts = (
        await session.execute(
            text(
                "select naics_code, count(*) from opportunities_raw "
                "where naics_code is not null group by 1 order by 2 desc limit 25"
            )
        )
    ).all()
    facets["naics"] = {r[0]: r[1] for r in naics_counts}

    founder_counts = (
        await session.execute(
            text(
                """
                select f.slug, count(*)
                from opportunity_scores s
                join founders f on f.id = s.assigned_founder_id
                where s.tenant_id = :t and s.score >= 60
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
        score_block = ScoreBlock(
            score=score_row.score,
            breakdown=score_row.score_breakdown,
            assigned_founder_slug=founder_slug,
            why_it_matters=score_row.why_it_matters,
            why_it_matters_model=score_row.why_it_matters_model,
            scored_at=score_row.scored_at.isoformat(),
            high_moat=hm_block,
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
        rendered_at=datetime.now(timezone.utc).isoformat(),
    )
