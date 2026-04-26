"""Per-opportunity natural-language Q&A.

Phase 3 Week 11 (UX Sprint 3). The "Ask Claude about this opp" panel
on the detail page. Streaming-only as of sprint 17.

Endpoints:
  POST /opportunities/{id}/ask/stream SSE: ask + persist on completion
  GET  /opportunities/{id}/questions  history (newest first, capped)
  DELETE /opportunity-questions/{id}  remove a single Q&A round
"""

from __future__ import annotations

import logging
import os
from datetime import date, datetime, timezone
from typing import Annotated, Any
from uuid import UUID

import json
from collections.abc import AsyncIterator

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import StreamingResponse
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
    stream_ask_about_opportunity,
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


@router.post(
    "/opportunities/{opportunity_id}/ask/stream",
    responses={
        200: {
            "content": {"text/event-stream": {}},
            "description": "SSE stream of {type:'delta',text:...} + final {type:'complete',question_id,...}",
        }
    },
)
async def ask_question_stream(
    opportunity_id: UUID,
    body: AskRequest,
    ctx: Annotated[RequestContext, Depends(get_request_context)],
) -> StreamingResponse:
    """Streaming variant of POST /opportunities/{id}/ask.

    Emits SSE events of the form `data: {"type":"delta","text":"..."}\\n\\n`
    as Claude composes, then a final `data: {"type":"complete",...}\\n\\n`
    with the persisted question_id, model, and token counts.

    On error during streaming, emits a `data: {"type":"error","message":"..."}\\n\\n`
    event and ends the stream cleanly. The HTTP status is always 200 once
    streaming has begun — caller checks the final event type.
    """
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

    inp = await _build_ask_input(
        ctx, opp, enr, score, body.question, body.starter_kind
    )
    persisted_question = inp.question
    starter_kind = (
        body.starter_kind if body.starter_kind in ASK_STARTERS else None
    )
    asked_by_id = ctx.founder.id if ctx.founder else None
    tenant_id = ctx.tenant.id
    # Capture session-bound state by value before entering the streaming
    # generator — the request context's session is closed once this handler
    # returns the StreamingResponse.

    async def stream() -> AsyncIterator[bytes]:
        client = AnthropicLLMClient(api_key=api_key)
        accumulated: list[str] = []
        final_model: str | None = None
        final_input_tokens: int | None = None
        final_output_tokens: int | None = None
        try:
            async for chunk in stream_ask_about_opportunity(client, inp):
                if chunk.kind == "delta":
                    accumulated.append(chunk.text)
                    payload = {"type": "delta", "text": chunk.text}
                    yield f"data: {json.dumps(payload)}\n\n".encode()
                elif chunk.kind == "final":
                    final_model = chunk.model
                    final_input_tokens = chunk.input_tokens
                    final_output_tokens = chunk.output_tokens
        except Exception as exc:
            log.exception("ask streaming failed: %s", exc)
            err = {
                "type": "error",
                "message": f"{exc.__class__.__name__}: {exc}"[:200],
            }
            yield f"data: {json.dumps(err)}\n\n".encode()
            return

        answer_text = "".join(accumulated).strip()
        if not answer_text:
            yield (
                b'data: {"type":"error","message":"empty model response"}\n\n'
            )
            return

        # Persist on stream completion. Use a fresh session because the
        # original ctx.session is tied to the request lifecycle.
        from mactech_db import scoped_session

        try:
            async with scoped_session(tenant_id) as persist_session:
                q = OpportunityQuestion(
                    tenant_id=tenant_id,
                    opportunity_id=opportunity_id,
                    asked_by_founder_id=asked_by_id,
                    question=persisted_question,
                    answer=answer_text,
                    starter_kind=starter_kind,
                    model=final_model,
                    input_tokens=final_input_tokens,
                    output_tokens=final_output_tokens,
                    prompt_version=PROMPT_VERSION,
                )
                persist_session.add(q)
                await persist_session.flush()
                question_id = str(q.id)
        except Exception as exc:  # noqa: BLE001
            log.exception("ask persistence failed: %s", exc)
            payload = {
                "type": "error",
                "message": f"answer streamed but persistence failed: {exc.__class__.__name__}",
            }
            yield f"data: {json.dumps(payload)}\n\n".encode()
            return

        complete = {
            "type": "complete",
            "question_id": question_id,
            "model": final_model,
            "input_tokens": final_input_tokens,
            "output_tokens": final_output_tokens,
        }
        yield f"data: {json.dumps(complete)}\n\n".encode()

    return StreamingResponse(
        stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache, no-transform",
            "X-Accel-Buffering": "no",
            "Connection": "keep-alive",
        },
    )


# Suppress unused-import false positive — reserved for future date-typed
# fields on QuestionOut.
_ = (date, datetime, timezone, Any)
