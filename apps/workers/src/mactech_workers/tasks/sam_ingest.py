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
from dataclasses import asdict, dataclass
from datetime import UTC, date, datetime, timedelta
from typing import Any

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from mactech_db import async_session_factory
from mactech_db.models import IngestionState, NaicsCode, OpportunityRaw
from mactech_integrations.sam_gov import OpportunityRecord, SamGovOpportunitiesClient
from mactech_workers.celery_app import celery_app

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


async def _upsert_record(session: AsyncSession, record: OpportunityRecord) -> str:
    """Returns 'inserted' | 'updated' | 'unchanged'."""
    row = _row_from_record(record)
    existing_hash = (
        await session.execute(
            select(OpportunityRaw.hash).where(
                OpportunityRaw.source == SOURCE,
                OpportunityRaw.source_id == record.notice_id,
            )
        )
    ).scalar_one_or_none()

    if existing_hash == row["hash"]:
        return "unchanged"

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

    async with session_factory() as session:
        posted_from, posted_to = await _resolve_window(
            session, naics_code, backfill_days=backfill_days
        )

        try:
            async with SamGovOpportunitiesClient(api_key=api_key) as client:
                async with session.begin():
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

                    await _record_state(
                        session, naics_code, posted_to=posted_to, upserts=upserts, status="ok"
                    )
        except Exception as exc:  # pragma: no cover -- exercised in prod
            async with session.begin():
                await _record_state(
                    session,
                    naics_code,
                    posted_to=posted_to,
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
