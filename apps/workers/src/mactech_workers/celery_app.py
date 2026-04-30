"""Celery app for MacTech CaptureOS background work.

Week 2: SAM.gov ingestion. Beat schedule below fires the orchestrator
task every 2 hours; the orchestrator fans out per-NAICS calls
sequentially. At ~20 NAICS × 12 ticks/day = ~240 SAM API calls/day,
well under the 1000/day cap from docs/SAM_GOV_API.md §6.

Week 3 will add enrichment beats; Week 4 will add the morning digest.
"""

from __future__ import annotations

import logging
import os

from celery import Celery
from celery.schedules import crontab
from celery.signals import task_prerun

log = logging.getLogger(__name__)

REDIS_URL = os.environ.get("REDIS_URL", "redis://localhost:6379/0")

celery_app = Celery(
    "mactech",
    broker=REDIS_URL,
    backend=REDIS_URL,
)

celery_app.conf.update(
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],
    timezone="America/New_York",
    enable_utc=True,
    task_track_started=True,
    task_acks_late=True,
    worker_max_tasks_per_child=200,
    broker_connection_retry_on_startup=True,
    # Redbeat persists the schedule in Redis so missed beats during
    # container restarts are caught up on the next interval. Without
    # this, every redeploy resets the beat schedule and a daily run
    # whose tick falls inside the deploy window is lost (we hit this
    # twice with the industry-days task — Apr 26 and Apr 27).
    beat_scheduler="redbeat.RedBeatScheduler",
    redbeat_redis_url=REDIS_URL,
    redbeat_lock_timeout=900,
    beat_schedule={
        "sam-ingest-all-mactech-naics": {
            "task": "mactech.sam.ingest_all",
            "schedule": crontab(minute=0, hour="*/2"),
            "options": {"expires": 60 * 60},  # don't pile up if a run skips
        },
        "enrich-unenriched-batch": {
            "task": "mactech.enrich.batch",
            "schedule": crontab(minute="*/30"),
            "options": {"expires": 25 * 60},
            "kwargs": {"batch_size": 25},
        },
        "embed-unembedded-batch": {
            "task": "mactech.embed.batch",
            "schedule": crontab(minute="*/15"),
            "options": {"expires": 12 * 60},
            "kwargs": {"batch_size": 64},
        },
        "score-unscored-batch": {
            "task": "mactech.score.batch",
            "schedule": crontab(minute="*/20"),
            "options": {"expires": 18 * 60},
            "kwargs": {"batch_size": 25},
        },
        "sam-fetch-descriptions": {
            "task": "mactech.sam.fetch_descriptions",
            "schedule": crontab(minute="*/30"),
            "options": {"expires": 25 * 60},
            "kwargs": {"batch_size": 50},
        },
        # Founder morning digest. America/New_York timezone is set at the top
        # of celery_app.conf.update so 6am means 6am ET.
        "founder-morning-digest": {
            "task": "mactech.digest.send_all",
            "schedule": crontab(minute=0, hour=6, day_of_week="mon-fri"),
            "options": {"expires": 60 * 60},
        },
        # Apify industry-day calendar — daily 0500 ET. Apify's webhook
        # then fires `mactech.apify.ingest_industry_days` on completion.
        "apify-industry-days-kick": {
            "task": "mactech.apify.kick_industry_days_run",
            "schedule": crontab(minute=0, hour=5),
            "options": {"expires": 60 * 60},
        },
        # DHS APFS direct API ingest — daily 0515 ET. Bypasses Apify
        # (APFS exposes a public JSON endpoint with ~700 structured
        # forecasts; cheaper + cleaner than scraping the SPA).
        "dhs-apfs-ingest": {
            "task": "mactech.dhs_apfs.ingest_all",
            "schedule": crontab(minute=15, hour=5),
            "options": {"expires": 30 * 60},
        },
        # DOE OSBP forecast XLSX — daily 0520 ET. ~880 rows with
        # incumbent + NAICS + value, fuels the recompete watchlist.
        "doe-forecast-ingest": {
            "task": "mactech.doe.ingest_forecast",
            "schedule": crontab(minute=20, hour=5),
            "options": {"expires": 30 * 60},
        },
        # NASA NAF XLSX — daily 0525 ET. ~150 rows with rich quarter
        # bands and NewOrRecompete flag.
        "nasa-naf-ingest": {
            "task": "mactech.nasa_naf.ingest",
            "schedule": crontab(minute=25, hour=5),
            "options": {"expires": 30 * 60},
        },
        # Apify forecast sweep — daily 0545 ET (after industry-days at
        # 0500 finishes). Catches GSA, VA, USACE, AFBES, HHS hubs that
        # don't expose a public JSON API. DHS is handled by dhs-apfs.
        "apify-forecasts-kick": {
            "task": "mactech.apify.kick_forecasts_run",
            "schedule": crontab(minute=45, hour=5),
            "options": {"expires": 90 * 60},
        },
        # SEC EDGAR distress signals — weekly Sunday 1800 ET (per
        # strategy doc §3.3). Matches top-200 federal contractors against
        # SEC's CIK registry, scores recent filings, populates
        # incumbent_signals for recompete-card flagging.
        "edgar-signals-refresh": {
            "task": "mactech.edgar.refresh_top_contractors",
            "schedule": crontab(minute=0, hour=18, day_of_week="sun"),
            "options": {"expires": 4 * 60 * 60},
            "kwargs": {"top_n": 200},
        },
        # Codex SPRS sync — daily 0610 ET. Codex (sibling product at
        # codex.mactechsolutionsllc.com) owns the CMMC Readiness workflow;
        # CaptureOS just consumes the published per-tenant SPRS score
        # for display + DFARS-7012 / CMMC-L2 eligibility chips.
        "codex-sprs-sync": {
            "task": "mactech.codex.refresh_sprs",
            "schedule": crontab(minute=10, hour=6),
            "options": {"expires": 30 * 60},
        },
        # Tenant SAM verification — daily 0630 ET, after Codex sync.
        # Hits SAM Entity + Exclusions APIs for every tenant with a UEI;
        # updates registration status / expiration / debarment flags;
        # emits audit events on state transitions.
        "tenant-sam-verify": {
            "task": "mactech.tenant.verify_sam",
            "schedule": crontab(minute=30, hour=6),
            "options": {"expires": 30 * 60},
        },
    },
)


@celery_app.task(name="mactech.health")
def health() -> str:
    return "ok"


@task_prerun.connect
def _reset_db_engine_per_task(*args: object, **kwargs: object) -> None:
    """Drop the lru_cache'd async engine + session factory before every
    task. Each task wraps its async work in asyncio.run() which creates
    a fresh event loop, but the engine's asyncpg connection pool binds
    its connections to whichever loop first used them. Reusing the
    cached engine across tasks → "got Future ... attached to a different
    loop" errors. Clearing the cache forces the next get_engine() call
    to build a fresh engine on the current task's loop.

    The orphaned engine + connections leak until process GC, but
    worker_max_tasks_per_child=200 recycles the process before that
    matters in practice.
    """
    try:
        from mactech_db.session import async_session_factory, get_engine

        get_engine.cache_clear()
        async_session_factory.cache_clear()
    except Exception as exc:  # noqa: BLE001
        log.warning("task_prerun engine reset failed: %s", exc)


# Side-effect imports to register tasks defined in submodules. Keep at end of file.
import mactech_workers.tasks.apify_forecasts  # noqa: E402, F401
import mactech_workers.tasks.apify_industry_days  # noqa: E402, F401
import mactech_workers.tasks.codex_sprs_sync  # noqa: E402, F401
import mactech_workers.tasks.dhs_apfs_ingest  # noqa: E402, F401
import mactech_workers.tasks.doe_forecast_ingest  # noqa: E402, F401
import mactech_workers.tasks.edgar_signals  # noqa: E402, F401
import mactech_workers.tasks.nasa_naf_ingest  # noqa: E402, F401
import mactech_workers.tasks.digest  # noqa: E402, F401
import mactech_workers.tasks.embed  # noqa: E402, F401
import mactech_workers.tasks.enrich  # noqa: E402, F401
import mactech_workers.tasks.library_import  # noqa: E402, F401
import mactech_workers.tasks.sam_descriptions  # noqa: E402, F401
import mactech_workers.tasks.sam_ingest  # noqa: E402, F401
import mactech_workers.tasks.score  # noqa: E402, F401
