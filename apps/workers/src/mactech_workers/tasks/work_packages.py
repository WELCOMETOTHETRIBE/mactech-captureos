"""Work-package adjudication worker (Slice 5).

Detects signals over the opportunity text, assembles ranked evidence with stable
ids, asks the LLM to decompose into evidence-cited work packages, validates the
citations, and persists opportunity_work_packages. Only runs for actionable opps
with real detected scope.
"""

from __future__ import annotations

import asyncio
import hashlib
import logging
from typing import Any
from uuid import UUID

from mactech_db import async_session_factory
from mactech_db.models import (
    OpportunityRaw,
    OpportunityWorkPackage,
    Tenant,
)
from mactech_intelligence.decision.adjudicate import PROMPT_VERSION, adjudicate_work_packages
from mactech_intelligence.decision.evidence import assemble_evidence
from mactech_intelligence.detection import detect_signals
from mactech_intelligence.knowledge.pack import pack_version
from mactech_intelligence.llm import AnthropicLLMClient
from mactech_intelligence.llm.client import MODEL_SMART
from sqlalchemy import delete, select, text

from mactech_workers.celery_app import celery_app

log = logging.getLogger(__name__)

_ACTIONABLE = ("PRIME_NOW", "PRIME_WITH_PARTNER", "SUB_TO_IDENTIFIED_PRIME",
               "SUB_TO_PRIME_NOT_YET_IDENTIFIED", "SHAPE_EARLY")


async def adjudicate_for_opportunity(tenant_id: UUID, opp_id: UUID) -> dict[str, Any]:
    session_factory = async_session_factory()
    async with session_factory() as session:
        opp = (
            await session.execute(select(OpportunityRaw).where(OpportunityRaw.id == opp_id))
        ).scalar_one_or_none()
        if opp is None:
            return {"status": "error", "reason": "opportunity_not_found"}
        attachment_text = (
            await session.execute(
                select(OpportunityRaw.attachment_text).where(OpportunityRaw.id == opp_id)
            )
        ).scalar_one_or_none()

    body = "\n\n".join(p for p in (opp.title, opp.description_text, attachment_text) if p)
    doc_hash = hashlib.sha1(body.encode()).hexdigest()
    report = detect_signals(body)
    evidence = assemble_evidence(report, doc_hash=doc_hash)
    if not evidence:
        return {"status": "skipped", "reason": "no_evidence"}

    client = AnthropicLLMClient()
    result, rejected = await adjudicate_work_packages(
        title=opp.title, evidence=evidence, client=client
    )

    pv = pack_version()
    async with session_factory() as session, session.begin():
        await session.execute(
            delete(OpportunityWorkPackage).where(
                OpportunityWorkPackage.tenant_id == tenant_id,
                OpportunityWorkPackage.opportunity_id == opp_id,
            )
        )
        for i, wp in enumerate(result.work_packages):
            session.add(
                OpportunityWorkPackage(
                    tenant_id=tenant_id,
                    opportunity_id=opp_id,
                    sort_order=i,
                    title=wp.title[:512],
                    scope_category=wp.scope_category or None,
                    description=wp.description or None,
                    deliverables=wp.deliverables,
                    required_roles=wp.required_roles,
                    required_credentials=wp.required_credentials,
                    mactech_role=wp.mactech_role,
                    confidence=wp.confidence,
                    evidence_ids=wp.evidence_ids,
                    model=MODEL_SMART,
                    prompt_version=PROMPT_VERSION,
                    knowledge_pack_version=pv[:128],
                )
            )

    return {
        "status": "ok",
        "work_packages": len(result.work_packages),
        "rejected_evidence_ids": len(rejected),
        "customer_need": result.customer_need[:160],
    }


async def adjudicate_batch(tenant_slug: str, *, limit: int = 20) -> dict[str, Any]:
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
                    "select dv.opportunity_id from opportunity_decision_vectors dv "
                    "left join opportunity_work_packages wp "
                    "  on wp.opportunity_id = dv.opportunity_id and wp.tenant_id = dv.tenant_id "
                    "where dv.tenant_id = :t and dv.pursuit_lane = any(:lanes) and wp.id is null "
                    "limit :n"
                ),
                {"t": str(tenant.id), "lanes": list(_ACTIONABLE), "n": limit},
            )
        ).scalars().all()

    done = 0
    for opp_id in ids:
        try:
            res = await adjudicate_for_opportunity(tenant.id, opp_id)
            if res.get("status") == "ok":
                done += 1
        except Exception as exc:
            log.warning("work-package adjudication failed for %s: %s", opp_id, exc)
    return {"status": "ok", "candidates": len(ids), "adjudicated": done}


@celery_app.task(name="mactech.work_packages.adjudicate_batch")
def adjudicate_batch_task(tenant_slug: str, limit: int = 20) -> dict[str, Any]:
    return asyncio.run(adjudicate_batch(tenant_slug, limit=limit))


@celery_app.task(name="mactech.work_packages.adjudicate_one")
def adjudicate_one_task(tenant_slug: str, opportunity_id: str) -> dict[str, Any]:
    async def _run() -> dict[str, Any]:
        session_factory = async_session_factory()
        async with session_factory() as session:
            tenant = (
                await session.execute(select(Tenant).where(Tenant.slug == tenant_slug))
            ).scalar_one()
        return await adjudicate_for_opportunity(tenant.id, UUID(opportunity_id))

    return asyncio.run(_run())
