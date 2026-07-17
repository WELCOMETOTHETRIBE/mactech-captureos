"""Capture queues — the This-Week operational view (Slice 6).

Replaces "top-scored notices" with four operational queues driven by the
decision engine: Pursue as Prime, Team as Sub, Shape Early, and Needs Review.
"""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends
from mactech_db.models import OpportunityDecisionVector, OpportunityRaw, PursuitRecommendation
from pydantic import BaseModel
from sqlalchemy import select

from mactech_api.auth import RequestContext, get_request_context

router = APIRouter(tags=["capture"])


class _Out(BaseModel):
    model_config = {"from_attributes": True}


class QueueItem(_Out):
    opportunity_id: str
    title: str
    agency: str | None
    naics_code: str | None
    set_aside: str | None
    pursuit_lane: str
    overall_priority: int
    confidence: str
    relevance: int
    prime_fit: int
    subcontract_fit: int
    response_deadline: str | None
    reason_codes: list[str]
    needs_human_review: bool
    next_action: str | None
    prime_target_names: list[str]


class CaptureQueues(_Out):
    pursue_as_prime: list[QueueItem]
    team_as_sub: list[QueueItem]
    shape_early: list[QueueItem]
    needs_review: list[QueueItem]
    counts: dict[str, int]


_PRIME = ("PRIME_NOW", "PRIME_WITH_PARTNER")
_SUB = ("SUB_TO_IDENTIFIED_PRIME", "SUB_TO_PRIME_NOT_YET_IDENTIFIED")


@router.get("/capture/queues", response_model=CaptureQueues)
async def capture_queues(
    ctx: Annotated[RequestContext, Depends(get_request_context)],
    limit: int = 25,
) -> CaptureQueues:
    session = ctx.session
    tenant_id = ctx.tenant.id

    rows = (
        await session.execute(
            select(OpportunityDecisionVector, OpportunityRaw, PursuitRecommendation)
            .join(OpportunityRaw, OpportunityRaw.id == OpportunityDecisionVector.opportunity_id)
            .outerjoin(
                PursuitRecommendation,
                (PursuitRecommendation.opportunity_id == OpportunityDecisionVector.opportunity_id)
                & (PursuitRecommendation.tenant_id == tenant_id),
            )
            .where(OpportunityDecisionVector.tenant_id == tenant_id)
            .order_by(OpportunityDecisionVector.overall_priority_score.desc())
        )
    ).all()

    prime: list[QueueItem] = []
    sub: list[QueueItem] = []
    shape: list[QueueItem] = []
    review: list[QueueItem] = []

    def _first_action(rec: PursuitRecommendation | None) -> str | None:
        return rec.executive_decision if rec is not None else None

    for dv, opp, rec in rows:
        item = QueueItem(
            opportunity_id=str(opp.id),
            title=opp.title,
            agency=opp.agency,
            naics_code=opp.naics_code,
            set_aside=opp.set_aside,
            pursuit_lane=dv.pursuit_lane,
            overall_priority=dv.overall_priority_score,
            confidence=dv.confidence,
            relevance=dv.relevance_score,
            prime_fit=dv.prime_fit_score,
            subcontract_fit=dv.subcontract_fit_score,
            response_deadline=opp.response_deadline.isoformat() if opp.response_deadline else None,
            reason_codes=list(dv.reason_codes or []),
            needs_human_review=dv.needs_human_review,
            next_action=_first_action(rec),
            prime_target_names=list(rec.prime_target_names or []) if rec else [],
        )
        # Needs Review is scoped to ACTIONABLE opps that need a human look
        # (low confidence / incomplete package / conflicting evidence) — not the
        # whole NO_BID tail, which is universally metadata-only.
        actionable = (
            dv.pursuit_lane in _PRIME or dv.pursuit_lane in _SUB or dv.pursuit_lane == "SHAPE_EARLY"
        )
        if dv.needs_human_review and actionable and len(review) < limit:
            review.append(item)
        if dv.pursuit_lane in _PRIME and len(prime) < limit:
            prime.append(item)
        elif dv.pursuit_lane in _SUB and len(sub) < limit:
            sub.append(item)
        elif dv.pursuit_lane == "SHAPE_EARLY" and len(shape) < limit:
            shape.append(item)

    return CaptureQueues(
        pursue_as_prime=prime,
        team_as_sub=sub,
        shape_early=shape,
        needs_review=review,
        counts={
            "pursue_as_prime": len(prime),
            "team_as_sub": len(sub),
            "shape_early": len(shape),
            "needs_review": len(review),
        },
    )
