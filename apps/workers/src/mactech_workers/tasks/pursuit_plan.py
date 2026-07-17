"""Pursuit-plan generation worker (Slice 6).

For each actionable opportunity (lane above WATCH), build the deterministic
pursuit plan from the decision + prime targets and persist
pursuit_recommendations + dated pursuit_actions.
"""

from __future__ import annotations

import asyncio
import logging
from datetime import UTC, datetime
from typing import Any
from uuid import UUID

from mactech_db import async_session_factory
from mactech_db.models import (
    OpportunityDecisionVector,
    OpportunityPrimeTarget,
    OpportunityRaw,
    PrimeTarget,
    PursuitAction,
    PursuitRecommendation,
    Tenant,
)
from mactech_intelligence.pursuit import PlanInputs, build_pursuit_plan
from mactech_intelligence.pursuit.plan import PrimeRef
from sqlalchemy import delete, select, text
from sqlalchemy.dialects.postgresql import insert as pg_insert

from mactech_workers.celery_app import celery_app

log = logging.getLogger(__name__)

_ACTIONABLE = ("PRIME_NOW", "PRIME_WITH_PARTNER", "SUB_TO_IDENTIFIED_PRIME",
               "SUB_TO_PRIME_NOT_YET_IDENTIFIED", "SHAPE_EARLY")


async def generate_for_opportunity(tenant_id: UUID, opp_id: UUID) -> dict[str, Any]:
    session_factory = async_session_factory()
    async with session_factory() as session, session.begin():
        dv = (
            await session.execute(
                select(OpportunityDecisionVector).where(
                    OpportunityDecisionVector.tenant_id == tenant_id,
                    OpportunityDecisionVector.opportunity_id == opp_id,
                )
            )
        ).scalar_one_or_none()
        if dv is None or dv.pursuit_lane not in _ACTIONABLE:
            return {"status": "skipped", "reason": "not_actionable"}

        opp = (
            await session.execute(select(OpportunityRaw).where(OpportunityRaw.id == opp_id))
        ).scalar_one()

        primes = (
            await session.execute(
                select(PrimeTarget.name, OpportunityPrimeTarget.confidence)
                .join(PrimeTarget, PrimeTarget.id == OpportunityPrimeTarget.prime_target_id)
                .where(
                    OpportunityPrimeTarget.tenant_id == tenant_id,
                    OpportunityPrimeTarget.opportunity_id == opp_id,
                )
                .order_by(OpportunityPrimeTarget.rank)
            )
        ).all()

        plan = build_pursuit_plan(
            PlanInputs(
                pursuit_lane=dv.pursuit_lane,
                reason_codes=tuple(dv.reason_codes or []),
                confidence=dv.confidence,
                why_this_is_real=_why(dv),
                mactech_work_package=_work_package(dv, opp),
                blocking_issues=tuple(dv.reason_codes or []),
                prime_targets=tuple(PrimeRef(name=n, confidence=c) for n, c in primes),
                response_deadline=opp.response_deadline.date() if opp.response_deadline else None,
                as_of=datetime.now(UTC).date(),
                needs_human_review=dv.needs_human_review,
            )
        )

        # Upsert the recommendation, replace its actions.
        rec_values = {
            "tenant_id": tenant_id,
            "opportunity_id": opp_id,
            "pursuit_lane": plan.recommended_lane,
            "executive_decision": plan.executive_decision,
            "why_this_is_real": plan.why_this_is_real,
            "mactech_work_package": plan.mactech_work_package,
            "blocking_issues": plan.blocking_issues,
            "prime_target_names": plan.prime_target_names,
            "recommended_owner_slug": (plan.next_actions[0].owner_slug if plan.next_actions else None),
            "decision_deadline": plan.decision_deadline,
            "response_deadline": plan.response_deadline,
            "confidence": plan.confidence,
            "updated_at": datetime.now(UTC),
        }
        await session.execute(
            pg_insert(PursuitRecommendation)
            .values(**rec_values)
            .on_conflict_do_update(
                constraint="uq_pursuit_recs_tenant_opp",
                set_={k: rec_values[k] for k in rec_values if k not in ("tenant_id", "opportunity_id")},
            )
        )
        rec_id = (
            await session.execute(
                select(PursuitRecommendation.id).where(
                    PursuitRecommendation.tenant_id == tenant_id,
                    PursuitRecommendation.opportunity_id == opp_id,
                )
            )
        ).scalar_one()

        await session.execute(
            delete(PursuitAction).where(PursuitAction.recommendation_id == rec_id)
        )
        for a in plan.next_actions:
            session.add(
                PursuitAction(
                    tenant_id=tenant_id,
                    opportunity_id=opp_id,
                    recommendation_id=rec_id,
                    sequence=a.sequence,
                    action=a.action,
                    owner_founder_slug=a.owner_slug,
                    due_at=a.due_at,
                    purpose=a.purpose,
                    completion_criteria=a.completion_criteria,
                    dependency=a.dependency,
                )
            )

    return {"status": "ok", "lane": plan.recommended_lane, "actions": len(plan.next_actions)}


def _why(dv: OpportunityDecisionVector) -> str:
    bits = []
    if dv.relevance_score:
        bits.append(f"relevance {dv.relevance_score}/100")
    if dv.subcontract_fit_score and dv.pursuit_lane.startswith("SUB"):
        bits.append(f"subcontract fit {dv.subcontract_fit_score}/100")
    if dv.prime_fit_score and dv.pursuit_lane.startswith("PRIME"):
        bits.append(f"prime fit {dv.prime_fit_score}/100")
    return "MacTech-aligned scope detected — " + ", ".join(bits) + "." if bits else ""


def _work_package(dv: OpportunityDecisionVector, opp: OpportunityRaw) -> str:
    if dv.pursuit_lane.startswith("SUB"):
        return ("Own the FRCS/OT cybersecurity work package: RMF artifacts, control-system "
                "inventory, secure architecture review, cybersecurity submittals, and "
                "commissioning support under the prime.")
    if dv.pursuit_lane.startswith("PRIME"):
        return ("Deliver the bounded cyber scope directly (assessment, SSP/POA&M, remediation "
                "roadmap, executive briefing).")
    return "Shape the acquisition toward a scoped cyber requirement."


async def generate_batch(tenant_slug: str, *, limit: int = 60) -> dict[str, Any]:
    session_factory = async_session_factory()
    async with session_factory() as session:
        tenant = (
            await session.execute(select(Tenant).where(Tenant.slug == tenant_slug))
        ).scalar_one_or_none()
        if tenant is None:
            return {"status": "error", "reason": "tenant_not_found"}
        ids = (
            await session.execute(
                text(
                    "select opportunity_id from opportunity_decision_vectors "
                    "where tenant_id=:t and pursuit_lane = any(:lanes) limit :n"
                ),
                {"t": str(tenant.id), "lanes": list(_ACTIONABLE), "n": limit},
            )
        ).scalars().all()

    generated = 0
    for opp_id in ids:
        try:
            res = await generate_for_opportunity(tenant.id, opp_id)
            if res.get("status") == "ok":
                generated += 1
        except Exception as exc:
            log.warning("pursuit plan gen failed for %s: %s", opp_id, exc)
    return {"status": "ok", "candidates": len(ids), "generated": generated}


@celery_app.task(name="mactech.pursuit.generate_batch")
def generate_batch_task(tenant_slug: str, limit: int = 60) -> dict[str, Any]:
    return asyncio.run(generate_batch(tenant_slug, limit=limit))
