"""Celery app for MacTech CaptureOS background work.

Week 2: SAM.gov ingestion. Beat schedule below fires the orchestrator
task every 2 hours; the orchestrator fans out per-NAICS calls
sequentially. At ~20 NAICS × 12 ticks/day = ~240 SAM API calls/day,
well under the 1000/day cap from docs/SAM_GOV_API.md §6.

Week 3 will add enrichment beats; Week 4 will add the morning digest.
"""

from __future__ import annotations

import os

from celery import Celery
from celery.schedules import crontab

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
        # Founder morning digest. America/New_York timezone is set at the top
        # of celery_app.conf.update so 6am means 6am ET.
        "founder-morning-digest": {
            "task": "mactech.digest.send_all",
            "schedule": crontab(minute=0, hour=6, day_of_week="mon-fri"),
            "options": {"expires": 60 * 60},
        },
    },
)


@celery_app.task(name="mactech.health")
def health() -> str:
    return "ok"


# Side-effect imports to register tasks defined in submodules. Keep at end of file.
import mactech_workers.tasks.digest  # noqa: E402, F401
import mactech_workers.tasks.embed  # noqa: E402, F401
import mactech_workers.tasks.enrich  # noqa: E402, F401
import mactech_workers.tasks.sam_ingest  # noqa: E402, F401
import mactech_workers.tasks.score  # noqa: E402, F401
