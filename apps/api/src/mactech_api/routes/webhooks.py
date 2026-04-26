"""Inbound webhooks — Apify ingest entry point.

Sprint 19. Unauthenticated by design (Apify can't carry our Clerk JWT);
security comes from HMAC-SHA256 verification of the request body using
APIFY_WEBHOOK_SECRET. Reject signature mismatches with 401.

Flow:
  1. Verify signature (constant-time HMAC).
  2. Persist an apify_runs audit row (idempotent on (run_id, event_type)).
  3. For RUN.SUCCEEDED on a known capability, dispatch the ingest
     Celery task (mactech.apify.ingest_<capability>).
  4. Return 202 Accepted with the audit row id; Apify retries on 5xx so
     we never throw past the audit insert.

  POST /webhooks/apify/{capability}
       Headers: Apify-Webhook-Signature: sha256=<hex>
       Body:    { "userId":..., "eventType":..., "createdAt":...,
                  "eventData": { "actorId":..., "actorRunId":... },
                  "resource":  { ... actor run resource ... } }
"""

from __future__ import annotations

import logging
from typing import Annotated, Any

from fastapi import APIRouter, Header, HTTPException, Request, status
from pydantic import BaseModel, ConfigDict
from sqlalchemy.dialects.postgresql import insert as pg_insert

from mactech_api.settings import settings
from mactech_db import unscoped_session
from mactech_db.models import ApifyRun
from mactech_integrations.apify import verify_webhook_signature

log = logging.getLogger(__name__)
router = APIRouter(tags=["webhooks"])


KNOWN_CAPABILITIES = {"industry_days"}


class ApifyWebhookAck(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    audit_id: str
    capability: str
    apify_run_id: str
    event_type: str
    dispatched: bool


@router.post(
    "/webhooks/apify/{capability}",
    response_model=ApifyWebhookAck,
    status_code=status.HTTP_202_ACCEPTED,
)
async def apify_webhook(
    capability: str,
    request: Request,
    x_apify_webhook_signature: Annotated[
        str | None, Header(alias="Apify-Webhook-Signature")
    ] = None,
) -> ApifyWebhookAck:
    if capability not in KNOWN_CAPABILITIES:
        raise HTTPException(
            status_code=404, detail=f"unknown capability: {capability}"
        )
    if not settings.apify_webhook_secret:
        log.error("APIFY_WEBHOOK_SECRET not configured; rejecting webhook")
        raise HTTPException(
            status_code=503,
            detail="APIFY_WEBHOOK_SECRET not configured on the API service.",
        )

    body = await request.body()
    if not verify_webhook_signature(
        body, x_apify_webhook_signature, settings.apify_webhook_secret
    ):
        log.warning(
            "rejected apify webhook with bad/missing signature for capability=%s",
            capability,
        )
        raise HTTPException(status_code=401, detail="bad webhook signature")

    payload = await _parse_json(body)

    event_type = str(payload.get("eventType") or "").strip() or "UNKNOWN"
    event_data: dict[str, Any] = payload.get("eventData") or {}
    resource: dict[str, Any] = payload.get("resource") or {}
    apify_run_id = str(
        event_data.get("actorRunId") or resource.get("id") or ""
    )
    apify_actor_id = str(
        event_data.get("actorId") or resource.get("actId") or ""
    )
    apify_status = (
        str(resource.get("status")) if resource.get("status") else None
    )
    dataset_id = (
        str(resource.get("defaultDatasetId"))
        if resource.get("defaultDatasetId")
        else None
    )
    items_count_val = (resource.get("stats") or {}).get("requestsFinished")
    items_count = (
        int(items_count_val) if isinstance(items_count_val, int) else None
    )

    if not apify_run_id:
        raise HTTPException(
            status_code=400, detail="missing actorRunId / resource.id"
        )

    async with unscoped_session() as session:
        stmt = (
            pg_insert(ApifyRun)
            .values(
                apify_run_id=apify_run_id,
                apify_actor_id=apify_actor_id,
                capability=capability,
                event_type=event_type,
                apify_status=apify_status,
                dataset_id=dataset_id,
                items_count=items_count,
                payload=payload,
            )
            .on_conflict_do_update(
                index_elements=["apify_run_id", "event_type"],
                set_={
                    "apify_status": apify_status,
                    "dataset_id": dataset_id,
                    "items_count": items_count,
                    "payload": payload,
                },
            )
            .returning(ApifyRun.id)
        )
        result = await session.execute(stmt)
        audit_id = str(result.scalar_one())

    dispatched = False
    if event_type == "ACTOR.RUN.SUCCEEDED" and dataset_id:
        dispatched = _dispatch_ingest(
            capability=capability,
            audit_id=audit_id,
            dataset_id=dataset_id,
            apify_run_id=apify_run_id,
        )

    return ApifyWebhookAck(
        audit_id=audit_id,
        capability=capability,
        apify_run_id=apify_run_id,
        event_type=event_type,
        dispatched=dispatched,
    )


async def _parse_json(body: bytes) -> dict[str, Any]:
    import json

    try:
        decoded = json.loads(body or b"{}")
    except json.JSONDecodeError as exc:
        raise HTTPException(
            status_code=400, detail=f"invalid JSON body: {exc}"
        ) from exc
    if not isinstance(decoded, dict):
        raise HTTPException(
            status_code=400,
            detail="webhook body must be a JSON object",
        )
    return decoded


def _dispatch_ingest(
    *,
    capability: str,
    audit_id: str,
    dataset_id: str,
    apify_run_id: str,
) -> bool:
    """Fire the right Celery task for a successful run. Capability →
    task name mapping is intentionally explicit so a misconfigured
    webhook can't spawn arbitrary work."""
    task_for_capability = {
        "industry_days": "mactech.apify.ingest_industry_days",
    }
    task_name = task_for_capability.get(capability)
    if not task_name:
        log.warning(
            "no ingest task wired for capability=%s (audit=%s)",
            capability,
            audit_id,
        )
        return False

    try:
        from mactech_workers.celery_app import celery_app

        celery_app.send_task(
            task_name,
            kwargs={
                "audit_id": audit_id,
                "dataset_id": dataset_id,
                "apify_run_id": apify_run_id,
            },
        )
        log.info(
            "dispatched %s for capability=%s run=%s",
            task_name,
            capability,
            apify_run_id,
        )
        return True
    except Exception as exc:  # noqa: BLE001
        log.warning(
            "failed to dispatch %s for run=%s: %s",
            task_name,
            apify_run_id,
            exc,
        )
        return False
