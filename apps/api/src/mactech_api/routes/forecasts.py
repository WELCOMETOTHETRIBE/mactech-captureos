"""Forecasts feed — agency procurement forecasts (pre-SAM intent).

Sprint 20. Tenant-shared (forecasts are public-data signal). Filters
by tenant.target_naics by default so each founder sees only the
forecasts that actually map to their NAICS profile. Dedups across
source URLs since the same forecast often appears on multiple agency
hubs (DHS APFS + DHS subcomponent + small-biz portal).

  GET /forecasts?upcoming_only=true&limit=100
"""

from __future__ import annotations

import logging
from datetime import UTC, datetime
from typing import Annotated

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, ConfigDict
from sqlalchemy import func, select

from mactech_api.auth import RequestContext, get_request_context
from mactech_db.models import ForecastRaw

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
    incumbent_name: str | None
    poc_name: str | None
    poc_email: str | None
    source_url: str
    source_host: str | None
    last_seen_at: str
    matches_target_naics: bool


class ForecastsResponse(_Out):
    total: int
    items: list[ForecastOut]
    target_naics_filter: bool
    target_naics: list[str]


def _to_out(fc: ForecastRaw, *, target_set: set[str]) -> ForecastOut:
    naics_set = set(fc.naics_codes or [])
    if fc.naics_code:
        naics_set.add(fc.naics_code)
    matches = bool(target_set) and bool(naics_set & target_set)
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
        incumbent_name=fc.incumbent_name,
        poc_name=fc.poc_name,
        poc_email=fc.poc_email,
        source_url=fc.source_url,
        source_host=fc.source_host,
        last_seen_at=fc.last_seen_at.isoformat(),
        matches_target_naics=matches,
    )


@router.get("/forecasts", response_model=ForecastsResponse)
async def list_forecasts(
    ctx: Annotated[RequestContext, Depends(get_request_context)],
    upcoming_only: Annotated[bool, Query()] = True,
    limit: Annotated[int, Query(ge=1, le=200)] = 100,
    naics_filter: Annotated[
        bool, Query(description="Restrict to forecasts matching tenant.target_naics")
    ] = True,
) -> ForecastsResponse:
    target_naics = list(ctx.tenant.target_naics or [])
    target_set = set(target_naics)

    title_l = func.lower(ForecastRaw.title)
    sub = (
        select(ForecastRaw)
        .distinct(title_l, ForecastRaw.expected_solicitation_date)
        .order_by(
            title_l,
            ForecastRaw.expected_solicitation_date,
            # Prefer rows with NAICS, value, POC, agency.
            ForecastRaw.naics_code.is_(None),
            ForecastRaw.estimated_value_high.is_(None),
            ForecastRaw.poc_email.is_(None),
            ForecastRaw.agency.is_(None),
            ForecastRaw.last_seen_at.desc(),
        )
        .subquery()
    )
    stmt = select(ForecastRaw).where(
        ForecastRaw.id.in_(select(sub.c.id))
    )

    if upcoming_only:
        now_d = datetime.now(UTC).date()
        stmt = stmt.where(
            (ForecastRaw.expected_solicitation_date >= now_d)
            | (ForecastRaw.expected_solicitation_date.is_(None))
        )

    if naics_filter and target_set:
        # Match either the primary naics_code or any entry in the
        # naics_codes JSONB array. We use ?| with the target set to
        # check JSONB containment in any direction.
        from sqlalchemy import or_, cast
        from sqlalchemy.dialects.postgresql import JSONB
        stmt = stmt.where(
            or_(
                ForecastRaw.naics_code.in_(list(target_set)),
                cast(ForecastRaw.naics_codes, JSONB).op("?|")(
                    list(target_set)
                ),
            )
        )

    stmt = stmt.order_by(
        ForecastRaw.expected_solicitation_date.asc().nulls_last(),
        ForecastRaw.last_seen_at.desc(),
    ).limit(limit)

    rows = (await ctx.session.execute(stmt)).scalars().all()
    items = [_to_out(r, target_set=target_set) for r in rows]
    return ForecastsResponse(
        total=len(items),
        items=items,
        target_naics_filter=bool(naics_filter and target_set),
        target_naics=target_naics,
    )
