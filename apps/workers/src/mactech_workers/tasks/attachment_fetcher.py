"""Acquire and parse a solicitation's full procurement package (Slice 2).

Generalized from the PDF-only, single-blob fetcher. For each opportunity it:
  1. downloads every publicly accessible ``resourceLinks`` file,
  2. preserves the original binary in the object store (content-hash keyed),
  3. safely expands ZIPs (bomb/traversal protected),
  4. extracts text across formats (PDF/DOCX/XLSX/CSV/TXT/HTML; OCR only when a
     PDF has no embedded text),
  5. classifies each document and records page/section provenance,
  6. writes ``opportunity_documents`` + ``document_sections`` rows, reprocessing
     only when a file's content hash changed, and
  7. summarizes package completeness on ``opportunities_raw.documents_status``.

It still writes the legacy concatenated ``attachment_text`` blob and re-enqueues
scoring + cyber-scope so downstream detection is unchanged during the
transition. Enqueue gating (which opportunities get here) is unchanged and still
lives in ``sam_ingest`` / ``cyber_scope_sam_search``.
"""

from __future__ import annotations

import asyncio
import hashlib
import logging
import os
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from urllib.parse import unquote, urlparse
from uuid import UUID

import httpx
from mactech_db import async_session_factory
from mactech_db.models import DocumentSection, OpportunityDocument, OpportunityRaw
from sqlalchemy import select, update

from mactech_workers.celery_app import celery_app
from mactech_workers.documents import (
    ArchiveError,
    build_sections,
    classify_document,
    expand_archive,
    extract_text,
    get_document_store,
    storage_key_for,
)
from mactech_workers.documents.archive import is_zip

log = logging.getLogger(__name__)

MAX_TEXT_CHARS = 25_000  # legacy attachment_text cap (unchanged)
MAX_DOC_BYTES = 40 * 1024 * 1024  # per-download ceiling
MAX_ATTACHMENTS_PER_OPP = 12
HTTP_TIMEOUT = httpx.Timeout(45.0, connect=10.0)


@dataclass
class _DownloadedFile:
    filename: str
    source_url: str
    data: bytes
    archived_from: str | None = None


@dataclass
class AttachmentFetchResult:
    opportunity_id: str
    attachments_attempted: int
    documents_written: int
    documents_reused: int
    documents_failed: int
    text_chars: int
    completeness: str
    status: str  # "ok" | "no_attachments" | "no_text" | "error"
    error_message: str | None = None
    per_document: list[dict] = field(default_factory=list)


def _candidate_links(opp: OpportunityRaw) -> list[str]:
    payload = opp.raw_payload or {}
    raw = payload.get("resourceLinks") or []
    if not isinstance(raw, list):
        return []
    out: list[str] = []
    for item in raw:
        if isinstance(item, str) and item.strip():
            out.append(item.strip())
        if len(out) >= MAX_ATTACHMENTS_PER_OPP:
            break
    return out


def _filename_from(url: str, headers: httpx.Headers | None) -> str:
    if headers is not None:
        disp = headers.get("content-disposition", "")
        if "filename=" in disp:
            name = disp.split("filename=", 1)[1].strip().strip('"; ')
            if name:
                return unquote(name)
    path = urlparse(url).path
    base = unquote(path.rsplit("/", 1)[-1]) if path else ""
    return base or "attachment"


async def _download_one(client: httpx.AsyncClient, url: str) -> tuple[bytes, str] | None:
    """Return (bytes, filename) or None. Accepts any content type under the size
    ceiling — format is sniffed from the bytes downstream."""
    try:
        head = await client.head(url, follow_redirects=True)
        if head.status_code == 200:
            length = int(head.headers.get("content-length") or 0)
            if length and length > MAX_DOC_BYTES:
                log.info("attachment too large (%d bytes): %s", length, url)
                return None
        elif head.status_code not in (403, 405, 501):
            # 403/405/501 often just mean "no HEAD" — fall through to GET.
            log.info("attachment HEAD %s for %s — skipping", head.status_code, url)
            return None
        resp = await client.get(url, follow_redirects=True)
        if resp.status_code >= 400:
            log.info("attachment GET %s for %s", resp.status_code, url)
            return None
        blob = resp.content
        if len(blob) > MAX_DOC_BYTES:
            log.info("attachment GET returned %d bytes — discarding", len(blob))
            return None
        return blob, _filename_from(url, resp.headers)
    except httpx.HTTPError as exc:
        log.warning("attachment fetch failed for %s: %s", url, exc)
        return None


async def _gather_files(links: list[str], *, sam_key: str) -> tuple[list[_DownloadedFile], int]:
    """Download every link, expanding archives. Returns (files, attempted)."""
    headers = {"User-Agent": "mactech-captureos/attachment-fetcher"}
    files: list[_DownloadedFile] = []
    attempted = 0
    async with httpx.AsyncClient(timeout=HTTP_TIMEOUT, headers=headers) as client:
        for url in links:
            attempted += 1
            signed = url
            if "api.sam.gov" in url and sam_key and "api_key=" not in url:
                signed = url + ("&" if "?" in url else "?") + f"api_key={sam_key}"
            got = await _download_one(client, signed)
            if got is None:
                continue
            blob, filename = got
            if is_zip(blob) and not filename.lower().endswith((".docx", ".xlsx", ".xlsm")):
                try:
                    for member in expand_archive(blob, source_name=filename):
                        files.append(
                            _DownloadedFile(
                                filename=member.filename,
                                source_url=url,
                                data=member.data,
                                archived_from=member.archived_from,
                            )
                        )
                except ArchiveError as exc:
                    log.warning("unsafe/invalid archive %s: %s", filename, exc)
                    continue
            else:
                files.append(_DownloadedFile(filename=filename, source_url=url, data=blob))
    return files, attempted


def _completeness(*, links: int, description: bool, parsed: int, failed: int) -> str:
    if links == 0:
        return "description_only" if description else "metadata_only"
    if parsed == 0:
        return "description_only" if description else "metadata_only"
    if failed == 0:
        return "all_accessible"
    return "partial_attachments"


async def persist_documents(
    session, opportunity_id: UUID, files: list[_DownloadedFile]
) -> tuple[list[dict], str, int, int, int]:
    """Store binaries + write document/section rows, reprocessing only changed
    hashes. Returns (per_document summaries, combined_text, written, reused,
    failed). Caller owns the transaction."""
    store = get_document_store()
    per_doc: list[dict] = []
    text_pieces: list[str] = []
    written = reused = failed = 0

    existing_hashes = set(
        (
            await session.execute(
                select(OpportunityDocument.content_hash).where(
                    OpportunityDocument.opportunity_id == opportunity_id
                )
            )
        )
        .scalars()
        .all()
    )

    now = datetime.now(UTC)
    for f in files:
        content_hash = hashlib.sha256(f.data).hexdigest()
        summary = {"filename": f.filename, "hash": content_hash[:12]}
        if content_hash in existing_hashes:
            reused += 1
            summary["status"] = "reused"
            per_doc.append(summary)
            continue
        existing_hashes.add(content_hash)

        extracted = extract_text(f.filename, f.data)
        doc_class = classify_document(f.filename, extracted.text)
        try:
            storage_key = store.put(
                storage_key_for(str(opportunity_id), content_hash, f.filename), f.data
            )
        except Exception as exc:  # storage failure is non-fatal to parsing
            log.warning("document store put failed for %s: %s", f.filename, exc)
            storage_key = None

        if extracted.ok:
            status = "parsed"
            if extracted.text:
                text_pieces.append(extracted.text)
        elif extracted.format == "unknown" or (
            extracted.error and "unsupported" in extracted.error
        ):
            status = "unsupported"
            failed += 1
        else:
            status = "partially_parsed"

        doc = OpportunityDocument(
            opportunity_id=opportunity_id,
            source_url=f.source_url[:2048],
            filename=f.filename[:512],
            doc_class=doc_class,
            content_hash=content_hash,
            storage_key=storage_key,
            mime_type=extracted.mime_type,
            doc_format=extracted.format,
            byte_size=len(f.data),
            page_count=extracted.page_count,
            extracted_char_count=len(extracted.text),
            ocr_used=extracted.ocr_used,
            archived_from=(f.archived_from or None),
            status=status,
            error=(extracted.error or None),
            fetched_at=now,
        )
        session.add(doc)
        await session.flush()  # get doc.id

        sections = build_sections(extracted.pages or ([extracted.text] if extracted.text else []))
        for s in sections:
            session.add(
                DocumentSection(
                    document_id=doc.id,
                    opportunity_id=opportunity_id,
                    ordinal=s.ordinal,
                    page_number=s.page_number,
                    section_heading=s.section_heading,
                    section_path=s.section_path,
                    char_start=s.char_start,
                    char_end=s.char_end,
                    text=s.text,
                )
            )
        written += 1
        summary["status"] = status
        summary["doc_class"] = doc_class
        summary["format"] = extracted.format
        per_doc.append(summary)

    combined = "\n\n---\n\n".join(text_pieces)[:MAX_TEXT_CHARS] if text_pieces else ""
    return per_doc, combined, written, reused, failed


async def _fetch_for_opportunity(opportunity_id: UUID) -> AttachmentFetchResult:
    session_factory = async_session_factory()
    async with session_factory() as session:
        opp = (
            await session.execute(select(OpportunityRaw).where(OpportunityRaw.id == opportunity_id))
        ).scalar_one_or_none()
        if opp is None:
            return AttachmentFetchResult(
                opportunity_id=str(opportunity_id),
                attachments_attempted=0,
                documents_written=0,
                documents_reused=0,
                documents_failed=0,
                text_chars=0,
                completeness="metadata_only",
                status="error",
                error_message="opportunity not found",
            )
        links = _candidate_links(opp)
        has_description = bool(opp.description_text and opp.description_text.strip())

    if not links:
        completeness = _completeness(links=0, description=has_description, parsed=0, failed=0)
        async with session_factory() as session, session.begin():
            await session.execute(
                update(OpportunityRaw)
                .where(OpportunityRaw.id == opportunity_id)
                .values(
                    attachments_fetched_at=datetime.now(UTC),
                    documents_status={
                        "completeness": completeness,
                        "discovered": 0,
                        "parsed": 0,
                        "failed": 0,
                    },
                )
            )
        return AttachmentFetchResult(
            opportunity_id=str(opportunity_id),
            attachments_attempted=0,
            documents_written=0,
            documents_reused=0,
            documents_failed=0,
            text_chars=0,
            completeness=completeness,
            status="no_attachments",
        )

    sam_key = os.environ.get("SAM_API_KEY") or os.environ.get("SAM_GOV_API_KEY") or ""
    files, attempted = await _gather_files(links, sam_key=sam_key)

    async with session_factory() as session, session.begin():
        per_doc, combined, written, reused, failed = await persist_documents(
            session, opportunity_id, files
        )
        completeness = _completeness(
            links=len(links), description=has_description, parsed=written + reused, failed=failed
        )
        values = {
            "attachments_fetched_at": datetime.now(UTC),
            "documents_status": {
                "completeness": completeness,
                "discovered": len(files),
                "written": written,
                "reused": reused,
                "failed": failed,
            },
        }
        # Preserve the legacy blob for downstream detection during transition.
        # Only overwrite when we actually extracted fresh text this run.
        if combined:
            values["attachment_text"] = combined
        await session.execute(
            update(OpportunityRaw).where(OpportunityRaw.id == opportunity_id).values(**values)
        )

    if combined:
        for task, kwargs in (
            ("mactech.score.one", {}),
            ("mactech.cyber_scope.scan_one", {"scan_pass": "with_attachments"}),
        ):
            try:
                celery_app.send_task(task, args=[str(opportunity_id)], kwargs=kwargs)
            except Exception as exc:
                log.warning(
                    "attachment_fetcher: enqueue %s failed for %s: %s", task, opportunity_id, exc
                )

    status = "ok" if combined else "no_text"
    return AttachmentFetchResult(
        opportunity_id=str(opportunity_id),
        attachments_attempted=attempted,
        documents_written=written,
        documents_reused=reused,
        documents_failed=failed,
        text_chars=len(combined),
        completeness=completeness,
        status=status,
        per_document=per_doc,
    )


@celery_app.task(name="mactech.attachments.fetch_one")
def fetch_one_task(opportunity_id: str) -> dict:
    return asdict(asyncio.run(_fetch_for_opportunity(UUID(opportunity_id))))
