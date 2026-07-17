"""Cyber scope LLM summaries, email drafts, and exports."""

from __future__ import annotations

import logging
import os
from datetime import UTC, datetime
from typing import Annotated, Any
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import Response
from mactech_db.audit import record_event
from mactech_db.models import (
    EVENT_CYBER_SCOPE_CLARIFICATION_EMAIL,
    EVENT_CYBER_SCOPE_PRIME_OUTREACH_EMAIL,
    EVENT_CYBER_SCOPE_SUMMARIZED,
    CyberScopeAnalysis,
    IngestionState,
    OpportunityRaw,
    SavedSearch,
)
from mactech_intelligence.cyber_scope.db_adapter import schema_from_persisted
from mactech_intelligence.cyber_scope.export_formats import (
    analysis_to_pdf_bytes,
    feed_rows_to_csv,
)
from mactech_intelligence.cyber_scope.llm_exports import (
    CLARIFICATION_VERSION,
    PRIME_VERSION,
    SUMMARY_VERSION,
    CyberScopeOppContext,
    build_governance_handoff_stub,
    build_pricing_handoff_stub,
    deterministic_clarification_email,
    deterministic_prime_outreach,
    deterministic_summary,
    generate_clarification_email,
    generate_cyber_scope_summary,
    generate_prime_outreach_email,
)
from mactech_intelligence.cyber_scope.sam_search import (
    build_sam_cyber_jobs,
    is_cyber_scope_saved_search,
)
from mactech_intelligence.llm import AnthropicLLMClient
from pydantic import BaseModel, ConfigDict
from sqlalchemy import select, text

from mactech_api.auth import RequestContext, get_request_context
from mactech_api.routes.cyber_scope import (
    CyberScopeFeedItemOut,
    _row_to_feed_item,
)

log = logging.getLogger(__name__)
router = APIRouter(tags=["cyber-scope"])


class _Out(BaseModel):
    model_config = ConfigDict(from_attributes=True)


class SamSearchStatusOut(_Out):
    state_key: str
    last_run_at: str | None
    last_success_at: str | None
    last_status: str | None
    last_error: str | None


class SamSearchRunOut(_Out):
    status: str
    jobs_run: int
    total_matched: int
    total_upserts: int
    errors: int


class EmailDraftOut(_Out):
    subject: str
    body: str
    generated_by: str
    model: str | None = None


class SummaryOut(_Out):
    summary: str
    generated_by: str
    model: str | None = None
    generated_at: str


class IntelligenceBundleOut(_Out):
    llm_summary: str | None = None
    llm_summary_generated_by: str | None = None
    llm_summary_at: str | None = None
    clarification_email: EmailDraftOut | None = None
    prime_outreach_email: EmailDraftOut | None = None
    governance_handoff: dict[str, Any] | None = None
    pricing_handoff: dict[str, Any] | None = None


def _audit_actor_kwargs(ctx: RequestContext) -> dict[str, Any]:
    if ctx.user:
        return {"actor_user_id": ctx.user.id, "actor_label": ctx.user.email}
    return {"actor_label": "system:api"}


async def _load_analysis_pair(
    ctx: RequestContext, analysis_id: UUID
) -> tuple[CyberScopeAnalysis, Any, OpportunityRaw | None]:
    row = (
        await ctx.session.execute(
            select(CyberScopeAnalysis).where(
                CyberScopeAnalysis.id == analysis_id,
                CyberScopeAnalysis.tenant_id == ctx.tenant.id,
            )
        )
    ).scalar_one_or_none()
    if row is None:
        raise HTTPException(status_code=404, detail="Analysis not found")
    opp = None
    if row.opportunity_id:
        opp = (
            await ctx.session.execute(
                select(OpportunityRaw).where(OpportunityRaw.id == row.opportunity_id)
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
    return row, schema, opp


def _opp_context(opp: OpportunityRaw | None, row: CyberScopeAnalysis) -> CyberScopeOppContext:
    meta = row.metadata_json or {}
    return CyberScopeOppContext(
        title=(opp.title if opp else None) or meta.get("title") or "Opportunity",
        agency=opp.agency if opp else meta.get("agency"),
        solicitation_number=(opp.solicitation_number if opp else meta.get("solicitation_number")),
        notice_type=opp.notice_type if opp else None,
        response_deadline=(
            opp.response_deadline.isoformat() if opp and opp.response_deadline else None
        ),
    )


def _llm_client() -> AnthropicLLMClient | None:
    key = os.environ.get("ANTHROPIC_API_KEY", "").strip()
    if not key:
        return None
    return AnthropicLLMClient(api_key=key)


def _intelligence_from_metadata(meta: dict[str, Any]) -> IntelligenceBundleOut:
    summary = meta.get("llm_summary")
    clar = meta.get("clarification_email")
    prime = meta.get("prime_outreach_email")
    return IntelligenceBundleOut(
        llm_summary=summary,
        llm_summary_generated_by=meta.get("llm_summary_generated_by"),
        llm_summary_at=meta.get("llm_summary_at"),
        clarification_email=(
            EmailDraftOut(
                subject=clar.get("subject", ""),
                body=clar.get("body", ""),
                generated_by=clar.get("generated_by", "unknown"),
                model=clar.get("model"),
            )
            if isinstance(clar, dict) and clar.get("body")
            else None
        ),
        prime_outreach_email=(
            EmailDraftOut(
                subject=prime.get("subject", ""),
                body=prime.get("body", ""),
                generated_by=prime.get("generated_by", "unknown"),
                model=prime.get("model"),
            )
            if isinstance(prime, dict) and prime.get("body")
            else None
        ),
        governance_handoff=meta.get("governance_handoff"),
        pricing_handoff=meta.get("pricing_handoff"),
    )


@router.get(
    "/tools/cyber-scope/analyses/{analysis_id}/intelligence",
    response_model=IntelligenceBundleOut,
)
async def get_intelligence_bundle(
    analysis_id: UUID,
    ctx: Annotated[RequestContext, Depends(get_request_context)],
) -> IntelligenceBundleOut:
    row, schema, _ = await _load_analysis_pair(ctx, analysis_id)
    meta = dict(row.metadata_json or {})
    if "governance_handoff" not in meta and row.opportunity_id:
        meta["governance_handoff"] = build_governance_handoff_stub(
            analysis_id=str(analysis_id),
            opportunity_id=str(row.opportunity_id),
            analysis=schema,
        )
    if "pricing_handoff" not in meta and row.opportunity_id:
        meta["pricing_handoff"] = build_pricing_handoff_stub(
            analysis_id=str(analysis_id),
            opportunity_id=str(row.opportunity_id),
            analysis=schema,
        )
    return _intelligence_from_metadata(meta)


@router.post(
    "/tools/cyber-scope/analyses/{analysis_id}/summarize",
    response_model=SummaryOut,
)
async def summarize_analysis(
    analysis_id: UUID,
    ctx: Annotated[RequestContext, Depends(get_request_context)],
) -> SummaryOut:
    row, schema, opp = await _load_analysis_pair(ctx, analysis_id)
    opp_ctx = _opp_context(opp, row)
    client = _llm_client()
    generated_by = "template"
    model: str | None = None
    if client:
        try:
            resp = await generate_cyber_scope_summary(client, schema, opp_ctx)
            summary = resp.text
            generated_by = "llm"
            model = resp.model
        except Exception as exc:
            log.warning("cyber_scope summarize LLM failed: %s", exc)
            summary = deterministic_summary(schema, opp_ctx)
    else:
        summary = deterministic_summary(schema, opp_ctx)

    now = datetime.now(UTC).isoformat()
    meta = dict(row.metadata_json or {})
    meta["llm_summary"] = summary
    meta["llm_summary_generated_by"] = generated_by
    meta["llm_summary_at"] = now
    meta["llm_summary_version"] = SUMMARY_VERSION
    if model:
        meta["llm_summary_model"] = model
    row.metadata_json = meta

    await record_event(
        ctx.session,
        tenant_id=ctx.tenant.id,
        event_type=EVENT_CYBER_SCOPE_SUMMARIZED,
        entity_type="cyber_scope_analysis",
        entity_id=row.id,
        payload={"generated_by": generated_by, "model": model},
        **_audit_actor_kwargs(ctx),
    )
    await ctx.session.commit()
    return SummaryOut(
        summary=summary,
        generated_by=generated_by,
        model=model,
        generated_at=now,
    )


@router.post(
    "/tools/cyber-scope/analyses/{analysis_id}/clarification-email",
    response_model=EmailDraftOut,
)
async def clarification_email(
    analysis_id: UUID,
    ctx: Annotated[RequestContext, Depends(get_request_context)],
) -> EmailDraftOut:
    row, schema, opp = await _load_analysis_pair(ctx, analysis_id)
    opp_ctx = _opp_context(opp, row)
    client = _llm_client()
    generated_by = "template"
    model: str | None = None
    if client and (
        schema.hidden_scope_indicators or schema.overall_cyber_likelihood in ("HIGH", "CRITICAL")
    ):
        try:
            email, resp = await generate_clarification_email(client, schema, opp_ctx)
            generated_by = "llm"
            model = resp.model
        except Exception as exc:
            log.warning("clarification email LLM failed: %s", exc)
            email = deterministic_clarification_email(schema, opp_ctx)
    else:
        email = deterministic_clarification_email(schema, opp_ctx)

    meta = dict(row.metadata_json or {})
    meta["clarification_email"] = {
        **email,
        "generated_by": generated_by,
        "model": model,
        "version": CLARIFICATION_VERSION,
        "generated_at": datetime.now(UTC).isoformat(),
    }
    row.metadata_json = meta

    await record_event(
        ctx.session,
        tenant_id=ctx.tenant.id,
        event_type=EVENT_CYBER_SCOPE_CLARIFICATION_EMAIL,
        entity_type="cyber_scope_analysis",
        entity_id=row.id,
        payload={"generated_by": generated_by},
        **_audit_actor_kwargs(ctx),
    )
    await ctx.session.commit()
    return EmailDraftOut(
        subject=email["subject"],
        body=email["body"],
        generated_by=generated_by,
        model=model,
    )


@router.post(
    "/tools/cyber-scope/analyses/{analysis_id}/prime-outreach-email",
    response_model=EmailDraftOut,
)
async def prime_outreach_email(
    analysis_id: UUID,
    ctx: Annotated[RequestContext, Depends(get_request_context)],
) -> EmailDraftOut:
    row, schema, opp = await _load_analysis_pair(ctx, analysis_id)
    opp_ctx = _opp_context(opp, row)
    client = _llm_client()
    generated_by = "template"
    model: str | None = None
    if client:
        try:
            email, resp = await generate_prime_outreach_email(client, schema, opp_ctx)
            generated_by = "llm"
            model = resp.model
        except Exception as exc:
            log.warning("prime outreach LLM failed: %s", exc)
            email = deterministic_prime_outreach(schema, opp_ctx)
    else:
        email = deterministic_prime_outreach(schema, opp_ctx)

    meta = dict(row.metadata_json or {})
    meta["prime_outreach_email"] = {
        **email,
        "generated_by": generated_by,
        "model": model,
        "version": PRIME_VERSION,
        "generated_at": datetime.now(UTC).isoformat(),
    }
    row.metadata_json = meta

    await record_event(
        ctx.session,
        tenant_id=ctx.tenant.id,
        event_type=EVENT_CYBER_SCOPE_PRIME_OUTREACH_EMAIL,
        entity_type="cyber_scope_analysis",
        entity_id=row.id,
        payload={"generated_by": generated_by},
        **_audit_actor_kwargs(ctx),
    )
    await ctx.session.commit()
    return EmailDraftOut(
        subject=email["subject"],
        body=email["body"],
        generated_by=generated_by,
        model=model,
    )


async def _feed_items_for_export(
    ctx: RequestContext,
    *,
    likelihood: str | None,
    min_score: int | None,
    limit: int,
) -> list[CyberScopeFeedItemOut]:
    tenant_id = ctx.tenant.id
    where = ["c.tenant_id = :tenant_id", "c.opportunity_id IS NOT NULL"]
    params: dict[str, Any] = {"tenant_id": str(tenant_id), "limit": limit}

    if likelihood:
        levels = [x.strip().upper() for x in likelihood.split(",") if x.strip()]
        where.append("c.overall_cyber_likelihood = ANY(:likelihoods)")
        params["likelihoods"] = levels
    if min_score is not None:
        where.append("c.score >= :min_score")
        params["min_score"] = min_score

    where_sql = " AND ".join(where)
    rows_sql = f"""
        SELECT c.id FROM cyber_scope_analyses c
        WHERE {where_sql}
        ORDER BY c.score DESC, c.updated_at DESC
        LIMIT :limit
    """
    ids = [r[0] for r in (await ctx.session.execute(text(rows_sql), params)).all()]
    items: list[CyberScopeFeedItemOut] = []
    for analysis_id in ids:
        row = (
            await ctx.session.execute(
                select(CyberScopeAnalysis).where(CyberScopeAnalysis.id == analysis_id)
            )
        ).scalar_one()
        opp = None
        if row.opportunity_id:
            opp = (
                await ctx.session.execute(
                    select(OpportunityRaw).where(OpportunityRaw.id == row.opportunity_id)
                )
            ).scalar_one_or_none()
        items.append(_row_to_feed_item(row, opp))
    return items


@router.get("/tools/cyber-scope/sam-search/status", response_model=list[SamSearchStatusOut])
async def sam_search_status(
    ctx: Annotated[RequestContext, Depends(get_request_context)],
) -> list[SamSearchStatusOut]:
    """Last run state for cyber-scope SAM search jobs (ingestion_state)."""
    searches = (
        (
            await ctx.session.execute(
                select(SavedSearch).where(SavedSearch.tenant_id == ctx.tenant.id)
            )
        )
        .scalars()
        .all()
    )
    out: list[SamSearchStatusOut] = []
    for search in searches:
        filters = dict(search.filters or {})
        filters["_name"] = search.name
        if not is_cyber_scope_saved_search(filters):
            continue
        for job in build_sam_cyber_jobs(
            saved_search_id=str(search.id),
            saved_search_name=search.name,
            tenant_id=str(ctx.tenant.id),
            filters=filters,
        ):
            row = (
                await ctx.session.execute(
                    select(IngestionState).where(
                        IngestionState.source == "sam_gov",
                        IngestionState.key == job.state_key,
                    )
                )
            ).scalar_one_or_none()
            out.append(
                SamSearchStatusOut(
                    state_key=job.state_key,
                    last_run_at=row.last_run_at.isoformat() if row and row.last_run_at else None,
                    last_success_at=(
                        row.last_success_at.isoformat() if row and row.last_success_at else None
                    ),
                    last_status=row.last_status if row else None,
                    last_error=row.last_error if row else None,
                )
            )
    return out


@router.post("/tools/cyber-scope/sam-search/run", response_model=SamSearchRunOut)
async def sam_search_run_now(
    ctx: Annotated[RequestContext, Depends(get_request_context)],
    lookback_days: int = 7,
    max_jobs: int = 12,
) -> SamSearchRunOut:
    """Trigger cyber SAM search for the current tenant (async via Celery)."""
    from mactech_workers.celery_app import celery_app

    try:
        celery_app.send_task(
            "mactech.cyber_scope.sam_search",
            kwargs={
                "tenant_slug": ctx.tenant.slug,
                "lookback_days": lookback_days,
                "max_jobs": max_jobs,
            },
        )
    except Exception as exc:
        raise HTTPException(status_code=503, detail=f"Could not enqueue: {exc}") from exc
    return SamSearchRunOut(
        status="enqueued",
        jobs_run=0,
        total_matched=0,
        total_upserts=0,
        errors=0,
    )


@router.get("/tools/cyber-scope/feed/export.csv")
async def export_feed_csv(
    ctx: Annotated[RequestContext, Depends(get_request_context)],
    likelihood: str | None = Query(None),
    min_score: int | None = Query(None, ge=0, le=100),
    limit: int = Query(500, ge=1, le=2000),
) -> Response:
    items = await _feed_items_for_export(
        ctx, likelihood=likelihood, min_score=min_score, limit=limit
    )
    csv_rows = [
        {
            "analysis_id": item.id,
            "opportunity_id": item.opportunity_id or "",
            "title": item.title or "",
            "agency": item.agency or "",
            "solicitation_number": item.solicitation_number or "",
            "likelihood": item.overall_cyber_likelihood,
            "pursuit_model": item.recommended_pursuit_model,
            "score": item.score,
            "ufgs_center_of_gravity": item.ufgs_center_of_gravity,
            "ufgs_tier_1_hit": item.ufgs_tier_1_hit,
            "top_ufgs_sections": "; ".join(item.top_ufgs_sections),
            "scan_pass": item.scan_pass,
            "attachments_pending": item.attachments_pending,
            "response_deadline": item.response_deadline or "",
            "updated_at": item.updated_at,
        }
        for item in items
    ]
    body = feed_rows_to_csv(csv_rows)
    filename = f"cyber-scope-feed-{datetime.now(UTC).strftime('%Y%m%d')}.csv"
    return Response(
        content=body,
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.get("/tools/cyber-scope/analyses/{analysis_id}/export.pdf")
async def export_analysis_pdf(
    analysis_id: UUID,
    ctx: Annotated[RequestContext, Depends(get_request_context)],
) -> Response:
    row, _schema, opp = await _load_analysis_pair(ctx, analysis_id)
    opp_ctx = _opp_context(opp, row)
    meta = row.metadata_json or {}
    clar = (
        meta.get("clarification_email")
        if isinstance(meta.get("clarification_email"), dict)
        else None
    )
    pdf = analysis_to_pdf_bytes(
        title=opp_ctx.title,
        agency=opp_ctx.agency,
        solicitation_number=opp_ctx.solicitation_number,
        analysis_summary=meta.get("llm_summary"),
        likelihood=row.overall_cyber_likelihood,
        pursuit_model=row.recommended_pursuit_model,
        score=row.score,
        top_signals=row.top_signals_json or [],
        hidden_scope=row.hidden_scope_indicators_json or [],
        missing=row.missing_requirements_json or [],
        clarification_email=clar,
    )
    safe_title = "".join(c if c.isalnum() or c in "-_" else "_" for c in opp_ctx.title[:40])
    filename = f"cyber-scope-{safe_title or analysis_id}.pdf"
    return Response(
        content=pdf,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
