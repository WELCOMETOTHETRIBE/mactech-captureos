"""Cyber scope downstream capture actions — clause risk, bid review, outline, pipeline."""

from __future__ import annotations

from typing import Annotated, Any
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from mactech_db.audit import record_event
from mactech_db.models import (
    EVENT_CYBER_SCOPE_ADDED_TO_PIPELINE,
    EVENT_CYBER_SCOPE_BID_REVIEW_CREATED,
    EVENT_CYBER_SCOPE_CLAUSE_RISK_LOG_CREATED,
    EVENT_CYBER_SCOPE_PROPOSAL_OUTLINE_CREATED,
    EVENT_PURSUIT_CREATED,
    BidNoBidReview,
    ClauseRiskLog,
    ClauseRiskLogEntry,
    CyberScopeAnalysis,
    OpportunityRaw,
    OpportunityScore,
    ProposalOutline,
    Pursuit,
)
from mactech_intelligence.cyber_scope.db_adapter import schema_from_persisted
from mactech_intelligence.cyber_scope.downstream import (
    build_bid_no_bid_review,
    build_clause_risk_entries,
    build_proposal_outline,
)
from mactech_intelligence.cyber_scope.schemas import (
    CyberScopeAnalysis as CyberScopeAnalysisSchema,
)
from pydantic import BaseModel, ConfigDict
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from mactech_api.auth import RequestContext, get_request_context

router = APIRouter(tags=["cyber-scope"])


class _Out(BaseModel):
    model_config = ConfigDict(from_attributes=True)


class DownstreamLinksOut(_Out):
    clause_risk_log_id: str | None = None
    bid_no_bid_review_id: str | None = None
    proposal_outline_id: str | None = None
    pursuit_id: str | None = None


class ClauseRiskEntryOut(_Out):
    id: str
    sort_order: int
    category: str
    severity: str
    reference: str
    finding: str
    evidence: str | None
    mitigation: str | None


class ClauseRiskLogOut(_Out):
    id: str
    opportunity_id: str
    cyber_scope_analysis_id: str
    title: str
    status: str
    entry_count: int
    entries: list[ClauseRiskEntryOut]
    created_at: str
    updated_at: str


class BidNoBidReviewOut(_Out):
    id: str
    opportunity_id: str
    cyber_scope_analysis_id: str
    pursuit_id: str | None
    recommended_decision: str
    cyber_scope_summary: str
    factors: list[dict[str, Any]]
    rationale_draft: str
    pursuit_model: str | None
    likelihood: str | None
    score: int | None
    created_at: str
    updated_at: str


class ProposalOutlineOut(_Out):
    id: str
    opportunity_id: str
    cyber_scope_analysis_id: str
    title: str
    sections: list[dict[str, Any]]
    status: str
    created_at: str
    updated_at: str


class AddToPipelineOut(_Out):
    pursuit_id: str
    created: bool
    bid_no_bid_review_id: str | None = None
    opportunity_url: str


def _audit_actor_kwargs(ctx: RequestContext) -> dict[str, Any]:
    if ctx.user:
        return {
            "actor_user_id": ctx.user.id,
            "actor_label": ctx.user.email,
        }
    return {"actor_label": "system:api"}


def _row_to_schema(row: CyberScopeAnalysis) -> CyberScopeAnalysisSchema:
    return schema_from_persisted(
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


async def _load_analysis(
    ctx: RequestContext, analysis_id: UUID
) -> tuple[CyberScopeAnalysis, CyberScopeAnalysisSchema, OpportunityRaw | None]:
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
    return row, _row_to_schema(row), opp


async def downstream_links(ctx: RequestContext, analysis_id: UUID) -> DownstreamLinksOut:
    tenant_id = ctx.tenant.id
    log = (
        await ctx.session.execute(
            select(ClauseRiskLog.id).where(
                ClauseRiskLog.tenant_id == tenant_id,
                ClauseRiskLog.cyber_scope_analysis_id == analysis_id,
            )
        )
    ).scalar_one_or_none()
    review = (
        await ctx.session.execute(
            select(BidNoBidReview.id, BidNoBidReview.pursuit_id).where(
                BidNoBidReview.tenant_id == tenant_id,
                BidNoBidReview.cyber_scope_analysis_id == analysis_id,
            )
        )
    ).first()
    outline = (
        await ctx.session.execute(
            select(ProposalOutline.id).where(
                ProposalOutline.tenant_id == tenant_id,
                ProposalOutline.cyber_scope_analysis_id == analysis_id,
            )
        )
    ).scalar_one_or_none()
    pursuit_id = None
    row = (
        await ctx.session.execute(
            select(CyberScopeAnalysis.opportunity_id).where(
                CyberScopeAnalysis.id == analysis_id,
                CyberScopeAnalysis.tenant_id == tenant_id,
            )
        )
    ).scalar_one_or_none()
    if row:
        p = (
            await ctx.session.execute(
                select(Pursuit.id).where(
                    Pursuit.tenant_id == tenant_id,
                    Pursuit.opportunity_id == row,
                )
            )
        ).scalar_one_or_none()
        pursuit_id = p
    return DownstreamLinksOut(
        clause_risk_log_id=str(log) if log else None,
        bid_no_bid_review_id=str(review[0]) if review else None,
        proposal_outline_id=str(outline) if outline else None,
        pursuit_id=str(pursuit_id)
        if pursuit_id
        else (str(review[1]) if review and review[1] else None),
    )


def _log_to_out(log: ClauseRiskLog, entries: list[ClauseRiskLogEntry]) -> ClauseRiskLogOut:
    return ClauseRiskLogOut(
        id=str(log.id),
        opportunity_id=str(log.opportunity_id),
        cyber_scope_analysis_id=str(log.cyber_scope_analysis_id),
        title=log.title,
        status=log.status,
        entry_count=len(entries),
        entries=[
            ClauseRiskEntryOut(
                id=str(e.id),
                sort_order=e.sort_order,
                category=e.category,
                severity=e.severity,
                reference=e.reference,
                finding=e.finding,
                evidence=e.evidence,
                mitigation=e.mitigation,
            )
            for e in entries
        ],
        created_at=log.created_at.isoformat(),
        updated_at=log.updated_at.isoformat(),
    )


@router.post(
    "/tools/cyber-scope/analyses/{analysis_id}/clause-risk-log",
    response_model=ClauseRiskLogOut,
)
async def create_clause_risk_log(
    analysis_id: UUID,
    ctx: Annotated[RequestContext, Depends(get_request_context)],
) -> ClauseRiskLogOut:
    row, schema, opp = await _load_analysis(ctx, analysis_id)
    if row.opportunity_id is None:
        raise HTTPException(
            status_code=400,
            detail="Clause risk log requires a SAM-linked opportunity",
        )

    existing = (
        await ctx.session.execute(
            select(ClauseRiskLog).where(
                ClauseRiskLog.tenant_id == ctx.tenant.id,
                ClauseRiskLog.cyber_scope_analysis_id == analysis_id,
            )
        )
    ).scalar_one_or_none()
    if existing:
        entries = (
            (
                await ctx.session.execute(
                    select(ClauseRiskLogEntry)
                    .where(ClauseRiskLogEntry.log_id == existing.id)
                    .order_by(ClauseRiskLogEntry.sort_order)
                )
            )
            .scalars()
            .all()
        )
        return _log_to_out(existing, list(entries))

    title = f"Clause risk log — {(opp.title if opp else 'Opportunity')[:200]}"
    prefill = build_clause_risk_entries(schema)
    log = ClauseRiskLog(
        tenant_id=ctx.tenant.id,
        opportunity_id=row.opportunity_id,
        cyber_scope_analysis_id=analysis_id,
        title=title,
        status="draft",
        created_by_id=ctx.user.id if ctx.user else None,
    )
    ctx.session.add(log)
    await ctx.session.flush()

    for item in prefill:
        ctx.session.add(
            ClauseRiskLogEntry(
                log_id=log.id,
                tenant_id=ctx.tenant.id,
                sort_order=item["sort_order"],
                category=item["category"],
                severity=item["severity"],
                reference=item["reference"],
                finding=item["finding"],
                evidence=item.get("evidence"),
                mitigation=item.get("mitigation"),
            )
        )

    await record_event(
        ctx.session,
        tenant_id=ctx.tenant.id,
        event_type=EVENT_CYBER_SCOPE_CLAUSE_RISK_LOG_CREATED,
        entity_type="clause_risk_log",
        entity_id=log.id,
        payload={
            "analysis_id": str(analysis_id),
            "opportunity_id": str(row.opportunity_id),
            "entry_count": len(prefill),
        },
        **_audit_actor_kwargs(ctx),
    )
    await ctx.session.commit()

    entries = (
        (
            await ctx.session.execute(
                select(ClauseRiskLogEntry)
                .where(ClauseRiskLogEntry.log_id == log.id)
                .order_by(ClauseRiskLogEntry.sort_order)
            )
        )
        .scalars()
        .all()
    )
    return _log_to_out(log, list(entries))


@router.get(
    "/tools/cyber-scope/clause-risk-logs/{log_id}",
    response_model=ClauseRiskLogOut,
)
async def get_clause_risk_log(
    log_id: UUID,
    ctx: Annotated[RequestContext, Depends(get_request_context)],
) -> ClauseRiskLogOut:
    log = (
        await ctx.session.execute(
            select(ClauseRiskLog).where(
                ClauseRiskLog.id == log_id,
                ClauseRiskLog.tenant_id == ctx.tenant.id,
            )
        )
    ).scalar_one_or_none()
    if log is None:
        raise HTTPException(status_code=404, detail="Clause risk log not found")
    entries = (
        (
            await ctx.session.execute(
                select(ClauseRiskLogEntry)
                .where(ClauseRiskLogEntry.log_id == log.id)
                .order_by(ClauseRiskLogEntry.sort_order)
            )
        )
        .scalars()
        .all()
    )
    return _log_to_out(log, list(entries))


@router.post(
    "/tools/cyber-scope/analyses/{analysis_id}/bid-no-bid-review",
    response_model=BidNoBidReviewOut,
)
async def create_bid_no_bid_review(
    analysis_id: UUID,
    ctx: Annotated[RequestContext, Depends(get_request_context)],
) -> BidNoBidReviewOut:
    row, schema, opp = await _load_analysis(ctx, analysis_id)
    if row.opportunity_id is None:
        raise HTTPException(status_code=400, detail="Bid review requires a SAM-linked opportunity")

    existing = (
        await ctx.session.execute(
            select(BidNoBidReview).where(
                BidNoBidReview.tenant_id == ctx.tenant.id,
                BidNoBidReview.cyber_scope_analysis_id == analysis_id,
            )
        )
    ).scalar_one_or_none()
    if existing:
        return _review_to_out(existing)

    prefill = build_bid_no_bid_review(
        schema,
        opportunity_title=opp.title if opp else None,
        agency=opp.agency if opp else None,
    )
    review = BidNoBidReview(
        tenant_id=ctx.tenant.id,
        opportunity_id=row.opportunity_id,
        cyber_scope_analysis_id=analysis_id,
        recommended_decision=prefill["recommended_decision"],
        cyber_scope_summary=prefill["cyber_scope_summary"],
        factors_json=prefill["factors"],
        rationale_draft=prefill["rationale_draft"],
        pursuit_model=prefill["pursuit_model"],
        likelihood=prefill["likelihood"],
        score=prefill["score"],
        created_by_id=ctx.user.id if ctx.user else None,
    )
    ctx.session.add(review)
    await ctx.session.flush()

    await record_event(
        ctx.session,
        tenant_id=ctx.tenant.id,
        event_type=EVENT_CYBER_SCOPE_BID_REVIEW_CREATED,
        entity_type="bid_no_bid_review",
        entity_id=review.id,
        payload={"analysis_id": str(analysis_id), "opportunity_id": str(row.opportunity_id)},
        **_audit_actor_kwargs(ctx),
    )
    await ctx.session.commit()
    return _review_to_out(review)


def _review_to_out(review: BidNoBidReview) -> BidNoBidReviewOut:
    return BidNoBidReviewOut(
        id=str(review.id),
        opportunity_id=str(review.opportunity_id),
        cyber_scope_analysis_id=str(review.cyber_scope_analysis_id),
        pursuit_id=str(review.pursuit_id) if review.pursuit_id else None,
        recommended_decision=review.recommended_decision,
        cyber_scope_summary=review.cyber_scope_summary,
        factors=review.factors_json or [],
        rationale_draft=review.rationale_draft,
        pursuit_model=review.pursuit_model,
        likelihood=review.likelihood,
        score=review.score,
        created_at=review.created_at.isoformat(),
        updated_at=review.updated_at.isoformat(),
    )


@router.get(
    "/tools/cyber-scope/bid-no-bid-reviews/{review_id}",
    response_model=BidNoBidReviewOut,
)
async def get_bid_no_bid_review(
    review_id: UUID,
    ctx: Annotated[RequestContext, Depends(get_request_context)],
) -> BidNoBidReviewOut:
    review = (
        await ctx.session.execute(
            select(BidNoBidReview).where(
                BidNoBidReview.id == review_id,
                BidNoBidReview.tenant_id == ctx.tenant.id,
            )
        )
    ).scalar_one_or_none()
    if review is None:
        raise HTTPException(status_code=404, detail="Bid/no-bid review not found")
    return _review_to_out(review)


@router.post(
    "/tools/cyber-scope/analyses/{analysis_id}/proposal-outline",
    response_model=ProposalOutlineOut,
)
async def create_proposal_outline(
    analysis_id: UUID,
    ctx: Annotated[RequestContext, Depends(get_request_context)],
) -> ProposalOutlineOut:
    row, schema, opp = await _load_analysis(ctx, analysis_id)
    if row.opportunity_id is None:
        raise HTTPException(status_code=400, detail="Outline requires a SAM-linked opportunity")

    existing = (
        await ctx.session.execute(
            select(ProposalOutline).where(
                ProposalOutline.tenant_id == ctx.tenant.id,
                ProposalOutline.cyber_scope_analysis_id == analysis_id,
            )
        )
    ).scalar_one_or_none()
    if existing:
        return _outline_to_out(existing)

    prefill = build_proposal_outline(schema, opportunity_title=opp.title if opp else None)
    outline = ProposalOutline(
        tenant_id=ctx.tenant.id,
        opportunity_id=row.opportunity_id,
        cyber_scope_analysis_id=analysis_id,
        title=prefill["title"],
        sections_json=prefill["sections"],
        status="draft",
        created_by_id=ctx.user.id if ctx.user else None,
    )
    ctx.session.add(outline)
    await ctx.session.flush()

    await record_event(
        ctx.session,
        tenant_id=ctx.tenant.id,
        event_type=EVENT_CYBER_SCOPE_PROPOSAL_OUTLINE_CREATED,
        entity_type="proposal_outline",
        entity_id=outline.id,
        payload={"analysis_id": str(analysis_id), "opportunity_id": str(row.opportunity_id)},
        **_audit_actor_kwargs(ctx),
    )
    await ctx.session.commit()
    return _outline_to_out(outline)


def _outline_to_out(outline: ProposalOutline) -> ProposalOutlineOut:
    return ProposalOutlineOut(
        id=str(outline.id),
        opportunity_id=str(outline.opportunity_id),
        cyber_scope_analysis_id=str(outline.cyber_scope_analysis_id),
        title=outline.title,
        sections=outline.sections_json or [],
        status=outline.status,
        created_at=outline.created_at.isoformat(),
        updated_at=outline.updated_at.isoformat(),
    )


@router.get(
    "/tools/cyber-scope/proposal-outlines/{outline_id}",
    response_model=ProposalOutlineOut,
)
async def get_proposal_outline(
    outline_id: UUID,
    ctx: Annotated[RequestContext, Depends(get_request_context)],
) -> ProposalOutlineOut:
    outline = (
        await ctx.session.execute(
            select(ProposalOutline).where(
                ProposalOutline.id == outline_id,
                ProposalOutline.tenant_id == ctx.tenant.id,
            )
        )
    ).scalar_one_or_none()
    if outline is None:
        raise HTTPException(status_code=404, detail="Proposal outline not found")
    return _outline_to_out(outline)


@router.get(
    "/tools/cyber-scope/analyses/{analysis_id}/downstream",
    response_model=DownstreamLinksOut,
)
async def get_downstream_links(
    analysis_id: UUID,
    ctx: Annotated[RequestContext, Depends(get_request_context)],
) -> DownstreamLinksOut:
    await _load_analysis(ctx, analysis_id)
    return await downstream_links(ctx, analysis_id)


@router.post(
    "/tools/cyber-scope/analyses/{analysis_id}/add-to-pipeline",
    response_model=AddToPipelineOut,
)
async def add_to_pipeline(
    analysis_id: UUID,
    ctx: Annotated[RequestContext, Depends(get_request_context)],
) -> AddToPipelineOut:
    row, schema, opp = await _load_analysis(ctx, analysis_id)
    if row.opportunity_id is None:
        raise HTTPException(
            status_code=400, detail="Pipeline add requires a SAM-linked opportunity"
        )

    tenant_id = ctx.tenant.id
    opp_id = row.opportunity_id
    created = False

    pursuit = (
        await ctx.session.execute(
            select(Pursuit).where(
                Pursuit.tenant_id == tenant_id,
                Pursuit.opportunity_id == opp_id,
            )
        )
    ).scalar_one_or_none()

    if pursuit is None:
        owner_id = None
        score_row = (
            await ctx.session.execute(
                select(OpportunityScore).where(
                    OpportunityScore.tenant_id == tenant_id,
                    OpportunityScore.opportunity_id == opp_id,
                )
            )
        ).scalar_one_or_none()
        if score_row and score_row.assigned_founder_id:
            owner_id = score_row.assigned_founder_id

        notes = (
            f"Added from Cyber Scope Parser ({schema.overall_cyber_likelihood}, "
            f"score {schema.score}). Model: {schema.recommended_pursuit_model}."
        )
        pursuit = Pursuit(
            tenant_id=tenant_id,
            opportunity_id=opp_id,
            owner_founder_id=owner_id,
            stage="qualify",
            notes=notes,
        )
        ctx.session.add(pursuit)
        try:
            await ctx.session.flush()
        except IntegrityError:
            await ctx.session.rollback()
            pursuit = (
                await ctx.session.execute(
                    select(Pursuit).where(
                        Pursuit.tenant_id == tenant_id,
                        Pursuit.opportunity_id == opp_id,
                    )
                )
            ).scalar_one()
        else:
            created = True
            await record_event(
                ctx.session,
                tenant_id=tenant_id,
                event_type=EVENT_PURSUIT_CREATED,
                entity_type="pursuit",
                entity_id=pursuit.id,
                payload={
                    "opportunity_id": str(opp_id),
                    "stage": "qualify",
                    "source": "cyber_scope",
                },
                **_audit_actor_kwargs(ctx),
            )

    review_row = (
        await ctx.session.execute(
            select(BidNoBidReview).where(
                BidNoBidReview.tenant_id == tenant_id,
                BidNoBidReview.cyber_scope_analysis_id == analysis_id,
            )
        )
    ).scalar_one_or_none()

    if review_row is None:
        prefill = build_bid_no_bid_review(
            schema,
            opportunity_title=opp.title if opp else None,
            agency=opp.agency if opp else None,
        )
        review_row = BidNoBidReview(
            tenant_id=tenant_id,
            opportunity_id=opp_id,
            cyber_scope_analysis_id=analysis_id,
            pursuit_id=pursuit.id,
            recommended_decision=prefill["recommended_decision"],
            cyber_scope_summary=prefill["cyber_scope_summary"],
            factors_json=prefill["factors"],
            rationale_draft=prefill["rationale_draft"],
            pursuit_model=prefill["pursuit_model"],
            likelihood=prefill["likelihood"],
            score=prefill["score"],
            created_by_id=ctx.user.id if ctx.user else None,
        )
        ctx.session.add(review_row)
        await ctx.session.flush()
    else:
        review_row.pursuit_id = pursuit.id

    if pursuit.bid_rationale is None or not pursuit.bid_rationale.strip():
        pursuit.bid_rationale = review_row.rationale_draft
        if ctx.user:
            pursuit.bid_decided_by_user_id = None
            pursuit.bid_decided_at = None

    await record_event(
        ctx.session,
        tenant_id=tenant_id,
        event_type=EVENT_CYBER_SCOPE_ADDED_TO_PIPELINE,
        entity_type="pursuit",
        entity_id=pursuit.id,
        payload={
            "analysis_id": str(analysis_id),
            "opportunity_id": str(opp_id),
            "created": created,
            "bid_review_id": str(review_row.id),
        },
        **_audit_actor_kwargs(ctx),
    )
    await ctx.session.commit()

    return AddToPipelineOut(
        pursuit_id=str(pursuit.id),
        created=created,
        bid_no_bid_review_id=str(review_row.id),
        opportunity_url=f"/opportunities/{opp_id}",
    )
