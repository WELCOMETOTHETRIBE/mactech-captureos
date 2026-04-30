"""Solicitation decoder — compliance + requirements matrix extraction.

Section C of CaptureOS_Requirements.md. Reads the opportunity's
description text and uses Claude to produce two structured matrices
that ProposalOS will consume via the Capture Package handoff.

Endpoints:

  GET    /opportunities/{id}/solicitation-extraction
         Cached extraction metadata (status, counts, model, tokens).
         404 if not yet extracted.

  POST   /opportunities/{id}/solicitation-extraction
         Generate or regenerate. Synchronous — returns when both matrices
         are persisted. ~30-60s typical.

  DELETE /opportunities/{id}/solicitation-extraction
         Throw out the cached extraction + items.

  GET    /opportunities/{id}/compliance-matrix
         Returns compliance items, ordered by sort_order. 404 if no
         extraction exists.

  GET    /opportunities/{id}/requirements-matrix
         Returns requirement items, ordered by sort_order. 404 if no
         extraction exists.
"""

from __future__ import annotations

import logging
import os
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, ConfigDict
from sqlalchemy import delete, select

from mactech_api.auth import RequestContext, get_request_context
from mactech_db.models import (
    ComplianceMatrixItem,
    OpportunityRaw,
    RequirementMatrixItem,
    SolicitationExtraction,
)
from mactech_intelligence import (
    AnthropicLLMClient,
    ExtractSolicitationInput,
    SolicitationExtractionError,
    extract_solicitation,
)
from mactech_intelligence.extract_solicitation import PROMPT_VERSION

log = logging.getLogger(__name__)
router = APIRouter(tags=["solicitation"])


class _Out(BaseModel):
    model_config = ConfigDict(from_attributes=True)


class ExtractionOut(_Out):
    id: str
    opportunity_id: str
    status: str
    description_chars: int | None
    compliance_count: int
    requirements_count: int
    model: str | None
    prompt_version: str | None
    input_tokens: int | None
    output_tokens: int | None
    error: str | None
    created_at: str
    updated_at: str


class ComplianceItemOut(_Out):
    id: str
    item_id: str
    statement: str
    section_l_citation: str | None
    pass_fail: bool
    notes: str | None
    sort_order: int


class RequirementItemOut(_Out):
    id: str
    item_id: str
    statement: str
    source_citation: str | None
    category: str
    sort_order: int


class ComplianceMatrixOut(_Out):
    extraction_id: str
    opportunity_id: str
    items: list[ComplianceItemOut]
    last_extracted_at: str


class RequirementsMatrixOut(_Out):
    extraction_id: str
    opportunity_id: str
    items: list[RequirementItemOut]
    last_extracted_at: str


def _extraction_to_out(e: SolicitationExtraction) -> ExtractionOut:
    return ExtractionOut(
        id=str(e.id),
        opportunity_id=str(e.opportunity_id),
        status=e.status,
        description_chars=e.description_chars,
        compliance_count=e.compliance_count,
        requirements_count=e.requirements_count,
        model=e.model,
        prompt_version=e.prompt_version,
        input_tokens=e.input_tokens,
        output_tokens=e.output_tokens,
        error=e.error,
        created_at=e.created_at.isoformat(),
        updated_at=e.updated_at.isoformat(),
    )


@router.get(
    "/opportunities/{opportunity_id}/solicitation-extraction",
    response_model=ExtractionOut,
)
async def get_extraction(
    opportunity_id: UUID,
    ctx: Annotated[RequestContext, Depends(get_request_context)],
) -> ExtractionOut:
    e = (
        await ctx.session.execute(
            select(SolicitationExtraction).where(
                SolicitationExtraction.tenant_id == ctx.tenant.id,
                SolicitationExtraction.opportunity_id == opportunity_id,
            )
        )
    ).scalar_one_or_none()
    if e is None:
        raise HTTPException(status_code=404, detail="no extraction generated yet")
    return _extraction_to_out(e)


@router.post(
    "/opportunities/{opportunity_id}/solicitation-extraction",
    response_model=ExtractionOut,
    status_code=status.HTTP_201_CREATED,
)
async def generate_extraction(
    opportunity_id: UUID,
    ctx: Annotated[RequestContext, Depends(get_request_context)],
) -> ExtractionOut:
    """Run Claude on the opportunity description and persist both matrices.

    Synchronous. Re-runs are safe — old items are deleted and re-inserted
    so the matrices always reflect the latest extraction.
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

    description = opp.description_text or ""
    if not description.strip():
        raise HTTPException(
            status_code=409,
            detail=(
                "opportunity has no description text on file yet. The "
                "fetch_descriptions worker pulls it on the next 30-minute "
                "tick — try again then."
            ),
        )

    inp = ExtractSolicitationInput(
        title=opp.title,
        agency=opp.agency,
        notice_type=opp.notice_type,
        set_aside=opp.set_aside,
        naics_code=opp.naics_code,
        posted_at=opp.posted_at,
        response_deadline=opp.response_deadline,
        description=description,
    )

    client = AnthropicLLMClient(api_key=api_key)
    try:
        result = await extract_solicitation(client, inp)
    except SolicitationExtractionError as exc:
        log.warning("extract_solicitation produced bad JSON: %s", exc)
        raise HTTPException(
            status_code=502,
            detail=f"solicitation extraction failed: {exc}",
        ) from exc
    except Exception as exc:
        log.exception("extract_solicitation failed: %s", exc)
        raise HTTPException(
            status_code=502,
            detail=f"Anthropic call failed: {exc.__class__.__name__}",
        ) from exc

    # Upsert the parent extraction row.
    existing = (
        await ctx.session.execute(
            select(SolicitationExtraction).where(
                SolicitationExtraction.tenant_id == ctx.tenant.id,
                SolicitationExtraction.opportunity_id == opportunity_id,
            )
        )
    ).scalar_one_or_none()

    if existing is None:
        extraction = SolicitationExtraction(
            tenant_id=ctx.tenant.id,
            opportunity_id=opportunity_id,
            status="complete",
            source_text_hash=result.source_text_hash,
            description_chars=result.description_chars,
            compliance_count=len(result.compliance_items),
            requirements_count=len(result.requirement_items),
            model=result.response.model,
            prompt_version=PROMPT_VERSION,
            input_tokens=result.response.input_tokens,
            output_tokens=result.response.output_tokens,
            error=None,
        )
        ctx.session.add(extraction)
        await ctx.session.flush()
    else:
        # Wipe prior items; cascade on extraction_id is fine but explicit
        # deletes keep the SQL audit trail readable in the logs.
        await ctx.session.execute(
            delete(ComplianceMatrixItem).where(
                ComplianceMatrixItem.extraction_id == existing.id
            )
        )
        await ctx.session.execute(
            delete(RequirementMatrixItem).where(
                RequirementMatrixItem.extraction_id == existing.id
            )
        )
        existing.status = "complete"
        existing.source_text_hash = result.source_text_hash
        existing.description_chars = result.description_chars
        existing.compliance_count = len(result.compliance_items)
        existing.requirements_count = len(result.requirement_items)
        existing.model = result.response.model
        existing.prompt_version = PROMPT_VERSION
        existing.input_tokens = result.response.input_tokens
        existing.output_tokens = result.response.output_tokens
        existing.error = None
        extraction = existing

    # Insert new child items.
    for idx, item in enumerate(result.compliance_items):
        ctx.session.add(
            ComplianceMatrixItem(
                extraction_id=extraction.id,
                tenant_id=ctx.tenant.id,
                opportunity_id=opportunity_id,
                item_id=item.item_id,
                statement=item.statement,
                section_l_citation=item.section_l_citation,
                pass_fail=item.pass_fail,
                notes=item.notes,
                sort_order=idx,
            )
        )
    for idx, item in enumerate(result.requirement_items):
        ctx.session.add(
            RequirementMatrixItem(
                extraction_id=extraction.id,
                tenant_id=ctx.tenant.id,
                opportunity_id=opportunity_id,
                item_id=item.item_id,
                statement=item.statement,
                source_citation=item.source_citation,
                category=item.category,
                sort_order=idx,
            )
        )

    await ctx.session.flush()
    return _extraction_to_out(extraction)


@router.delete(
    "/opportunities/{opportunity_id}/solicitation-extraction",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def delete_extraction(
    opportunity_id: UUID,
    ctx: Annotated[RequestContext, Depends(get_request_context)],
) -> None:
    e = (
        await ctx.session.execute(
            select(SolicitationExtraction).where(
                SolicitationExtraction.tenant_id == ctx.tenant.id,
                SolicitationExtraction.opportunity_id == opportunity_id,
            )
        )
    ).scalar_one_or_none()
    if e is None:
        raise HTTPException(status_code=404, detail="no extraction to delete")
    # ON DELETE CASCADE wipes the child items.
    await ctx.session.delete(e)
    await ctx.session.flush()


@router.get(
    "/opportunities/{opportunity_id}/compliance-matrix",
    response_model=ComplianceMatrixOut,
)
async def get_compliance_matrix(
    opportunity_id: UUID,
    ctx: Annotated[RequestContext, Depends(get_request_context)],
) -> ComplianceMatrixOut:
    extraction = (
        await ctx.session.execute(
            select(SolicitationExtraction).where(
                SolicitationExtraction.tenant_id == ctx.tenant.id,
                SolicitationExtraction.opportunity_id == opportunity_id,
            )
        )
    ).scalar_one_or_none()
    if extraction is None:
        raise HTTPException(status_code=404, detail="no compliance matrix generated yet")

    items = (
        (
            await ctx.session.execute(
                select(ComplianceMatrixItem)
                .where(ComplianceMatrixItem.extraction_id == extraction.id)
                .order_by(ComplianceMatrixItem.sort_order.asc())
            )
        )
        .scalars()
        .all()
    )

    return ComplianceMatrixOut(
        extraction_id=str(extraction.id),
        opportunity_id=str(opportunity_id),
        items=[
            ComplianceItemOut(
                id=str(it.id),
                item_id=it.item_id,
                statement=it.statement,
                section_l_citation=it.section_l_citation,
                pass_fail=it.pass_fail,
                notes=it.notes,
                sort_order=it.sort_order,
            )
            for it in items
        ],
        last_extracted_at=extraction.updated_at.isoformat(),
    )


@router.get(
    "/opportunities/{opportunity_id}/requirements-matrix",
    response_model=RequirementsMatrixOut,
)
async def get_requirements_matrix(
    opportunity_id: UUID,
    ctx: Annotated[RequestContext, Depends(get_request_context)],
) -> RequirementsMatrixOut:
    extraction = (
        await ctx.session.execute(
            select(SolicitationExtraction).where(
                SolicitationExtraction.tenant_id == ctx.tenant.id,
                SolicitationExtraction.opportunity_id == opportunity_id,
            )
        )
    ).scalar_one_or_none()
    if extraction is None:
        raise HTTPException(status_code=404, detail="no requirements matrix generated yet")

    items = (
        (
            await ctx.session.execute(
                select(RequirementMatrixItem)
                .where(RequirementMatrixItem.extraction_id == extraction.id)
                .order_by(RequirementMatrixItem.sort_order.asc())
            )
        )
        .scalars()
        .all()
    )

    return RequirementsMatrixOut(
        extraction_id=str(extraction.id),
        opportunity_id=str(opportunity_id),
        items=[
            RequirementItemOut(
                id=str(it.id),
                item_id=it.item_id,
                statement=it.statement,
                source_citation=it.source_citation,
                category=it.category,
                sort_order=it.sort_order,
            )
            for it in items
        ],
        last_extracted_at=extraction.updated_at.isoformat(),
    )
