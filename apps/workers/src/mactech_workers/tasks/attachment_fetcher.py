"""Fetch a solicitation's PDF attachments and extract text for high-moat scoring.

Reuses the PyMuPDF + Tesseract OCR pattern from library_import.py — the
fast path is PyMuPDF text extraction; if a PDF returns < 80 chars (i.e. a
scanned image), we fall through to Tesseract. Capped at OCR_MAX_PAGES per
document to bound worst-case latency on dense scanned RFPs.

Gating lives in sam_ingest (and in the scoring worker, for re-scoring):
this task only runs for opportunities where the title regex matches an
OT/ICS clause/clearance/role pattern OR the base score is already >= 50.
Bounded fetch volume keeps the worker pool from being pinned by Tesseract.

After persisting attachment_text, the task re-enqueues mactech.score.one
so the high_moat_score is recomputed with the new text in scope.
"""

from __future__ import annotations

import asyncio
import io
import logging
import os
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from typing import Any
from uuid import UUID

import fitz  # type: ignore[import-untyped]
import httpx
import pytesseract  # type: ignore[import-untyped]
from mactech_db import async_session_factory
from mactech_db.models import OpportunityRaw
from PIL import Image
from sqlalchemy import select, update

from mactech_workers.celery_app import celery_app

log = logging.getLogger(__name__)

# Tunables — mirror library_import.py constants so behaviour stays uniform.
OCR_FALLBACK_THRESHOLD = 80
OCR_RENDER_DPI = 220
OCR_MAX_PAGES = 12
MAX_TEXT_CHARS = 25_000
MAX_PDF_BYTES = 25 * 1024 * 1024  # 25 MB — skip anything bigger
MAX_ATTACHMENTS_PER_OPP = 8
HTTP_TIMEOUT = httpx.Timeout(45.0, connect=10.0)


@dataclass
class AttachmentFetchResult:
    opportunity_id: str
    attachments_attempted: int
    attachments_fetched: int
    text_chars: int
    status: str  # "ok" | "no_attachments" | "no_text" | "error"
    error_message: str | None = None


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
            pages = [page.get_text("text") for page in doc[:OCR_MAX_PAGES]]
        embedded = "\n\n".join(pages).strip()
    except (fitz.FileDataError, RuntimeError) as exc:
        log.warning("PyMuPDF could not parse PDF: %s", exc)
        return ""
    if len(embedded) >= OCR_FALLBACK_THRESHOLD:
        return embedded
    log.info(
        "attachment_fetcher: PyMuPDF returned %d chars, OCR fall-through",
        len(embedded),
    )
    ocr_text = _ocr_pdf(blob)
    return ocr_text if len(ocr_text) > len(embedded) else embedded


def _candidate_links(opp: OpportunityRaw) -> list[str]:
    """Return up to MAX_ATTACHMENTS_PER_OPP candidate URLs from the raw
    payload's resourceLinks. SAM's noticedesc HTML link (opp.description)
    is intentionally NOT included here — that's handled by the existing
    sam_descriptions worker."""
    payload = opp.raw_payload or {}
    raw = payload.get("resourceLinks") or []
    if not isinstance(raw, list):
        return []
    out: list[str] = []
    for item in raw:
        if not isinstance(item, str) or not item.strip():
            continue
        out.append(item.strip())
        if len(out) >= MAX_ATTACHMENTS_PER_OPP:
            break
    return out


async def _download_one(client: httpx.AsyncClient, url: str) -> bytes | None:
    try:
        head = await client.head(url, follow_redirects=True)
        # Some SAM hosts respond to HEAD with 405; fall through to GET.
        if head.status_code not in (200, 405):
            log.info("attachment HEAD %s for %s — skipping", head.status_code, url)
            return None
        if head.status_code == 200:
            ctype = head.headers.get("content-type", "").lower()
            length = int(head.headers.get("content-length") or 0)
            if length and length > MAX_PDF_BYTES:
                log.info("attachment too large (%d bytes): %s", length, url)
                return None
            if ctype and "pdf" not in ctype and "octet-stream" not in ctype:
                # Skip HTML / image / zip mid-attachments; we only parse PDFs.
                log.info("attachment ctype %s skipped: %s", ctype, url)
                return None
        resp = await client.get(url, follow_redirects=True)
        if resp.status_code >= 400:
            log.info("attachment GET %s for %s", resp.status_code, url)
            return None
        blob = resp.content
        if len(blob) > MAX_PDF_BYTES:
            log.info("attachment GET returned %d bytes — discarding", len(blob))
            return None
        # Quick magic-bytes check; if it's not a PDF, skip.
        if not blob.startswith(b"%PDF"):
            return None
        return blob
    except httpx.HTTPError as exc:
        log.warning("attachment fetch failed for %s: %s", url, exc)
        return None


async def _fetch_for_opportunity(opportunity_id: UUID) -> AttachmentFetchResult:
    started = datetime.now(UTC)
    session_factory = async_session_factory()

    async with session_factory() as session:
        opp = (
            await session.execute(
                select(OpportunityRaw).where(OpportunityRaw.id == opportunity_id)
            )
        ).scalar_one_or_none()
        if opp is None:
            return AttachmentFetchResult(
                opportunity_id=str(opportunity_id),
                attachments_attempted=0,
                attachments_fetched=0,
                text_chars=0,
                status="error",
                error_message="opportunity not found",
            )
        links = _candidate_links(opp)
        if not links:
            # Stamp the timestamp anyway so we don't re-enqueue this opp.
            async with session.begin():
                await session.execute(
                    update(OpportunityRaw)
                    .where(OpportunityRaw.id == opportunity_id)
                    .values(attachments_fetched_at=started)
                )
            return AttachmentFetchResult(
                opportunity_id=str(opportunity_id),
                attachments_attempted=0,
                attachments_fetched=0,
                text_chars=0,
                status="no_attachments",
            )

    sam_key = os.environ.get("SAM_API_KEY") or os.environ.get("SAM_GOV_API_KEY") or ""
    headers = {"User-Agent": "mactech-captureos/attachment-fetcher"}
    fetched = 0
    pieces: list[str] = []

    async with httpx.AsyncClient(timeout=HTTP_TIMEOUT, headers=headers) as client:
        for url in links:
            signed = url
            # SAM resource links are typically pre-signed S3 URLs; some routes
            # require api_key. Append only when the URL is a SAM API host.
            if "api.sam.gov" in url and sam_key and "api_key=" not in url:
                signed = url + ("&" if "?" in url else "?") + f"api_key={sam_key}"
            blob = await _download_one(client, signed)
            if blob is None:
                continue
            text = _pdf_to_text(blob)
            if text:
                pieces.append(text)
                fetched += 1
            if sum(len(p) for p in pieces) >= MAX_TEXT_CHARS:
                break

    combined = "\n\n---\n\n".join(pieces)[:MAX_TEXT_CHARS] if pieces else ""
    completed = datetime.now(UTC)

    async with session_factory() as session, session.begin():
        await session.execute(
            update(OpportunityRaw)
            .where(OpportunityRaw.id == opportunity_id)
            .values(
                attachment_text=combined or None,
                attachments_fetched_at=completed,
            )
        )

    # Trigger a re-score with the new text in scope. Fire-and-forget — if
    # the scoring worker isn't running we still persisted the text.
    if combined:
        try:
            celery_app.send_task(
                "mactech.score.one", args=[str(opportunity_id)]
            )
        except Exception as exc:
            log.warning(
                "attachment_fetcher: couldn't enqueue re-score for %s: %s",
                opportunity_id,
                exc,
            )

    status = "ok" if combined else "no_text"
    return AttachmentFetchResult(
        opportunity_id=str(opportunity_id),
        attachments_attempted=len(links),
        attachments_fetched=fetched,
        text_chars=len(combined),
        status=status,
    )


@celery_app.task(name="mactech.attachments.fetch_one")
def fetch_one_task(opportunity_id: str) -> dict[str, Any]:
    return asdict(asyncio.run(_fetch_for_opportunity(UUID(opportunity_id))))
