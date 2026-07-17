"""PDF import for the library catalogues.

Phase 3 Week 13 (UX Sprint 6) + sprint 18 async OCR. Drop a PDF on
/library; this endpoint:

  1. Tries PyMuPDF text extraction (fast, in-process).
  2. If the PDF has an embedded text layer, runs Claude Sonnet
     synchronously to extract structured fields, persists the new
     past_performance / capability_statement, and returns 201 with
     the new record id (existing happy-path UX, ~5–15s).
  3. If PyMuPDF returns < OCR_FALLBACK_THRESHOLD chars, the PDF is
     scanned and needs OCR — too slow for an HTTP request. Persist a
     library_import_jobs row with the blob, fire the Celery task, and
     return 202 with the job_id. The client polls
     GET /library/import/jobs/{id} until done.

  POST /library/import/past-performance/from-pdf
  POST /library/import/capability-statements/from-pdf
       multipart/form-data with file=<pdf>

  GET  /library/import/jobs/{id}
       returns {status, result_id, edit_url, error_message, notes}
"""

from __future__ import annotations

import logging
import os
from datetime import date
from decimal import Decimal
from typing import Annotated
from uuid import UUID

import fitz  # type: ignore[import-untyped]  # PyMuPDF
from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status
from fastapi.responses import JSONResponse
from mactech_db.models import (
    CapabilityStatement,
    LibraryImportJob,
    PastPerformance,
)
from mactech_intelligence import (
    AnthropicLLMClient,
    CapabilityExtractionError,
    PastPerformanceExtractionError,
    extract_capability_statement,
    extract_past_performance,
)
from pydantic import BaseModel, ConfigDict
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from mactech_api.auth import RequestContext, get_request_context
from mactech_api.embed_helpers import embed_capability_inline

log = logging.getLogger(__name__)
router = APIRouter(tags=["library-import"])

MAX_PDF_BYTES = 20 * 1024 * 1024  # 20 MB cap.
MAX_TEXT_CHARS = 25_000


class _Out(BaseModel):
    model_config = ConfigDict(from_attributes=True)


class ImportedPastPerformanceOut(_Out):
    id: str
    title: str
    extracted_text_chars: int
    edit_url: str
    notes: list[str]


class ImportedCapabilityStatementOut(_Out):
    id: str
    title: str
    extracted_text_chars: int
    edit_url: str
    notes: list[str]


class ImportJobAcceptedOut(_Out):
    """202 response — async job queued."""

    job_id: str
    status: str
    poll_url: str
    message: str


class ImportJobStatusOut(_Out):
    id: str
    kind: str
    status: str
    filename: str | None
    result_id: str | None
    edit_url: str | None
    text_chars: int | None
    notes: list[str]
    error_message: str | None
    created_at: str
    completed_at: str | None


# If PyMuPDF returns less than this many chars, the PDF is image-only
# and needs OCR — which runs async in the worker. Matches the worker's
# threshold so the sync/async decision is consistent.
OCR_FALLBACK_THRESHOLD = 80


def _pdf_text_pymupdf(blob: bytes) -> str:
    """Embedded-text-layer extraction only. Fast, in-process. Returns ''
    if no text layer (signal to dispatch OCR via the worker).
    """
    try:
        with fitz.open(stream=blob, filetype="pdf") as doc:
            pages = [page.get_text("text") for page in doc]
        return "\n\n".join(pages).strip()
    except fitz.FileDataError as exc:
        raise HTTPException(status_code=400, detail=f"not a valid PDF: {exc}") from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=400, detail=f"could not parse PDF: {exc}") from exc


def _date_or_none(d: date | None) -> date | None:
    return d if d else None


def _kind_to_edit_url(kind: str, result_id: str | None) -> str | None:
    if not result_id:
        return None
    if kind == "past_performance":
        return f"/library/past-performance/{result_id}/edit"
    if kind == "capability_statement":
        return f"/library/capability-statements/{result_id}/edit"
    return None


async def _validate_pdf(file: UploadFile) -> bytes:
    if file.content_type and file.content_type != "application/pdf":
        raise HTTPException(
            status_code=400,
            detail=(
                f"expected application/pdf, got {file.content_type}. "
                "If your file is a PDF, try saving it again."
            ),
        )
    blob = await file.read()
    if not blob:
        raise HTTPException(status_code=400, detail="empty file")
    if len(blob) > MAX_PDF_BYTES:
        raise HTTPException(
            status_code=413,
            detail=(f"PDF too large ({len(blob):,} bytes). Limit is {MAX_PDF_BYTES:,} bytes."),
        )
    return blob


async def _enqueue_ocr_job(
    ctx: RequestContext,
    *,
    kind: str,
    blob: bytes,
    filename: str | None,
) -> ImportJobAcceptedOut:
    job = LibraryImportJob(
        tenant_id=ctx.tenant.id,
        created_by_founder_id=ctx.founder.id if ctx.founder else None,
        kind=kind,
        status="queued",
        filename=filename,
        file_size_bytes=len(blob),
        file_blob=blob,
    )
    ctx.session.add(job)
    await ctx.session.flush()
    job_id = str(job.id)

    try:
        from mactech_workers.celery_app import celery_app

        celery_app.send_task(
            "mactech.library.process_pdf_import",
            args=[job_id],
        )
        log.info(
            "library_import: queued OCR job %s kind=%s size=%d",
            job_id,
            kind,
            len(blob),
        )
    except Exception as exc:
        # The job row is persisted; the cron beat (added below) will pick
        # it up on the next sweep. Don't fail the request.
        log.warning(
            "library_import: failed to dispatch celery task for job %s: %s",
            job_id,
            exc,
        )

    return ImportJobAcceptedOut(
        job_id=job_id,
        status="queued",
        poll_url=f"/library/import/jobs/{job_id}",
        message=(
            "Scanned PDF detected — running OCR + extraction in the "
            "background. This usually takes 30 seconds to 2 minutes."
        ),
    )


@router.post(
    "/library/import/past-performance/from-pdf",
    responses={
        201: {"model": ImportedPastPerformanceOut},
        202: {"model": ImportJobAcceptedOut},
    },
)
async def import_past_performance_pdf(
    ctx: Annotated[RequestContext, Depends(get_request_context)],
    file: Annotated[UploadFile, File(description="PDF file to parse")],
) -> JSONResponse:
    api_key = os.environ.get("ANTHROPIC_API_KEY", "")
    if not api_key:
        raise HTTPException(
            status_code=503,
            detail="ANTHROPIC_API_KEY not configured on the API service.",
        )

    blob = await _validate_pdf(file)
    text = _pdf_text_pymupdf(blob)

    # Image-only / scanned PDF — go async.
    if len(text) < OCR_FALLBACK_THRESHOLD:
        accepted = await _enqueue_ocr_job(
            ctx, kind="past_performance", blob=blob, filename=file.filename
        )
        return JSONResponse(
            status_code=status.HTTP_202_ACCEPTED,
            content=accepted.model_dump(),
        )

    notes: list[str] = []
    if len(text) > MAX_TEXT_CHARS:
        notes.append(
            f"Document has {len(text):,} characters; only the first "
            f"{MAX_TEXT_CHARS:,} were sent to the model."
        )

    client = AnthropicLLMClient(api_key=api_key)
    try:
        ext = await extract_past_performance(client, text)
    except PastPerformanceExtractionError as exc:
        log.warning("pdf import got bad extraction: %s", exc)
        raise HTTPException(status_code=502, detail=f"extraction failed: {exc}") from exc
    except Exception as exc:
        log.exception("pdf import unexpected: %s", exc)
        raise HTTPException(
            status_code=502,
            detail=f"Anthropic call failed: {exc.__class__.__name__}",
        ) from exc

    pp = PastPerformance(
        tenant_id=ctx.tenant.id,
        title=ext.title,
        customer_agency=ext.customer_agency,
        customer_office=ext.customer_office,
        contract_number=ext.contract_number,
        role=ext.role,
        period_start=_date_or_none(ext.period_start),
        period_end=_date_or_none(ext.period_end),
        contract_value=(
            Decimal(str(ext.contract_value)) if ext.contract_value is not None else None
        ),
        naics_code=ext.naics_code,
        summary=ext.summary,
        keywords=ext.keywords or None,
    )
    ctx.session.add(pp)
    try:
        await ctx.session.flush()
    except IntegrityError:
        await ctx.session.rollback()
        pp = PastPerformance(
            tenant_id=ctx.tenant.id,
            title=f"{ext.title} (imported {date.today().isoformat()})"[:255],
            customer_agency=ext.customer_agency,
            customer_office=ext.customer_office,
            contract_number=ext.contract_number,
            role=ext.role,
            period_start=_date_or_none(ext.period_start),
            period_end=_date_or_none(ext.period_end),
            contract_value=(
                Decimal(str(ext.contract_value)) if ext.contract_value is not None else None
            ),
            naics_code=ext.naics_code,
            summary=ext.summary,
            keywords=ext.keywords or None,
        )
        ctx.session.add(pp)
        await ctx.session.flush()
        notes.append(
            "A record with the same title already existed. The new record "
            "got a date suffix; rename it in the edit form."
        )

    body = ImportedPastPerformanceOut(
        id=str(pp.id),
        title=pp.title,
        extracted_text_chars=ext.text_chars,
        edit_url=f"/library/past-performance/{pp.id}/edit",
        notes=notes,
    )
    return JSONResponse(status_code=status.HTTP_201_CREATED, content=body.model_dump())


@router.post(
    "/library/import/capability-statements/from-pdf",
    responses={
        201: {"model": ImportedCapabilityStatementOut},
        202: {"model": ImportJobAcceptedOut},
    },
)
async def import_capability_statement_pdf(
    ctx: Annotated[RequestContext, Depends(get_request_context)],
    file: Annotated[UploadFile, File(description="PDF file to parse")],
) -> JSONResponse:
    api_key = os.environ.get("ANTHROPIC_API_KEY", "")
    if not api_key:
        raise HTTPException(
            status_code=503,
            detail="ANTHROPIC_API_KEY not configured on the API service.",
        )

    blob = await _validate_pdf(file)
    text = _pdf_text_pymupdf(blob)

    if len(text) < OCR_FALLBACK_THRESHOLD:
        accepted = await _enqueue_ocr_job(
            ctx,
            kind="capability_statement",
            blob=blob,
            filename=file.filename,
        )
        return JSONResponse(
            status_code=status.HTTP_202_ACCEPTED,
            content=accepted.model_dump(),
        )

    notes: list[str] = []
    if len(text) > MAX_TEXT_CHARS:
        notes.append(
            f"Document has {len(text):,} characters; only the first "
            f"{MAX_TEXT_CHARS:,} were sent to the model."
        )

    client = AnthropicLLMClient(api_key=api_key)
    try:
        ext = await extract_capability_statement(client, text)
    except CapabilityExtractionError as exc:
        log.warning("capability pdf import got bad extraction: %s", exc)
        raise HTTPException(status_code=502, detail=f"extraction failed: {exc}") from exc
    except Exception as exc:
        log.exception("capability pdf import unexpected: %s", exc)
        raise HTTPException(
            status_code=502,
            detail=f"Anthropic call failed: {exc.__class__.__name__}",
        ) from exc

    related_founders_payload: list[dict[str, str]] | None = None
    if ext.related_founder_slugs:
        related_founders_payload = [{"slug": s} for s in ext.related_founder_slugs]

    cs = CapabilityStatement(
        tenant_id=ctx.tenant.id,
        title=ext.title,
        summary=ext.summary,
        keywords=ext.keywords or None,
        related_naics=ext.related_naics or None,
        related_founders=related_founders_payload,
    )
    ctx.session.add(cs)
    try:
        await ctx.session.flush()
    except IntegrityError:
        await ctx.session.rollback()
        cs = CapabilityStatement(
            tenant_id=ctx.tenant.id,
            title=f"{ext.title} (imported {date.today().isoformat()})"[:255],
            summary=ext.summary,
            keywords=ext.keywords or None,
            related_naics=ext.related_naics or None,
            related_founders=related_founders_payload,
        )
        ctx.session.add(cs)
        await ctx.session.flush()
        notes.append(
            "A capability statement with the same title already existed. "
            "The new record got a date suffix; rename it in the edit form."
        )

    embedded = await embed_capability_inline(
        ctx.session,
        capability_id=str(cs.id),
        title=cs.title,
        summary=cs.summary,
    )
    if not embedded:
        notes.append(
            "Capability saved, but embedding wasn't generated inline. The "
            "embed worker will pick it up within 15 minutes."
        )

    body = ImportedCapabilityStatementOut(
        id=str(cs.id),
        title=cs.title,
        extracted_text_chars=ext.text_chars,
        edit_url=f"/library/capability-statements/{cs.id}/edit",
        notes=notes,
    )
    return JSONResponse(status_code=status.HTTP_201_CREATED, content=body.model_dump())


@router.get(
    "/library/import/jobs/{job_id}",
    response_model=ImportJobStatusOut,
)
async def get_library_import_job(
    job_id: UUID,
    ctx: Annotated[RequestContext, Depends(get_request_context)],
) -> ImportJobStatusOut:
    job = (
        await ctx.session.execute(
            select(LibraryImportJob).where(
                LibraryImportJob.id == job_id,
                LibraryImportJob.tenant_id == ctx.tenant.id,
            )
        )
    ).scalar_one_or_none()
    if job is None:
        raise HTTPException(status_code=404, detail="job not found")
    return ImportJobStatusOut(
        id=str(job.id),
        kind=job.kind,
        status=job.status,
        filename=job.filename,
        result_id=str(job.result_id) if job.result_id else None,
        edit_url=_kind_to_edit_url(job.kind, str(job.result_id) if job.result_id else None),
        text_chars=job.text_chars,
        notes=list(job.notes or []),
        error_message=job.error_message,
        created_at=job.created_at.isoformat(),
        completed_at=(job.completed_at.isoformat() if job.completed_at else None),
    )
