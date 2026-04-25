"""Capture pipeline kanban API.

Phase 2 Week 7. One pursuit per (tenant, opportunity). Stages flow
lead → qualify → pursue → propose → submit → won/lost. Free transitions
allowed — pursuits drop back all the time in real BD work.

Endpoints:
  GET    /pursuits                  kanban payload, grouped by stage
  GET    /pursuits/by-opportunity/{opportunity_id}   single pursuit (or 404)
  POST   /pursuits                  create a pursuit from an opportunity
  PATCH  /pursuits/{id}             change stage / owner / notes
  DELETE /pursuits/{id}             remove from pipeline
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import select, text

from mactech_api.auth import RequestContext, get_request_context
from mactech_db.models import Founder, OpportunityRaw, Pursuit
from mactech_db.models.pursuit import PURSUIT_STAGES

router = APIRouter(tags=["pursuits"])


class _Out(BaseModel):
    model_config = ConfigDict(from_attributes=True)


class PursuitOpp(_Out):
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


class PursuitCard(_Out):
    id: str
    stage: str
    owner_founder_slug: str | None
    owner_founder_name: str | None
    notes: str | None
    created_at: str
    updated_at: str
    last_stage_change_at: str
    days_in_stage: int
    opportunity: PursuitOpp


class StageColumn(_Out):
    stage: str
    label: str
    count: int
    cards: list[PursuitCard]


class KanbanResponse(_Out):
    rendered_at: str
    total: int
    by_owner: dict[str, int]
    columns: list[StageColumn]


class CreatePursuitRequest(BaseModel):
    opportunity_id: UUID
    stage: str = "lead"
    owner_founder_slug: str | None = None
    notes: str | None = None


class UpdatePursuitRequest(BaseModel):
    stage: str | None = None
    owner_founder_slug: str | None = Field(default=None)
    clear_owner: bool = False
    notes: str | None = None


STAGE_LABELS = {
    "lead": "Lead",
    "qualify": "Qualify",
    "pursue": "Pursue",
    "propose": "Propose",
    "submit": "Submit",
    "won": "Won",
    "lost": "Lost",
}


def _short_agency(p: str | None) -> str | None:
    if not p:
        return None
    return p.split(".")[0].strip()


def _days_until(dt: datetime | None) -> int | None:
    if dt is None:
        return None
    return int((dt - datetime.now(timezone.utc)).total_seconds() / 86400)


def _days_in_stage(dt: datetime) -> int:
    return max(0, int((datetime.now(timezone.utc) - dt).total_seconds() / 86400))


async def _resolve_owner_founder_id(
    ctx: RequestContext, slug: str | None
) -> UUID | None:
    if not slug:
        return None
    f = (
        await ctx.session.execute(select(Founder).where(Founder.slug == slug))
    ).scalar_one_or_none()
    if f is None:
        raise HTTPException(
            status_code=400, detail=f"founder slug '{slug}' not found"
        )
    return f.id


def _validate_stage(stage: str) -> str:
    if stage not in PURSUIT_STAGES:
        raise HTTPException(
            status_code=400,
            detail=f"invalid stage '{stage}'. Allowed: {list(PURSUIT_STAGES)}",
        )
    return stage


@router.get("/pursuits", response_model=KanbanResponse)
async def get_kanban(
    ctx: Annotated[RequestContext, Depends(get_request_context)],
    owner: str | None = None,
) -> KanbanResponse:
    session = ctx.session
    tenant_id = ctx.tenant.id

    # One round-trip: pursuits + opportunity columns + score + founder slug.
    where_owner = ""
    params: dict[str, object] = {"tenant_id": str(tenant_id)}
    if owner:
        where_owner = (
            "and (select f2.slug from founders f2 "
            "where f2.id = p.owner_founder_id) = :owner"
        )
        params["owner"] = owner

    rows = (
        await session.execute(
            text(
                f"""
                select
                    p.id::text, p.stage, p.notes,
                    p.created_at, p.updated_at, p.last_stage_change_at,
                    f.slug, f.full_name,
                    o.id::text, o.source_id, o.title, o.notice_type, o.set_aside,
                    o.naics_code, o.agency, o.posted_at, o.response_deadline,
                    s.score
                from pursuits p
                join opportunities_raw o on o.id = p.opportunity_id
                left join opportunity_scores s
                    on s.opportunity_id = o.id and s.tenant_id = p.tenant_id
                left join founders f on f.id = p.owner_founder_id
                where p.tenant_id = :tenant_id
                {where_owner}
                order by
                    case p.stage
                        when 'lead' then 0 when 'qualify' then 1
                        when 'pursue' then 2 when 'propose' then 3
                        when 'submit' then 4 when 'won' then 5
                        when 'lost' then 6 else 7
                    end,
                    s.score desc nulls last,
                    p.last_stage_change_at desc
                """
            ),
            params,
        )
    ).all()

    cards_by_stage: dict[str, list[PursuitCard]] = {s: [] for s in PURSUIT_STAGES}
    by_owner: dict[str, int] = {}
    total = 0

    for r in rows:
        deadline = r[16]
        card = PursuitCard(
            id=r[0],
            stage=r[1],
            notes=r[2],
            created_at=r[3].isoformat(),
            updated_at=r[4].isoformat(),
            last_stage_change_at=r[5].isoformat(),
            days_in_stage=_days_in_stage(r[5]),
            owner_founder_slug=r[6],
            owner_founder_name=r[7],
            opportunity=PursuitOpp(
                id=r[8],
                notice_id=r[9],
                title=r[10],
                notice_type=r[11],
                set_aside=r[12],
                naics_code=r[13],
                agency_short=_short_agency(r[14]),
                posted_at=r[15].isoformat() if r[15] else None,
                response_deadline=deadline.isoformat() if deadline else None,
                days_until_deadline=_days_until(deadline),
                score=int(r[17]) if r[17] is not None else None,
            ),
        )
        cards_by_stage.setdefault(r[1], []).append(card)
        total += 1
        owner_key = r[6] or "_unassigned"
        by_owner[owner_key] = by_owner.get(owner_key, 0) + 1

    columns = [
        StageColumn(
            stage=s,
            label=STAGE_LABELS[s],
            count=len(cards_by_stage.get(s, [])),
            cards=cards_by_stage.get(s, []),
        )
        for s in PURSUIT_STAGES
    ]

    return KanbanResponse(
        rendered_at=datetime.now(timezone.utc).isoformat(),
        total=total,
        by_owner=by_owner,
        columns=columns,
    )


@router.get("/pursuits/by-opportunity/{opportunity_id}", response_model=PursuitCard)
async def get_pursuit_for_opp(
    opportunity_id: UUID,
    ctx: Annotated[RequestContext, Depends(get_request_context)],
) -> PursuitCard:
    session = ctx.session
    tenant_id = ctx.tenant.id

    row = (
        await session.execute(
            text(
                """
                select
                    p.id::text, p.stage, p.notes,
                    p.created_at, p.updated_at, p.last_stage_change_at,
                    f.slug, f.full_name,
                    o.id::text, o.source_id, o.title, o.notice_type, o.set_aside,
                    o.naics_code, o.agency, o.posted_at, o.response_deadline,
                    s.score
                from pursuits p
                join opportunities_raw o on o.id = p.opportunity_id
                left join opportunity_scores s
                    on s.opportunity_id = o.id and s.tenant_id = p.tenant_id
                left join founders f on f.id = p.owner_founder_id
                where p.tenant_id = :t and p.opportunity_id = :o
                """
            ),
            {"t": str(tenant_id), "o": str(opportunity_id)},
        )
    ).first()

    if row is None:
        raise HTTPException(status_code=404, detail="no pursuit for this opportunity")

    deadline = row[16]
    return PursuitCard(
        id=row[0],
        stage=row[1],
        notes=row[2],
        created_at=row[3].isoformat(),
        updated_at=row[4].isoformat(),
        last_stage_change_at=row[5].isoformat(),
        days_in_stage=_days_in_stage(row[5]),
        owner_founder_slug=row[6],
        owner_founder_name=row[7],
        opportunity=PursuitOpp(
            id=row[8],
            notice_id=row[9],
            title=row[10],
            notice_type=row[11],
            set_aside=row[12],
            naics_code=row[13],
            agency_short=_short_agency(row[14]),
            posted_at=row[15].isoformat() if row[15] else None,
            response_deadline=deadline.isoformat() if deadline else None,
            days_until_deadline=_days_until(deadline),
            score=int(row[17]) if row[17] is not None else None,
        ),
    )


@router.post(
    "/pursuits",
    response_model=PursuitCard,
    status_code=status.HTTP_201_CREATED,
)
async def create_pursuit(
    body: CreatePursuitRequest,
    ctx: Annotated[RequestContext, Depends(get_request_context)],
) -> PursuitCard:
    session = ctx.session
    tenant_id = ctx.tenant.id

    _validate_stage(body.stage)

    opp = (
        await session.execute(
            select(OpportunityRaw).where(OpportunityRaw.id == body.opportunity_id)
        )
    ).scalar_one_or_none()
    if opp is None:
        raise HTTPException(status_code=404, detail="opportunity not found")

    existing = (
        await session.execute(
            select(Pursuit).where(
                Pursuit.tenant_id == tenant_id,
                Pursuit.opportunity_id == body.opportunity_id,
            )
        )
    ).scalar_one_or_none()
    if existing is not None:
        raise HTTPException(
            status_code=409,
            detail=f"pursuit already exists for this opportunity (id={existing.id})",
        )

    owner_id = await _resolve_owner_founder_id(ctx, body.owner_founder_slug)

    pursuit = Pursuit(
        tenant_id=tenant_id,
        opportunity_id=body.opportunity_id,
        owner_founder_id=owner_id,
        stage=body.stage,
        notes=body.notes,
    )
    session.add(pursuit)
    await session.flush()

    return await get_pursuit_for_opp(body.opportunity_id, ctx)


@router.patch("/pursuits/{pursuit_id}", response_model=PursuitCard)
async def update_pursuit(
    pursuit_id: UUID,
    body: UpdatePursuitRequest,
    ctx: Annotated[RequestContext, Depends(get_request_context)],
) -> PursuitCard:
    session = ctx.session
    tenant_id = ctx.tenant.id

    pursuit = (
        await session.execute(
            select(Pursuit).where(
                Pursuit.id == pursuit_id, Pursuit.tenant_id == tenant_id
            )
        )
    ).scalar_one_or_none()
    if pursuit is None:
        raise HTTPException(status_code=404, detail="pursuit not found")

    if body.stage is not None:
        _validate_stage(body.stage)
        if body.stage != pursuit.stage:
            pursuit.stage = body.stage
            pursuit.last_stage_change_at = datetime.now(timezone.utc)

    if body.clear_owner:
        pursuit.owner_founder_id = None
    elif body.owner_founder_slug is not None:
        pursuit.owner_founder_id = await _resolve_owner_founder_id(
            ctx, body.owner_founder_slug
        )

    if body.notes is not None:
        pursuit.notes = body.notes

    await session.flush()
    return await get_pursuit_for_opp(pursuit.opportunity_id, ctx)


@router.delete("/pursuits/{pursuit_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_pursuit(
    pursuit_id: UUID,
    ctx: Annotated[RequestContext, Depends(get_request_context)],
) -> None:
    session = ctx.session
    tenant_id = ctx.tenant.id

    pursuit = (
        await session.execute(
            select(Pursuit).where(
                Pursuit.id == pursuit_id, Pursuit.tenant_id == tenant_id
            )
        )
    ).scalar_one_or_none()
    if pursuit is None:
        raise HTTPException(status_code=404, detail="pursuit not found")

    await session.delete(pursuit)
    await session.flush()
