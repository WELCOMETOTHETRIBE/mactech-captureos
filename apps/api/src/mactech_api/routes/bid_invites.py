"""Bid invites — read/triage API over bid_invites.

Rows are created by POST /webhooks/postmark/inbound (Gmail filter →
Postmark inbound stream → webhook). This router is the app-facing side:

  GET   /bid-invites?status=new&limit=50
  PATCH /bid-invites/{id}   { "status": "reviewed" | "archived" | "new" }
"""

from __future__ import annotations

import logging
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, ConfigDict
from sqlalchemy import func, select

from mactech_api.auth import RequestContext, get_request_context
from mactech_db.models import BID_INVITE_STATUSES, BidInvite

log = logging.getLogger(__name__)
router = APIRouter(tags=["bid-invites"])


class _Out(BaseModel):
    model_config = ConfigDict(from_attributes=True)


class BidInviteOut(_Out):
    id: str
    from_email: str | None
    from_name: str | None
    subject: str
    text_body: str | None
    html_body: str | None
    attachments: list | None
    status: str
    sent_at: str | None
    received_at: str


class BidInvitesResponse(_Out):
    total: int
    items: list[BidInviteOut]


def _to_out(inv: BidInvite) -> BidInviteOut:
    return BidInviteOut(
        id=str(inv.id),
        from_email=inv.from_email,
        from_name=inv.from_name,
        subject=inv.subject,
        text_body=inv.text_body,
        html_body=inv.html_body,
        attachments=inv.attachments,
        status=inv.status,
        sent_at=inv.sent_at.isoformat() if inv.sent_at else None,
        received_at=inv.received_at.isoformat(),
    )


@router.get("/bid-invites", response_model=BidInvitesResponse)
async def list_bid_invites(
    ctx: Annotated[RequestContext, Depends(get_request_context)],
    status_filter: Annotated[
        str | None, Query(alias="status", pattern="^(new|reviewed|archived)$")
    ] = None,
    limit: Annotated[int, Query(ge=1, le=200)] = 50,
) -> BidInvitesResponse:
    base = select(BidInvite).where(BidInvite.tenant_id == ctx.tenant.id)
    if status_filter:
        base = base.where(BidInvite.status == status_filter)

    total = (
        await ctx.session.execute(
            select(func.count()).select_from(base.subquery())
        )
    ).scalar_one()
    rows = (
        (
            await ctx.session.execute(
                base.order_by(BidInvite.received_at.desc()).limit(limit)
            )
        )
        .scalars()
        .all()
    )
    return BidInvitesResponse(total=total, items=[_to_out(r) for r in rows])


class BidInviteStatusUpdate(BaseModel):
    status: str


@router.patch("/bid-invites/{invite_id}", response_model=BidInviteOut)
async def update_bid_invite_status(
    invite_id: UUID,
    body: BidInviteStatusUpdate,
    ctx: Annotated[RequestContext, Depends(get_request_context)],
) -> BidInviteOut:
    if body.status not in BID_INVITE_STATUSES:
        raise HTTPException(
            status_code=422,
            detail=f"status must be one of {BID_INVITE_STATUSES}",
        )
    inv = (
        await ctx.session.execute(
            select(BidInvite).where(
                BidInvite.id == invite_id,
                BidInvite.tenant_id == ctx.tenant.id,
            )
        )
    ).scalar_one_or_none()
    if inv is None:
        raise HTTPException(status_code=404, detail="bid invite not found")
    inv.status = body.status
    return _to_out(inv)
