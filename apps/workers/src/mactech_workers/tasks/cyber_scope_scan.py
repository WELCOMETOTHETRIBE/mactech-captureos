"""Cyber scope scan worker — runs after SAM ingest and attachment fetch."""

from __future__ import annotations

import asyncio
import hashlib
import logging
import os
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from typing import Any
from uuid import UUID

from mactech_db import async_session_factory
from mactech_db.audit import record_event
from mactech_db.models import (
    EVENT_CYBER_SCOPE_ANALYSIS_RUN,
    CyberScopeAnalysis,
    OpportunityRaw,
    OpportunityScore,
    Tenant,
)
from mactech_intelligence.cyber_scope import analyze_cyber_scope
from mactech_intelligence.cyber_scope.sources import CyberScopeTextSource
from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import undefer

from mactech_workers.celery_app import celery_app

log = logging.getLogger(__name__)


@dataclass
class CyberScopeScanResult:
    opportunity_id: str
    tenant_slug: str
    score: int
    likelihood: str
    pursuit_model: str
    status: str


def _text_hash(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _analysis_to_row(
    *,
    tenant_id: UUID,
    opportunity_id: UUID,
    analysis,
    source_hash: str,
    scan_pass: str,
) -> dict[str, Any]:
    cats = analysis.detected_categories
    return {
        "tenant_id": tenant_id,
        "opportunity_id": opportunity_id,
        "source_type": "SAM_INGEST",
        "source_hash": source_hash,
        "scan_pass": scan_pass,
        "parser_version": analysis.parser_version,
        "overall_cyber_likelihood": analysis.overall_cyber_likelihood,
        "recommended_pursuit_model": analysis.recommended_pursuit_model,
        "score": analysis.score,
        "detected_categories_json": cats.model_dump(),
        "top_signals_json": [s.model_dump() for s in analysis.top_signals],
        "hidden_scope_indicators_json": [s.model_dump() for s in analysis.hidden_scope_indicators],
        "missing_requirements_json": analysis.missing_but_likely_requirements,
        "suggested_actions_json": [a.model_dump() for a in analysis.suggested_actions],
        "evidence_snippets_json": [s.model_dump() for s in analysis.evidence_snippets],
        "metadata_json": analysis.metadata,
        "ufgs_center_of_gravity": analysis.ufgs_center_of_gravity,
        "ufgs_tier_1_hit": analysis.ufgs_tier_1_hit,
        "updated_at": datetime.now(UTC),
    }


async def scan_opportunity_for_tenant(
    *,
    opportunity_id: UUID,
    tenant: Tenant,
    scan_pass: str | None = None,
) -> CyberScopeScanResult | None:
    session_factory = async_session_factory()
    async with session_factory() as session, session.begin():
        opp = (
            await session.execute(
                select(OpportunityRaw)
                # attachment_text is deferred; accessed below. Without undefer()
                # the lazy load fires outside the async greenlet and raises
                # MissingGreenlet — the same bug that silently killed scoring.
                .options(undefer(OpportunityRaw.attachment_text))
                .where(OpportunityRaw.id == opportunity_id)
            )
        ).scalar_one_or_none()
        if opp is None:
            return None

        pass_kind = scan_pass or (
            "with_attachments"
            if opp.attachment_text and opp.attachment_text.strip()
            else "description_only"
        )
        source = CyberScopeTextSource.from_opportunity(
            title=opp.title,
            description_text=opp.description_text,
            attachment_text=opp.attachment_text,
            opportunity_id=str(opp.id),
            agency=opp.agency,
            solicitation_number=opp.solicitation_number,
            source_url=opp.description_url,
        )
        if scan_pass:
            source = CyberScopeTextSource(
                source_type=source.source_type,
                title=source.title,
                description_text=source.description_text,
                attachment_text=source.attachment_text,
                metadata=source.metadata,
                scan_pass=scan_pass,  # type: ignore[arg-type]
            )

        combined = source.combined_text
        if not combined.strip():
            return CyberScopeScanResult(
                opportunity_id=str(opportunity_id),
                tenant_slug=tenant.slug,
                score=0,
                likelihood="NONE",
                pursuit_model="NO_ACTION",
                status="no_text",
            )

        analysis = analyze_cyber_scope(source)
        source_hash = _text_hash(combined)
        row = _analysis_to_row(
            tenant_id=tenant.id,
            opportunity_id=opportunity_id,
            analysis=analysis,
            source_hash=source_hash,
            scan_pass=pass_kind,
        )

        stmt = insert(CyberScopeAnalysis).values(**row)
        stmt = stmt.on_conflict_do_update(
            constraint="uq_cyber_scope_tenant_opp",
            set_={k: v for k, v in row.items() if k not in ("tenant_id", "opportunity_id")},
        )
        await session.execute(stmt)

        score_row = (
            await session.execute(
                select(OpportunityScore).where(
                    OpportunityScore.tenant_id == tenant.id,
                    OpportunityScore.opportunity_id == opportunity_id,
                )
            )
        ).scalar_one_or_none()
        if score_row is not None:
            score_row.cyber_scope_score = analysis.score
            score_row.cyber_scope_likelihood = analysis.overall_cyber_likelihood
            score_row.cyber_scope_pursuit_model = analysis.recommended_pursuit_model
            score_row.cyber_scope_flags = {
                "ufgs_center_of_gravity": analysis.ufgs_center_of_gravity,
                "ufgs_tier_1_hit": analysis.ufgs_tier_1_hit,
                "top_ufgs_sections": analysis.top_ufgs_sections,
                "parser_version": analysis.parser_version,
            }

        await record_event(
            session,
            tenant_id=tenant.id,
            event_type=EVENT_CYBER_SCOPE_ANALYSIS_RUN,
            entity_type="cyber_scope_analysis",
            entity_id=opportunity_id,
            actor_label="system:cyber_scope_scan",
            payload={
                "parser_version": analysis.parser_version,
                "score": analysis.score,
                "likelihood": analysis.overall_cyber_likelihood,
                "source_hash": source_hash,
                "scan_pass": pass_kind,
            },
        )

    return CyberScopeScanResult(
        opportunity_id=str(opportunity_id),
        tenant_slug=tenant.slug,
        score=analysis.score,
        likelihood=analysis.overall_cyber_likelihood,
        pursuit_model=analysis.recommended_pursuit_model,
        status="ok",
    )


async def scan_opportunity_all_tenants(
    opportunity_id: UUID | str,
    *,
    scan_pass: str | None = None,
) -> list[CyberScopeScanResult]:
    opp_uuid = UUID(str(opportunity_id))
    pin = os.environ.get("MACTECH_PIN_TENANT_SLUG") or os.environ.get(
        "MACTECH_TENANT_SLUG", "mactech"
    )
    session_factory = async_session_factory()
    results: list[CyberScopeScanResult] = []

    async with session_factory() as session:
        stmt = select(Tenant)
        if pin:
            stmt = stmt.where(Tenant.slug == pin)
        tenants = (await session.execute(stmt)).scalars().all()

    for tenant in tenants:
        try:
            r = await scan_opportunity_for_tenant(
                opportunity_id=opp_uuid,
                tenant=tenant,
                scan_pass=scan_pass,
            )
            if r is not None:
                results.append(r)
        except Exception as exc:
            log.warning(
                "cyber_scope_scan failed tenant=%s opp=%s: %s",
                tenant.slug,
                opp_uuid,
                exc,
            )
    return results


@celery_app.task(name="mactech.cyber_scope.scan_one")
def scan_one_task(opportunity_id: str, scan_pass: str | None = None) -> list[dict[str, Any]]:
    return [
        asdict(r)
        for r in asyncio.run(scan_opportunity_all_tenants(opportunity_id, scan_pass=scan_pass))
    ]


@celery_app.task(name="mactech.cyber_scope.scan_batch")
def scan_batch_task(batch_size: int = 50) -> dict[str, Any]:
    """Rescan recent opportunities that lack cyber scope or have new attachments."""

    async def _run() -> dict[str, Any]:
        session_factory = async_session_factory()
        scanned = 0
        async with session_factory() as session:
            # Only opps that (a) have text to scan, (b) aren't expired, and
            # (c) haven't been scanned yet. Without the "not yet scanned"
            # guard the batch re-scanned the newest 50 every tick and never
            # reached the backlog. analyze_cyber_scope is a deterministic
            # parser (no LLM), so a full backfill is cheap.
            rows = (
                (
                    await session.execute(
                        select(OpportunityRaw.id)
                        .where(OpportunityRaw.description_text.isnot(None))
                        .where(
                            (OpportunityRaw.response_deadline.is_(None))
                            | (OpportunityRaw.response_deadline >= func.now())
                        )
                        .where(
                            ~select(CyberScopeAnalysis.id)
                            .where(CyberScopeAnalysis.opportunity_id == OpportunityRaw.id)
                            .exists()
                        )
                        .order_by(OpportunityRaw.posted_at.desc().nullslast())
                        .limit(batch_size)
                    )
                )
                .scalars()
                .all()
            )

        for opp_id in rows:
            await scan_opportunity_all_tenants(opp_id)
            scanned += 1
        return {"scanned": scanned}

    return asyncio.run(_run())
