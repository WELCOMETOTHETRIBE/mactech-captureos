"""Authenticated /me endpoints — what the logged-in founder sees.

Two endpoints:

  GET /me           the founder profile + tenant header
  GET /me/dashboard the "This Week" dashboard payload per
                    docs/MACTECH_PLAYBOOK.md §5
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Annotated, Any

from fastapi import APIRouter, Depends
from pydantic import BaseModel, ConfigDict
from sqlalchemy import func, select

from mactech_api.auth import RequestContext, get_request_context
from mactech_db.models import (
    Founder,
    OpportunityEnriched,
    OpportunityRaw,
    OpportunityScore,
    ProposalDraft,
    Pursuit,
)

router = APIRouter(tags=["me"])


class _Out(BaseModel):
    model_config = ConfigDict(from_attributes=True)


class FounderHeader(_Out):
    slug: str
    full_name: str
    title: str
    pillar: str
    email: str | None


class TenantHeader(_Out):
    slug: str
    name: str
    plan: str
    uei: str | None = None
    cage_code: str | None = None
    set_aside_certifications: list[str] = []
    onboarding_completed_at: str | None = None


class MeResponse(_Out):
    user_id: str
    user_email: str
    founder: FounderHeader | None
    tenant: TenantHeader


class TopOpportunity(_Out):
    id: str
    title: str
    notice_type: str | None
    set_aside: str | None
    naics_code: str | None
    agency_short: str | None
    posted_at: str | None
    response_deadline: str | None
    score: int
    why_it_matters: str | None
    incumbent_name: str | None
    incumbent_amount: float | None
    sam_link: str | None
    detail_url: str


class FounderCard(_Out):
    slug: str
    full_name: str
    pillar: str
    high_score_count: int  # opps scoring >= 60 assigned to this founder


class DashboardKpis(_Out):
    # Tenant-wide vital signs.
    opportunities_total: int
    opportunities_last_24h: int
    scored_above_60: int
    enriched_with_incumbent: int
    # Action-oriented KPIs (founder-scoped where applicable).
    your_high_fit_open: int  # opps assigned to me, score >=60, NOT in pipeline yet
    your_deadlines_lt_7d: int  # opps assigned to me with deadline in <=7 days
    your_active_pursuits: int  # pursuits I own, not in won/lost
    drafts_awaiting_review: int  # tenant-wide drafts in 'draft' status


class DashboardResponse(_Out):
    rendered_at: str
    you: FounderHeader | None
    your_top: list[TopOpportunity]
    pillar_cards: list[FounderCard]
    kpis: DashboardKpis


def _short_agency(p: str | None) -> str | None:
    if not p:
        return None
    return p.split(".")[0].strip()


@router.get("/me", response_model=MeResponse)
async def me(
    ctx: Annotated[RequestContext, Depends(get_request_context)],
) -> MeResponse:
    return MeResponse(
        user_id=str(ctx.user.id),
        user_email=ctx.user.email,
        founder=(
            FounderHeader(
                slug=ctx.founder.slug,
                full_name=ctx.founder.full_name,
                title=ctx.founder.title,
                pillar=ctx.founder.pillar,
                email=ctx.founder.email,
            )
            if ctx.founder
            else None
        ),
        tenant=TenantHeader(
            slug=ctx.tenant.slug,
            name=ctx.tenant.name,
            plan=ctx.tenant.plan,
            uei=ctx.tenant.uei,
            cage_code=ctx.tenant.cage_code,
            set_aside_certifications=list(
                ctx.tenant.set_aside_certifications or []
            ),
            onboarding_completed_at=(
                ctx.tenant.onboarding_completed_at.isoformat()
                if ctx.tenant.onboarding_completed_at
                else None
            ),
        ),
    )


@router.get("/me/dashboard", response_model=DashboardResponse)
async def dashboard(
    ctx: Annotated[RequestContext, Depends(get_request_context)],
) -> DashboardResponse:
    session = ctx.session
    tenant_id = ctx.tenant.id

    # Your top — top 5 scored opps assigned to this founder, score >= 60.
    your_top: list[TopOpportunity] = []
    if ctx.founder is not None:
        rows = (
            await session.execute(
                select(OpportunityScore, OpportunityRaw, OpportunityEnriched)
                .join(
                    OpportunityRaw, OpportunityRaw.id == OpportunityScore.opportunity_id
                )
                .outerjoin(
                    OpportunityEnriched,
                    OpportunityEnriched.opportunity_id == OpportunityRaw.id,
                )
                .where(
                    OpportunityScore.tenant_id == tenant_id,
                    OpportunityScore.assigned_founder_id == ctx.founder.id,
                    OpportunityScore.score >= 60,
                )
                .order_by(OpportunityScore.score.desc())
                .limit(5)
            )
        ).all()
        for sc, opp, enr in rows:
            payload: dict[str, Any] = opp.raw_payload or {}
            your_top.append(
                TopOpportunity(
                    id=str(opp.id),
                    title=opp.title,
                    notice_type=opp.notice_type,
                    set_aside=opp.set_aside,
                    naics_code=opp.naics_code,
                    agency_short=_short_agency(opp.agency),
                    posted_at=opp.posted_at.isoformat() if opp.posted_at else None,
                    response_deadline=(
                        opp.response_deadline.isoformat()
                        if opp.response_deadline
                        else None
                    ),
                    score=sc.score,
                    why_it_matters=sc.why_it_matters,
                    incumbent_name=enr.incumbent_name if enr else None,
                    incumbent_amount=(
                        float(enr.incumbent_award_amount)
                        if enr and enr.incumbent_award_amount is not None
                        else None
                    ),
                    sam_link=payload.get("uiLink"),
                    detail_url=f"/opportunities/{opp.id}",
                )
            )

    # Pillar cards — one per founder with their high-score count.
    founders = (
        await session.execute(
            select(Founder)
            .where(Founder.tenant_id == tenant_id)
            .order_by(Founder.full_name)
        )
    ).scalars().all()
    pillar_cards: list[FounderCard] = []
    for f in founders:
        n = (
            await session.execute(
                select(func.count())
                .select_from(OpportunityScore)
                .where(
                    OpportunityScore.tenant_id == tenant_id,
                    OpportunityScore.assigned_founder_id == f.id,
                    OpportunityScore.score >= 60,
                )
            )
        ).scalar_one()
        pillar_cards.append(
            FounderCard(
                slug=f.slug,
                full_name=f.full_name,
                pillar=f.pillar,
                high_score_count=int(n or 0),
            )
        )

    # Tenant-wide KPIs.
    twenty_four_hours_ago = datetime.now(UTC) - timedelta(hours=24)
    opps_total = (
        await session.execute(select(func.count()).select_from(OpportunityRaw))
    ).scalar_one()
    opps_24h = (
        await session.execute(
            select(func.count())
            .select_from(OpportunityRaw)
            .where(OpportunityRaw.posted_at >= twenty_four_hours_ago)
        )
    ).scalar_one()
    scored_60 = (
        await session.execute(
            select(func.count())
            .select_from(OpportunityScore)
            .where(
                OpportunityScore.tenant_id == tenant_id,
                OpportunityScore.score >= 60,
            )
        )
    ).scalar_one()
    enriched_incumbent = (
        await session.execute(
            select(func.count())
            .select_from(OpportunityEnriched)
            .where(OpportunityEnriched.incumbent_uei.is_not(None))
        )
    ).scalar_one()

    # Action-oriented KPIs.
    seven_days_from_now = datetime.now(UTC) + timedelta(days=7)
    your_high_fit_open = 0
    your_deadlines_lt_7d = 0
    your_active_pursuits = 0
    if ctx.founder is not None:
        your_high_fit_open = int(
            (
                await session.execute(
                    select(func.count())
                    .select_from(OpportunityScore)
                    .where(
                        OpportunityScore.tenant_id == tenant_id,
                        OpportunityScore.assigned_founder_id == ctx.founder.id,
                        OpportunityScore.score >= 60,
                        ~OpportunityScore.opportunity_id.in_(
                            select(Pursuit.opportunity_id).where(
                                Pursuit.tenant_id == tenant_id
                            )
                        ),
                    )
                )
            ).scalar_one()
            or 0
        )
        your_deadlines_lt_7d = int(
            (
                await session.execute(
                    select(func.count())
                    .select_from(OpportunityScore)
                    .join(
                        OpportunityRaw,
                        OpportunityRaw.id == OpportunityScore.opportunity_id,
                    )
                    .where(
                        OpportunityScore.tenant_id == tenant_id,
                        OpportunityScore.assigned_founder_id == ctx.founder.id,
                        OpportunityRaw.response_deadline.is_not(None),
                        OpportunityRaw.response_deadline <= seven_days_from_now,
                        OpportunityRaw.response_deadline >= datetime.now(UTC),
                    )
                )
            ).scalar_one()
            or 0
        )
        your_active_pursuits = int(
            (
                await session.execute(
                    select(func.count())
                    .select_from(Pursuit)
                    .where(
                        Pursuit.tenant_id == tenant_id,
                        Pursuit.owner_founder_id == ctx.founder.id,
                        Pursuit.stage.notin_(("won", "lost")),
                    )
                )
            ).scalar_one()
            or 0
        )

    drafts_awaiting_review = int(
        (
            await session.execute(
                select(func.count())
                .select_from(ProposalDraft)
                .where(
                    ProposalDraft.tenant_id == tenant_id,
                    ProposalDraft.status.in_(("draft", "reviewed")),
                )
            )
        ).scalar_one()
        or 0
    )

    return DashboardResponse(
        rendered_at=datetime.now(UTC).isoformat(),
        you=(
            FounderHeader(
                slug=ctx.founder.slug,
                full_name=ctx.founder.full_name,
                title=ctx.founder.title,
                pillar=ctx.founder.pillar,
                email=ctx.founder.email,
            )
            if ctx.founder
            else None
        ),
        your_top=your_top,
        pillar_cards=pillar_cards,
        kpis=DashboardKpis(
            opportunities_total=int(opps_total or 0),
            opportunities_last_24h=int(opps_24h or 0),
            scored_above_60=int(scored_60 or 0),
            enriched_with_incumbent=int(enriched_incumbent or 0),
            your_high_fit_open=your_high_fit_open,
            your_deadlines_lt_7d=your_deadlines_lt_7d,
            your_active_pursuits=your_active_pursuits,
            drafts_awaiting_review=drafts_awaiting_review,
        ),
    )
