"""Integration status + on-demand triggers.

Lets the UI tell the user *why* there's no forecast / industry-day data
yet instead of the opaque "check back tomorrow" empty state. Surfaces
the most recent ApifyRun audit row per capability + a retry button.

Endpoints:

  GET  /me/integrations
       Per-capability last-run summary (status, error, processed_at)
       across Apify forecasts + industry days. Read-only; safe for any
       authenticated tenant user.

  POST /me/integrations/apify/forecasts/trigger
  POST /me/integrations/apify/industry-days/trigger
       Enqueue the corresponding kick task on demand. Useful for
       verifying a config fix without waiting for the next 0530 ET beat.
"""

from __future__ import annotations

import logging
import os
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from mactech_db.models import ApifyRun
from pydantic import BaseModel, ConfigDict
from sqlalchemy import select

from mactech_api.auth import RequestContext, get_request_context

log = logging.getLogger(__name__)
router = APIRouter(tags=["integrations"])


class _Out(BaseModel):
    model_config = ConfigDict(from_attributes=True)


class IntegrationRunOut(_Out):
    capability: str
    last_event_type: str | None
    apify_status: str | None
    items_count: int | None
    ingest_error: str | None
    received_at: str | None
    processed_at: str | None


class IntegrationStatusOut(_Out):
    capability: str
    label: str
    description: str
    schedule: str
    api_token_var: str
    api_token_set: bool
    last_run: IntegrationRunOut | None


class IntegrationsResponse(_Out):
    integrations: list[IntegrationStatusOut]


CAPABILITY_DEFS = (
    {
        "capability": "forecasts",
        "label": "Agency forecasts",
        "description": (
            "Daily Apify scrape of agency acquisition-forecast hubs "
            "(DHS APFS, VA FCO, USACE, Air Force BES). Feeds the "
            "/forecasts page with planned procurements 30-180 days "
            "before they hit SAM."
        ),
        "schedule": "Daily 05:30 ET",
        "api_token_var": "APIFY_API_TOKEN",
    },
    {
        "capability": "industry_days",
        "label": "Industry days",
        "description": (
            "Daily Apify scrape of agency event calendars (AFCEA, IWRP, "
            "USACE small-business outreach). Feeds the /events page."
        ),
        "schedule": "Daily 05:00 ET",
        "api_token_var": "APIFY_API_TOKEN",
    },
)


async def _last_run_for_capability(session, capability: str) -> IntegrationRunOut | None:
    row = (
        await session.execute(
            select(ApifyRun)
            .where(ApifyRun.capability == capability)
            .order_by(ApifyRun.received_at.desc())
            .limit(1)
        )
    ).scalar_one_or_none()
    if row is None:
        return None
    return IntegrationRunOut(
        capability=capability,
        last_event_type=row.event_type,
        apify_status=row.apify_status,
        items_count=row.items_count,
        ingest_error=row.ingest_error,
        received_at=row.received_at.isoformat() if row.received_at else None,
        processed_at=row.processed_at.isoformat() if row.processed_at else None,
    )


@router.get("/me/integrations", response_model=IntegrationsResponse)
async def get_integrations(
    ctx: Annotated[RequestContext, Depends(get_request_context)],
) -> IntegrationsResponse:
    out: list[IntegrationStatusOut] = []
    for spec in CAPABILITY_DEFS:
        run = await _last_run_for_capability(ctx.session, spec["capability"])
        out.append(
            IntegrationStatusOut(
                capability=spec["capability"],
                label=spec["label"],
                description=spec["description"],
                schedule=spec["schedule"],
                api_token_var=spec["api_token_var"],
                # Token presence is checked from the *API* environment.
                # In a multi-service deployment the workers may have a
                # different env, but the API service typically holds
                # the same secrets too — a mismatch is itself useful
                # signal.
                api_token_set=bool(os.environ.get(spec["api_token_var"])),
                last_run=run,
            )
        )
    return IntegrationsResponse(integrations=out)


class TriggerOut(_Out):
    capability: str
    queued: bool
    task_id: str | None
    error: str | None = None


def _enqueue_task(name: str) -> tuple[bool, str | None, str | None]:
    """Send a task by name. Avoid importing the worker package directly
    (the API container doesn't have it); use celery's send_task."""
    try:
        from celery import Celery

        broker_url = os.environ.get("REDIS_URL", "redis://localhost:6379/0")
        celery_app = Celery(broker=broker_url, backend=broker_url)
        result = celery_app.send_task(name)
        return True, result.id, None
    except Exception as exc:
        log.warning("integrations trigger failed for %s: %s", name, exc)
        return False, None, str(exc)[:300]


@router.post(
    "/me/integrations/apify/forecasts/trigger",
    response_model=TriggerOut,
)
async def trigger_forecasts(
    ctx: Annotated[RequestContext, Depends(get_request_context)],
) -> TriggerOut:
    """Fire mactech.apify.kick_forecasts_run on demand.

    Useful for verifying a config fix without waiting for the next
    05:30 ET beat. Returns immediately; the kick itself runs for up to
    25 min on the worker side. Refresh /me/integrations afterward.
    """
    queued, task_id, error = _enqueue_task("mactech.apify.kick_forecasts_run")
    if not queued:
        raise HTTPException(
            status_code=503,
            detail=f"could not enqueue kick task: {error}",
        )
    return TriggerOut(capability="forecasts", queued=True, task_id=task_id, error=None)


@router.post(
    "/me/integrations/apify/industry-days/trigger",
    response_model=TriggerOut,
)
async def trigger_industry_days(
    ctx: Annotated[RequestContext, Depends(get_request_context)],
) -> TriggerOut:
    """Fire mactech.apify.kick_industry_days_run on demand."""
    queued, task_id, error = _enqueue_task("mactech.apify.kick_industry_days_run")
    if not queued:
        raise HTTPException(
            status_code=503,
            detail=f"could not enqueue kick task: {error}",
        )
    return TriggerOut(capability="industry_days", queued=True, task_id=task_id, error=None)
