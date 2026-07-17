"""Async PDF import worker — OCR + LLM extraction off the request path.

Phase 3 sprint 18. The API endpoint persists a `library_import_jobs`
row with the PDF blob, fires `mactech.library.process_pdf_import`,
and returns 202 + job_id. This task does the slow work:

  1. Pull the job + blob.
  2. Try PyMuPDF text extraction first (fast).
  3. If that returns < threshold chars, run Tesseract OCR over each
     page (the slow path — can be 30-180s for a 12-page scan).
  4. Call Claude (extract_past_performance | extract_capability_statement).
  5. Insert the resulting record (past_performance | capability_statements)
     in a tenant-scoped transaction.
  6. Mark the job done (or failed with error_message).

Embedding for capabilities is left to the regular embed worker (every
15 min). The async path is already a "this is taking a while" UX, so
a few extra minutes for the embed isn't a regression.
"""

from __future__ import annotations

import asyncio
import io
import logging
import os
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from decimal import Decimal
from typing import Any
from uuid import UUID

import fitz  # type: ignore[import-untyped]
import pytesseract  # type: ignore[import-untyped]
from mactech_db import scoped_session
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
from PIL import Image
from sqlalchemy import select

from mactech_workers.celery_app import celery_app

log = logging.getLogger(__name__)


OCR_FALLBACK_THRESHOLD = 80
OCR_RENDER_DPI = 220
OCR_MAX_PAGES = 12
MAX_TEXT_CHARS = 25_000


@dataclass
class ImportJobResult:
    job_id: str
    status: str
    result_id: str | None
    text_chars: int | None
    error_message: str | None


def _ocr_pdf(blob: bytes) -> str:
    pages: list[str] = []
    try:
        with fitz.open(stream=blob, filetype="pdf") as doc:
            for i, page in enumerate(doc):
                if i >= OCR_MAX_PAGES:
                    break
                pix = page.get_pixmap(dpi=OCR_RENDER_DPI, alpha=False)
                img_bytes = pix.tobytes("png")
                with Image.open(io.BytesIO(img_bytes)) as img:
                    text = pytesseract.image_to_string(img, lang="eng")
                if text.strip():
                    pages.append(text.strip())
    except pytesseract.TesseractNotFoundError as exc:
        log.warning("tesseract binary not found at runtime: %s", exc)
        return ""
    except Exception as exc:
        log.warning("OCR fall-through errored: %s", exc)
        return ""
    return "\n\n".join(pages).strip()


def _pdf_to_text(blob: bytes) -> str:
    try:
        with fitz.open(stream=blob, filetype="pdf") as doc:
            pages = [page.get_text("text") for page in doc]
        embedded = "\n\n".join(pages).strip()
    except (fitz.FileDataError, RuntimeError) as exc:
        log.warning("PyMuPDF could not parse PDF: %s", exc)
        return ""

    if len(embedded) >= OCR_FALLBACK_THRESHOLD:
        return embedded

    log.info(
        "library_import: PyMuPDF returned %d chars, falling through to OCR",
        len(embedded),
    )
    ocr_text = _ocr_pdf(blob)
    return ocr_text if len(ocr_text) > len(embedded) else embedded


async def _process_job(job_id: UUID) -> ImportJobResult:
    api_key = os.environ.get("ANTHROPIC_API_KEY", "")
    if not api_key:
        # Persist the failure so the UI can surface it.
        from mactech_db import unscoped_session

        async with unscoped_session() as session:
            job = (
                await session.execute(select(LibraryImportJob).where(LibraryImportJob.id == job_id))
            ).scalar_one_or_none()
            if job is not None:
                job.status = "failed"
                job.error_message = "ANTHROPIC_API_KEY not configured on the worker"
                job.completed_at = datetime.now(UTC)
                await session.flush()
                return ImportJobResult(
                    job_id=str(job_id),
                    status="failed",
                    result_id=None,
                    text_chars=None,
                    error_message=job.error_message,
                )
        return ImportJobResult(
            job_id=str(job_id),
            status="failed",
            result_id=None,
            text_chars=None,
            error_message="job not found",
        )

    # First transaction: claim the job + read the blob.
    from mactech_db import unscoped_session

    async with unscoped_session() as session:
        job = (
            await session.execute(select(LibraryImportJob).where(LibraryImportJob.id == job_id))
        ).scalar_one_or_none()
        if job is None:
            return ImportJobResult(
                job_id=str(job_id),
                status="failed",
                result_id=None,
                text_chars=None,
                error_message="job not found",
            )
        if job.status not in ("queued", "running"):
            # Already done/failed — idempotent re-fire.
            return ImportJobResult(
                job_id=str(job_id),
                status=job.status,
                result_id=str(job.result_id) if job.result_id else None,
                text_chars=job.text_chars,
                error_message=job.error_message,
            )
        job.status = "running"
        await session.flush()
        kind = job.kind
        tenant_id = job.tenant_id
        blob = bytes(job.file_blob)

    # Slow work happens outside the DB transaction.
    text = _pdf_to_text(blob)

    if len(text) < 30:
        async with unscoped_session() as session:
            job = (
                await session.execute(select(LibraryImportJob).where(LibraryImportJob.id == job_id))
            ).scalar_one()
            job.status = "failed"
            job.text_chars = len(text)
            job.error_message = (
                "Couldn't extract usable text from this PDF — neither the "
                "embedded text layer nor OCR returned anything readable."
            )
            job.completed_at = datetime.now(UTC)
            await session.flush()
        return ImportJobResult(
            job_id=str(job_id),
            status="failed",
            result_id=None,
            text_chars=len(text),
            error_message="no usable text",
        )

    notes: list[str] = []
    if len(text) > MAX_TEXT_CHARS:
        notes.append(
            f"Document has {len(text):,} characters; only the first "
            f"{MAX_TEXT_CHARS:,} were sent to the model."
        )

    client = AnthropicLLMClient(api_key=api_key)

    try:
        if kind == "past_performance":
            ext = await extract_past_performance(client, text)
        else:
            ext = await extract_capability_statement(client, text)
    except (PastPerformanceExtractionError, CapabilityExtractionError) as exc:
        async with unscoped_session() as session:
            job = (
                await session.execute(select(LibraryImportJob).where(LibraryImportJob.id == job_id))
            ).scalar_one()
            job.status = "failed"
            job.text_chars = len(text)
            job.error_message = f"extraction failed: {exc}"[:1000]
            job.completed_at = datetime.now(UTC)
            await session.flush()
        return ImportJobResult(
            job_id=str(job_id),
            status="failed",
            result_id=None,
            text_chars=len(text),
            error_message=str(exc),
        )
    except Exception as exc:
        log.exception("library_import: unexpected extraction failure")
        async with unscoped_session() as session:
            job = (
                await session.execute(select(LibraryImportJob).where(LibraryImportJob.id == job_id))
            ).scalar_one()
            job.status = "failed"
            job.text_chars = len(text)
            job.error_message = f"Anthropic call failed: {exc.__class__.__name__}"
            job.completed_at = datetime.now(UTC)
            await session.flush()
        return ImportJobResult(
            job_id=str(job_id),
            status="failed",
            result_id=None,
            text_chars=len(text),
            error_message=str(exc),
        )

    # Persist the resulting record + flip job to done in one tenant-scoped tx.
    async with scoped_session(tenant_id) as session:
        result_id: UUID | None = None
        if kind == "past_performance":
            pp = PastPerformance(
                tenant_id=tenant_id,
                title=ext.title,
                customer_agency=ext.customer_agency,
                customer_office=ext.customer_office,
                contract_number=ext.contract_number,
                role=ext.role,
                period_start=ext.period_start or None,
                period_end=ext.period_end or None,
                contract_value=(
                    Decimal(str(ext.contract_value)) if ext.contract_value is not None else None
                ),
                naics_code=ext.naics_code,
                summary=ext.summary,
                keywords=ext.keywords or None,
            )
            session.add(pp)
            try:
                await session.flush()
            except Exception:
                await session.rollback()
                # Title collision — append a date suffix and retry inside a
                # fresh nested begin.
                pp = PastPerformance(
                    tenant_id=tenant_id,
                    title=f"{ext.title} (imported {datetime.now(UTC).date().isoformat()})"[:255],
                    customer_agency=ext.customer_agency,
                    customer_office=ext.customer_office,
                    contract_number=ext.contract_number,
                    role=ext.role,
                    period_start=ext.period_start or None,
                    period_end=ext.period_end or None,
                    contract_value=(
                        Decimal(str(ext.contract_value)) if ext.contract_value is not None else None
                    ),
                    naics_code=ext.naics_code,
                    summary=ext.summary,
                    keywords=ext.keywords or None,
                )
                session.add(pp)
                await session.flush()
                notes.append(
                    "A record with the same title already existed. The new "
                    "record got a date suffix; rename it in the edit form."
                )
            result_id = pp.id
        else:
            related_founders_payload: list[dict[str, str]] | None = None
            if ext.related_founder_slugs:
                related_founders_payload = [{"slug": s} for s in ext.related_founder_slugs]
            cs = CapabilityStatement(
                tenant_id=tenant_id,
                title=ext.title,
                summary=ext.summary,
                keywords=ext.keywords or None,
                related_naics=ext.related_naics or None,
                related_founders=related_founders_payload,
            )
            session.add(cs)
            try:
                await session.flush()
            except Exception:
                await session.rollback()
                cs = CapabilityStatement(
                    tenant_id=tenant_id,
                    title=f"{ext.title} (imported {datetime.now(UTC).date().isoformat()})"[:255],
                    summary=ext.summary,
                    keywords=ext.keywords or None,
                    related_naics=ext.related_naics or None,
                    related_founders=related_founders_payload,
                )
                session.add(cs)
                await session.flush()
                notes.append(
                    "A capability statement with the same title already "
                    "existed. The new record got a date suffix; rename it "
                    "in the edit form."
                )
            notes.append(
                "Capability saved. The embed worker will index it within 15 "
                "minutes for opportunity scoring."
            )
            result_id = cs.id

        job = (
            await session.execute(select(LibraryImportJob).where(LibraryImportJob.id == job_id))
        ).scalar_one()
        job.status = "done"
        job.result_id = result_id
        job.text_chars = ext.text_chars
        job.notes = notes or None
        job.error_message = None
        job.completed_at = datetime.now(UTC)
        await session.flush()

    return ImportJobResult(
        job_id=str(job_id),
        status="done",
        result_id=str(result_id),
        text_chars=ext.text_chars,
        error_message=None,
    )


@celery_app.task(name="mactech.library.process_pdf_import")
def process_pdf_import_task(job_id: str) -> dict[str, Any]:
    return asdict(asyncio.run(_process_job(UUID(job_id))))
