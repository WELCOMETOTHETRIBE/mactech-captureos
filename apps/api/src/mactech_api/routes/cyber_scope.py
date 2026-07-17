"""Cyber Scope Contract Parser API — feed, scan, supplemental analyze."""

from __future__ import annotations

import hashlib
import logging
from typing import Annotated, Any
from uuid import UUID

from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile
from mactech_db.audit import record_event
from mactech_db.models import (
    EVENT_CYBER_SCOPE_ANALYSIS_RUN,
    CyberScopeAnalysis,
    OpportunityRaw,
    OpportunityScore,
)
from mactech_intelligence.cyber_scope import analyze_cyber_scope
from mactech_intelligence.cyber_scope.sources import CyberScopeTextSource
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import select, text
from sqlalchemy.dialects.postgresql import insert

from mactech_api.auth import RequestContext, get_request_context

log = logging.getLogger(__name__)
router = APIRouter(tags=["cyber-scope"])


class _Out(BaseModel):
    model_config = ConfigDict(from_attributes=True)


class AnalyzeTextIn(BaseModel):
    text: str = Field(min_length=10)
    title: str | None = None
    agency: str | None = None
    solicitation_number: str | None = None
    opportunity_id: str | None = None


class CyberScopeFeedItemOut(_Out):
    id: str
    opportunity_id: str | None
    title: str | None
    agency: str | None
    solicitation_number: str | None
    response_deadline: str | None
    overall_cyber_likelihood: str
    recommended_pursuit_model: str
    score: int
    ufgs_center_of_gravity: bool
    ufgs_tier_1_hit: bool
    top_ufgs_sections: list[str]
    top_signals: list[dict[str, Any]]
    scan_pass: str
    attachments_pending: bool = False
    updated_at: str
    opportunity_url: str | None = None


class CyberScopeFeedOut(_Out):
    total: int
    items: list[CyberScopeFeedItemOut]


class CyberScopeDownstreamOut(_Out):
    clause_risk_log_id: str | None = None
    bid_no_bid_review_id: str | None = None
    proposal_outline_id: str | None = None
    pursuit_id: str | None = None


class CyberScopeAnalysisOut(_Out):
    id: str
    opportunity_id: str | None
    source_type: str
    scan_pass: str
    parser_version: str
    overall_cyber_likelihood: str
    recommended_pursuit_model: str
    score: int
    ufgs_center_of_gravity: bool
    ufgs_tier_1_hit: bool
    detected_categories: dict[str, Any]
    top_signals: list[dict[str, Any]]
    hidden_scope_indicators: list[dict[str, Any]]
    missing_but_likely_requirements: list[str]
    suggested_actions: list[dict[str, Any]]
    evidence_snippets: list[dict[str, Any]]
    metadata: dict[str, Any]
    updated_at: str
    downstream: CyberScopeDownstreamOut | None = None


def _row_to_feed_item(row: CyberScopeAnalysis, opp: OpportunityRaw | None) -> CyberScopeFeedItemOut:
    meta = row.metadata_json or {}
    top_signals = row.top_signals_json or []
    cats = row.detected_categories_json or {}
    ufgs = cats.get("ufgs") or []
    top_ufgs = list(
        dict.fromkeys(u.get("normalized_term") for u in ufgs if u.get("normalized_term"))
    )[:6]
    attachments_pending = bool(
        row.scan_pass == "description_only"
        and opp is not None
        and not (opp.attachment_text and opp.attachment_text.strip())
    )
    return CyberScopeFeedItemOut(
        id=str(row.id),
        opportunity_id=str(row.opportunity_id) if row.opportunity_id else None,
        title=opp.title if opp else meta.get("title"),
        agency=opp.agency if opp else meta.get("agency"),
        solicitation_number=opp.solicitation_number if opp else meta.get("solicitation_number"),
        response_deadline=opp.response_deadline.isoformat()
        if opp and opp.response_deadline
        else None,
        overall_cyber_likelihood=row.overall_cyber_likelihood,
        recommended_pursuit_model=row.recommended_pursuit_model,
        score=row.score,
        ufgs_center_of_gravity=row.ufgs_center_of_gravity,
        ufgs_tier_1_hit=row.ufgs_tier_1_hit,
        top_ufgs_sections=top_ufgs or [],
        top_signals=top_signals[:5],
        scan_pass=row.scan_pass,
        attachments_pending=attachments_pending,
        updated_at=row.updated_at.isoformat(),
        opportunity_url=f"/opportunities/{row.opportunity_id}" if row.opportunity_id else None,
    )


def _row_to_detail(
    row: CyberScopeAnalysis,
    *,
    downstream: CyberScopeDownstreamOut | None = None,
) -> CyberScopeAnalysisOut:
    return CyberScopeAnalysisOut(
        id=str(row.id),
        opportunity_id=str(row.opportunity_id) if row.opportunity_id else None,
        source_type=row.source_type,
        scan_pass=row.scan_pass,
        parser_version=row.parser_version,
        overall_cyber_likelihood=row.overall_cyber_likelihood,
        recommended_pursuit_model=row.recommended_pursuit_model,
        score=row.score,
        ufgs_center_of_gravity=row.ufgs_center_of_gravity,
        ufgs_tier_1_hit=row.ufgs_tier_1_hit,
        detected_categories=row.detected_categories_json,
        top_signals=row.top_signals_json,
        hidden_scope_indicators=row.hidden_scope_indicators_json,
        missing_but_likely_requirements=row.missing_requirements_json,
        suggested_actions=row.suggested_actions_json,
        evidence_snippets=row.evidence_snippets_json,
        metadata=row.metadata_json,
        updated_at=row.updated_at.isoformat(),
        downstream=downstream,
    )


async def _persist_analysis(
    ctx: RequestContext,
    *,
    analysis,
    opportunity_id: UUID | None,
    source_type: str,
    source_hash: str,
    scan_pass: str,
) -> CyberScopeAnalysis:
    session = ctx.session
    cats = analysis.detected_categories
    values = {
        "tenant_id": ctx.tenant.id,
        "opportunity_id": opportunity_id,
        "source_type": source_type,
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
        "created_by_id": ctx.user.id if ctx.user else None,
    }
    if opportunity_id is not None:
        stmt = insert(CyberScopeAnalysis).values(**values)
        stmt = stmt.on_conflict_do_update(
            constraint="uq_cyber_scope_tenant_opp",
            set_={k: v for k, v in values.items() if k not in ("tenant_id", "opportunity_id")},
        )
        await session.execute(stmt)
        row = (
            await session.execute(
                select(CyberScopeAnalysis).where(
                    CyberScopeAnalysis.tenant_id == ctx.tenant.id,
                    CyberScopeAnalysis.opportunity_id == opportunity_id,
                )
            )
        ).scalar_one()
        score_row = (
            await session.execute(
                select(OpportunityScore).where(
                    OpportunityScore.tenant_id == ctx.tenant.id,
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
            }
    else:
        row = CyberScopeAnalysis(**values)
        session.add(row)
        await session.flush()

    await record_event(
        session,
        tenant_id=ctx.tenant.id,
        event_type=EVENT_CYBER_SCOPE_ANALYSIS_RUN,
        entity_type="cyber_scope_analysis",
        entity_id=row.id,
        actor_user_id=ctx.user.id if ctx.user else None,
        payload={
            "parser_version": analysis.parser_version,
            "score": analysis.score,
            "likelihood": analysis.overall_cyber_likelihood,
            "source_hash": source_hash,
        },
    )
    return row


@router.get("/tools/cyber-scope/feed", response_model=CyberScopeFeedOut)
async def cyber_scope_feed(
    ctx: Annotated[RequestContext, Depends(get_request_context)],
    likelihood: str | None = Query(None, description="Comma-separated: HIGH,CRITICAL"),
    pursuit_model: str | None = Query(None),
    center_of_gravity: bool | None = Query(None),
    ufgs_tier_1: bool | None = Query(None),
    min_score: int | None = Query(None, ge=0, le=100),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
) -> CyberScopeFeedOut:
    tenant_id = ctx.tenant.id
    where = ["c.tenant_id = :tenant_id", "c.opportunity_id IS NOT NULL"]
    params: dict[str, Any] = {"tenant_id": str(tenant_id), "limit": limit, "offset": offset}

    if likelihood:
        levels = [x.strip().upper() for x in likelihood.split(",") if x.strip()]
        where.append("c.overall_cyber_likelihood = ANY(:likelihoods)")
        params["likelihoods"] = levels
    if pursuit_model:
        where.append("c.recommended_pursuit_model = :pursuit_model")
        params["pursuit_model"] = pursuit_model
    if center_of_gravity is True:
        where.append("c.ufgs_center_of_gravity = true")
    if ufgs_tier_1 is True:
        where.append("c.ufgs_tier_1_hit = true")
    if min_score is not None:
        where.append("c.score >= :min_score")
        params["min_score"] = min_score

    where_sql = " AND ".join(where)
    count_sql = f"SELECT count(*) FROM cyber_scope_analyses c WHERE {where_sql}"
    rows_sql = f"""
        SELECT c.id FROM cyber_scope_analyses c
        WHERE {where_sql}
        ORDER BY c.score DESC, c.updated_at DESC
        LIMIT :limit OFFSET :offset
    """
    session = ctx.session
    total = (await session.execute(text(count_sql), params)).scalar_one()
    ids = [r[0] for r in (await session.execute(text(rows_sql), params)).all()]

    items: list[CyberScopeFeedItemOut] = []
    for analysis_id in ids:
        row = (
            await session.execute(
                select(CyberScopeAnalysis).where(CyberScopeAnalysis.id == analysis_id)
            )
        ).scalar_one()
        opp = None
        if row.opportunity_id:
            opp = (
                await session.execute(
                    select(OpportunityRaw).where(OpportunityRaw.id == row.opportunity_id)
                )
            ).scalar_one_or_none()
        items.append(_row_to_feed_item(row, opp))

    return CyberScopeFeedOut(total=int(total), items=items)


@router.get("/tools/cyber-scope/analyses/{analysis_id}", response_model=CyberScopeAnalysisOut)
async def get_analysis(
    analysis_id: UUID,
    ctx: Annotated[RequestContext, Depends(get_request_context)],
) -> CyberScopeAnalysisOut:
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
    from mactech_api.routes.cyber_scope_downstream import downstream_links

    links = await downstream_links(ctx, analysis_id)
    return _row_to_detail(
        row,
        downstream=CyberScopeDownstreamOut(
            clause_risk_log_id=links.clause_risk_log_id,
            bid_no_bid_review_id=links.bid_no_bid_review_id,
            proposal_outline_id=links.proposal_outline_id,
            pursuit_id=links.pursuit_id,
        ),
    )


@router.post(
    "/tools/cyber-scope/opportunities/{opportunity_id}/rescan",
    response_model=CyberScopeAnalysisOut,
)
async def rescan_opportunity(
    opportunity_id: UUID,
    ctx: Annotated[RequestContext, Depends(get_request_context)],
) -> CyberScopeAnalysisOut:
    opp = (
        await ctx.session.execute(select(OpportunityRaw).where(OpportunityRaw.id == opportunity_id))
    ).scalar_one_or_none()
    if opp is None:
        raise HTTPException(status_code=404, detail="Opportunity not found")

    source = CyberScopeTextSource.from_opportunity(
        title=opp.title,
        description_text=opp.description_text,
        attachment_text=opp.attachment_text,
        opportunity_id=str(opp.id),
        agency=opp.agency,
        solicitation_number=opp.solicitation_number,
        source_url=opp.description_url,
    )
    analysis = analyze_cyber_scope(source)
    source_hash = hashlib.sha256(source.combined_text.encode()).hexdigest()
    row = await _persist_analysis(
        ctx,
        analysis=analysis,
        opportunity_id=opportunity_id,
        source_type="SAM_INGEST",
        source_hash=source_hash,
        scan_pass=source.scan_pass,
    )
    await ctx.session.commit()
    return _row_to_detail(row)


@router.post("/tools/cyber-scope/analyze", response_model=CyberScopeAnalysisOut)
async def analyze_text(
    body: AnalyzeTextIn,
    ctx: Annotated[RequestContext, Depends(get_request_context)],
) -> CyberScopeAnalysisOut:
    metadata = {
        "title": body.title,
        "agency": body.agency,
        "solicitation_number": body.solicitation_number,
    }
    source = CyberScopeTextSource.from_paste(body.text, metadata)
    analysis = analyze_cyber_scope(source)
    source_hash = hashlib.sha256(body.text.encode()).hexdigest()
    opp_id = UUID(body.opportunity_id) if body.opportunity_id else None
    row = await _persist_analysis(
        ctx,
        analysis=analysis,
        opportunity_id=opp_id,
        source_type="PASTED_TEXT",
        source_hash=source_hash,
        scan_pass="description_only",
    )
    await ctx.session.commit()
    return _row_to_detail(row)


@router.post("/tools/cyber-scope/analyze/upload", response_model=CyberScopeAnalysisOut)
async def analyze_upload(
    ctx: Annotated[RequestContext, Depends(get_request_context)],
    file: UploadFile = File(...),
    title: str | None = None,
) -> CyberScopeAnalysisOut:
    try:
        import fitz  # type: ignore[import-untyped]
    except ImportError as exc:
        raise HTTPException(status_code=500, detail="PDF support unavailable") from exc

    blob = await file.read()
    if len(blob) > 20 * 1024 * 1024:
        raise HTTPException(status_code=413, detail="File too large (max 20 MB)")
    text = ""
    if file.filename and file.filename.lower().endswith(".pdf"):
        with fitz.open(stream=blob, filetype="pdf") as doc:
            text = "\n".join(page.get_text() for page in doc)[:25_000]
    else:
        text = blob.decode("utf-8", errors="replace")[:25_000]

    if len(text.strip()) < 10:
        raise HTTPException(status_code=400, detail="Could not extract enough text")

    source = CyberScopeTextSource.from_paste(
        text, {"title": title or file.filename, "source_name": file.filename}
    )
    analysis = analyze_cyber_scope(source)
    source_hash = hashlib.sha256(text.encode()).hexdigest()
    row = await _persist_analysis(
        ctx,
        analysis=analysis,
        opportunity_id=None,
        source_type="UPLOAD",
        source_hash=source_hash,
        scan_pass="description_only",
    )
    await ctx.session.commit()
    return _row_to_detail(row)
