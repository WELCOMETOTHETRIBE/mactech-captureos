"""Pursuit detail + per-pursuit asset linking.

Section F of CaptureOS_Requirements.md and the missing piece that lets
the Capture Package's selected[] arrays carry real content. Endpoints:

  GET /pursuits/{id}
      Full pursuit detail including opportunity excerpt, win themes,
      discriminators, and the currently-selected past performance, key
      personnel, and teaming partners.

  PUT /pursuits/{id}/past-performance      body: {past_performance_ids: [...]}
  PUT /pursuits/{id}/key-personnel         body: {founder_ids: [...]}
  PUT /pursuits/{id}/teaming-partners      body: {teaming_partner_ids: [...]}
      Replace the entire selection in array order. IDs must belong to
      this tenant or the request is rejected with 400.

We chose PUT-replace over POST-add/DELETE-remove because the UI is
selection-oriented (list + checkboxes), and replacing makes the
client-server contract trivial: client sends what it wants, server
matches.
"""

from __future__ import annotations

import logging
from datetime import datetime
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, ConfigDict
from sqlalchemy import delete, select

from mactech_api.auth import RequestContext, get_request_context
from mactech_db.models import (
    Founder,
    OpportunityRaw,
    PastPerformance,
    Pursuit,
    PursuitKeyPersonnel,
    PursuitPastPerformance,
    PursuitTeamingPartner,
    TeamingPartner,
)

log = logging.getLogger(__name__)
router = APIRouter(tags=["pursuits"])


class _Out(BaseModel):
    model_config = ConfigDict(from_attributes=True)


class PursuitOppLite(_Out):
    id: str
    notice_id: str
    title: str
    agency: str | None
    naics_code: str | None
    set_aside: str | None
    posted_at: str | None
    response_deadline: str | None


class LinkedPastPerformance(_Out):
    id: str
    title: str
    customer_agency: str | None
    customer_office: str | None
    contract_number: str | None
    role: str | None
    period_start: str | None
    period_end: str | None
    contract_value: float | None
    summary: str | None
    sort_order: int


class LinkedKeyPerson(_Out):
    id: str
    slug: str
    full_name: str
    title: str | None
    pillar: str | None
    sort_order: int


class LinkedTeamingPartner(_Out):
    id: str
    name: str
    uei: str | None
    capabilities: list[str]
    naics_codes: list[str]
    set_aside_certifications: list[str]
    sort_order: int


class PursuitDetailOut(_Out):
    id: str
    stage: str
    notes: str | None
    win_themes: list[str]
    discriminators: list[str]
    owner_founder_slug: str | None
    owner_founder_name: str | None
    created_at: str
    updated_at: str
    last_stage_change_at: str
    opportunity: PursuitOppLite
    selected_past_performance: list[LinkedPastPerformance]
    selected_key_personnel: list[LinkedKeyPerson]
    selected_teaming_partners: list[LinkedTeamingPartner]
    library_size_past_performance: int
    library_size_key_personnel: int
    library_size_teaming_partners: int


class ReplaceLinksRequest(BaseModel):
    """Generic body shape — one field per endpoint."""

    past_performance_ids: list[UUID] | None = None
    founder_ids: list[UUID] | None = None
    teaming_partner_ids: list[UUID] | None = None


def _to_iso(dt: datetime | None) -> str | None:
    return dt.isoformat() if dt else None


async def _load_pursuit_or_404(
    ctx: RequestContext, pursuit_id: UUID
) -> Pursuit:
    pursuit = (
        await ctx.session.execute(
            select(Pursuit).where(
                Pursuit.id == pursuit_id, Pursuit.tenant_id == ctx.tenant.id
            )
        )
    ).scalar_one_or_none()
    if pursuit is None:
        raise HTTPException(status_code=404, detail="pursuit not found")
    return pursuit


@router.get("/pursuits/{pursuit_id}", response_model=PursuitDetailOut)
async def get_pursuit_detail(
    pursuit_id: UUID,
    ctx: Annotated[RequestContext, Depends(get_request_context)],
) -> PursuitDetailOut:
    pursuit = await _load_pursuit_or_404(ctx, pursuit_id)
    session = ctx.session
    tenant_id = ctx.tenant.id

    opp = (
        await session.execute(
            select(OpportunityRaw).where(OpportunityRaw.id == pursuit.opportunity_id)
        )
    ).scalar_one()

    owner = None
    if pursuit.owner_founder_id is not None:
        owner = (
            await session.execute(
                select(Founder).where(Founder.id == pursuit.owner_founder_id)
            )
        ).scalar_one_or_none()

    pp_rows = list(
        (
            await session.execute(
                select(PastPerformance, PursuitPastPerformance)
                .join(
                    PursuitPastPerformance,
                    PursuitPastPerformance.past_performance_id == PastPerformance.id,
                )
                .where(PursuitPastPerformance.pursuit_id == pursuit_id)
                .order_by(PursuitPastPerformance.sort_order.asc())
            )
        ).all()
    )

    kp_rows = list(
        (
            await session.execute(
                select(Founder, PursuitKeyPersonnel)
                .join(PursuitKeyPersonnel, PursuitKeyPersonnel.founder_id == Founder.id)
                .where(PursuitKeyPersonnel.pursuit_id == pursuit_id)
                .order_by(PursuitKeyPersonnel.sort_order.asc())
            )
        ).all()
    )

    tp_rows = list(
        (
            await session.execute(
                select(TeamingPartner, PursuitTeamingPartner)
                .join(
                    PursuitTeamingPartner,
                    PursuitTeamingPartner.teaming_partner_id == TeamingPartner.id,
                )
                .where(PursuitTeamingPartner.pursuit_id == pursuit_id)
                .order_by(PursuitTeamingPartner.sort_order.asc())
            )
        ).all()
    )

    # Library counts — used by the UI to surface "X available, N selected".
    pp_lib_count = (
        await session.execute(
            select(PastPerformance).where(PastPerformance.tenant_id == tenant_id)
        )
    ).scalars().all()
    kp_lib_count = (
        await session.execute(
            select(Founder).where(Founder.tenant_id == tenant_id)
        )
    ).scalars().all()
    tp_lib_count = (
        await session.execute(
            select(TeamingPartner).where(TeamingPartner.tenant_id == tenant_id)
        )
    ).scalars().all()

    return PursuitDetailOut(
        id=str(pursuit.id),
        stage=pursuit.stage,
        notes=pursuit.notes,
        win_themes=list(pursuit.win_themes or []),
        discriminators=list(pursuit.discriminators or []),
        owner_founder_slug=owner.slug if owner else None,
        owner_founder_name=owner.full_name if owner else None,
        created_at=pursuit.created_at.isoformat(),
        updated_at=pursuit.updated_at.isoformat(),
        last_stage_change_at=pursuit.last_stage_change_at.isoformat(),
        opportunity=PursuitOppLite(
            id=str(opp.id),
            notice_id=opp.source_id,
            title=opp.title,
            agency=opp.agency,
            naics_code=opp.naics_code,
            set_aside=opp.set_aside,
            posted_at=_to_iso(opp.posted_at),
            response_deadline=_to_iso(opp.response_deadline),
        ),
        selected_past_performance=[
            LinkedPastPerformance(
                id=str(pp.id),
                title=pp.title,
                customer_agency=pp.customer_agency,
                customer_office=pp.customer_office,
                contract_number=pp.contract_number,
                role=link.role or pp.role,
                period_start=_to_iso(pp.period_start),
                period_end=_to_iso(pp.period_end),
                contract_value=float(pp.contract_value) if pp.contract_value else None,
                summary=pp.summary,
                sort_order=link.sort_order,
            )
            for pp, link in pp_rows
        ],
        selected_key_personnel=[
            LinkedKeyPerson(
                id=str(f.id),
                slug=f.slug,
                full_name=f.full_name,
                title=link.role or f.title,
                pillar=f.pillar,
                sort_order=link.sort_order,
            )
            for f, link in kp_rows
        ],
        selected_teaming_partners=[
            LinkedTeamingPartner(
                id=str(p.id),
                name=p.name,
                uei=p.uei,
                capabilities=list(p.capabilities or []),
                naics_codes=list(p.naics_codes or []),
                set_aside_certifications=list(p.set_aside_certifications or []),
                sort_order=link.sort_order,
            )
            for p, link in tp_rows
        ],
        library_size_past_performance=len(pp_lib_count),
        library_size_key_personnel=len(kp_lib_count),
        library_size_teaming_partners=len(tp_lib_count),
    )


async def _validate_tenant_owned(
    ctx: RequestContext, model: type, ids: list[UUID]
) -> None:
    if not ids:
        return
    rows = (
        await ctx.session.execute(
            select(model.id).where(
                model.id.in_(ids), model.tenant_id == ctx.tenant.id
            )
        )
    ).scalars().all()
    found = {row for row in rows}
    missing = [i for i in ids if i not in found]
    if missing:
        raise HTTPException(
            status_code=400,
            detail=f"{model.__name__} IDs not in this tenant: {[str(i) for i in missing]}",
        )


@router.put(
    "/pursuits/{pursuit_id}/past-performance",
    response_model=PursuitDetailOut,
    status_code=status.HTTP_200_OK,
)
async def replace_past_performance(
    pursuit_id: UUID,
    body: ReplaceLinksRequest,
    ctx: Annotated[RequestContext, Depends(get_request_context)],
) -> PursuitDetailOut:
    pursuit = await _load_pursuit_or_404(ctx, pursuit_id)
    ids = list(dict.fromkeys(body.past_performance_ids or []))
    await _validate_tenant_owned(ctx, PastPerformance, ids)

    await ctx.session.execute(
        delete(PursuitPastPerformance).where(
            PursuitPastPerformance.pursuit_id == pursuit_id
        )
    )
    for idx, pp_id in enumerate(ids):
        ctx.session.add(
            PursuitPastPerformance(
                pursuit_id=pursuit_id,
                past_performance_id=pp_id,
                tenant_id=ctx.tenant.id,
                sort_order=idx,
            )
        )
    pursuit.updated_at = datetime.utcnow()
    await ctx.session.flush()
    return await get_pursuit_detail(pursuit_id, ctx)


@router.put(
    "/pursuits/{pursuit_id}/key-personnel",
    response_model=PursuitDetailOut,
    status_code=status.HTTP_200_OK,
)
async def replace_key_personnel(
    pursuit_id: UUID,
    body: ReplaceLinksRequest,
    ctx: Annotated[RequestContext, Depends(get_request_context)],
) -> PursuitDetailOut:
    pursuit = await _load_pursuit_or_404(ctx, pursuit_id)
    ids = list(dict.fromkeys(body.founder_ids or []))
    await _validate_tenant_owned(ctx, Founder, ids)

    await ctx.session.execute(
        delete(PursuitKeyPersonnel).where(
            PursuitKeyPersonnel.pursuit_id == pursuit_id
        )
    )
    for idx, founder_id in enumerate(ids):
        ctx.session.add(
            PursuitKeyPersonnel(
                pursuit_id=pursuit_id,
                founder_id=founder_id,
                tenant_id=ctx.tenant.id,
                sort_order=idx,
            )
        )
    pursuit.updated_at = datetime.utcnow()
    await ctx.session.flush()
    return await get_pursuit_detail(pursuit_id, ctx)


@router.put(
    "/pursuits/{pursuit_id}/teaming-partners",
    response_model=PursuitDetailOut,
    status_code=status.HTTP_200_OK,
)
async def replace_teaming_partners(
    pursuit_id: UUID,
    body: ReplaceLinksRequest,
    ctx: Annotated[RequestContext, Depends(get_request_context)],
) -> PursuitDetailOut:
    pursuit = await _load_pursuit_or_404(ctx, pursuit_id)
    ids = list(dict.fromkeys(body.teaming_partner_ids or []))
    await _validate_tenant_owned(ctx, TeamingPartner, ids)

    await ctx.session.execute(
        delete(PursuitTeamingPartner).where(
            PursuitTeamingPartner.pursuit_id == pursuit_id
        )
    )
    for idx, tp_id in enumerate(ids):
        ctx.session.add(
            PursuitTeamingPartner(
                pursuit_id=pursuit_id,
                teaming_partner_id=tp_id,
                tenant_id=ctx.tenant.id,
                sort_order=idx,
            )
        )
    pursuit.updated_at = datetime.utcnow()
    await ctx.session.flush()
    return await get_pursuit_detail(pursuit_id, ctx)
