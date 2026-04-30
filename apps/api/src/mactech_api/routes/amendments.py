"""Opportunity amendments and pursuit audit log.

Two read-only endpoints fed by the data Sprint 1 lays down:

  GET /opportunities/{id}/amendments
      List of amendments detected on this opportunity, newest first.
      Tenant-scoped only insofar as we require an authenticated session;
      amendments themselves are facts about the opportunity, not the
      tenant.

  GET /pursuits/{id}/audit
      Audit-event timeline for this pursuit. Includes pursuit-scoped
      events plus opportunity-amendment events that affected this
      pursuit's parent opportunity.
"""

from __future__ import annotations

import logging
from typing import Annotated, Any
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, ConfigDict
from sqlalchemy import or_, select

from mactech_api.auth import RequestContext, get_request_context
from mactech_db.models import (
    AuditEvent,
    Founder,
    OpportunityAmendment,
    OpportunityRaw,
    Pursuit,
    User,
)

log = logging.getLogger(__name__)
router = APIRouter(tags=["amendments", "audit"])


class _Out(BaseModel):
    model_config = ConfigDict(from_attributes=True)


class AmendmentDiffEntry(_Out):
    field: str
    before: Any | None = None
    after: Any | None = None


class AmendmentOut(_Out):
    id: str
    opportunity_id: str
    previous_hash: str | None
    new_hash: str
    previous_response_deadline: str | None
    new_response_deadline: str | None
    previous_title: str | None
    new_title: str | None
    diff_summary: list[AmendmentDiffEntry]
    detected_at: str


class AmendmentListOut(_Out):
    opportunity_id: str
    amendments: list[AmendmentOut]


class AuditEventOut(_Out):
    id: str
    event_type: str
    entity_type: str
    entity_id: str
    actor_user_email: str | None = None
    actor_founder_slug: str | None = None
    actor_founder_name: str | None = None
    actor_label: str | None = None
    payload: dict[str, Any]
    created_at: str


class AuditTrailOut(_Out):
    pursuit_id: str
    events: list[AuditEventOut]


@router.get(
    "/opportunities/{opportunity_id}/amendments",
    response_model=AmendmentListOut,
)
async def list_amendments(
    opportunity_id: UUID,
    ctx: Annotated[RequestContext, Depends(get_request_context)],
) -> AmendmentListOut:
    # Confirm the opportunity exists. Tenants can read any opportunity's
    # amendments — they don't carry CUI by themselves; per-tenant
    # context is in the audit trail instead.
    opp = (
        await ctx.session.execute(
            select(OpportunityRaw.id).where(OpportunityRaw.id == opportunity_id)
        )
    ).scalar_one_or_none()
    if opp is None:
        raise HTTPException(status_code=404, detail="opportunity not found")

    rows = (
        await ctx.session.execute(
            select(OpportunityAmendment)
            .where(OpportunityAmendment.opportunity_id == opportunity_id)
            .order_by(OpportunityAmendment.detected_at.desc())
        )
    ).scalars().all()

    return AmendmentListOut(
        opportunity_id=str(opportunity_id),
        amendments=[
            AmendmentOut(
                id=str(a.id),
                opportunity_id=str(a.opportunity_id),
                previous_hash=a.previous_hash,
                new_hash=a.new_hash,
                previous_response_deadline=(
                    a.previous_response_deadline.isoformat()
                    if a.previous_response_deadline
                    else None
                ),
                new_response_deadline=(
                    a.new_response_deadline.isoformat()
                    if a.new_response_deadline
                    else None
                ),
                previous_title=a.previous_title,
                new_title=a.new_title,
                diff_summary=[
                    AmendmentDiffEntry(**entry) for entry in (a.diff_summary or [])
                ],
                detected_at=a.detected_at.isoformat(),
            )
            for a in rows
        ],
    )


@router.get(
    "/pursuits/{pursuit_id}/audit",
    response_model=AuditTrailOut,
)
async def list_pursuit_audit(
    pursuit_id: UUID,
    ctx: Annotated[RequestContext, Depends(get_request_context)],
    limit: int = 100,
) -> AuditTrailOut:
    pursuit = (
        await ctx.session.execute(
            select(Pursuit).where(
                Pursuit.id == pursuit_id, Pursuit.tenant_id == ctx.tenant.id
            )
        )
    ).scalar_one_or_none()
    if pursuit is None:
        raise HTTPException(status_code=404, detail="pursuit not found")

    # Pursuit-scoped events plus opportunity-scoped events that affect
    # this pursuit's parent opportunity. Tenant filter still applies
    # because amendment events are written per-tenant.
    events = (
        await ctx.session.execute(
            select(AuditEvent)
            .where(
                AuditEvent.tenant_id == ctx.tenant.id,
                or_(
                    (AuditEvent.entity_type == "pursuit")
                    & (AuditEvent.entity_id == pursuit_id),
                    (AuditEvent.entity_type == "opportunity")
                    & (AuditEvent.entity_id == pursuit.opportunity_id),
                ),
            )
            .order_by(AuditEvent.created_at.desc())
            .limit(min(max(limit, 1), 500))
        )
    ).scalars().all()

    # Resolve actor labels in a single batch each.
    user_ids = {e.actor_user_id for e in events if e.actor_user_id is not None}
    founder_ids = {
        e.actor_founder_id for e in events if e.actor_founder_id is not None
    }
    user_map: dict[UUID, str] = {}
    founder_map: dict[UUID, tuple[str, str]] = {}
    if user_ids:
        user_rows = (
            await ctx.session.execute(
                select(User.id, User.email).where(User.id.in_(user_ids))
            )
        ).all()
        user_map = {row[0]: row[1] for row in user_rows}
    if founder_ids:
        founder_rows = (
            await ctx.session.execute(
                select(Founder.id, Founder.slug, Founder.full_name).where(
                    Founder.id.in_(founder_ids)
                )
            )
        ).all()
        founder_map = {row[0]: (row[1], row[2]) for row in founder_rows}

    return AuditTrailOut(
        pursuit_id=str(pursuit_id),
        events=[
            AuditEventOut(
                id=str(e.id),
                event_type=e.event_type,
                entity_type=e.entity_type,
                entity_id=str(e.entity_id),
                actor_user_email=user_map.get(e.actor_user_id) if e.actor_user_id else None,
                actor_founder_slug=(
                    founder_map.get(e.actor_founder_id, (None, None))[0]
                    if e.actor_founder_id
                    else None
                ),
                actor_founder_name=(
                    founder_map.get(e.actor_founder_id, (None, None))[1]
                    if e.actor_founder_id
                    else None
                ),
                actor_label=e.actor_label,
                payload=e.payload or {},
                created_at=e.created_at.isoformat(),
            )
            for e in events
        ],
    )
