"""Celery app for MacTech CaptureOS background work.

Week 1: bootstrap only, no tasks registered. Tasks arrive in Week 2
(SAM.gov ingestion), Week 3 (enrichment + embeddings), Week 4 (scoring +
morning digest). See docs/ROADMAP.md.
"""

from __future__ import annotations

import os

from celery import Celery

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
)


@celery_app.task(name="mactech.health")
def health() -> str:
    return "ok"
