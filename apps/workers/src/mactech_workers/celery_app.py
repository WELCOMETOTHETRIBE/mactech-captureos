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
    },
)


@celery_app.task(name="mactech.health")
def health() -> str:
    return "ok"


# Side-effect import to register tasks defined in submodules. Keep at end of file.
import mactech_workers.tasks.sam_ingest  # noqa: E402, F401
