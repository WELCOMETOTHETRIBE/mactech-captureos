"""Proactive SAM.gov search for cyber-scope saved searches.

Runs daily (Beat) per tenant: pulls opportunities by NAICS and optional SAM
`title` queries, filters by saved-search keywords, upserts into
`opportunities_raw`, and enqueues cyber scope scan + attachment fetch.
"""

from __future__ import annotations

import asyncio
import logging
import os
from dataclasses import asdict, dataclass
from datetime import UTC, date, datetime, timedelta
from typing import Any
from uuid import UUID

from mactech_db import async_session_factory
from mactech_db.audit import record_event
from mactech_db.models import (
    EVENT_CYBER_SCOPE_SAM_SEARCH_RUN,
    IngestionState,
    OpportunityRaw,
    SavedSearch,
    Tenant,
)
from mactech_integrations.sam_gov import SamGovOpportunitiesClient
from mactech_intelligence.cyber_scope.sam_search import (
    SamCyberSearchJob,
    build_sam_cyber_jobs,
    is_cyber_scope_saved_search,
    record_matches_keywords,
)
from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert

from mactech_workers.celery_app import celery_app
from mactech_workers.tasks.sam_ingest import (
    SOURCE,
    _should_fetch_attachments,
    _upsert_record,
)

log = logging.getLogger(__name__)

DEFAULT_LOOKBACK_DAYS = 7
DEFAULT_MAX_API_JOBS = 24


@dataclass
class SamCyberJobResult:
    saved_search_name: str
    state_key: str
    naics_code: str | None
    title_query: str | None
    pages: int
    examined: int
    matched: int
    upserts: int
    inserts: int
    updates: int
    posted_from: str
    posted_to: str
    duration_ms: int
    status: str


async def _resolve_job_window(
    session,
    state_key: str,
    *,
    lookback_days: int,
) -> tuple[date, date]:
    today = datetime.now(UTC).date()
    row = (
        await session.execute(
            select(IngestionState).where(
                IngestionState.source == SOURCE,
                IngestionState.key == state_key,
            )
        )
    ).scalar_one_or_none()
    if row is None or row.last_success_at is None:
        posted_from = today - timedelta(days=lookback_days)
    else:
        posted_from = row.last_success_at.date()
    return posted_from, today


async def _record_job_state(
    session,
    state_key: str,
    *,
    posted_to: date,
    upserts: int,
    status: str,
    error: str | None = None,
) -> None:
    now = datetime.now(UTC)
    state_row = {
        "source": SOURCE,
        "key": state_key,
        "last_run_at": now,
        "last_success_at": now if status == "ok" else None,
        "last_cursor": posted_to.isoformat() if status == "ok" else None,
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


async def _execute_job(
    job: SamCyberSearchJob,
    *,
    api_key: str,
    lookback_days: int,
) -> SamCyberJobResult:
    started = datetime.now(UTC)
    session_factory = async_session_factory()
    pages = 0
    examined = 0
    matched = 0
    inserts = 0
    updates = 0
    upserts = 0
    posted_from: date | None = None
    posted_to: date | None = None

    async with session_factory() as session:
        try:
            async with SamGovOpportunitiesClient(api_key=api_key) as client, session.begin():
                posted_from, posted_to = await _resolve_job_window(
                    session, job.state_key, lookback_days=lookback_days
                )
                async for page in client.iter_opportunities(
                    posted_from=posted_from,
                    posted_to=posted_to,
                    ncode=job.naics_code,
                    title=job.title_query,
                    page_size=job.page_size,
                    max_pages=job.max_pages,
                ):
                    pages += 1
                    for record in page.opportunities_data:
                        examined += 1
                        if not record_matches_keywords(
                            title=record.title,
                            solicitation_number=record.solicitation_number,
                            keywords=job.keywords,
                        ):
                            continue
                        matched += 1
                        outcome = await _upsert_record(session, record)
                        if outcome == "inserted":
                            inserts += 1
                            upserts += 1
                        elif outcome == "updated":
                            updates += 1
                            upserts += 1
                        if outcome in ("inserted", "updated"):
                            opp_id = (
                                await session.execute(
                                    select(OpportunityRaw.id).where(
                                        OpportunityRaw.source == SOURCE,
                                        OpportunityRaw.source_id == record.notice_id,
                                    )
                                )
                            ).scalar_one_or_none()
                            if opp_id is not None:
                                try:
                                    celery_app.send_task(
                                        "mactech.cyber_scope.scan_one",
                                        args=[str(opp_id)],
                                        kwargs={"scan_pass": "description_only"},
                                    )
                                except Exception as exc:
                                    log.warning(
                                        "cyber_sam_search: scan enqueue failed %s: %s",
                                        record.notice_id,
                                        exc,
                                    )
                                if _should_fetch_attachments(record):
                                    try:
                                        celery_app.send_task(
                                            "mactech.attachments.fetch_one",
                                            args=[str(opp_id)],
                                        )
                                    except Exception as exc:
                                        log.warning(
                                            "cyber_sam_search: attachment failed %s: %s",
                                            record.notice_id,
                                            exc,
                                        )

                await _record_job_state(
                    session,
                    job.state_key,
                    posted_to=posted_to,
                    upserts=upserts,
                    status="ok",
                )
        except Exception as exc:
            await session.rollback()
            async with session.begin():
                await _record_job_state(
                    session,
                    job.state_key,
                    posted_to=posted_to or datetime.now(UTC).date(),
                    upserts=0,
                    status="error",
                    error=f"{type(exc).__name__}: {exc}"[:1000],
                )
            raise

    duration_ms = int((datetime.now(UTC) - started).total_seconds() * 1000)
    return SamCyberJobResult(
        saved_search_name=job.saved_search_name,
        state_key=job.state_key,
        naics_code=job.naics_code,
        title_query=job.title_query,
        pages=pages,
        examined=examined,
        matched=matched,
        upserts=upserts,
        inserts=inserts,
        updates=updates,
        posted_from=posted_from.isoformat() if posted_from else "",
        posted_to=posted_to.isoformat() if posted_to else "",
        duration_ms=duration_ms,
        status="ok",
    )


async def run_cyber_sam_search(
    *,
    tenant_slug: str | None = None,
    lookback_days: int = DEFAULT_LOOKBACK_DAYS,
    max_jobs: int = DEFAULT_MAX_API_JOBS,
) -> dict[str, Any]:
    api_key = os.environ.get("SAM_API_KEY", "").strip()
    if not api_key:
        log.warning("cyber_scope_sam_search: SAM_API_KEY not set")
        return {"status": "skipped", "reason": "no_sam_api_key"}

    session_factory = async_session_factory()
    async with session_factory() as session:
        stmt = select(Tenant)
        if tenant_slug:
            stmt = stmt.where(Tenant.slug == tenant_slug)
        tenants = (await session.execute(stmt)).scalars().all()

    all_jobs: list[tuple[Tenant, SamCyberSearchJob]] = []
    for tenant in tenants:
        async with session_factory() as session:
            searches = (
                await session.execute(
                    select(SavedSearch).where(SavedSearch.tenant_id == tenant.id)
                )
            ).scalars().all()
        for search in searches:
            filters = dict(search.filters or {})
            filters["_name"] = search.name
            if not is_cyber_scope_saved_search(filters):
                continue
            for job in build_sam_cyber_jobs(
                saved_search_id=str(search.id),
                saved_search_name=search.name,
                tenant_id=str(tenant.id),
                filters=filters,
            ):
                all_jobs.append((tenant, job))

    results: list[SamCyberJobResult] = []
    jobs_run = 0
    errors = 0
    for tenant, job in all_jobs:
        if jobs_run >= max_jobs:
            break
        try:
            result = await _execute_job(job, api_key=api_key, lookback_days=lookback_days)
            results.append(result)
            jobs_run += 1
            async with session_factory() as session:
                await record_event(
                    session,
                    tenant_id=tenant.id,
                    event_type=EVENT_CYBER_SCOPE_SAM_SEARCH_RUN,
                    entity_type="saved_search",
                    entity_id=UUID(job.saved_search_id),
                    actor_label="system:cyber_scope_sam_search",
                    payload={
                        "saved_search_name": job.saved_search_name,
                        "state_key": job.state_key,
                        "matched": result.matched,
                        "upserts": result.upserts,
                    },
                )
                await session.commit()
        except Exception as exc:
            errors += 1
            log.exception(
                "cyber_sam_search failed tenant=%s search=%s: %s",
                tenant.slug,
                job.saved_search_name,
                exc,
            )

    return {
        "status": "ok",
        "tenants": len(tenants),
        "jobs_scheduled": len(all_jobs),
        "jobs_run": jobs_run,
        "errors": errors,
        "total_matched": sum(r.matched for r in results),
        "total_upserts": sum(r.upserts for r in results),
        "results": [asdict(r) for r in results],
    }


@celery_app.task(name="mactech.cyber_scope.sam_search")
def sam_search_task(
    tenant_slug: str | None = None,
    lookback_days: int = DEFAULT_LOOKBACK_DAYS,
    max_jobs: int = DEFAULT_MAX_API_JOBS,
) -> dict[str, Any]:
    return asyncio.run(
        run_cyber_sam_search(
            tenant_slug=tenant_slug,
            lookback_days=lookback_days,
            max_jobs=max_jobs,
        )
    )
