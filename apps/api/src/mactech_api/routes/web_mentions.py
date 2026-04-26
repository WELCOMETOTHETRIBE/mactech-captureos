"""Web-mentions panel for the opportunity detail page.

Sprint 19. Surfaces top Google organic results for an opportunity so
the founder sees relevant prior press, GAO reports, recompete chatter,
and incumbent context without leaving CaptureOS.

  GET  /opportunities/{id}/web-mentions       (cached, returns 200 with cached JSON)
  POST /opportunities/{id}/web-mentions/refresh  (force a SerpAPI call)

7-day TTL. Three query kinds run per opportunity:
  - program: "<title>" <agency>
  - incumbent: when an incumbent name is known from enrichment
  - agency_news: agency name + NAICS narrative + "contract"

SerpAPI is paid per-search, so the GET path NEVER triggers a fetch
unless the cache row is missing. The refresh endpoint is the only
way to bust cache, and it stamps fetched_at so subsequent GETs read
the new payload until the next 7-day expiry.
"""

from __future__ import annotations

import logging
import os
from dataclasses import asdict
from datetime import UTC, datetime, timedelta
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, ConfigDict
from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert

from mactech_api.auth import RequestContext, get_request_context
from mactech_db.models import (
    OpportunityEnriched,
    OpportunityRaw,
    WebMentionCache,
)
from mactech_integrations.serpapi import (
    SerpApiClient,
    SerpApiError,
    SerpApiRateLimitError,
)

log = logging.getLogger(__name__)
router = APIRouter(tags=["web-mentions"])

CACHE_TTL = timedelta(days=7)
RESULTS_PER_KIND = 5


class _Out(BaseModel):
    model_config = ConfigDict(from_attributes=True)


class WebMentionResult(_Out):
    position: int
    title: str
    link: str
    displayed_link: str | None
    snippet: str | None
    source: str | None
    date: str | None


class WebMentionGroup(_Out):
    kind: str
    query: str
    results: list[WebMentionResult]
    fetched_at: str | None
    is_stale: bool


class WebMentionsResponse(_Out):
    opportunity_id: str
    groups: list[WebMentionGroup]
    has_serpapi_key: bool


def _build_queries(
    opp: OpportunityRaw, enr: OpportunityEnriched | None
) -> list[tuple[str, str]]:
    """Return (kind, query) pairs to issue. Skip kinds whose inputs are
    missing — e.g., no incumbent name, no agency."""
    out: list[tuple[str, str]] = []
    title = (opp.title or "").strip()
    agency_full = (opp.agency or "").strip()
    agency_short = agency_full.split(".")[0].strip() if agency_full else ""

    if title:
        # Quote the title so search hits press/govwide releases that
        # reference the program by name, not just keyword overlap.
        q = f'"{title[:120]}"'
        if agency_short:
            q = f"{q} {agency_short}"
        out.append(("program", q))

    if enr and enr.incumbent_name:
        incumbent = enr.incumbent_name.strip()
        if incumbent:
            q = f'"{incumbent}" {agency_short or "federal"} contract'
            out.append(("incumbent", q.strip()))

    if agency_short and opp.naics_code:
        q = f"{agency_short} NAICS {opp.naics_code} contract"
        out.append(("agency_news", q))

    return out


def _to_group(row: WebMentionCache, *, now: datetime) -> WebMentionGroup:
    age = now - row.fetched_at if row.fetched_at else timedelta(days=999)
    return WebMentionGroup(
        kind=row.query_kind,
        query=row.query,
        results=[
            WebMentionResult(
                position=int(r.get("position") or i + 1),
                title=str(r.get("title") or ""),
                link=str(r.get("link") or ""),
                displayed_link=r.get("displayed_link"),
                snippet=r.get("snippet"),
                source=r.get("source"),
                date=r.get("date"),
            )
            for i, r in enumerate(row.results or [])
        ],
        fetched_at=row.fetched_at.isoformat() if row.fetched_at else None,
        is_stale=age > CACHE_TTL,
    )


async def _read_cache(
    ctx: RequestContext, opportunity_id: UUID
) -> list[WebMentionCache]:
    rows = (
        await ctx.session.execute(
            select(WebMentionCache).where(
                WebMentionCache.tenant_id == ctx.tenant.id,
                WebMentionCache.opportunity_id == opportunity_id,
            )
        )
    ).scalars().all()
    return list(rows)


@router.get(
    "/opportunities/{opportunity_id}/web-mentions",
    response_model=WebMentionsResponse,
)
async def get_web_mentions(
    opportunity_id: UUID,
    ctx: Annotated[RequestContext, Depends(get_request_context)],
) -> WebMentionsResponse:
    """Return cached web-mentions for the opp. Never fetches — the
    refresh endpoint is the only path that calls SerpAPI."""
    opp = (
        await ctx.session.execute(
            select(OpportunityRaw).where(OpportunityRaw.id == opportunity_id)
        )
    ).scalar_one_or_none()
    if opp is None:
        raise HTTPException(status_code=404, detail="opportunity not found")

    rows = await _read_cache(ctx, opportunity_id)
    now = datetime.now(UTC)
    groups = [_to_group(r, now=now) for r in rows]
    groups.sort(key=lambda g: ("program", "incumbent", "agency_news").index(g.kind) if g.kind in ("program", "incumbent", "agency_news") else 99)
    return WebMentionsResponse(
        opportunity_id=str(opportunity_id),
        groups=groups,
        has_serpapi_key=bool(os.environ.get("SERPAPI_KEY")),
    )


@router.post(
    "/opportunities/{opportunity_id}/web-mentions/refresh",
    response_model=WebMentionsResponse,
    status_code=status.HTTP_200_OK,
)
async def refresh_web_mentions(
    opportunity_id: UUID,
    ctx: Annotated[RequestContext, Depends(get_request_context)],
) -> WebMentionsResponse:
    """Force a SerpAPI fetch for every applicable query kind. Bills against
    the platform SerpAPI key. Frontend exposes this as an explicit "Refresh"
    button so spend is user-driven, not page-load driven."""
    api_key = os.environ.get("SERPAPI_KEY", "")
    if not api_key:
        raise HTTPException(
            status_code=503,
            detail="SERPAPI_KEY not configured on the API service.",
        )

    opp = (
        await ctx.session.execute(
            select(OpportunityRaw).where(OpportunityRaw.id == opportunity_id)
        )
    ).scalar_one_or_none()
    if opp is None:
        raise HTTPException(status_code=404, detail="opportunity not found")

    enr = (
        await ctx.session.execute(
            select(OpportunityEnriched).where(
                OpportunityEnriched.opportunity_id == opportunity_id
            )
        )
    ).scalar_one_or_none()

    queries = _build_queries(opp, enr)
    if not queries:
        return WebMentionsResponse(
            opportunity_id=str(opportunity_id),
            groups=[],
            has_serpapi_key=True,
        )

    fetched_at = datetime.now(UTC)
    async with SerpApiClient(api_key=api_key) as client:
        for kind, query in queries:
            try:
                resp = await client.search(query, num=RESULTS_PER_KIND)
            except SerpApiRateLimitError as exc:
                log.warning(
                    "SerpAPI rate-limited on %s/%s: %s",
                    opportunity_id,
                    kind,
                    exc,
                )
                # Don't blow up the whole refresh — leave existing
                # cache row in place for the rate-limited kind.
                continue
            except SerpApiError as exc:
                log.warning(
                    "SerpAPI error on %s/%s: %s",
                    opportunity_id,
                    kind,
                    exc,
                )
                continue

            results_payload = [asdict(r) for r in resp.organic_results]
            stmt = (
                pg_insert(WebMentionCache)
                .values(
                    tenant_id=ctx.tenant.id,
                    opportunity_id=opportunity_id,
                    query_kind=kind,
                    query=query,
                    results=results_payload,
                    result_count=len(results_payload),
                    engine=resp.engine,
                    fetched_at=fetched_at,
                )
                .on_conflict_do_update(
                    index_elements=[
                        "tenant_id",
                        "opportunity_id",
                        "query_kind",
                    ],
                    set_={
                        "query": query,
                        "results": results_payload,
                        "result_count": len(results_payload),
                        "engine": resp.engine,
                        "fetched_at": fetched_at,
                    },
                )
            )
            await ctx.session.execute(stmt)

    await ctx.session.flush()
    rows = await _read_cache(ctx, opportunity_id)
    now = datetime.now(UTC)
    groups = [_to_group(r, now=now) for r in rows]
    groups.sort(
        key=lambda g: (
            ("program", "incumbent", "agency_news").index(g.kind)
            if g.kind in ("program", "incumbent", "agency_news")
            else 99
        )
    )
    return WebMentionsResponse(
        opportunity_id=str(opportunity_id),
        groups=groups,
        has_serpapi_key=True,
    )
