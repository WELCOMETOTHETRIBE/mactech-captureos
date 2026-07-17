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
import re
from dataclasses import asdict
from datetime import UTC, datetime, timedelta
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
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
from pydantic import BaseModel, ConfigDict
from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert

from mactech_api.auth import RequestContext, get_request_context

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


# Domains that just mirror SAM.gov listings without adding intel —
# excluding them with -site: dramatically increases signal quality.
# Tuned against real opportunities; revisit when bookmarking new
# aggregators in the wild.
_AGGREGATOR_DOMAINS = (
    "sam.gov",
    "govtribe.com",
    "highergov.com",
    "samclerk.com",
    "mysetaside.com",
    "globaltenders.com",
    "tenderimpulse.com",
    "govcontoday.com",
    "g2xchange.com",
    "gsaelibrary.gsa.gov",
    "proposalhelper.com",
    "bidbanana.thebidlab.com",
    "opengrants.io",
    "ops.opengrants.io",
    "sweetspotgov.com",
    "cleat.ai",
    "govcontractfinder.com",
    "govdash.com",
    "usaspending.gov",
    "federalschedules.com",
    "biddetail.com",
    "publicbidsearch.com",
    "instantmarkets.com",
    "tendersontime.com",
    "tendersinfo.com",
    "biztorg.com",
)
_EXCLUDE_AGGREGATORS = " ".join(f"-site:{d}" for d in _AGGREGATOR_DOMAINS)


# Top-level agency names that are too broad to be useful in a query.
# Map to a canonical short form, then fall through to a deeper segment
# for specificity.
_AGENCY_TOP_REWRITES = {
    "VETERANS AFFAIRS, DEPARTMENT OF": "VA",
    "DEPT OF DEFENSE": "DoD",
    "DEPT OF HOMELAND SECURITY": "DHS",
}


def _short_agency(agency_full: str | None) -> str:
    """Pick the most specific *useful* agency segment from a SAM full
    path. Prefer segments[2] (sub-bureau like NAVAIR, USACE) when it
    exists and isn't a duplicate of segments[0]. Strip parenthesized
    office codes like "(36C247)" and leading numeric prefixes like
    "247-"."""
    if not agency_full:
        return ""
    segs = [s.strip() for s in agency_full.split(".") if s.strip()]
    if not segs:
        return ""
    top_canonical = _AGENCY_TOP_REWRITES.get(segs[0], segs[0])
    if len(segs) >= 3 and segs[2] != segs[0]:
        seg = segs[2]
        # Drop "(36C247)" and "247-" admin codes that hurt query recall.
        seg = re.sub(r"\(\d+[A-Z]+\d*\)", "", seg).strip()
        seg = re.sub(r"^\d+-", "", seg).strip()
        if seg:
            return seg
    return top_canonical


def _build_queries(opp: OpportunityRaw, enr: OpportunityEnriched | None) -> list[tuple[str, str]]:
    """Return (kind, query) pairs to issue. Three kinds:

      program    — direct match on the program/RFP title scoped to the
                   sub-bureau. Aggregator exclusions kill SAM-mirror SEO.
      incumbent  — incumbent contractor + substantive corporate signal
                   keywords (lawsuit, layoffs, GAO, settlement, etc.).
                   The interesting question isn't "do they have any
                   federal contracts" (we know from USASpending) — it's
                   "is this incumbent in trouble?"
      press      — program-specific press scoped to industry-news
                   surfaces (govconwire, fedscoop, breaking defense).

    Skip kinds whose inputs are missing — e.g., no incumbent name. The
    old `agency_news` kind was structurally noisy (returned NAICS
    directory pages) and is replaced by `press`.
    """
    out: list[tuple[str, str]] = []
    title = (opp.title or "").strip()
    agency = _short_agency(opp.agency)
    sol = (opp.solicitation_number or "").strip()

    if title:
        title_core = title[:80]
        q = f'"{title_core}" {agency} {_EXCLUDE_AGGREGATORS}'.strip()
        out.append(("program", q))

    if enr and enr.incumbent_name:
        incumbent = enr.incumbent_name.strip()
        if incumbent:
            # Hunt for substance, not award listings.
            q = (
                f'"{incumbent}" '
                f"(lawsuit OR earnings OR layoff OR layoffs OR protest OR "
                f'"GAO" OR settlement OR resigns OR acquires OR fraud) '
                f"{_EXCLUDE_AGGREGATORS}"
            ).strip()
            out.append(("incumbent", q))

    if agency and title:
        title_core = title[:60]
        q_parts = [f'"{title_core}"', agency]
        if sol:
            q_parts.append(f'OR "{sol}"')
        q_parts.append(
            "(news OR awarded OR protest OR announce OR "
            '"breaking defense" OR fedscoop OR nextgov OR '
            "govconwire OR federalnewsnetwork)"
        )
        q_parts.append(_EXCLUDE_AGGREGATORS)
        out.append(("press", " ".join(q_parts).strip()))

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


async def _read_cache(ctx: RequestContext, opportunity_id: UUID) -> list[WebMentionCache]:
    rows = (
        (
            await ctx.session.execute(
                select(WebMentionCache).where(
                    WebMentionCache.tenant_id == ctx.tenant.id,
                    WebMentionCache.opportunity_id == opportunity_id,
                )
            )
        )
        .scalars()
        .all()
    )
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
        await ctx.session.execute(select(OpportunityRaw).where(OpportunityRaw.id == opportunity_id))
    ).scalar_one_or_none()
    if opp is None:
        raise HTTPException(status_code=404, detail="opportunity not found")

    rows = await _read_cache(ctx, opportunity_id)
    now = datetime.now(UTC)
    groups = [_to_group(r, now=now) for r in rows]
    groups.sort(
        key=lambda g: (
            ("program", "incumbent", "press", "agency_news").index(g.kind)
            if g.kind in ("program", "incumbent", "press", "agency_news")
            else 99
        )
    )
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
        await ctx.session.execute(select(OpportunityRaw).where(OpportunityRaw.id == opportunity_id))
    ).scalar_one_or_none()
    if opp is None:
        raise HTTPException(status_code=404, detail="opportunity not found")

    enr = (
        await ctx.session.execute(
            select(OpportunityEnriched).where(OpportunityEnriched.opportunity_id == opportunity_id)
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
            ("program", "incumbent", "press", "agency_news").index(g.kind)
            if g.kind in ("program", "incumbent", "press", "agency_news")
            else 99
        )
    )
    return WebMentionsResponse(
        opportunity_id=str(opportunity_id),
        groups=groups,
        has_serpapi_key=True,
    )
