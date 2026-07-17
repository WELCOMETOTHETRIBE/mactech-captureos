"""Industry-day calendar — read-only API over agency_events.

Sprint 19. agency_events is shared across tenants (events are public-
data signal). The endpoint returns upcoming events ordered by start
date, optionally filtered to "soon" (next 60 days) for the dashboard.

  GET /events?upcoming_only=true&limit=50
"""

from __future__ import annotations

import logging
from datetime import UTC, datetime
from typing import Annotated

from fastapi import APIRouter, Depends, Query
from mactech_db.models import AgencyEvent
from pydantic import BaseModel, ConfigDict
from sqlalchemy import func, select

from mactech_api.auth import RequestContext, get_request_context

log = logging.getLogger(__name__)
router = APIRouter(tags=["events"])


class _Out(BaseModel):
    model_config = ConfigDict(from_attributes=True)


class AgencyEventOut(_Out):
    id: str
    title: str
    agency: str | None
    kind: str | None
    starts_at: str | None
    ends_at: str | None
    location: str | None
    source_url: str
    source_host: str | None
    registration_url: str | None
    naics_codes: list[str]
    summary: str | None
    last_seen_at: str


class AgencyEventsResponse(_Out):
    total: int
    items: list[AgencyEventOut]


def _to_out(ev: AgencyEvent) -> AgencyEventOut:
    return AgencyEventOut(
        id=str(ev.id),
        title=ev.title,
        agency=ev.agency,
        kind=ev.kind,
        starts_at=ev.starts_at.isoformat() if ev.starts_at else None,
        ends_at=ev.ends_at.isoformat() if ev.ends_at else None,
        location=ev.location,
        source_url=ev.source_url,
        source_host=ev.source_host,
        registration_url=ev.registration_url,
        naics_codes=list(ev.naics_codes or []),
        summary=ev.summary,
        last_seen_at=ev.last_seen_at.isoformat(),
    )


@router.get("/events", response_model=AgencyEventsResponse)
async def list_events(
    ctx: Annotated[RequestContext, Depends(get_request_context)],
    upcoming_only: Annotated[bool, Query()] = True,
    limit: Annotated[int, Query(ge=1, le=200)] = 100,
) -> AgencyEventsResponse:
    """List industry-day / pre-sol / agency events, deduped.

    The same event is often captured from many source URLs (an AFCEA
    symposium appears on the events index, the calendar, and its own
    detail page) so we DISTINCT ON `(lower(title), starts_at)` and pick
    the row most likely to have complete metadata (most-recently seen,
    has a registration URL, has an agency).
    """
    # Sub-select: keep one row per (lower(title), starts_at) pair, with
    # a deterministic tiebreaker that prefers more-complete records.
    title_l = func.lower(AgencyEvent.title)
    sub = (
        select(AgencyEvent)
        .distinct(title_l, AgencyEvent.starts_at)
        .order_by(
            title_l,
            AgencyEvent.starts_at,
            # Prefer rows with a registration_url, then those with an
            # agency, then the most-recently-seen.
            AgencyEvent.registration_url.is_(None),
            AgencyEvent.agency.is_(None),
            AgencyEvent.last_seen_at.desc(),
        )
        .subquery()
    )
    Aliased = sub.c
    stmt = select(AgencyEvent).where(AgencyEvent.id.in_(select(Aliased.id)))

    if upcoming_only:
        now = datetime.now(UTC)
        # Keep events with no starts_at OR starts_at strictly in the future.
        # Tighter than v1 (was >= now) so events that started today but
        # ended yesterday don't surface.
        stmt = stmt.where((AgencyEvent.starts_at >= now) | (AgencyEvent.starts_at.is_(None)))

    stmt = stmt.order_by(
        AgencyEvent.starts_at.asc().nulls_last(),
        AgencyEvent.last_seen_at.desc(),
    ).limit(limit)
    rows = (await ctx.session.execute(stmt)).scalars().all()
    return AgencyEventsResponse(total=len(rows), items=[_to_out(r) for r in rows])
