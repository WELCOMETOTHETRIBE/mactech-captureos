"""Bid invites — read/triage API over bid_invites.

Rows are created by POST /webhooks/postmark/inbound (Gmail filter →
Postmark inbound stream → webhook), parsed at ingest by
mactech_intelligence.bid_invite_parser. This router is the app-facing
side:

  GET   /bid-invites?status=new&limit=200   (list, bodies omitted)
  GET   /bid-invites/{id}                   (full record incl. bodies)
  PATCH /bid-invites/{id}    { "status": "reviewed"|"archived"|"new" }
  POST  /bid-invites/{id}/pursue            (promote project → pipeline)
  POST  /bid-invites/reparse                (re-run parser on all rows)
"""

from __future__ import annotations

import logging
from datetime import UTC, datetime, time as dt_time
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, ConfigDict
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError

from mactech_api.auth import RequestContext, get_request_context
from mactech_db.audit import record_event
from mactech_db.models import (
    BID_INVITE_STATUSES,
    EVENT_PURSUIT_CREATED,
    BidInvite,
    Founder,
    OpportunityRaw,
    Pursuit,
)
from mactech_intelligence.bid_invite_parser import parse_bid_invite
from mactech_intelligence.bid_invite_routing import (
    project_group_key,
    suggest_founder,
)

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
    # coalesce(sent_at, received_at) — the true arrival time and the key
    # every surface sorts and displays on. received_at is ingest time,
    # which the mbox backfill collapsed onto a single import timestamp.
    arrived_at: str
    # Arrived since this founder last acknowledged the inbox, and still
    # untriaged. Transient signal; `status` is the durable state.
    unseen: bool
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
    opportunity_id: str | None
    suggested_founder_slug: str | None
    suggested_founder_name: str | None
    suggestion_reason: str | None


class BidInviteDetail(BidInviteListItem):
    text_body: str | None
    html_body: str | None


class BidInvitesResponse(_Out):
    total: int
    # Per-status counts plus "unseen" — arrived since you last looked.
    counts: dict[str, int]
    items: list[BidInviteListItem]


def is_unseen(inv: BidInvite, seen_at: datetime | None) -> bool:
    """Whether `inv` arrived since the founder last acknowledged the inbox.

    Untriaged is a precondition: once you review or archive something it
    stops being a new arrival regardless of the watermark.

    `seen_at` is None either for a tenant member with no founder profile
    or for the (server_default=now(), so effectively unreachable) case of
    a founder who never acknowledged. Both resolve to "not unseen" — the
    conservative direction. Claiming the opposite would light up the
    whole untriaged backlog, which is the exact noise this replaces, and
    it keeps this in lockstep with `unseen_count`.
    """
    if inv.status != "new" or seen_at is None:
        return False
    return inv.arrived_at > seen_at


def _to_item(
    inv: BidInvite,
    cls: type[BidInviteListItem] = BidInviteListItem,
    founder_names: dict[str, str] | None = None,
    seen_at: datetime | None = None,
) -> BidInviteListItem:
    suggestion = suggest_founder(inv.bid_package, inv.project_name, inv.subject)
    suggested_slug, reason = suggestion if suggestion else (None, None)
    common = dict(
        id=str(inv.id),
        from_email=inv.from_email,
        from_name=inv.from_name,
        subject=inv.subject,
        attachments=inv.attachments,
        status=inv.status,
        sent_at=inv.sent_at.isoformat() if inv.sent_at else None,
        received_at=inv.received_at.isoformat(),
        arrived_at=inv.arrived_at.isoformat(),
        unseen=is_unseen(inv, seen_at),
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
        opportunity_id=str(inv.opportunity_id) if inv.opportunity_id else None,
        suggested_founder_slug=suggested_slug,
        suggested_founder_name=(founder_names or {}).get(suggested_slug or ""),
        suggestion_reason=reason,
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
    """List invites by true arrival time (newest first), with tab counts.

    Ordered on coalesce(sent_at, received_at), not received_at: the
    latter is ingest time, so the mbox backfill stamped every historical
    message with its import timestamp and sorting on it interleaves
    weeks-old mail with this morning's.

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

    seen_at = ctx.founder.bid_invites_seen_at if ctx.founder else None
    # Counted over the whole table, not just the returned page, so the
    # badge stays true when `limit` truncates.
    counts["unseen"] = await unseen_count(ctx)

    rows = (
        (
            await ctx.session.execute(
                base.order_by(BidInvite.arrived_at.desc()).limit(limit)
            )
        )
        .scalars()
        .all()
    )
    founder_names = await _founder_names(ctx)
    return BidInvitesResponse(
        # Statuses only — "unseen" overlaps 'new' and would double-count.
        total=sum(counts[s] for s in BID_INVITE_STATUSES),
        counts=counts,
        items=[
            _to_item(r, founder_names=founder_names, seen_at=seen_at) for r in rows
        ],
    )


async def unseen_count(ctx: RequestContext) -> int:
    """How many untriaged invites arrived since this founder last looked.

    Drives the sidebar badge (via /me) and the page's unseen band. A
    tenant member not linked to a founder profile has no watermark, so
    they get 0 rather than the entire untriaged backlog.
    """
    seen_at = ctx.founder.bid_invites_seen_at if ctx.founder else None
    if seen_at is None:  # see is_unseen() for why this is 0, not "all"
        return 0
    stmt = (
        select(func.count())
        .select_from(BidInvite)
        .where(
            BidInvite.tenant_id == ctx.tenant.id,
            BidInvite.status == "new",
            BidInvite.arrived_at > seen_at,
        )
    )
    return int((await ctx.session.execute(stmt)).scalar_one() or 0)


async def _founder_names(ctx: RequestContext) -> dict[str, str]:
    rows = (
        await ctx.session.execute(
            select(Founder.slug, Founder.full_name).where(
                Founder.tenant_id == ctx.tenant.id
            )
        )
    ).all()
    return {slug: name for slug, name in rows}


@router.get("/bid-invites/{invite_id}", response_model=BidInviteDetail)
async def get_bid_invite(
    invite_id: UUID,
    ctx: Annotated[RequestContext, Depends(get_request_context)],
) -> BidInviteDetail:
    inv = await _get_owned(invite_id, ctx)
    return _to_item(
        inv,
        BidInviteDetail,
        founder_names=await _founder_names(ctx),
        seen_at=ctx.founder.bid_invites_seen_at if ctx.founder else None,
    )


class SeenResult(_Out):
    seen_at: str
    cleared: int


@router.post("/bid-invites/seen", response_model=SeenResult)
async def mark_bid_invites_seen(
    ctx: Annotated[RequestContext, Depends(get_request_context)],
) -> SeenResult:
    """Acknowledge the inbox: everything that has arrived is no longer new.

    Deliberately an explicit POST rather than a side effect of rendering
    the page — Next.js prefetches nav links, so advancing the watermark
    during a GET would silently clear the badge for mail the founder
    never actually saw.

    This does not triage anything; `status` is untouched, so the New tab
    keeps its backlog. It only resets the "since you last looked" line.
    """
    if ctx.founder is None:
        raise HTTPException(
            status_code=400,
            detail="only founders have a bid invite inbox watermark",
        )
    cleared = await unseen_count(ctx)
    now = datetime.now(UTC)
    ctx.founder.bid_invites_seen_at = now
    log.info(
        "bid invites acknowledged by founder=%s, %d cleared",
        ctx.founder.slug,
        cleared,
    )
    return SeenResult(seen_at=now.isoformat(), cleared=cleared)


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
    return _to_item(
        inv, seen_at=ctx.founder.bid_invites_seen_at if ctx.founder else None
    )


class PursueRequest(BaseModel):
    model_config = ConfigDict(extra="ignore")

    owner_founder_slug: str | None = None
    stage: str = "qualify"


class PursueResult(_Out):
    opportunity_id: str
    pursuit_id: str
    created: bool
    owner_founder_slug: str | None


@router.post("/bid-invites/{invite_id}/pursue", response_model=PursueResult)
async def pursue_bid_invite(
    invite_id: UUID,
    body: PursueRequest,
    ctx: Annotated[RequestContext, Depends(get_request_context)],
) -> PursueResult:
    """Promote a bid invite's project into the capture pipeline.

    Creates (or reuses) a buildingconnected-sourced opportunities_raw
    row keyed by the project group, hangs a Pursuit off it, links every
    email in the group to the opportunity, and flips new emails to
    reviewed — adding to the pipeline IS the triage. Idempotent: a
    second call returns the existing pursuit.
    """
    if body.stage not in ("lead", "qualify", "pursue"):
        raise HTTPException(
            status_code=422, detail="stage must be lead, qualify, or pursue"
        )
    inv = await _get_owned(invite_id, ctx)
    session = ctx.session
    group_key = inv.group_key or project_group_key(inv.project_name, inv.subject)

    siblings = (
        (
            await session.execute(
                select(BidInvite).where(
                    BidInvite.tenant_id == ctx.tenant.id,
                    BidInvite.group_key == group_key,
                )
            )
        )
        .scalars()
        .all()
    ) or [inv]

    title = inv.project_name or inv.subject
    if inv.bid_package:
        title = f"{title}: {inv.bid_package}"
    deadline = (
        datetime.combine(inv.bid_due_on, dt_time(17, 0), tzinfo=UTC)
        if inv.bid_due_on
        else None
    )

    opp = (
        await session.execute(
            select(OpportunityRaw).where(
                OpportunityRaw.source == "buildingconnected",
                OpportunityRaw.source_id == group_key,
            )
        )
    ).scalar_one_or_none()
    if opp is None:
        opp = OpportunityRaw(
            source="buildingconnected",
            source_id=group_key,
            notice_type="Bid Invite",
            title=title[:512],
            description_url=inv.rfp_url,
            description_text=inv.text_body,
            agency=inv.gc_company,
            response_deadline=deadline,
            posted_at=inv.sent_at or inv.received_at,
            place_of_performance=(
                {"raw": inv.location} if inv.location else None
            ),
            raw_payload={
                "origin": "bid_invite",
                "bid_invite_id": str(inv.id),
                "group_key": group_key,
                "gc_company": inv.gc_company,
                "lead_name": inv.lead_name,
                "lead_email": inv.lead_email,
                "lead_phone": inv.lead_phone,
                "rfp_id": inv.rfp_id,
            },
        )
        session.add(opp)
        await session.flush()

    pursuit = (
        await session.execute(
            select(Pursuit).where(
                Pursuit.tenant_id == ctx.tenant.id,
                Pursuit.opportunity_id == opp.id,
            )
        )
    ).scalar_one_or_none()
    created = pursuit is None
    owner_slug = body.owner_founder_slug
    if created:
        if owner_slug is None:
            suggestion = suggest_founder(
                inv.bid_package, inv.project_name, inv.subject
            )
            owner_slug = suggestion[0] if suggestion else None
        owner_id = None
        if owner_slug:
            owner_id = (
                await session.execute(
                    select(Founder.id).where(
                        Founder.tenant_id == ctx.tenant.id,
                        Founder.slug == owner_slug,
                    )
                )
            ).scalar_one_or_none()
            if owner_id is None:
                raise HTTPException(
                    status_code=422,
                    detail=f"unknown founder slug: {owner_slug}",
                )
        pursuit = Pursuit(
            tenant_id=ctx.tenant.id,
            opportunity_id=opp.id,
            owner_founder_id=owner_id,
            stage=body.stage,
            notes=(
                f"From BuildingConnected bid invite — {inv.gc_company or 'GC'}"
                f"{f', lead {inv.lead_name}' if inv.lead_name else ''}"
                f"{f' ({inv.lead_email})' if inv.lead_email else ''}."
            ),
        )
        session.add(pursuit)
        try:
            await session.flush()
        except IntegrityError:
            raise HTTPException(
                status_code=409, detail="pursuit already exists"
            ) from None
        await record_event(
            session,
            tenant_id=ctx.tenant.id,
            event_type=EVENT_PURSUIT_CREATED,
            entity_type="pursuit",
            entity_id=pursuit.id,
            payload={
                "opportunity_id": str(opp.id),
                "stage": body.stage,
                "owner_founder_slug": owner_slug,
                "origin": "bid_invite",
                "bid_invite_id": str(inv.id),
            },
            actor_user_id=ctx.user.id if ctx.user else None,
            actor_founder_id=ctx.founder.id if ctx.founder else None,
        )

    for sib in siblings:
        sib.opportunity_id = opp.id
        if sib.group_key is None:
            sib.group_key = group_key
        if sib.status == "new":
            sib.status = "reviewed"

    log.info(
        "bid invite %s pursued: opportunity=%s pursuit=%s created=%s",
        inv.id,
        opp.id,
        pursuit.id,
        created,
    )
    return PursueResult(
        opportunity_id=str(opp.id),
        pursuit_id=str(pursuit.id),
        created=created,
        owner_founder_slug=owner_slug,
    )


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
        inv.group_key = project_group_key(parsed.project_name, inv.subject)
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
