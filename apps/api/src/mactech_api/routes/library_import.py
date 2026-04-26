"""PDF import for the library catalogues.

Phase 3 Week 13 (UX Sprint 6). Drop a past-performance PDF on /library;
this endpoint parses the text (PyMuPDF), extracts structured fields
(Claude Sonnet, strict JSON), creates a `past_performance` row, and
returns the new record so the UI can redirect the user to the edit
page for review.

  POST /library/import/past-performance/from-pdf
       multipart/form-data with file=<pdf>

The whole flow is one round-trip — PyMuPDF runs in-process, Claude is
hit synchronously. Typical end-to-end: 5–15s for a 2-page PDF.
"""

from __future__ import annotations

import io
import logging
import os
from datetime import date
from decimal import Decimal
from typing import Annotated
from uuid import UUID

import fitz  # type: ignore[import-untyped]  # PyMuPDF
import pytesseract  # type: ignore[import-untyped]
from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status
from PIL import Image
from pydantic import BaseModel, ConfigDict
from sqlalchemy.exc import IntegrityError

from mactech_api.auth import RequestContext, get_request_context
from mactech_api.embed_helpers import embed_capability_inline
from mactech_db.models import CapabilityStatement, PastPerformance
from mactech_intelligence import (
    AnthropicLLMClient,
    CapabilityExtractionError,
    PastPerformanceExtractionError,
    extract_capability_statement,
    extract_past_performance,
)

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


# OCR knobs.
OCR_FALLBACK_THRESHOLD = 80  # if PyMuPDF returns < this many chars, OCR.
OCR_RENDER_DPI = 220         # pixels per inch when rasterizing pages.
OCR_MAX_PAGES = 12           # hard cap to bound OCR latency / cost.


def _ocr_pdf(blob: bytes) -> str:
    """Tesseract OCR fall-through for image-based / scanned PDFs.

    Renders each page to a PNG via PyMuPDF at ~220dpi and runs pytesseract.
    Capped at OCR_MAX_PAGES; for typical past-performance / capability
    statements that's plenty.
    """
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
    """Extract text via PyMuPDF; fall through to Tesseract OCR for scanned
    PDFs where the embedded text layer is empty.
    """
    try:
        with fitz.open(stream=blob, filetype="pdf") as doc:
            pages: list[str] = []
            for page in doc:
                pages.append(page.get_text("text"))
        embedded = "\n\n".join(pages).strip()
    except fitz.FileDataError as exc:
        raise HTTPException(
            status_code=400, detail=f"not a valid PDF: {exc}"
        ) from exc
    except RuntimeError as exc:
        raise HTTPException(
            status_code=400, detail=f"could not parse PDF: {exc}"
        ) from exc

    # If PyMuPDF found a real text layer, use it. OCR is the fallback.
    if len(embedded) >= OCR_FALLBACK_THRESHOLD:
        return embedded

    log.info(
        "PyMuPDF returned %d chars; attempting OCR fall-through (max %d pages)",
        len(embedded),
        OCR_MAX_PAGES,
    )
    ocr_text = _ocr_pdf(blob)
    # Prefer whichever produced more usable text.
    if len(ocr_text) > len(embedded):
        return ocr_text
    return embedded


def _date_or_none(d: date | None) -> date | None:
    return d if d else None


@router.post(
    "/library/import/past-performance/from-pdf",
    response_model=ImportedPastPerformanceOut,
    status_code=status.HTTP_201_CREATED,
)
async def import_past_performance_pdf(
    ctx: Annotated[RequestContext, Depends(get_request_context)],
    file: Annotated[UploadFile, File(description="PDF file to parse")],
) -> ImportedPastPerformanceOut:
    api_key = os.environ.get("ANTHROPIC_API_KEY", "")
    if not api_key:
        raise HTTPException(
            status_code=503,
            detail="ANTHROPIC_API_KEY not configured on the API service.",
        )
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
            detail=(
                f"PDF too large ({len(blob):,} bytes). "
                f"Limit is {MAX_PDF_BYTES:,} bytes."
            ),
        )

    text = _pdf_to_text(blob)
    if len(text) < 30:
        raise HTTPException(
            status_code=422,
            detail=(
                "Couldn't extract usable text from this PDF — neither the "
                "embedded text layer nor OCR returned anything readable. "
                "Try a higher-resolution scan, or paste the content into "
                "the manual form."
            ),
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
        raise HTTPException(
            status_code=502,
            detail=f"extraction failed: {exc}",
        ) from exc
    except Exception as exc:
        log.exception("pdf import unexpected: %s", exc)
        raise HTTPException(
            status_code=502,
            detail=f"Anthropic call failed: {exc.__class__.__name__}",
        ) from exc

    # Persist as a fresh past_performance record. The user lands on the edit
    # page next so they can review/correct before keeping it.
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
            Decimal(str(ext.contract_value))
            if ext.contract_value is not None
            else None
        ),
        naics_code=ext.naics_code,
        summary=ext.summary,
        keywords=ext.keywords or None,
        related_capability_slugs=None,
        related_founder_slugs=None,
    )
    ctx.session.add(pp)
    try:
        await ctx.session.flush()
    except IntegrityError:
        # Title collision with an existing record. Append a marker so the
        # user can rename in the edit form.
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
                Decimal(str(ext.contract_value))
                if ext.contract_value is not None
                else None
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

    return ImportedPastPerformanceOut(
        id=str(pp.id),
        title=pp.title,
        extracted_text_chars=ext.text_chars,
        edit_url=f"/library/past-performance/{pp.id}/edit",
        notes=notes,
    )


# ── Capability statements ─────────────────────────────────────────────


class ImportedCapabilityStatementOut(_Out):
    id: str
    title: str
    extracted_text_chars: int
    edit_url: str
    notes: list[str]


@router.post(
    "/library/import/capability-statements/from-pdf",
    response_model=ImportedCapabilityStatementOut,
    status_code=status.HTTP_201_CREATED,
)
async def import_capability_statement_pdf(
    ctx: Annotated[RequestContext, Depends(get_request_context)],
    file: Annotated[UploadFile, File(description="PDF file to parse")],
) -> ImportedCapabilityStatementOut:
    api_key = os.environ.get("ANTHROPIC_API_KEY", "")
    if not api_key:
        raise HTTPException(
            status_code=503,
            detail="ANTHROPIC_API_KEY not configured on the API service.",
        )
    if file.content_type and file.content_type != "application/pdf":
        raise HTTPException(
            status_code=400,
            detail=f"expected application/pdf, got {file.content_type}.",
        )

    blob = await file.read()
    if not blob:
        raise HTTPException(status_code=400, detail="empty file")
    if len(blob) > MAX_PDF_BYTES:
        raise HTTPException(
            status_code=413,
            detail=f"PDF too large ({len(blob):,} bytes). "
            f"Limit is {MAX_PDF_BYTES:,} bytes.",
        )

    text = _pdf_to_text(blob)
    if len(text) < 30:
        raise HTTPException(
            status_code=422,
            detail=(
                "Couldn't extract usable text from this PDF — neither the "
                "embedded text layer nor OCR returned anything readable. "
                "Try a higher-resolution scan, or paste the content into "
                "the manual form."
            ),
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
        raise HTTPException(
            status_code=502, detail=f"extraction failed: {exc}"
        ) from exc
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
        # Title collision — append a date suffix and try again.
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

    # Embed inline so the new capability is immediately live in scoring.
    # Fail-soft: the embed worker picks it up on its next 15-min tick.
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

    return ImportedCapabilityStatementOut(
        id=str(cs.id),
        title=cs.title,
        extracted_text_chars=ext.text_chars,
        edit_url=f"/library/capability-statements/{cs.id}/edit",
        notes=notes,
    )
