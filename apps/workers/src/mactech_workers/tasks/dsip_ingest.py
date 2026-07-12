"""Direct DSIP (dodsbirsttr.mil) ingest + per-topic enrichment.

Replaces the Apify/Playwright path (`apify_dsip_lookup.py`). DSIP's public
JSON API is reachable server-side, so we pull the full content of topics
directly — no browser, no Apify credits, no LLM extraction (the API returns
discrete structured fields).

Lives in the workers package (not the API) so the Celery Beat schedule can
drive it, matching the DHS APFS / DOE / NASA direct-ingest tasks. The API
imports the plain async helpers from here (api depends on workers).

Entry points:

  `refresh_dsip_topics(scope=...)` — bulk: paginate the search endpoint,
      (optionally) fetch each topic's /details, and upsert into `sbir_topics`
      with source='dsip'. Two scopes:
        - SCOPE_OPEN   (default): open + pre-release, WITH full details. ~70
          topics, ~50s. This is the actionable feed; run daily.
        - SCOPE_CLOSED: the historical archive (~32k closed topics back to
          2003). Metadata-only by default (fetching /details for 32k topics
          is infeasible) and capped at `max_topics`, newest-first by close
          date. Details are filled lazily via `enrich_dsip_topic` when a user
          opens one. Run weekly.

  `enrich_dsip_topic(topic_number)` — single: resolve topic_number → topicId,
      fetch /details (+ optional PDF text), update every `sbir_topics` row
      with that number across sources. Used by the 'Use this topic' route.

Celery tasks:
  mactech.dsip.ingest_open    — daily open+pre-release with details
  mactech.dsip.ingest_closed  — weekly closed metadata backfill (capped)

Source name is 'dsip' so a DSIP row coexists with any 'sbirdashboard' row
for the same topic_number (different source ⇒ different uniqueness key).
"""

from __future__ import annotations

import asyncio
import logging
from dataclasses import asdict, dataclass
from datetime import UTC, datetime, timedelta
from typing import Any

from mactech_db import unscoped_session
from mactech_db.models import SBIRTopic
from mactech_integrations.dsip import (
    SCOPE_CLOSED,
    SCOPE_OPEN,
    DsipClient,
    DsipError,
    DsipFullTopic,
    DsipTopicSummary,
)
from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import insert as pg_insert

from mactech_workers.celery_app import celery_app

log = logging.getLogger(__name__)

SOURCE = "dsip"
DEFAULT_STALE_AFTER = timedelta(hours=6)
# The closed archive is ~32k topics (reported total is clamped at 32767).
# The weekly backfill takes the most-recently-closed slice, not all of it.
DEFAULT_CLOSED_MAX = 3000

# DSIP component codes → the submission engine's component vocabulary, so
# /sbir/submit pre-fill and founder routing work the same as sbirdashboard.
_COMPONENT_MAP = {
    "ARMY": "Army",
    "USA": "Army",
    "NAVY": "Navy",
    "USN": "Navy",
    "USMC": "Navy",  # Marine Corps proposals route through DON / Navy.
    "USAF": "Air Force",
    "AIR FORCE": "Air Force",
    "USSF": "Space Force",
    "SPACE FORCE": "Space Force",
    "DARPA": "DARPA",
    "DLA": "DLA",
    "DHA": "DHA",
    "MDA": "MDA",
    "OSD": "OSD",
    "SOCOM": "SOCOM",
    "USSOCOM": "SOCOM",
    "CBD": "CBD",
    "NGA": "NGA",
}


@dataclass(frozen=True)
class DsipSyncResult:
    scope: str
    fetched: int
    upserted: int
    details_ok: int
    truncated: bool
    error: str | None
    elapsed_secs: float


@dataclass(frozen=True)
class DsipEnrichResult:
    topic_number: str
    success: bool
    error: str | None
    pdf_url: str | None
    pdf_text_chars: int
    updated_rows: int


def _map_component(raw: str | None) -> str | None:
    if not raw:
        return None
    return _COMPONENT_MAP.get(raw.strip().upper(), raw.strip().title())


def _map_status(raw: str | None) -> str:
    if not raw:
        return "unknown"
    s = raw.strip().lower()
    if s in ("open", "active"):
        return "open"
    if s in ("pre-release", "pre release", "prerelease"):
        return "prerelease"
    if s == "closed":
        return "closed"
    return "unknown"


def _map_itar(itar: bool | None) -> str | None:
    if itar is None:
        return None
    return "yes" if itar else "no"


def _topic_url(topic_id: str) -> str:
    return f"https://www.dodsbirsttr.mil/topics-app/#/topics/{topic_id}"


def _full_topic_to_values(full: DsipFullTopic, *, now: datetime, pdf_url: str) -> dict[str, object]:
    s: DsipTopicSummary = full.summary
    d = full.detail
    phase = "/".join(s.phases)[:16] if s.phases else None
    description = d.composed_description() if d else s.solicitation_title
    tech = d.technology_areas if (d and d.technology_areas) else None
    mods = d.focus_areas if (d and d.focus_areas) else None
    keywords = d.keywords if (d and d.keywords) else None
    itar = _map_itar(d.itar) if d else None
    # Only claim a row is DSIP-enriched when we actually pulled its details.
    # Metadata-only closed rows stay un-enriched so the UI still offers the
    # 'Use this topic' lazy detail fetch on them.
    enriched_at = now if d is not None else None
    return {
        "source": SOURCE,
        "topic_number": s.topic_code,
        "title": s.title,
        "component": _map_component(s.component),
        "program": s.program,
        "phase": phase,
        "status": _map_status(s.status),
        "prerelease_date": s.prerelease_start,
        "open_date": s.open_date,
        "close_date": s.close_date,
        "description": description,
        "url": _topic_url(s.topic_id),
        "technology_areas": tech,
        "modernization_priorities": mods,
        "keywords": keywords,
        "itar_export_status": itar,
        "phase_i_ceiling": None,
        "phase_i_duration_months": None,
        "raw": {"summary": s.raw, "detail": d.raw if d else None},
        "apify_run_id": None,
        "last_seen_at": now,
        "dsip_enriched_at": enriched_at,
        "dsip_tpoc": s.tpoc,
        "dsip_pdf_url": pdf_url,
    }


async def is_stale(*, stale_after: timedelta = DEFAULT_STALE_AFTER) -> bool:
    """True when DSIP topics have never been ingested, or the most recent
    ingest is older than `stale_after`."""
    async with unscoped_session() as session:
        latest = (
            await session.execute(
                select(func.max(SBIRTopic.last_seen_at)).where(SBIRTopic.source == SOURCE)
            )
        ).scalar_one_or_none()
    if latest is None:
        return True
    return bool(datetime.now(UTC) - latest > stale_after)


async def refresh_dsip_topics(
    *,
    scope: str = SCOPE_OPEN,
    page_size: int = 50,
    fetch_details: bool = True,
    max_topics: int | None = None,
) -> DsipSyncResult:
    """Bulk ingest DSIP topics for a scope. Never raises — failures land in
    the `error` field so an inline caller can degrade gracefully.

    For SCOPE_CLOSED, `fetch_details` defaults are irrelevant to the caller's
    intent: closed is metadata-only in practice (pass fetch_details=False).
    """
    started = datetime.now(UTC)
    fetched = 0
    upserted = 0
    details_ok = 0
    truncated = False
    try:
        async with DsipClient() as client:
            # Learn the true total first so we can report truncation honestly.
            head = await client.search_page(scope=scope, size=1, page=0)
            total_available = head.total
            summaries = await client.iter_topics(
                scope=scope, page_size=page_size, max_topics=max_topics
            )
            fetched = len(summaries)
            truncated = max_topics is not None and total_available > fetched
            if truncated:
                log.info(
                    "dsip %s ingest capped at %d of %d available topics",
                    scope,
                    fetched,
                    total_available,
                )
            now = datetime.now(UTC)
            async with unscoped_session() as session:
                for summary in summaries:
                    if fetch_details:
                        full = await client.fetch_full_topic(summary)
                        if full.detail is not None:
                            details_ok += 1
                    else:
                        full = DsipFullTopic(summary=summary)
                    values = _full_topic_to_values(
                        full, now=now, pdf_url=client.pdf_url(summary.topic_id)
                    )
                    stmt = (
                        pg_insert(SBIRTopic)
                        .values(**values)
                        .on_conflict_do_update(
                            index_elements=["source", "topic_number"],
                            set_={
                                k: v
                                for k, v in values.items()
                                if k not in ("source", "topic_number")
                            },
                        )
                    )
                    await session.execute(stmt)
                    upserted += 1
    except DsipError as exc:
        elapsed = (datetime.now(UTC) - started).total_seconds()
        log.warning("dsip %s refresh failed: %s", scope, exc)
        return DsipSyncResult(
            scope=scope,
            fetched=fetched,
            upserted=upserted,
            details_ok=details_ok,
            truncated=truncated,
            error=str(exc)[:300],
            elapsed_secs=elapsed,
        )
    except Exception as exc:
        elapsed = (datetime.now(UTC) - started).total_seconds()
        log.exception("dsip %s refresh crashed", scope)
        return DsipSyncResult(
            scope=scope,
            fetched=fetched,
            upserted=upserted,
            details_ok=details_ok,
            truncated=truncated,
            error=f"{exc.__class__.__name__}: {exc}"[:300],
            elapsed_secs=elapsed,
        )

    elapsed = (datetime.now(UTC) - started).total_seconds()
    log.info(
        "dsip %s refresh: fetched=%d upserted=%d details_ok=%d truncated=%s elapsed=%.2fs",
        scope,
        fetched,
        upserted,
        details_ok,
        truncated,
        elapsed,
    )
    return DsipSyncResult(
        scope=scope,
        fetched=fetched,
        upserted=upserted,
        details_ok=details_ok,
        truncated=truncated,
        error=None,
        elapsed_secs=elapsed,
    )


async def enrich_dsip_topic(topic_number: str, *, with_pdf_text: bool = True) -> DsipEnrichResult:
    """Resolve topic_number → topicId, fetch full DSIP detail, and update
    every `sbir_topics` row with that number (across sources).

    Replaces `apify_dsip_lookup.run_dsip_lookup`. Direct, cheap, no LLM.
    """
    try:
        async with DsipClient() as client:
            summary = await client.resolve_topic_id(topic_number)
            if summary is None:
                return DsipEnrichResult(
                    topic_number=topic_number,
                    success=False,
                    error="topic not found on DSIP",
                    pdf_url=None,
                    pdf_text_chars=0,
                    updated_rows=0,
                )
            detail = await client.fetch_details(summary.topic_id)
            pdf_url = client.pdf_url(summary.topic_id)
            pdf_text: str | None = None
            if with_pdf_text:
                pdf_text = await _extract_pdf_text(client, summary.topic_id)
    except DsipError as exc:
        log.warning("dsip enrich failed for %s: %s", topic_number, exc)
        return DsipEnrichResult(
            topic_number=topic_number,
            success=False,
            error=str(exc)[:300],
            pdf_url=None,
            pdf_text_chars=0,
            updated_rows=0,
        )

    full = DsipFullTopic(summary=summary, detail=detail)
    updated = await _persist_enrichment(
        topic_number=topic_number, full=full, pdf_url=pdf_url, pdf_text=pdf_text
    )
    return DsipEnrichResult(
        topic_number=topic_number,
        success=True,
        error=None,
        pdf_url=pdf_url,
        pdf_text_chars=len(pdf_text) if pdf_text else 0,
        updated_rows=updated,
    )


async def _extract_pdf_text(client: DsipClient, topic_id: str) -> str | None:
    content = await client.fetch_pdf(topic_id)
    if not content:
        return None
    try:
        import fitz  # type: ignore[import-untyped]
    except ImportError:
        log.info("pymupdf not available; skipping DSIP PDF decode")
        return None
    try:
        with fitz.open(stream=content, filetype="pdf") as doc:
            text = "\n".join(page.get_text() for page in doc)
    except Exception as exc:
        log.info("dsip pdf decode failed for %s: %s", topic_id, exc)
        return None
    return text.strip()[:80_000] or None


async def _persist_enrichment(
    *,
    topic_number: str,
    full: DsipFullTopic,
    pdf_url: str | None,
    pdf_text: str | None,
) -> int:
    """Update every row matching this topic_number across sources so the
    submitter sees the same enriched data regardless of which row it holds.
    """
    s = full.summary
    d = full.detail
    now = datetime.now(UTC)
    async with unscoped_session() as session:
        rows = (
            (await session.execute(select(SBIRTopic).where(SBIRTopic.topic_number == topic_number)))
            .scalars()
            .all()
        )
        if not rows:
            log.info("dsip enrich %s — no matching row to persist", topic_number)
            return 0
        for row in rows:
            row.dsip_enriched_at = now
            row.dsip_tpoc = s.tpoc
            if pdf_url:
                row.dsip_pdf_url = pdf_url
            if pdf_text:
                row.dsip_pdf_text = pdf_text
            # Fill richer content only where DSIP produced a value — the
            # lighter sbirdashboard values win when DSIP is empty.
            if d is not None:
                composed = d.composed_description()
                if composed:
                    row.description = composed
                if s.title:
                    row.title = s.title
                if s.component:
                    row.component = _map_component(s.component)
                if s.program:
                    row.program = s.program
                if s.phases:
                    row.phase = "/".join(s.phases)[:16]
                if d.technology_areas:
                    row.technology_areas = d.technology_areas
                if d.focus_areas:
                    row.modernization_priorities = d.focus_areas
                if d.keywords:
                    row.keywords = d.keywords
                itar = _map_itar(d.itar)
                if itar is not None:
                    row.itar_export_status = itar
    return len(rows)


# ---------- Celery task wrappers ----------


@celery_app.task(name="mactech.dsip.ingest_open")
def dsip_ingest_open_task() -> dict[str, Any]:
    """Daily: open + pre-release topics with full content."""
    return asdict(asyncio.run(refresh_dsip_topics(scope=SCOPE_OPEN, fetch_details=True)))


@celery_app.task(name="mactech.dsip.ingest_closed")
def dsip_ingest_closed_task(max_topics: int = DEFAULT_CLOSED_MAX) -> dict[str, Any]:
    """Weekly: most-recently-closed topics, metadata only (details on demand)."""
    return asdict(
        asyncio.run(
            refresh_dsip_topics(scope=SCOPE_CLOSED, fetch_details=False, max_topics=max_topics)
        )
    )
