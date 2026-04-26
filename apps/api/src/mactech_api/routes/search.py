"""Hybrid global search.

Phase 3 Week 12 (UX Sprint 5). Backs the Cmd-K modal — searches across
opportunities, drafts, teaming partners, and past performance using
pg_trgm similarity on title/name columns.

Tenant-scoped end-to-end. Opportunities themselves are not tenant-scoped
(they're SAM.gov public data) but we surface only those the tenant has
either scored or has a pursuit on by default; with `all=true` we expose
the full tenant feed up to the limit.

Endpoint:
  GET /search?q=<query>[&all=false][&limit=8]

Returns up to N grouped results per kind. Empty `q` returns the most
recent items per kind (act as a "recents" view when the modal opens).
"""

from __future__ import annotations

import logging
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, ConfigDict
from sqlalchemy import text

from mactech_api.auth import RequestContext, get_request_context

log = logging.getLogger(__name__)
router = APIRouter(tags=["search"])

DEFAULT_LIMIT = 8
MIN_QUERY_LEN = 2
MAX_QUERY_LEN = 120
SIMILARITY_THRESHOLD = 0.10


class _Out(BaseModel):
    model_config = ConfigDict(from_attributes=True)


class SearchHit(_Out):
    kind: str  # 'opportunity' | 'draft' | 'teaming_partner' | 'past_performance'
    id: str
    title: str
    subtitle: str | None
    score: float | None  # pg_trgm similarity, 0..1
    url: str


class SearchResponse(_Out):
    query: str
    total: int
    hits: list[SearchHit]
    grouped: dict[str, list[SearchHit]]


async def _opportunities_recents(
    ctx: RequestContext, limit: int
) -> list[SearchHit]:
    """When q is empty, surface recent scored opps for this tenant."""
    rows = (
        await ctx.session.execute(
            text(
                """
                select o.id::text, o.title, o.agency, s.score
                from opportunities_raw o
                join opportunity_scores s on s.opportunity_id = o.id
                  and s.tenant_id = :tenant_id
                order by s.scored_at desc nulls last
                limit :limit
                """
            ),
            {"tenant_id": str(ctx.tenant.id), "limit": limit},
        )
    ).all()
    return [
        SearchHit(
            kind="opportunity",
            id=r[0],
            title=r[1],
            subtitle=(
                f"{r[2].split('.')[0]} · score {r[3]}"
                if r[2] and r[3] is not None
                else (r[2] or None)
            ),
            score=None,
            url=f"/opportunities/{r[0]}",
        )
        for r in rows
    ]


async def _opportunities_search(
    ctx: RequestContext, q: str, limit: int
) -> list[SearchHit]:
    rows = (
        await ctx.session.execute(
            text(
                """
                select o.id::text, o.title, o.agency, s.score,
                       similarity(o.title, :q) as sim
                from opportunities_raw o
                left join opportunity_scores s
                  on s.opportunity_id = o.id and s.tenant_id = :tenant_id
                where o.title % :q
                order by sim desc, s.score desc nulls last
                limit :limit
                """
            ),
            {"q": q, "tenant_id": str(ctx.tenant.id), "limit": limit},
        )
    ).all()
    return [
        SearchHit(
            kind="opportunity",
            id=r[0],
            title=r[1],
            subtitle=(
                f"{r[2].split('.')[0]} · score {r[3]}"
                if r[2] and r[3] is not None
                else (r[2] or None)
            ),
            score=float(r[4]) if r[4] is not None else None,
            url=f"/opportunities/{r[0]}",
        )
        for r in rows
    ]


async def _drafts_search(
    ctx: RequestContext, q: str | None, limit: int
) -> list[SearchHit]:
    if q:
        rows = (
            await ctx.session.execute(
                text(
                    """
                    select d.id::text, d.title, d.status, d.draft_type,
                           similarity(d.title, :q) as sim
                    from proposal_drafts d
                    where d.tenant_id = :tenant_id and d.title % :q
                    order by sim desc, d.updated_at desc
                    limit :limit
                    """
                ),
                {"q": q, "tenant_id": str(ctx.tenant.id), "limit": limit},
            )
        ).all()
    else:
        rows = (
            await ctx.session.execute(
                text(
                    """
                    select d.id::text, d.title, d.status, d.draft_type, NULL::float
                    from proposal_drafts d
                    where d.tenant_id = :tenant_id
                    order by d.updated_at desc
                    limit :limit
                    """
                ),
                {"tenant_id": str(ctx.tenant.id), "limit": limit},
            )
        ).all()
    return [
        SearchHit(
            kind="draft",
            id=r[0],
            title=r[1],
            subtitle=f"{r[3].replace('_', ' ')} · {r[2]}" if r[2] else r[3],
            score=float(r[4]) if r[4] is not None else None,
            url=f"/drafts/{r[0]}",
        )
        for r in rows
    ]


async def _partners_search(
    ctx: RequestContext, q: str | None, limit: int
) -> list[SearchHit]:
    if q:
        rows = (
            await ctx.session.execute(
                text(
                    """
                    select p.id::text, p.name, p.status,
                           similarity(p.name, :q) as sim
                    from teaming_partners p
                    where p.tenant_id = :tenant_id and p.name % :q
                    order by sim desc, p.name
                    limit :limit
                    """
                ),
                {"q": q, "tenant_id": str(ctx.tenant.id), "limit": limit},
            )
        ).all()
    else:
        rows = (
            await ctx.session.execute(
                text(
                    """
                    select p.id::text, p.name, p.status, NULL::float
                    from teaming_partners p
                    where p.tenant_id = :tenant_id
                    order by case when p.status='active' then 0 else 1 end, p.name
                    limit :limit
                    """
                ),
                {"tenant_id": str(ctx.tenant.id), "limit": limit},
            )
        ).all()
    return [
        SearchHit(
            kind="teaming_partner",
            id=r[0],
            title=r[1],
            subtitle=str(r[2]),
            score=float(r[3]) if r[3] is not None else None,
            url="/library#teaming-partners",
        )
        for r in rows
    ]


async def _pp_search(
    ctx: RequestContext, q: str | None, limit: int
) -> list[SearchHit]:
    if q:
        rows = (
            await ctx.session.execute(
                text(
                    """
                    select p.id::text, p.title, p.customer_agency, p.role,
                           similarity(p.title, :q) as sim
                    from past_performance p
                    where p.tenant_id = :tenant_id and p.title % :q
                    order by sim desc, p.period_end desc nulls last
                    limit :limit
                    """
                ),
                {"q": q, "tenant_id": str(ctx.tenant.id), "limit": limit},
            )
        ).all()
    else:
        rows = (
            await ctx.session.execute(
                text(
                    """
                    select p.id::text, p.title, p.customer_agency, p.role, NULL::float
                    from past_performance p
                    where p.tenant_id = :tenant_id
                    order by p.period_end desc nulls last, p.created_at desc
                    limit :limit
                    """
                ),
                {"tenant_id": str(ctx.tenant.id), "limit": limit},
            )
        ).all()
    return [
        SearchHit(
            kind="past_performance",
            id=r[0],
            title=r[1],
            subtitle=f"{r[3]} · {r[2] or '(customer not on file)'}",
            score=float(r[4]) if r[4] is not None else None,
            url=f"/library/past-performance/{r[0]}/edit",
        )
        for r in rows
    ]


@router.get("/search", response_model=SearchResponse)
async def global_search(
    ctx: Annotated[RequestContext, Depends(get_request_context)],
    q: str = "",
    limit: int = DEFAULT_LIMIT,
) -> SearchResponse:
    q = q.strip()
    if len(q) > MAX_QUERY_LEN:
        raise HTTPException(status_code=400, detail="query too long")
    if 0 < len(q) < MIN_QUERY_LEN:
        # Treat too-short queries as empty (return recents) instead of erroring.
        q = ""
    if limit < 1 or limit > 25:
        raise HTTPException(status_code=400, detail="limit must be 1..25")

    # Set similarity threshold for this transaction so the % operator is
    # selective. SET LOCAL doesn't accept bind params, so use set_config.
    if q:
        await ctx.session.execute(
            text(
                "select set_config('pg_trgm.similarity_threshold', :t, true)"
            ),
            {"t": str(SIMILARITY_THRESHOLD)},
        )

    if q:
        opps = await _opportunities_search(ctx, q, limit)
    else:
        opps = await _opportunities_recents(ctx, limit)
    drafts = await _drafts_search(ctx, q or None, limit)
    partners = await _partners_search(ctx, q or None, limit)
    pp = await _pp_search(ctx, q or None, limit)

    grouped: dict[str, list[SearchHit]] = {
        "opportunity": opps,
        "draft": drafts,
        "teaming_partner": partners,
        "past_performance": pp,
    }
    flat = opps + drafts + partners + pp
    return SearchResponse(
        query=q,
        total=len(flat),
        hits=flat,
        grouped=grouped,
    )
