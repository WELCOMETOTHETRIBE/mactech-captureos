"""Inline (non-Celery) SBIR topics refresh from sbirdashboard.com.

The Apify worker covers the heterogeneous landing-page sources (DSIP,
sbir.gov, AFWERX, …) — slow, accurate, and gated behind a user-clicked
"Refresh feed" button. This module covers the *one* source that gives us
structured JSON inline (sbirdashboard.com), runs sub-second, and is safe
to trigger on every /sbir page load when the cached rows are stale.

Source name on the row is `"sbirdashboard"` so the row coexists with any
later DSIP/sbir.gov copy of the same topic_number (different source ⇒
different uniqueness key).
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from mactech_db import unscoped_session
from mactech_db.models import SBIRTopic
from mactech_integrations.sbirdashboard import (
    SBIRDashboardError,
    SBIRDashboardTopic,
    fetch_sbirdashboard_topics,
)
from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import insert as pg_insert

log = logging.getLogger(__name__)

SOURCE = "sbirdashboard"
DEFAULT_STALE_AFTER = timedelta(minutes=15)


# sbirdashboard uses agency codes (USAF, USA, USN, USMC, USSF, DARPA, …).
# Map to the engine's component vocabulary so /sbir/submit pre-fill works.
_COMPONENT_MAP = {
    "USAF": "Air Force",
    "USSF": "Space Force",
    "USA": "Army",
    "USN": "Navy",
    "USMC": "Navy",  # Marine Corps proposals route through DON / Navy.
    "DARPA": "DARPA",
    "DLA": "DLA",
    "DHA": "DHA",
    "MDA": "MDA",
    "OSD": "OSD",
    "SOCOM": "SOCOM",
    "USSOCOM": "SOCOM",
}


@dataclass(frozen=True)
class TopicsSyncResult:
    fetched: int
    upserted: int
    error: str | None
    elapsed_secs: float


def _map_component(raw: str | None) -> str | None:
    if not raw:
        return None
    return _COMPONENT_MAP.get(raw.strip().upper(), raw.strip())


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


def _topic_to_values(t: SBIRDashboardTopic) -> dict[str, object]:
    now = datetime.now(UTC)
    return {
        "source": SOURCE,
        "topic_number": t.topic_number,
        "title": t.topic_title,
        "component": _map_component(t.component),
        "program": t.program,
        "phase": None,
        "status": _map_status(t.topic_status),
        "prerelease_date": None,
        "open_date": t.submission_window_open,
        "close_date": t.submission_deadline,
        "description": t.solicitation_title,
        "url": "https://www.sbirdashboard.com/",
        "technology_areas": None,
        "modernization_priorities": None,
        "keywords": None,
        "itar_export_status": None,
        "phase_i_ceiling": None,
        "phase_i_duration_months": None,
        "raw": t.raw,
        "apify_run_id": None,
        "last_seen_at": now,
    }


async def is_stale(*, stale_after: timedelta = DEFAULT_STALE_AFTER) -> bool:
    """True when sbirdashboard topics have never been ingested, or the
    most recent ingest is older than `stale_after`."""
    async with unscoped_session() as session:
        latest = (
            await session.execute(
                select(func.max(SBIRTopic.last_seen_at)).where(
                    SBIRTopic.source == SOURCE
                )
            )
        ).scalar_one_or_none()
    if latest is None:
        return True
    return datetime.now(UTC) - latest > stale_after


async def refresh_sbirdashboard_topics(*, timeout_secs: float = 8.0) -> TopicsSyncResult:
    """Fetch and upsert. Safe to call inline from a request handler.

    Never raises — failure modes are returned as a populated `error`
    field so the caller (often a Next.js server component) can degrade
    gracefully and still render whatever's already in the DB.
    """
    started = datetime.now(UTC)
    try:
        topics = await fetch_sbirdashboard_topics(timeout_secs=timeout_secs)
    except SBIRDashboardError as exc:
        elapsed = (datetime.now(UTC) - started).total_seconds()
        log.warning("sbirdashboard refresh failed: %s", exc)
        return TopicsSyncResult(fetched=0, upserted=0, error=str(exc), elapsed_secs=elapsed)
    except Exception as exc:
        elapsed = (datetime.now(UTC) - started).total_seconds()
        log.exception("sbirdashboard refresh crashed: %s", exc)
        return TopicsSyncResult(
            fetched=0,
            upserted=0,
            error=f"{exc.__class__.__name__}: {exc}"[:300],
            elapsed_secs=elapsed,
        )

    upserted = 0
    async with unscoped_session() as session:
        for t in topics:
            values = _topic_to_values(t)
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

    elapsed = (datetime.now(UTC) - started).total_seconds()
    log.info(
        "sbirdashboard refresh: fetched=%d upserted=%d elapsed=%.2fs",
        len(topics),
        upserted,
        elapsed,
    )
    return TopicsSyncResult(
        fetched=len(topics), upserted=upserted, error=None, elapsed_secs=elapsed
    )
