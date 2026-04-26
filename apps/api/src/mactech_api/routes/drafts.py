"""Proposal drafts API.

Phase 3 Week 9 / sprint 17. The Sources Sought drafter is the first
user. Generation is streaming-only (SSE). Endpoints:

  POST   /opportunities/{id}/drafts/sources-sought/stream   SSE: generate
  POST   /drafts/{id}/regenerate/stream                     SSE: regenerate
  GET    /drafts                                            list (newest first)
  GET    /drafts/{id}                                       single
  PATCH  /drafts/{id}                                       edit content / status
  DELETE /drafts/{id}
  GET    /drafts/{id}/export.docx                           DOCX download
"""

from __future__ import annotations

import logging
import os
from datetime import date as _date_t, datetime
from typing import Annotated
from uuid import UUID

import json
from collections.abc import AsyncIterator

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import Response, StreamingResponse
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import desc, select

from mactech_api.auth import RequestContext, get_request_context
from mactech_api.docx_export import DocxMetadata, markdown_to_docx_bytes
from mactech_db.models import (
    CapabilityStatement,
    Founder,
    OpportunityRaw,
    PastPerformance,
    ProposalDraft,
    TeamingPartner,
)
from mactech_intelligence import (
    AnthropicLLMClient,
    CapabilityContext,
    FounderContext,
    OpportunityContext,
    PastPerformanceContext,
    SourcesSoughtInput,
    TeamingPartnerContext,
    TenantIdentity,
    context_hash,
    stream_sources_sought_draft,
)

log = logging.getLogger(__name__)
router = APIRouter(tags=["drafts"])


class _Out(BaseModel):
    model_config = ConfigDict(from_attributes=True)


class DraftOpp(_Out):
    id: str
    notice_id: str
    title: str
    notice_type: str | None


class DraftFounderRef(_Out):
    slug: str
    full_name: str


class DraftOut(_Out):
    id: str
    opportunity: DraftOpp
    parent_draft_id: str | None
    created_by: DraftFounderRef | None
    draft_type: str
    title: str
    content: str
    status: str
    version: int
    custom_instructions: str | None
    model: str | None
    input_tokens: int | None
    output_tokens: int | None
    citations: dict | None
    created_at: str
    updated_at: str


class DraftListItem(_Out):
    id: str
    opportunity: DraftOpp
    draft_type: str
    title: str
    status: str
    version: int
    model: str | None
    output_tokens: int | None
    created_at: str
    updated_at: str


class DraftListResponse(_Out):
    total: int
    items: list[DraftListItem]


class GenerateSourcesSoughtRequest(BaseModel):
    custom_instructions: str | None = Field(default=None, max_length=4000)
    max_tokens: int = Field(default=4000, ge=500, le=8000)


class UpdateDraftRequest(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=255)
    content: str | None = Field(default=None, min_length=1)
    status: str | None = None


VALID_STATUSES = {"draft", "reviewed", "submitted", "archived"}


def _draft_out(
    draft: ProposalDraft,
    opp: OpportunityRaw,
    created_by: Founder | None,
) -> DraftOut:
    return DraftOut(
        id=str(draft.id),
        opportunity=DraftOpp(
            id=str(opp.id),
            notice_id=opp.source_id,
            title=opp.title,
            notice_type=opp.notice_type,
        ),
        parent_draft_id=str(draft.parent_draft_id) if draft.parent_draft_id else None,
        created_by=(
            DraftFounderRef(slug=created_by.slug, full_name=created_by.full_name)
            if created_by
            else None
        ),
        draft_type=draft.draft_type,
        title=draft.title,
        content=draft.content,
        status=draft.status,
        version=draft.version,
        custom_instructions=draft.custom_instructions,
        model=draft.model,
        input_tokens=draft.input_tokens,
        output_tokens=draft.output_tokens,
        citations=draft.citations,
        created_at=draft.created_at.isoformat(),
        updated_at=draft.updated_at.isoformat(),
    )


async def _build_input(
    ctx: RequestContext,
    opp: OpportunityRaw,
    custom_instructions: str | None,
) -> SourcesSoughtInput:
    """Pull every piece of context the drafter needs in one round-trip set."""
    session = ctx.session
    tenant = ctx.tenant

    founders = (
        await session.execute(
            select(Founder)
            .where(Founder.tenant_id == tenant.id)
            .order_by(Founder.full_name)
        )
    ).scalars().all()

    caps = (
        await session.execute(
            select(CapabilityStatement).where(
                CapabilityStatement.tenant_id == tenant.id
            )
        )
    ).scalars().all()

    pp_rows = (
        await session.execute(
            select(PastPerformance)
            .where(PastPerformance.tenant_id == tenant.id)
            .order_by(PastPerformance.period_end.desc().nulls_last())
        )
    ).scalars().all()

    partner_rows = (
        await session.execute(
            select(TeamingPartner).where(
                TeamingPartner.tenant_id == tenant.id,
                TeamingPartner.status == "active",
            )
        )
    ).scalars().all()

    # Tenant identity. UEI/CAGE may still be pending — the prompt handles that
    # and the drafter is instructed not to fabricate.
    tenant_identity = TenantIdentity(
        name=tenant.name,
        uei=tenant.uei,
        cage_code=tenant.cage_code,
        plan=tenant.plan,
        primary_contact_email=ctx.user.email if ctx.user else None,
        primary_contact_name=ctx.founder.full_name if ctx.founder else None,
        set_aside_certifications=[],
        address=None,
    )

    return SourcesSoughtInput(
        opportunity=OpportunityContext(
            notice_id=opp.source_id,
            title=opp.title,
            notice_type=opp.notice_type,
            set_aside=opp.set_aside,
            set_aside_description=(opp.raw_payload or {}).get(
                "typeOfSetAsideDescription"
            ),
            naics_code=opp.naics_code,
            agency=opp.agency,
            solicitation_number=opp.solicitation_number,
            posted_at=opp.posted_at,
            response_deadline=opp.response_deadline,
            description=opp.description_text,
        ),
        tenant=tenant_identity,
        founders=[
            FounderContext(
                slug=f.slug,
                full_name=f.full_name,
                title=f.title,
                pillar=f.pillar,
                email=f.email,
            )
            for f in founders
        ],
        capabilities=[
            CapabilityContext(
                slug=getattr(c, "slug", None) or _slugify(c.title),
                title=c.title,
                summary=c.summary,
                related_naics=c.related_naics or [],
                related_founder_slugs=[
                    rf.get("slug", "") if isinstance(rf, dict) else str(rf)
                    for rf in (c.related_founders or [])
                ],
            )
            for c in caps
        ],
        past_performance=[
            PastPerformanceContext(
                title=p.title,
                customer_agency=p.customer_agency,
                customer_office=p.customer_office,
                contract_number=p.contract_number,
                role=p.role,
                period_start=p.period_start,
                period_end=p.period_end,
                contract_value=(
                    float(p.contract_value) if p.contract_value is not None else None
                ),
                naics_code=p.naics_code,
                summary=p.summary,
                keywords=p.keywords or [],
            )
            for p in pp_rows
        ],
        teaming_partners=[
            TeamingPartnerContext(
                name=tp.name,
                uei=tp.uei,
                capabilities=tp.capabilities or [],
                naics_codes=tp.naics_codes or [],
                set_aside_certifications=tp.set_aside_certifications or [],
                notes=tp.notes,
            )
            for tp in partner_rows
        ],
        custom_instructions=custom_instructions,
    )


def _slugify(s: str) -> str:
    return "".join(c.lower() if c.isalnum() else "-" for c in s).strip("-")


def _make_title(opp: OpportunityRaw, version: int) -> str:
    base = f"Sources Sought response — {opp.title}"
    if version > 1:
        base += f" (v{version})"
    return base[:255]


async def _stream_draft(
    *,
    ctx: RequestContext,
    opp: OpportunityRaw,
    custom_instructions: str | None,
    parent: ProposalDraft | None,
    max_tokens: int,
) -> StreamingResponse:
    """Build the input, kick off Anthropic streaming, persist on finish.

    Emits SSE events:
      - data: {"type":"delta","text":"..."}
      - data: {"type":"complete","draft_id":"...","version":N,"model":"...","input_tokens":N,"output_tokens":N}
      - data: {"type":"error","message":"..."} on failure mid-stream
    """
    api_key = os.environ.get("ANTHROPIC_API_KEY", "")
    if not api_key:
        raise HTTPException(
            status_code=503,
            detail="ANTHROPIC_API_KEY not configured on the API service.",
        )

    inp = await _build_input(ctx, opp, custom_instructions)
    # Capture state by value before entering the streaming generator —
    # ctx.session is closed once StreamingResponse takes over.
    tenant_id = ctx.tenant.id
    opp_id = opp.id
    parent_id = parent.id if parent else None
    parent_version = parent.version if parent else 0
    created_by_founder_id = ctx.founder.id if ctx.founder else None
    title = _make_title(opp, (parent.version + 1) if parent else 1)
    ctx_hash = context_hash(inp)
    cap_count = len(inp.capabilities)
    pp_count = len(inp.past_performance)
    tp_count = len(inp.teaming_partners)

    async def stream() -> AsyncIterator[bytes]:
        client = AnthropicLLMClient(api_key=api_key)
        accumulated: list[str] = []
        final_model: str | None = None
        final_input_tokens: int | None = None
        final_output_tokens: int | None = None
        final_stop_reason: str | None = None
        try:
            async for chunk in stream_sources_sought_draft(
                client, inp, max_tokens=max_tokens
            ):
                if chunk.kind == "delta":
                    accumulated.append(chunk.text)
                    payload = {"type": "delta", "text": chunk.text}
                    yield f"data: {json.dumps(payload)}\n\n".encode()
                elif chunk.kind == "final":
                    final_model = chunk.model
                    final_input_tokens = chunk.input_tokens
                    final_output_tokens = chunk.output_tokens
                    final_stop_reason = chunk.stop_reason
        except Exception as exc:
            log.exception("draft streaming failed: %s", exc)
            err = {
                "type": "error",
                "message": f"{exc.__class__.__name__}: {exc}"[:200],
            }
            yield f"data: {json.dumps(err)}\n\n".encode()
            return

        content = "".join(accumulated).strip()
        if not content:
            yield (
                b'data: {"type":"error","message":"empty model response"}\n\n'
            )
            return

        # Persist on stream completion via fresh session.
        from mactech_db import scoped_session

        try:
            async with scoped_session(tenant_id) as persist_session:
                version = parent_version + 1 if parent_id else 1
                draft = ProposalDraft(
                    tenant_id=tenant_id,
                    opportunity_id=opp_id,
                    parent_draft_id=parent_id,
                    created_by_founder_id=created_by_founder_id,
                    draft_type="sources_sought",
                    title=title,
                    content=content,
                    status="draft",
                    version=version,
                    custom_instructions=custom_instructions,
                    prompt_context_hash=ctx_hash,
                    model=final_model,
                    input_tokens=final_input_tokens,
                    output_tokens=final_output_tokens,
                    citations={
                        "capability_count": cap_count,
                        "past_performance_count": pp_count,
                        "teaming_partner_count": tp_count,
                        "stop_reason": final_stop_reason,
                    },
                )
                persist_session.add(draft)
                await persist_session.flush()
                draft_id = str(draft.id)
                final_version = draft.version
        except Exception as exc:  # noqa: BLE001
            log.exception("draft persistence failed: %s", exc)
            payload = {
                "type": "error",
                "message": f"draft streamed but persistence failed: {exc.__class__.__name__}",
            }
            yield f"data: {json.dumps(payload)}\n\n".encode()
            return

        complete = {
            "type": "complete",
            "draft_id": draft_id,
            "version": final_version,
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


@router.post(
    "/opportunities/{opportunity_id}/drafts/sources-sought/stream",
    responses={
        200: {
            "content": {"text/event-stream": {}},
            "description": "SSE stream of {type:'delta',text:...} + final {type:'complete',draft_id,version,...}",
        }
    },
)
async def create_sources_sought_draft_stream(
    opportunity_id: UUID,
    body: GenerateSourcesSoughtRequest,
    ctx: Annotated[RequestContext, Depends(get_request_context)],
) -> StreamingResponse:
    """Streaming variant of POST /opportunities/{id}/drafts/sources-sought.

    Same persistence + tenant scoping as the non-streaming version; the
    UI sees the markdown compose live and navigates to /drafts/{id} on
    the final event.
    """
    opp = (
        await ctx.session.execute(
            select(OpportunityRaw).where(OpportunityRaw.id == opportunity_id)
        )
    ).scalar_one_or_none()
    if opp is None:
        raise HTTPException(status_code=404, detail="opportunity not found")

    return await _stream_draft(
        ctx=ctx,
        opp=opp,
        custom_instructions=body.custom_instructions,
        parent=None,
        max_tokens=body.max_tokens,
    )


@router.post(
    "/drafts/{draft_id}/regenerate/stream",
    responses={
        200: {
            "content": {"text/event-stream": {}},
            "description": "Streaming regeneration; emits a new draft with parent_draft_id chained.",
        }
    },
)
async def regenerate_draft_stream(
    draft_id: UUID,
    body: GenerateSourcesSoughtRequest,
    ctx: Annotated[RequestContext, Depends(get_request_context)],
) -> StreamingResponse:
    parent = (
        await ctx.session.execute(
            select(ProposalDraft).where(
                ProposalDraft.id == draft_id,
                ProposalDraft.tenant_id == ctx.tenant.id,
            )
        )
    ).scalar_one_or_none()
    if parent is None:
        raise HTTPException(status_code=404, detail="draft not found")

    opp = (
        await ctx.session.execute(
            select(OpportunityRaw).where(OpportunityRaw.id == parent.opportunity_id)
        )
    ).scalar_one_or_none()
    if opp is None:
        raise HTTPException(
            status_code=404, detail="parent draft's opportunity is gone"
        )

    instructions = body.custom_instructions or parent.custom_instructions
    return await _stream_draft(
        ctx=ctx,
        opp=opp,
        custom_instructions=instructions,
        parent=parent,
        max_tokens=body.max_tokens,
    )


@router.get("/drafts", response_model=DraftListResponse)
async def list_drafts(
    ctx: Annotated[RequestContext, Depends(get_request_context)],
    opportunity_id: UUID | None = None,
) -> DraftListResponse:
    stmt = (
        select(ProposalDraft, OpportunityRaw)
        .join(OpportunityRaw, OpportunityRaw.id == ProposalDraft.opportunity_id)
        .where(ProposalDraft.tenant_id == ctx.tenant.id)
        .order_by(desc(ProposalDraft.created_at))
    )
    if opportunity_id is not None:
        stmt = stmt.where(ProposalDraft.opportunity_id == opportunity_id)

    rows = (await ctx.session.execute(stmt)).all()
    items: list[DraftListItem] = []
    for d, opp in rows:
        items.append(
            DraftListItem(
                id=str(d.id),
                opportunity=DraftOpp(
                    id=str(opp.id),
                    notice_id=opp.source_id,
                    title=opp.title,
                    notice_type=opp.notice_type,
                ),
                draft_type=d.draft_type,
                title=d.title,
                status=d.status,
                version=d.version,
                model=d.model,
                output_tokens=d.output_tokens,
                created_at=d.created_at.isoformat(),
                updated_at=d.updated_at.isoformat(),
            )
        )
    return DraftListResponse(total=len(items), items=items)


@router.get("/drafts/{draft_id}", response_model=DraftOut)
async def get_draft(
    draft_id: UUID,
    ctx: Annotated[RequestContext, Depends(get_request_context)],
) -> DraftOut:
    row = (
        await ctx.session.execute(
            select(ProposalDraft, OpportunityRaw, Founder)
            .join(OpportunityRaw, OpportunityRaw.id == ProposalDraft.opportunity_id)
            .outerjoin(Founder, Founder.id == ProposalDraft.created_by_founder_id)
            .where(
                ProposalDraft.id == draft_id,
                ProposalDraft.tenant_id == ctx.tenant.id,
            )
        )
    ).first()
    if row is None:
        raise HTTPException(status_code=404, detail="draft not found")
    draft, opp, founder = row
    return _draft_out(draft, opp, founder)


@router.patch("/drafts/{draft_id}", response_model=DraftOut)
async def update_draft(
    draft_id: UUID,
    body: UpdateDraftRequest,
    ctx: Annotated[RequestContext, Depends(get_request_context)],
) -> DraftOut:
    draft = (
        await ctx.session.execute(
            select(ProposalDraft).where(
                ProposalDraft.id == draft_id,
                ProposalDraft.tenant_id == ctx.tenant.id,
            )
        )
    ).scalar_one_or_none()
    if draft is None:
        raise HTTPException(status_code=404, detail="draft not found")

    if body.title is not None:
        draft.title = body.title.strip()
    if body.content is not None:
        draft.content = body.content
    if body.status is not None:
        if body.status not in VALID_STATUSES:
            raise HTTPException(
                status_code=400,
                detail=f"invalid status '{body.status}'. allowed: {sorted(VALID_STATUSES)}",
            )
        draft.status = body.status

    draft.updated_at = datetime.utcnow()
    await ctx.session.flush()

    opp = (
        await ctx.session.execute(
            select(OpportunityRaw).where(OpportunityRaw.id == draft.opportunity_id)
        )
    ).scalar_one()
    founder = None
    if draft.created_by_founder_id:
        founder = (
            await ctx.session.execute(
                select(Founder).where(Founder.id == draft.created_by_founder_id)
            )
        ).scalar_one_or_none()
    return _draft_out(draft, opp, founder)


@router.delete("/drafts/{draft_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_draft(
    draft_id: UUID,
    ctx: Annotated[RequestContext, Depends(get_request_context)],
) -> None:
    draft = (
        await ctx.session.execute(
            select(ProposalDraft).where(
                ProposalDraft.id == draft_id,
                ProposalDraft.tenant_id == ctx.tenant.id,
            )
        )
    ).scalar_one_or_none()
    if draft is None:
        raise HTTPException(status_code=404, detail="draft not found")
    await ctx.session.delete(draft)
    await ctx.session.flush()


# ── helper used in opportunity detail (fetched separately by the web client) ──


@router.get(
    "/opportunities/{opportunity_id}/drafts", response_model=DraftListResponse
)
async def list_drafts_for_opportunity(
    opportunity_id: UUID,
    ctx: Annotated[RequestContext, Depends(get_request_context)],
) -> DraftListResponse:
    return await list_drafts(ctx, opportunity_id=opportunity_id)


def _safe_filename(s: str) -> str:
    """Slugify a draft title for the Content-Disposition filename."""
    cleaned = "".join(c if c.isalnum() or c in "-_." else "-" for c in s)
    cleaned = cleaned.strip("-").lower()[:100]
    return cleaned or "draft"


@router.get(
    "/drafts/{draft_id}/export.docx",
    responses={
        200: {
            "content": {
                "application/vnd.openxmlformats-officedocument.wordprocessingml.document": {}
            },
            "description": "Generated DOCX file.",
        }
    },
)
async def export_draft_docx(
    draft_id: UUID,
    ctx: Annotated[RequestContext, Depends(get_request_context)],
) -> Response:
    """Render the draft's markdown content as a DOCX binary download."""
    row = (
        await ctx.session.execute(
            select(ProposalDraft, OpportunityRaw, Founder)
            .join(OpportunityRaw, OpportunityRaw.id == ProposalDraft.opportunity_id)
            .outerjoin(Founder, Founder.id == ProposalDraft.created_by_founder_id)
            .where(
                ProposalDraft.id == draft_id,
                ProposalDraft.tenant_id == ctx.tenant.id,
            )
        )
    ).first()
    if row is None:
        raise HTTPException(status_code=404, detail="draft not found")
    draft, opp, founder = row

    blob = markdown_to_docx_bytes(
        draft.content,
        metadata=DocxMetadata(
            title=draft.title,
            subject=f"Response to SAM.gov notice {opp.source_id}",
            author=founder.full_name if founder else ctx.tenant.name,
        ),
    )

    filename = f"{_safe_filename(draft.title)}-v{draft.version}.docx"
    return Response(
        content=blob,
        media_type=(
            "application/vnd.openxmlformats-officedocument."
            "wordprocessingml.document"
        ),
        headers={
            "Content-Disposition": f'attachment; filename="{filename}"',
            "Cache-Control": "no-store",
        },
    )


# Suppress unused-import false positive (F401) — _date_t may be referenced
# by future date-typed fields on DraftOut.
_ = _date_t
