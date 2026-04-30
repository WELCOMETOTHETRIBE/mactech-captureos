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
from sqlalchemy.exc import IntegrityError

from mactech_api.auth import RequestContext, get_request_context
from mactech_db.audit import record_event
from mactech_db.models import (
    EVENT_PURSUIT_BID_DECIDED,
    EVENT_PURSUIT_CREATED,
    EVENT_PURSUIT_DELETED,
    EVENT_PURSUIT_NOTES_UPDATED,
    EVENT_PURSUIT_OWNER_CHANGED,
    EVENT_PURSUIT_STAGE_CHANGED,
    EVENT_PURSUIT_WIN_STRATEGY_UPDATED,
    Founder,
    OpportunityRaw,
    Pursuit,
)
from mactech_db.models.pursuit import BID_DECISIONS, PURSUIT_STAGES

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
    # Capture-strategy fields. Pass an array (possibly empty) to replace
    # the current contents; pass None / omit to leave them alone.
    win_themes: list[str] | None = None
    discriminators: list[str] | None = None
    # Structured bid memo. Setting `bid_decision` to bid|no_bid stamps
    # bid_decided_at + bid_decided_by_user_id automatically; setting it
    # back to "pending" clears them.
    bid_decision: str | None = None
    bid_rationale: str | None = None


def _validate_bid_decision(decision: str) -> str:
    if decision not in BID_DECISIONS:
        raise HTTPException(
            status_code=400,
            detail=f"invalid bid_decision '{decision}'. Allowed: {list(BID_DECISIONS)}",
        )
    return decision


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
        await ctx.session.execute(
            select(Founder).where(
                Founder.tenant_id == ctx.tenant.id,
                Founder.slug == slug,
            )
        )
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
    try:
        await session.flush()
    except IntegrityError:
        # Concurrent POST passed the existence check above — the unique
        # constraint caught the duplicate. Surface as a 409 instead of 500.
        await session.rollback()
        raise HTTPException(
            status_code=409,
            detail="pursuit already exists for this opportunity",
        ) from None

    await record_event(
        session,
        tenant_id=tenant_id,
        event_type=EVENT_PURSUIT_CREATED,
        entity_type="pursuit",
        entity_id=pursuit.id,
        payload={
            "opportunity_id": str(body.opportunity_id),
            "stage": body.stage,
            "owner_founder_slug": body.owner_founder_slug,
        },
        **_audit_actor_kwargs(ctx),
    )
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

    actor_kwargs = _audit_actor_kwargs(ctx)

    if body.stage is not None:
        _validate_stage(body.stage)
        if body.stage != pursuit.stage:
            previous_stage = pursuit.stage
            pursuit.stage = body.stage
            pursuit.last_stage_change_at = datetime.now(timezone.utc)
            await record_event(
                session,
                tenant_id=tenant_id,
                event_type=EVENT_PURSUIT_STAGE_CHANGED,
                entity_type="pursuit",
                entity_id=pursuit.id,
                payload={"from": previous_stage, "to": body.stage},
                **actor_kwargs,
            )

    if body.clear_owner:
        if pursuit.owner_founder_id is not None:
            previous_owner_id = pursuit.owner_founder_id
            pursuit.owner_founder_id = None
            await record_event(
                session,
                tenant_id=tenant_id,
                event_type=EVENT_PURSUIT_OWNER_CHANGED,
                entity_type="pursuit",
                entity_id=pursuit.id,
                payload={
                    "from_founder_id": str(previous_owner_id),
                    "to_founder_id": None,
                },
                **actor_kwargs,
            )
    elif body.owner_founder_slug is not None:
        new_owner_id = await _resolve_owner_founder_id(ctx, body.owner_founder_slug)
        if new_owner_id != pursuit.owner_founder_id:
            previous_owner_id = pursuit.owner_founder_id
            pursuit.owner_founder_id = new_owner_id
            await record_event(
                session,
                tenant_id=tenant_id,
                event_type=EVENT_PURSUIT_OWNER_CHANGED,
                entity_type="pursuit",
                entity_id=pursuit.id,
                payload={
                    "from_founder_id": (
                        str(previous_owner_id) if previous_owner_id else None
                    ),
                    "to_founder_id": str(new_owner_id) if new_owner_id else None,
                    "to_founder_slug": body.owner_founder_slug,
                },
                **actor_kwargs,
            )

    if body.notes is not None and body.notes != pursuit.notes:
        pursuit.notes = body.notes
        await record_event(
            session,
            tenant_id=tenant_id,
            event_type=EVENT_PURSUIT_NOTES_UPDATED,
            entity_type="pursuit",
            entity_id=pursuit.id,
            payload={"chars": len(body.notes)},
            **actor_kwargs,
        )

    if body.win_themes is not None or body.discriminators is not None:
        if body.win_themes is not None:
            pursuit.win_themes = [
                t.strip() for t in body.win_themes if t and t.strip()
            ]
        if body.discriminators is not None:
            pursuit.discriminators = [
                d.strip() for d in body.discriminators if d and d.strip()
            ]
        await record_event(
            session,
            tenant_id=tenant_id,
            event_type=EVENT_PURSUIT_WIN_STRATEGY_UPDATED,
            entity_type="pursuit",
            entity_id=pursuit.id,
            payload={
                "win_theme_count": len(pursuit.win_themes or []),
                "discriminator_count": len(pursuit.discriminators or []),
            },
            **actor_kwargs,
        )

    if body.bid_decision is not None:
        new_decision = _validate_bid_decision(body.bid_decision)
        if new_decision != pursuit.bid_decision or body.bid_rationale is not None:
            previous_decision = pursuit.bid_decision
            pursuit.bid_decision = new_decision
            if body.bid_rationale is not None:
                pursuit.bid_rationale = body.bid_rationale or None
            if new_decision == "pending":
                pursuit.bid_decided_at = None
                pursuit.bid_decided_by_user_id = None
            else:
                pursuit.bid_decided_at = datetime.now(timezone.utc)
                pursuit.bid_decided_by_user_id = ctx.user.id
            await record_event(
                session,
                tenant_id=tenant_id,
                event_type=EVENT_PURSUIT_BID_DECIDED,
                entity_type="pursuit",
                entity_id=pursuit.id,
                payload={
                    "from": previous_decision,
                    "to": new_decision,
                    "rationale_chars": len(pursuit.bid_rationale or ""),
                },
                **actor_kwargs,
            )
    elif body.bid_rationale is not None and body.bid_rationale != pursuit.bid_rationale:
        # Update rationale only — no decision change.
        pursuit.bid_rationale = body.bid_rationale or None
        await record_event(
            session,
            tenant_id=tenant_id,
            event_type=EVENT_PURSUIT_BID_DECIDED,
            entity_type="pursuit",
            entity_id=pursuit.id,
            payload={
                "decision": pursuit.bid_decision,
                "rationale_only_update": True,
                "rationale_chars": len(pursuit.bid_rationale or ""),
            },
            **actor_kwargs,
        )

    # SQLAlchemy `onupdate=func.now()` should bump `updated_at` on flush, but
    # set it explicitly so the value is correct even if a future raw-SQL path
    # bypasses the ORM. Belt-and-suspenders.
    pursuit.updated_at = datetime.now(timezone.utc)

    await session.flush()
    return await get_pursuit_for_opp(pursuit.opportunity_id, ctx)


def _audit_actor_kwargs(ctx: RequestContext) -> dict:
    """Translate a RequestContext into the actor_* kwargs for record_event."""
    return {
        "actor_user_id": ctx.user.id if ctx.user else None,
        "actor_founder_id": ctx.founder.id if ctx.founder else None,
    }


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

    # Emit before delete so the foreign key still resolves and the event
    # has the final pursuit shape captured in its payload.
    await record_event(
        session,
        tenant_id=tenant_id,
        event_type=EVENT_PURSUIT_DELETED,
        entity_type="pursuit",
        entity_id=pursuit.id,
        payload={
            "opportunity_id": str(pursuit.opportunity_id),
            "stage_at_delete": pursuit.stage,
            "bid_decision_at_delete": pursuit.bid_decision,
        },
        **_audit_actor_kwargs(ctx),
    )
    await session.delete(pursuit)
    await session.flush()
