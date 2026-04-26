"""Per-opportunity natural-language Q&A.

Phase 3 Week 11 (UX Sprint 3). The "Ask Claude about this opp" panel
on the detail page. Synchronous (5–15s typical); streaming variant
ships next sprint.

Endpoints:
  POST /opportunities/{id}/ask        ask + persist
  GET  /opportunities/{id}/questions  history (newest first, capped)
  DELETE /opportunity-questions/{id}  remove a single Q&A round
"""

from __future__ import annotations

import logging
import os
from datetime import date, datetime, timezone
from typing import Annotated, Any
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import desc, select

from mactech_api.auth import RequestContext, get_request_context
from mactech_db.models import (
    CapabilityStatement,
    Founder,
    OpportunityEnriched,
    OpportunityQuestion,
    OpportunityRaw,
    OpportunityScore,
    PastPerformance,
    TeamingPartner,
)
from mactech_intelligence import (
    ASK_STARTERS,
    AnthropicLLMClient,
    AskFirmContext,
    AskInput,
    AskOpportunityContext,
    ask_about_opportunity,
)
from mactech_intelligence.ask_about_opportunity import PROMPT_VERSION

log = logging.getLogger(__name__)
router = APIRouter(tags=["ask"])

QUESTION_MAX_LEN = 1000
HISTORY_LIMIT = 25


class _Out(BaseModel):
    model_config = ConfigDict(from_attributes=True)


class AskerRef(_Out):
    slug: str
    full_name: str


class QuestionOut(_Out):
    id: str
    question: str
    answer: str
    starter_kind: str | None
    asked_by: AskerRef | None
    model: str | None
    input_tokens: int | None
    output_tokens: int | None
    created_at: str


class QuestionListResponse(_Out):
    total: int
    items: list[QuestionOut]
    starters: dict[str, str]


class AskRequest(BaseModel):
    question: str = Field(min_length=2, max_length=QUESTION_MAX_LEN)
    starter_kind: str | None = Field(default=None, max_length=32)


def _q_out(q: OpportunityQuestion, asker: Founder | None) -> QuestionOut:
    return QuestionOut(
        id=str(q.id),
        question=q.question,
        answer=q.answer,
        starter_kind=q.starter_kind,
        asked_by=(
            AskerRef(slug=asker.slug, full_name=asker.full_name) if asker else None
        ),
        model=q.model,
        input_tokens=q.input_tokens,
        output_tokens=q.output_tokens,
        created_at=q.created_at.isoformat(),
    )


def _resolve_question(starter_kind: str | None, raw_question: str) -> str:
    if starter_kind and starter_kind in ASK_STARTERS:
        return ASK_STARTERS[starter_kind]
    return raw_question.strip()


async def _build_ask_input(
    ctx: RequestContext,
    opp: OpportunityRaw,
    enr: OpportunityEnriched | None,
    score: OpportunityScore | None,
    raw_question: str,
    starter_kind: str | None,
) -> AskInput:
    session = ctx.session
    tenant = ctx.tenant

    caps = (
        await session.execute(
            select(CapabilityStatement).where(
                CapabilityStatement.tenant_id == tenant.id
            )
        )
    ).scalars().all()
    pp = (
        await session.execute(
            select(PastPerformance)
            .where(PastPerformance.tenant_id == tenant.id)
            .order_by(PastPerformance.period_end.desc().nulls_last())
        )
    ).scalars().all()
    partners = (
        await session.execute(
            select(TeamingPartner).where(
                TeamingPartner.tenant_id == tenant.id,
                TeamingPartner.status == "active",
            )
        )
    ).scalars().all()
    founders = (
        await session.execute(
            select(Founder)
            .where(Founder.tenant_id == tenant.id)
            .order_by(Founder.full_name)
        )
    ).scalars().all()

    return AskInput(
        question=_resolve_question(starter_kind, raw_question),
        starter_kind=starter_kind,
        opportunity=AskOpportunityContext(
            title=opp.title,
            agency=opp.agency,
            notice_type=opp.notice_type,
            set_aside=opp.set_aside,
            naics_code=opp.naics_code,
            posted_at=opp.posted_at,
            response_deadline=opp.response_deadline,
            description=opp.description_text,
            score=score.score if score else None,
            score_breakdown=dict(score.score_breakdown) if score else None,
            why_it_matters=score.why_it_matters if score else None,
            incumbent_name=enr.incumbent_name if enr else None,
            incumbent_amount=(
                float(enr.incumbent_award_amount)
                if enr and enr.incumbent_award_amount is not None
                else None
            ),
            incumbent_end_date=(
                enr.incumbent_end_date.isoformat()
                if enr and enr.incumbent_end_date
                else None
            ),
        ),
        firm=AskFirmContext(
            tenant_name=tenant.name,
            uei=tenant.uei,
            cage_code=tenant.cage_code,
            plan=tenant.plan,
            set_aside_certifications=[],
            capability_titles_and_summaries=[(c.title, c.summary) for c in caps],
            past_performance_summaries=[
                _summarize_pp(p) for p in pp[:8]
            ],
            teaming_partner_summaries=[
                _summarize_partner(p) for p in partners[:8]
            ],
            founder_summaries=[
                f"{f.full_name}, {f.title} ({f.pillar} pillar)"
                for f in founders
            ],
        ),
    )


def _summarize_pp(p: PastPerformance) -> str:
    parts = [p.title, f"({p.role})"]
    if p.customer_agency:
        parts.append(f"customer: {p.customer_agency}")
    if p.contract_value is not None:
        parts.append(f"${float(p.contract_value):,.0f}")
    parts.append("— " + p.summary[:200])
    return " ".join(parts)


def _summarize_partner(p: TeamingPartner) -> str:
    bits = [p.name]
    if p.capabilities:
        bits.append(f"caps: {', '.join(p.capabilities[:5])}")
    if p.set_aside_certifications:
        bits.append(f"certs: {', '.join(p.set_aside_certifications)}")
    return " | ".join(bits)


@router.post(
    "/opportunities/{opportunity_id}/ask",
    response_model=QuestionOut,
    status_code=status.HTTP_201_CREATED,
)
async def ask_question(
    opportunity_id: UUID,
    body: AskRequest,
    ctx: Annotated[RequestContext, Depends(get_request_context)],
) -> QuestionOut:
    api_key = os.environ.get("ANTHROPIC_API_KEY", "")
    if not api_key:
        raise HTTPException(
            status_code=503,
            detail="ANTHROPIC_API_KEY not configured on the API service.",
        )

    opp = (
        await ctx.session.execute(
            select(OpportunityRaw).where(OpportunityRaw.id == opportunity_id)
        )
    ).scalar_one_or_none()
    if opp is None:
        raise HTTPException(status_code=404, detail="opportunity not found")

    enr = (
        await ctx.session.execute(
            select(OpportunityEnriched).where(
                OpportunityEnriched.opportunity_id == opportunity_id
            )
        )
    ).scalar_one_or_none()
    score = (
        await ctx.session.execute(
            select(OpportunityScore).where(
                OpportunityScore.tenant_id == ctx.tenant.id,
                OpportunityScore.opportunity_id == opportunity_id,
            )
        )
    ).scalar_one_or_none()

    inp = await _build_ask_input(ctx, opp, enr, score, body.question, body.starter_kind)

    client = AnthropicLLMClient(api_key=api_key)
    try:
        response = await ask_about_opportunity(client, inp)
    except Exception as exc:
        log.exception("ask_about_opportunity failed: %s", exc)
        raise HTTPException(
            status_code=502,
            detail=f"Anthropic call failed: {exc.__class__.__name__}",
        ) from exc

    persisted_question = inp.question
    q = OpportunityQuestion(
        tenant_id=ctx.tenant.id,
        opportunity_id=opportunity_id,
        asked_by_founder_id=ctx.founder.id if ctx.founder else None,
        question=persisted_question,
        answer=response.text.strip(),
        starter_kind=body.starter_kind if body.starter_kind in ASK_STARTERS else None,
        model=response.model,
        input_tokens=response.input_tokens,
        output_tokens=response.output_tokens,
        prompt_version=PROMPT_VERSION,
    )
    ctx.session.add(q)
    await ctx.session.flush()
    return _q_out(q, ctx.founder)


@router.get(
    "/opportunities/{opportunity_id}/questions",
    response_model=QuestionListResponse,
)
async def list_questions(
    opportunity_id: UUID,
    ctx: Annotated[RequestContext, Depends(get_request_context)],
) -> QuestionListResponse:
    rows = (
        await ctx.session.execute(
            select(OpportunityQuestion, Founder)
            .outerjoin(
                Founder, Founder.id == OpportunityQuestion.asked_by_founder_id
            )
            .where(
                OpportunityQuestion.tenant_id == ctx.tenant.id,
                OpportunityQuestion.opportunity_id == opportunity_id,
            )
            .order_by(desc(OpportunityQuestion.created_at))
            .limit(HISTORY_LIMIT)
        )
    ).all()
    items = [_q_out(q, asker) for q, asker in rows]
    return QuestionListResponse(
        total=len(items), items=items, starters=dict(ASK_STARTERS)
    )


@router.delete(
    "/opportunity-questions/{question_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def delete_question(
    question_id: UUID,
    ctx: Annotated[RequestContext, Depends(get_request_context)],
) -> None:
    q = (
        await ctx.session.execute(
            select(OpportunityQuestion).where(
                OpportunityQuestion.id == question_id,
                OpportunityQuestion.tenant_id == ctx.tenant.id,
            )
        )
    ).scalar_one_or_none()
    if q is None:
        raise HTTPException(status_code=404, detail="question not found")
    await ctx.session.delete(q)
    await ctx.session.flush()


# Suppress unused-import false positive — reserved for future date-typed
# fields on QuestionOut.
_ = (date, datetime, timezone, Any)
