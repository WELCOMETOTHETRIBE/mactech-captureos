"""Bid invites — read/triage API over bid_invites.

Rows are created by POST /webhooks/postmark/inbound (Gmail filter →
Postmark inbound stream → webhook), parsed at ingest by
mactech_intelligence.bid_invite_parser. This router is the app-facing
side:

  GET   /bid-invites?status=new&limit=200   (list, bodies omitted)
  GET   /bid-invites/{id}                   (full record incl. bodies)
  PATCH /bid-invites/{id}    { "status": "reviewed"|"archived"|"new" }
  POST  /bid-invites/reparse                (re-run parser on all rows)
"""

from __future__ import annotations

import logging
from datetime import UTC, datetime
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, ConfigDict
from sqlalchemy import func, select

from mactech_api.auth import RequestContext, get_request_context
from mactech_db.models import BID_INVITE_STATUSES, BidInvite
from mactech_intelligence.bid_invite_parser import parse_bid_invite

log = logging.getLogger(__name__)
router = APIRouter(tags=["bid-invites"])


class _Out(BaseModel):
    model_config = ConfigDict(from_attributes=True)


class BidInviteListItem(_Out):
    id: str
    from_email: str | None
    from_name: str | None
    subject: str
    attachments: list | None
    status: str
    sent_at: str | None
    received_at: str
    kind: str | None
    project_name: str | None
    bid_package: str | None
    gc_company: str | None
    lead_name: str | None
    lead_email: str | None
    lead_phone: str | None
    location: str | None
    bid_due_on: str | None
    rfp_id: str | None
    rfp_url: str | None
    headline: str | None


class BidInviteDetail(BidInviteListItem):
    text_body: str | None
    html_body: str | None


class BidInvitesResponse(_Out):
    total: int
    counts: dict[str, int]
    items: list[BidInviteListItem]


def _to_item(inv: BidInvite, cls: type[BidInviteListItem] = BidInviteListItem) -> BidInviteListItem:
    common = dict(
        id=str(inv.id),
        from_email=inv.from_email,
        from_name=inv.from_name,
        subject=inv.subject,
        attachments=inv.attachments,
        status=inv.status,
        sent_at=inv.sent_at.isoformat() if inv.sent_at else None,
        received_at=inv.received_at.isoformat(),
        kind=inv.kind,
        project_name=inv.project_name,
        bid_package=inv.bid_package,
        gc_company=inv.gc_company,
        lead_name=inv.lead_name,
        lead_email=inv.lead_email,
        lead_phone=inv.lead_phone,
        location=inv.location,
        bid_due_on=inv.bid_due_on.isoformat() if inv.bid_due_on else None,
        rfp_id=inv.rfp_id,
        rfp_url=inv.rfp_url,
        headline=inv.headline,
    )
    if cls is BidInviteDetail:
        return BidInviteDetail(
            **common, text_body=inv.text_body, html_body=inv.html_body
        )
    return cls(**common)


@router.get("/bid-invites", response_model=BidInvitesResponse)
async def list_bid_invites(
    ctx: Annotated[RequestContext, Depends(get_request_context)],
    status_filter: Annotated[
        str | None, Query(alias="status", pattern="^(new|reviewed|archived)$")
    ] = None,
    limit: Annotated[int, Query(ge=1, le=500)] = 200,
) -> BidInvitesResponse:
    """List invites, newest first, with per-status counts for the tabs.

    Bodies are omitted (they can be hundreds of KB of BuildingConnected
    HTML each); GET /bid-invites/{id} returns them.
    """
    base = select(BidInvite).where(BidInvite.tenant_id == ctx.tenant.id)
    if status_filter:
        base = base.where(BidInvite.status == status_filter)

    counts_rows = (
        await ctx.session.execute(
            select(BidInvite.status, func.count())
            .where(BidInvite.tenant_id == ctx.tenant.id)
            .group_by(BidInvite.status)
        )
    ).all()
    counts = {s: 0 for s in BID_INVITE_STATUSES}
    counts.update({row[0]: row[1] for row in counts_rows})

    rows = (
        (
            await ctx.session.execute(
                base.order_by(BidInvite.received_at.desc()).limit(limit)
            )
        )
        .scalars()
        .all()
    )
    return BidInvitesResponse(
        total=sum(counts.values()),
        counts=counts,
        items=[_to_item(r) for r in rows],
    )


@router.get("/bid-invites/{invite_id}", response_model=BidInviteDetail)
async def get_bid_invite(
    invite_id: UUID,
    ctx: Annotated[RequestContext, Depends(get_request_context)],
) -> BidInviteDetail:
    inv = await _get_owned(invite_id, ctx)
    return _to_item(inv, BidInviteDetail)


class BidInviteStatusUpdate(BaseModel):
    status: str


@router.patch("/bid-invites/{invite_id}", response_model=BidInviteListItem)
async def update_bid_invite_status(
    invite_id: UUID,
    body: BidInviteStatusUpdate,
    ctx: Annotated[RequestContext, Depends(get_request_context)],
) -> BidInviteListItem:
    if body.status not in BID_INVITE_STATUSES:
        raise HTTPException(
            status_code=422,
            detail=f"status must be one of {BID_INVITE_STATUSES}",
        )
    inv = await _get_owned(invite_id, ctx)
    inv.status = body.status
    return _to_item(inv)


class ReparseResult(_Out):
    reparsed: int


@router.post("/bid-invites/reparse", response_model=ReparseResult)
async def reparse_bid_invites(
    ctx: Annotated[RequestContext, Depends(get_request_context)],
) -> ReparseResult:
    """Re-run the parser over every stored invite.

    Idempotent; used to backfill rows ingested before parsing existed
    and after parser improvements.
    """
    rows = (
        (
            await ctx.session.execute(
                select(BidInvite).where(BidInvite.tenant_id == ctx.tenant.id)
            )
        )
        .scalars()
        .all()
    )
    now = datetime.now(UTC)
    for inv in rows:
        parsed = parse_bid_invite(inv.subject, inv.text_body)
        inv.kind = parsed.kind
        inv.project_name = parsed.project_name
        inv.bid_package = parsed.bid_package
        inv.gc_company = parsed.gc_company
        inv.lead_name = parsed.lead_name
        inv.lead_email = parsed.lead_email
        inv.lead_phone = parsed.lead_phone
        inv.location = parsed.location
        inv.bid_due_on = parsed.bid_due_on
        inv.rfp_id = parsed.rfp_id
        inv.rfp_url = parsed.rfp_url
        inv.headline = parsed.headline
        inv.parsed_at = now
    log.info("reparsed %d bid invites for tenant=%s", len(rows), ctx.tenant.slug)
    return ReparseResult(reparsed=len(rows))


async def _get_owned(invite_id: UUID, ctx: RequestContext) -> BidInvite:
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
    return inv
