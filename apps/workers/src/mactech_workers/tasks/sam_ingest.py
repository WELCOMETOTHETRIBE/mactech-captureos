"""SAM.gov Opportunities ingestion.

Pulls per-NAICS pages from the SAM.gov Get Opportunities Public API and
upserts into `opportunities_raw`. Tracks per-NAICS cursor in
`ingestion_state` so subsequent runs are incremental.

Phase 1 Week 2 scope:
  - Pull all opportunities matching each of MacTech's 20 NAICS codes
    (primary + secondary). No set_aside filter — we store everything
    and let the scoring engine apply MacTech's allowlist downstream.
  - Default backfill window on first run: 30 days.
  - Subsequent runs: postedFrom = last_success_at, postedTo = today.
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import logging
import os
import re
from dataclasses import asdict, dataclass
from datetime import UTC, date, datetime, timedelta
from typing import Any

from mactech_db import async_session_factory
from mactech_db.amendments import record_amendment, snapshot_for_diff
from mactech_db.models import IngestionState, NaicsCode, OpportunityRaw
from mactech_integrations.sam_gov import OpportunityRecord, SamGovOpportunitiesClient
from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from mactech_workers.celery_app import celery_app

# Title-level heuristic for whether an opportunity is worth running the
# attachment fetcher against. Designed to catch OT/ICS cyber work mandated
# inside construction RFPs even when the prime title is generic ("Design
# Build, Fort X Renovation"). Anything matching here gets a PDF fetch +
# parse; the parsed text feeds the high-moat clause detector on next score.
_HIGH_MOAT_TITLE_RE = re.compile(
    r"(?:"
    r"\bUFGS\s*25\b|"
    r"\b25\s*05\s*11\b|\b25\s*08\s*11\b|"
    r"\bFRCS\b|\bUMCS\b|\bSCADA\b|"
    r"\b(?:PIT|platform\s+information\s+technology)\b|"
    r"\bcontrol\s+system(?:s)?\b|"
    r"\bTS/SCI\b|\bSCIF\b|"
    r"\bISSM\b|\bISSE\b|"
    r"\bRMF\b|\bATO\b|\b3PAO\b|"
    r"\b(?:cyber\s*security|cybersecurity)\b"
    r")",
    re.IGNORECASE,
)

log = logging.getLogger(__name__)

SOURCE = "sam_gov"
DEFAULT_BACKFILL_DAYS = 30
DEFAULT_PAGE_SIZE = 1000


@dataclass
class IngestStats:
    naics_code: str
    pages: int
    total_records: int
    upserts: int
    inserts: int
    updates: int
    posted_from: str
    posted_to: str
    duration_ms: int


async def _resolve_window(
    session: AsyncSession, naics_code: str, *, backfill_days: int
) -> tuple[date, date]:
    today = datetime.now(UTC).date()
    state = (
        await session.execute(
            select(IngestionState).where(
                IngestionState.source == SOURCE,
                IngestionState.key == _state_key(naics_code),
            )
        )
    ).scalar_one_or_none()

    if state is None or state.last_success_at is None:
        posted_from = today - timedelta(days=backfill_days)
    else:
        posted_from = state.last_success_at.date()
    return posted_from, today


def _state_key(naics_code: str) -> str:
    return f"opportunities:{naics_code}"


def _normalize_payload(record: OpportunityRecord) -> dict[str, Any]:
    return record.model_dump(mode="json", by_alias=True)


def _hash_payload(payload: dict[str, Any]) -> str:
    blob = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
    return hashlib.sha256(blob).hexdigest()


def _row_from_record(record: OpportunityRecord) -> dict[str, Any]:
    raw = _normalize_payload(record)
    pop = record.place_of_performance.model_dump(mode="json") if record.place_of_performance else None
    return {
        "source": SOURCE,
        "source_id": record.notice_id,
        "notice_type": record.type,
        "title": record.title,
        "description_url": record.description,
        "solicitation_number": record.solicitation_number,
        "agency": record.full_parent_path_name,
        "subagency": None,
        "office": record.office_address.city if record.office_address else None,
        "naics_code": record.naics_code,
        "set_aside": record.type_of_set_aside,
        "posted_at": (
            datetime.combine(record.posted_date, datetime.min.time(), tzinfo=UTC)
            if record.posted_date
            else None
        ),
        "response_deadline": record.response_deadline,
        "place_of_performance": pop,
        "raw_payload": raw,
        "hash": _hash_payload(raw),
    }


def _should_fetch_attachments(record: OpportunityRecord) -> bool:
    """Cheap title-level gate for the attachment fetcher.

    Matches the OT/ICS / cyber / clearance vocabulary that almost always
    indicates a solicitation where the PDF body is worth parsing for the
    high-moat track. Returns False for generic titles to keep PDF
    parsing bounded; opportunities whose base score later climbs above
    HIGH_MOAT_BASE_SCORE_GATE without this match will still get an IVL
    fetch on the next scoring pass — just no attachment text.
    """
    blob = " | ".join(filter(None, [record.title, record.solicitation_number]))
    if not blob:
        return False
    return bool(_HIGH_MOAT_TITLE_RE.search(blob))


async def _upsert_record(session: AsyncSession, record: OpportunityRecord) -> str:
    """Returns 'inserted' | 'updated' | 'unchanged'.

    On 'updated' (an existing opportunity's content hash changed), we
    record an OpportunityAmendment with a structured diff_summary so the
    UI can show what changed. This satisfies G2 (amendment ingest) and
    feeds the audit trail.
    """
    row = _row_from_record(record)

    # Load the existing row (full, not just hash) so we can snapshot it
    # before the upsert. If absent, this is a clean insert.
    existing = (
        await session.execute(
            select(OpportunityRaw).where(
                OpportunityRaw.source == SOURCE,
                OpportunityRaw.source_id == record.notice_id,
            )
        )
    ).scalar_one_or_none()

    existing_hash = existing.hash if existing else None
    if existing_hash == row["hash"]:
        return "unchanged"

    previous_snapshot = snapshot_for_diff(existing) if existing is not None else None

    stmt = (
        pg_insert(OpportunityRaw)
        .values(**row)
        .on_conflict_do_update(
            index_elements=["source", "source_id"],
            set_={
                "notice_type": row["notice_type"],
                "title": row["title"],
                "description_url": row["description_url"],
                "solicitation_number": row["solicitation_number"],
                "agency": row["agency"],
                "office": row["office"],
                "naics_code": row["naics_code"],
                "set_aside": row["set_aside"],
                "posted_at": row["posted_at"],
                "response_deadline": row["response_deadline"],
                "place_of_performance": row["place_of_performance"],
                "raw_payload": row["raw_payload"],
                "hash": row["hash"],
                "updated_at": datetime.now(UTC),
            },
        )
    )
    await session.execute(stmt)

    if existing is not None and previous_snapshot is not None:
        # Re-load to get the post-upsert state for amendment recording.
        refreshed = (
            await session.execute(
                select(OpportunityRaw).where(OpportunityRaw.id == existing.id)
            )
        ).scalar_one()
        await record_amendment(
            session,
            opportunity=refreshed,
            previous_snapshot=previous_snapshot,
            previous_hash=existing_hash,
            new_hash=row["hash"],
        )

    return "inserted" if existing_hash is None else "updated"


async def _record_state(
    session: AsyncSession,
    naics_code: str,
    *,
    posted_to: date,
    upserts: int,
    status: str,
    error: str | None = None,
) -> None:
    now = datetime.now(UTC)
    cursor = posted_to.isoformat()
    state_row = {
        "source": SOURCE,
        "key": _state_key(naics_code),
        "last_run_at": now,
        "last_success_at": now if status == "ok" else None,
        "last_cursor": cursor if status == "ok" else None,
        "last_status": status,
        "last_error": error,
        "updated_at": now,
    }
    stmt = (
        pg_insert(IngestionState)
        .values(**state_row, ingested_count_lifetime=upserts)
        .on_conflict_do_update(
            index_elements=["source", "key"],
            set_={
                "last_run_at": state_row["last_run_at"],
                **(
                    {
                        "last_success_at": state_row["last_success_at"],
                        "last_cursor": state_row["last_cursor"],
                    }
                    if status == "ok"
                    else {}
                ),
                "last_status": status,
                "last_error": error,
                "ingested_count_lifetime": IngestionState.ingested_count_lifetime + upserts,
                "updated_at": state_row["updated_at"],
            },
        )
    )
    await session.execute(stmt)


async def ingest_one_naics(
    naics_code: str,
    *,
    backfill_days: int = DEFAULT_BACKFILL_DAYS,
    page_size: int = DEFAULT_PAGE_SIZE,
    api_key: str | None = None,
) -> IngestStats:
    """Idempotent per-NAICS incremental pull from SAM.gov."""
    started = datetime.now(UTC)
    api_key = api_key or os.environ.get("SAM_API_KEY")
    if not api_key:
        raise RuntimeError("SAM_API_KEY not set")

    session_factory = async_session_factory()
    pages = 0
    total_records = 0
    inserts = 0
    updates = 0
    upserts = 0

    posted_from: date | None = None
    posted_to: date | None = None

    async with session_factory() as session:
        try:
            async with SamGovOpportunitiesClient(api_key=api_key) as client, session.begin():
                posted_from, posted_to = await _resolve_window(
                    session, naics_code, backfill_days=backfill_days
                )
                async for page in client.iter_opportunities(
                    posted_from=posted_from,
                    posted_to=posted_to,
                    ncode=naics_code,
                    page_size=page_size,
                ):
                    pages += 1
                    total_records = page.total_records
                    for record in page.opportunities_data:
                        outcome = await _upsert_record(session, record)
                        if outcome == "inserted":
                            inserts += 1
                            upserts += 1
                        elif outcome == "updated":
                            updates += 1
                            upserts += 1
                        # Gate the attachment fetcher on the title-level heuristic
                        # to bound PDF parsing volume. "unchanged" rows are skipped
                        # — we'd be repeating work the previous run did.
                        if outcome in ("inserted", "updated"):
                            row = (
                                await session.execute(
                                    select(OpportunityRaw.id).where(
                                        OpportunityRaw.source == SOURCE,
                                        OpportunityRaw.source_id == record.notice_id,
                                    )
                                )
                            ).scalar_one_or_none()
                            if row is not None:
                                try:
                                    celery_app.send_task(
                                        "mactech.cyber_scope.scan_one",
                                        args=[str(row)],
                                        kwargs={"scan_pass": "description_only"},
                                    )
                                except Exception as exc:
                                    log.warning(
                                        "sam_ingest: couldn't enqueue cyber_scope for %s: %s",
                                        record.notice_id,
                                        exc,
                                    )
                                if _should_fetch_attachments(record):
                                    try:
                                        celery_app.send_task(
                                            "mactech.attachments.fetch_one",
                                            args=[str(row)],
                                        )
                                    except Exception as exc:
                                        log.warning(
                                            "sam_ingest: couldn't enqueue attachment_fetcher for %s: %s",
                                            record.notice_id,
                                            exc,
                                        )

                await _record_state(
                    session, naics_code, posted_to=posted_to, upserts=upserts, status="ok"
                )
        except Exception as exc:  # pragma: no cover -- exercised in prod
            await session.rollback()
            async with session.begin():
                await _record_state(
                    session,
                    naics_code,
                    posted_to=posted_to or datetime.now(UTC).date(),
                    upserts=0,
                    status="error",
                    error=f"{type(exc).__name__}: {exc}"[:1000],
                )
            raise

    duration_ms = int((datetime.now(UTC) - started).total_seconds() * 1000)
    return IngestStats(
        naics_code=naics_code,
        pages=pages,
        total_records=total_records,
        upserts=upserts,
        inserts=inserts,
        updates=updates,
        posted_from=posted_from.isoformat(),
        posted_to=posted_to.isoformat(),
        duration_ms=duration_ms,
    )


async def ingest_all_mactech_naics(
    *, backfill_days: int = DEFAULT_BACKFILL_DAYS
) -> list[IngestStats]:
    """Sequentially run incremental ingest for every MacTech NAICS code in the DB."""
    session_factory = async_session_factory()
    async with session_factory() as session:
        rows = (
            await session.execute(
                select(NaicsCode.code).where(
                    NaicsCode.mactech_tier.in_(["primary", "secondary"])
                ).order_by(NaicsCode.code)
            )
        ).scalars().all()

    log.info("ingesting %d NAICS codes", len(rows))
    stats: list[IngestStats] = []
    for code in rows:
        try:
            s = await ingest_one_naics(code, backfill_days=backfill_days)
            log.info("naics %s: +%d (%d inserts, %d updates) over %d pages",
                     code, s.upserts, s.inserts, s.updates, s.pages)
            stats.append(s)
        except Exception as exc:
            log.exception("naics %s failed: %s", code, exc)
    return stats


# --- Celery task wrappers (thin shims around the async functions above) ---


@celery_app.task(name="mactech.sam.ingest_one_naics")
def ingest_one_naics_task(naics_code: str, *, backfill_days: int = DEFAULT_BACKFILL_DAYS) -> dict[str, Any]:
    return asdict(asyncio.run(ingest_one_naics(naics_code, backfill_days=backfill_days)))


@celery_app.task(name="mactech.sam.ingest_all")
def ingest_all_task(*, backfill_days: int = DEFAULT_BACKFILL_DAYS) -> list[dict[str, Any]]:
    return [asdict(s) for s in asyncio.run(ingest_all_mactech_naics(backfill_days=backfill_days))]


# --- First-feed ingest for net-new tenants (Sprint 16) ---


async def first_feed_ingest_for_tenant(
    tenant_slug: str,
    *,
    backfill_days: int = 30,
) -> dict[str, Any]:
    """Sequential ingest for one tenant's full NAICS list, then chain
    into a one-off scoring sweep so the new tenant sees scored opps in
    minutes instead of hours.

    If the tenant has no `target_naics` set, this falls back to the
    seed-config NAICS list — same behaviour as the cron beat — so
    MacTech-style tenants who haven't customised their picker still
    get a useful first feed.
    """
    from mactech_db.models import Tenant as _T

    session_factory = async_session_factory()
    async with session_factory() as session:
        tenant = (
            await session.execute(select(_T).where(_T.slug == tenant_slug))
        ).scalar_one_or_none()
        if tenant is None:
            return {
                "tenant_slug": tenant_slug,
                "status": "tenant_not_found",
                "naics_count": 0,
                "ingest_stats": [],
            }

        target_naics: list[str] = list(tenant.target_naics or [])

        if not target_naics:
            seeded = (
                await session.execute(
                    select(NaicsCode.code).where(
                        NaicsCode.mactech_tier.in_(["primary", "secondary"])
                    )
                )
            ).scalars().all()
            target_naics = list(seeded)

    log.info(
        "first-feed ingest for tenant=%s — %d NAICS, backfill=%d days",
        tenant_slug,
        len(target_naics),
        backfill_days,
    )
    stats: list[IngestStats] = []
    for code in target_naics:
        try:
            s = await ingest_one_naics(code, backfill_days=backfill_days)
            stats.append(s)
        except Exception as exc:
            log.exception("first-feed ingest naics=%s failed: %s", code, exc)

    # Chain into scoring so the freshly-ingested opps land in the user's
    # dashboard via the same Sprint 15 path. Fire as a separate Celery
    # task so this function returns promptly and the chain stays observable.
    try:
        celery_app.send_task(
            "mactech.onboarding.first_score",
            args=[tenant_slug],
            kwargs={"batch_size": 200},
        )
    except Exception as exc:
        log.warning(
            "first-feed ingest finished but couldn't fire score task: %s",
            exc,
        )

    return {
        "tenant_slug": tenant_slug,
        "status": "ok",
        "naics_count": len(target_naics),
        "ingest_stats": [asdict(s) for s in stats],
    }


@celery_app.task(name="mactech.onboarding.first_feed_ingest")
def first_feed_ingest_task(
    tenant_slug: str, backfill_days: int = 30
) -> dict[str, Any]:
    return asyncio.run(
        first_feed_ingest_for_tenant(
            tenant_slug, backfill_days=backfill_days
        )
    )
