"""Decision-engine worker (Slice 4).

Assembles ``DecisionInputs`` from the DB (detection over the opportunity's text,
enrichment/exclusions, package completeness, tenant config), runs the pure
``decide`` engine, and persists the authoritative ``opportunity_decision_vectors``
+ ``opportunity_gates`` rows, mirroring overall_priority + pursuit_lane onto
``opportunity_scores`` in the SAME transaction to avoid drift.

Deterministic end-to-end; the LLM adjudication layer (Slice 5) will sit above
this and may refine work packages but never overrule a hard gate.
"""

from __future__ import annotations

import asyncio
import logging
from datetime import UTC, datetime
from typing import Any
from uuid import UUID

from mactech_db import async_session_factory
from mactech_db.models import (
    ExclusionsCache,
    OpportunityDecisionVector,
    OpportunityEnriched,
    OpportunityGate,
    OpportunityPrimeTarget,
    OpportunityRaw,
    OpportunityScore,
    Tenant,
)
from mactech_intelligence.decision import decide
from mactech_intelligence.decision.facts import (
    SDVOSB_CODES,
    SMALL_BIZ_CODES,
    DecisionInputs,
    DeliveryCapacity,
)
from mactech_intelligence.detection import detect_signals
from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import insert as pg_insert

from mactech_workers.celery_app import celery_app

log = logging.getLogger(__name__)

_CONSTRUCTION_NAICS = frozenset({"236220", "237130", "237310", "237990", "238210", "562910"})
_TENANT_SET_ASIDES = frozenset(SDVOSB_CODES | SMALL_BIZ_CODES)


def _combined_text(opp: OpportunityRaw, attachment_text: str | None) -> str:
    return "\n\n".join(p for p in (opp.title, opp.description_text, attachment_text) if p)


def _completeness(opp: OpportunityRaw, attachment_text: str | None) -> str:
    # NB: never read opp.attachment_text here — it is a deferred column and a
    # lazy load would emit SQL outside the async greenlet. The caller passes the
    # already-loaded value in.
    status = opp.documents_status or {}
    value = status.get("completeness")
    if value:
        return str(value)
    if attachment_text:
        return "partial_attachments"
    if opp.description_text and opp.description_text.strip():
        return "description_only"
    return "metadata_only"


def _build_inputs(
    opp: OpportunityRaw,
    enr: OpportunityEnriched | None,
    incumbent_excluded: bool | None,
    attachment_text: str | None,
    prime_targets_count: int = 0,
) -> DecisionInputs:
    report = detect_signals(_combined_text(opp, attachment_text))
    hard_barriers, soft_barriers = report.barriers_by_severity()
    est_high = float(opp.estimated_value_high) if opp.estimated_value_high is not None else None
    deadline = opp.response_deadline.date() if opp.response_deadline else None

    return DecisionInputs(
        set_aside=opp.set_aside,
        tenant_set_aside_codes=_TENANT_SET_ASIDES,
        scan_unrestricted=True,
        response_deadline=deadline,
        as_of=datetime.now(UTC).date(),
        notice_type=opp.notice_type,
        has_direct_cyber=report.has_direct_cyber,
        has_frcs_ot=report.has_frcs_ot,
        has_training=report.has_training,
        has_facility_adjacency=report.has_facility_adjacency,
        has_construction_context=report.has_acquisition_context
        or (opp.naics_code in _CONSTRUCTION_NAICS),
        relevance_weight=report.relevance_weight,
        has_page_evidence=bool(attachment_text),
        hard_barriers=hard_barriers,
        soft_barriers=soft_barriers,
        estimated_value_high=est_high,
        naics_is_construction=opp.naics_code in _CONSTRUCTION_NAICS,
        incumbent_excluded=incumbent_excluded,
        has_incumbent=bool(enr and enr.incumbent_uei),
        prime_targets_count=prime_targets_count,
        completeness=_completeness(opp, attachment_text),
        capacity=DeliveryCapacity(),
    )


async def _persist(
    session, tenant_id: UUID, opp_id: UUID, result, pack_version: str, snapshot: dict[str, Any]
) -> None:
    now = datetime.now(UTC)
    v = result.vector

    # Upsert the authoritative decision vector.
    values = {
        "tenant_id": tenant_id,
        "opportunity_id": opp_id,
        "relevance_score": v.relevance_score,
        "prime_fit_score": v.prime_fit_score,
        "subcontract_fit_score": v.subcontract_fit_score,
        "winability_score": v.winability_score,
        "deliverability_score": v.deliverability_score,
        "strategic_value_score": v.strategic_value_score,
        "urgency_score": v.urgency_score,
        "evidence_completeness_score": v.evidence_completeness_score,
        "overall_priority_score": v.overall_priority_score,
        "pursuit_lane": result.pursuit_lane,
        "reason_codes": result.reason_codes,
        "confidence": result.confidence,
        "lane_weight_profile": result.lane_weight_profile,
        "needs_human_review": result.needs_human_review,
        "formula_version": result.to_lane_decision().formula_version,
        "knowledge_pack_version": pack_version[:128] if pack_version else None,
        "inputs_snapshot": snapshot,
        "computed_at": now,
        "updated_at": now,
    }
    update_cols = {k: values[k] for k in values if k not in ("tenant_id", "opportunity_id")}
    await session.execute(
        pg_insert(OpportunityDecisionVector)
        .values(**values)
        .on_conflict_do_update(constraint="uq_decision_vectors_tenant_opp", set_=update_cols)
    )

    # Replace gate rows for this (tenant, opp): upsert each detected gate.
    for g in result.gates:
        await session.execute(
            pg_insert(OpportunityGate)
            .values(
                tenant_id=tenant_id,
                opportunity_id=opp_id,
                gate_code=g.gate_code,
                status=g.status,
                severity=g.severity,
                reason_code=g.reason_code,
                detail=g.detail,
                source=g.source,
                detected_at=now,
            )
            .on_conflict_do_update(
                constraint="uq_gates_tenant_opp_code",
                set_={
                    "status": g.status,
                    "severity": g.severity,
                    "reason_code": g.reason_code,
                    "detail": g.detail,
                    "source": g.source,
                    "detected_at": now,
                },
            )
        )

    # Mirror the two headline fields onto opportunity_scores (same txn).
    score_row = (
        await session.execute(
            select(OpportunityScore).where(
                OpportunityScore.tenant_id == tenant_id,
                OpportunityScore.opportunity_id == opp_id,
            )
        )
    ).scalar_one_or_none()
    if score_row is not None:
        score_row.overall_priority_score = v.overall_priority_score
        score_row.pursuit_lane = result.pursuit_lane


async def compute_one(tenant_slug: str, opportunity_id: str) -> dict[str, Any]:
    opp_uuid = UUID(opportunity_id)
    session_factory = async_session_factory()
    async with session_factory() as session, session.begin():
        tenant = (
            await session.execute(select(Tenant).where(Tenant.slug == tenant_slug))
        ).scalar_one_or_none()
        if tenant is None:
            return {"status": "error", "reason": "tenant_not_found"}

        opp = (
            await session.execute(select(OpportunityRaw).where(OpportunityRaw.id == opp_uuid))
        ).scalar_one_or_none()
        if opp is None:
            return {"status": "error", "reason": "opportunity_not_found"}

        # attachment_text is deferred on the ORM; load it explicitly.
        attachment_text = (
            await session.execute(
                select(OpportunityRaw.attachment_text).where(OpportunityRaw.id == opp_uuid)
            )
        ).scalar_one_or_none()

        enr = (
            await session.execute(
                select(OpportunityEnriched).where(OpportunityEnriched.opportunity_id == opp_uuid)
            )
        ).scalar_one_or_none()
        incumbent_excluded = None
        if enr and enr.incumbent_uei:
            excl = (
                await session.execute(
                    select(ExclusionsCache).where(ExclusionsCache.uei == enr.incumbent_uei)
                )
            ).scalar_one_or_none()
            incumbent_excluded = None if excl is None else bool(excl.is_excluded)

        prime_targets_count = (
            await session.execute(
                select(func.count())
                .select_from(OpportunityPrimeTarget)
                .where(
                    OpportunityPrimeTarget.tenant_id == tenant.id,
                    OpportunityPrimeTarget.opportunity_id == opp_uuid,
                )
            )
        ).scalar_one()

        inputs = _build_inputs(opp, enr, incumbent_excluded, attachment_text, prime_targets_count)
        result = decide(inputs)
        snapshot = {
            "has_direct_cyber": inputs.has_direct_cyber,
            "has_frcs_ot": inputs.has_frcs_ot,
            "has_facility_adjacency": inputs.has_facility_adjacency,
            "completeness": inputs.completeness,
            "hard_barriers": sorted(inputs.hard_barriers),
            "estimated_value_high": inputs.estimated_value_high,
        }
        from mactech_intelligence.knowledge.pack import pack_version

        await _persist(session, tenant.id, opp_uuid, result, pack_version(), snapshot)

    return {
        "status": "ok",
        "opportunity_id": opportunity_id,
        "pursuit_lane": result.pursuit_lane,
        "overall_priority": result.vector.overall_priority_score,
        "reason_codes": result.reason_codes,
        "needs_human_review": result.needs_human_review,
    }


async def compute_batch(tenant_slug: str, limit: int = 50) -> dict[str, Any]:
    """Compute decisions for scored opportunities that lack a decision vector."""
    session_factory = async_session_factory()
    async with session_factory() as session:
        tenant = (
            await session.execute(select(Tenant).where(Tenant.slug == tenant_slug))
        ).scalar_one_or_none()
        if tenant is None:
            return {"status": "error", "reason": "tenant_not_found"}
        rows = (
            (
                await session.execute(
                    select(OpportunityScore.opportunity_id)
                    .outerjoin(
                        OpportunityDecisionVector,
                        (
                            OpportunityDecisionVector.opportunity_id
                            == OpportunityScore.opportunity_id
                        )
                        & (OpportunityDecisionVector.tenant_id == tenant.id),
                    )
                    .where(
                        OpportunityScore.tenant_id == tenant.id,
                        OpportunityDecisionVector.id.is_(None),
                    )
                    .limit(limit)
                )
            )
            .scalars()
            .all()
        )

    computed = 0
    for opp_id in rows:
        try:
            await compute_one(tenant_slug, str(opp_id))
            computed += 1
        except Exception as exc:
            log.warning("decision compute failed for %s: %s", opp_id, exc)
    return {"status": "ok", "candidates": len(rows), "computed": computed}


@celery_app.task(name="mactech.decision.compute_one")
def compute_one_task(tenant_slug: str, opportunity_id: str) -> dict[str, Any]:
    return asyncio.run(compute_one(tenant_slug, opportunity_id))


@celery_app.task(name="mactech.decision.compute_batch")
def compute_batch_task(tenant_slug: str, limit: int = 50) -> dict[str, Any]:
    return asyncio.run(compute_batch(tenant_slug, limit))
