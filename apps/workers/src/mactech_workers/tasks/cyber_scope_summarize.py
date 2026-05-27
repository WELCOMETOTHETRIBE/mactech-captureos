"""Batch LLM summaries for HIGH/CRITICAL cyber scope analyses."""

from __future__ import annotations

import asyncio
import logging
import os
from datetime import UTC, datetime

from mactech_db import async_session_factory
from mactech_db.audit import record_event
from mactech_db.models import (
    EVENT_CYBER_SCOPE_SUMMARIZED,
    CyberScopeAnalysis,
    Tenant,
)
from mactech_intelligence.cyber_scope.llm_exports import (
    SUMMARY_VERSION,
    CyberScopeOppContext,
    deterministic_summary,
    generate_cyber_scope_summary,
)
from mactech_intelligence.llm import AnthropicLLMClient
from sqlalchemy import select

from mactech_intelligence.cyber_scope.db_adapter import schema_from_persisted
from mactech_workers.celery_app import celery_app

log = logging.getLogger(__name__)


async def _summarize_batch(*, batch_size: int = 15) -> dict[str, int]:
    key = os.environ.get("ANTHROPIC_API_KEY", "").strip()
    if not key:
        log.info("cyber_scope_summarize_batch: no ANTHROPIC_API_KEY, skipping")
        return {"skipped": 0, "summarized": 0, "reason": "no_key"}

    client = AnthropicLLMClient(api_key=key)
    summarized = 0
    skipped = 0

    async with async_session_factory() as session:
        tenants = (await session.execute(select(Tenant))).scalars().all()
        for tenant in tenants:
            rows = (
                await session.execute(
                    select(CyberScopeAnalysis)
                    .where(
                        CyberScopeAnalysis.tenant_id == tenant.id,
                        CyberScopeAnalysis.opportunity_id.is_not(None),
                        CyberScopeAnalysis.overall_cyber_likelihood.in_(
                            ("HIGH", "CRITICAL")
                        ),
                    )
                    .order_by(CyberScopeAnalysis.score.desc())
                    .limit(batch_size * 3)
                )
            ).scalars().all()

            for row in rows:
                meta = row.metadata_json or {}
                if meta.get("llm_summary") and meta.get("llm_summary_version") == SUMMARY_VERSION:
                    skipped += 1
                    continue
                if summarized >= batch_size:
                    break

                from mactech_db.models import OpportunityRaw

                opp = None
                if row.opportunity_id:
                    opp = (
                        await session.execute(
                            select(OpportunityRaw).where(
                                OpportunityRaw.id == row.opportunity_id
                            )
                        )
                    ).scalar_one_or_none()

                schema = schema_from_persisted(
                    overall_cyber_likelihood=row.overall_cyber_likelihood,
                    recommended_pursuit_model=row.recommended_pursuit_model,
                    score=row.score,
                    detected_categories_json=row.detected_categories_json,
                    top_signals_json=row.top_signals_json,
                    hidden_scope_indicators_json=row.hidden_scope_indicators_json,
                    missing_requirements_json=row.missing_requirements_json,
                    suggested_actions_json=row.suggested_actions_json,
                    evidence_snippets_json=row.evidence_snippets_json,
                    ufgs_center_of_gravity=row.ufgs_center_of_gravity,
                    ufgs_tier_1_hit=row.ufgs_tier_1_hit,
                    scan_pass=row.scan_pass,
                    parser_version=row.parser_version,
                    metadata_json=row.metadata_json,
                )
                m = row.metadata_json or {}
                opp_ctx = CyberScopeOppContext(
                    title=(opp.title if opp else None) or m.get("title") or "Opportunity",
                    agency=opp.agency if opp else m.get("agency"),
                    solicitation_number=(
                        opp.solicitation_number if opp else m.get("solicitation_number")
                    ),
                )
                try:
                    resp = await generate_cyber_scope_summary(client, schema, opp_ctx)
                    summary = resp.text
                    generated_by = "llm"
                    model = resp.model
                except Exception as exc:
                    log.warning(
                        "summarize failed analysis=%s: %s", row.id, exc
                    )
                    summary = deterministic_summary(schema, opp_ctx)
                    generated_by = "template"
                    model = None

                now = datetime.now(UTC).isoformat()
                new_meta = dict(meta)
                new_meta["llm_summary"] = summary
                new_meta["llm_summary_generated_by"] = generated_by
                new_meta["llm_summary_at"] = now
                new_meta["llm_summary_version"] = SUMMARY_VERSION
                if model:
                    new_meta["llm_summary_model"] = model
                row.metadata_json = new_meta

                await record_event(
                    session,
                    tenant_id=tenant.id,
                    event_type=EVENT_CYBER_SCOPE_SUMMARIZED,
                    entity_type="cyber_scope_analysis",
                    entity_id=row.id,
                    actor_label="system:cyber_scope_summarize_batch",
                    payload={"generated_by": generated_by, "batch": True},
                )
                summarized += 1

        await session.commit()

    return {"summarized": summarized, "skipped": skipped}


@celery_app.task(name="mactech.cyber_scope.summarize_batch")
def summarize_batch(batch_size: int = 15) -> dict[str, int]:
    return asyncio.run(_summarize_batch(batch_size=batch_size))
