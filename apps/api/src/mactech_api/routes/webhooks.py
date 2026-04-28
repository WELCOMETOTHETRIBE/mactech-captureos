"""Inbound webhooks — Apify ingest + Codex SPRS push.

Sprint 19/24. Each webhook is unauthenticated for Clerk (the source
can't carry our JWT) and instead verifies its own shared secret:
  - Apify: HMAC-SHA256 of body with APIFY_WEBHOOK_SECRET
  - Codex: bearer secret in Authorization header (CODEX_WEBHOOK_SECRET)

Routes:

  POST /webhooks/apify/{capability}
       Headers: Apify-Webhook-Signature: sha256=<hex>
       Body:    { "userId":..., "eventType":..., "createdAt":...,
                  "eventData": { "actorId":..., "actorRunId":... },
                  "resource":  { ... actor run resource ... } }

  POST /webhooks/codex/sprs
       Headers: Authorization: Bearer <CODEX_WEBHOOK_SECRET>
       Body:    { "clerk_org_id": str, "score": int|null, "max": int,
                  "assessment_date": "YYYY-MM-DD"|null,
                  "source_url": str, "computed_at": ISO8601 }
       Effect: updates tenants.sprs_* for the matching clerk_org_id.
       Replaces the daily 0610 ET pull as the primary refresh path —
       the beat now exists only as a safety-net reconciler.
"""

from __future__ import annotations

import logging
from datetime import UTC, date, datetime
from typing import Annotated, Any

from fastapi import APIRouter, Header, HTTPException, Request, status
from mactech_db import unscoped_session
from mactech_db.models import ApifyRun, Tenant
from mactech_integrations.apify import verify_webhook_signature
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert

from mactech_api.settings import settings

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
    except Exception as exc:
        log.warning(
            "failed to dispatch %s for run=%s: %s",
            task_name,
            apify_run_id,
            exc,
        )
        return False


# ────────────────────────────────────────────────────────────────────────
# Codex SPRS push — real-time refresh trigger
# ────────────────────────────────────────────────────────────────────────


class CodexSprsWebhookBody(BaseModel):
    model_config = ConfigDict(extra="ignore")

    clerk_org_id: str
    score: int | None = None
    max: int = 110
    assessment_date: str | None = None  # "YYYY-MM-DD"
    source_url: str | None = None
    computed_at: str | None = None  # ISO8601 — informational, not stored
    reason: str | None = Field(
        default=None,
        description="Human-readable trigger (e.g. 'governance_wizard_save').",
    )


class CodexSprsWebhookAck(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    tenant_slug: str | None
    score: int | None
    updated: bool
    reason: str


@router.post(
    "/webhooks/codex/sprs",
    response_model=CodexSprsWebhookAck,
    status_code=status.HTTP_200_OK,
)
async def codex_sprs_webhook(
    body: CodexSprsWebhookBody,
    authorization: Annotated[str | None, Header()] = None,
) -> CodexSprsWebhookAck:
    """Receive an SPRS-changed push from Codex and update the tenant.

    Idempotent: sending the same payload twice has no extra effect.
    Non-fatal misses (no tenant for that clerk_org_id, score=null) are
    returned as 200 with `updated: false` so Codex can log them but
    doesn't retry forever — wedge-recovery is the daily beat's job.
    """
    expected = settings.codex_webhook_secret
    if not expected:
        log.error("CODEX_WEBHOOK_SECRET not configured; rejecting webhook")
        raise HTTPException(
            status_code=503,
            detail="CODEX_WEBHOOK_SECRET not configured on the API service.",
        )
    token = (
        authorization.removeprefix("Bearer ").strip()
        if authorization and authorization.startswith("Bearer ")
        else None
    )
    if not token or token != expected:
        raise HTTPException(status_code=401, detail="bad bearer token")

    if body.score is None:
        # Codex pushed a "no assessment yet" event — don't blow away an
        # existing manual value with NULL. Treat as a quiet no-op.
        return CodexSprsWebhookAck(
            tenant_slug=None,
            score=None,
            updated=False,
            reason="score_null_ignored",
        )

    async with unscoped_session() as session:
        tenant = (
            await session.execute(
                select(Tenant).where(Tenant.clerk_org_id == body.clerk_org_id)
            )
        ).scalar_one_or_none()

        if tenant is None:
            # Unknown clerk org — likely a Codex tenant that hasn't been
            # mirrored into CaptureOS yet. Log and return 200 so Codex
            # doesn't keep retrying.
            log.info(
                "codex_sprs webhook: no tenant for clerk_org=%s (score=%d)",
                body.clerk_org_id,
                body.score,
            )
            return CodexSprsWebhookAck(
                tenant_slug=None,
                score=body.score,
                updated=False,
                reason="no_tenant_for_clerk_org",
            )

        tenant.sprs_score = body.score
        tenant.sprs_max = body.max
        tenant.sprs_assessment_date = (
            date.fromisoformat(body.assessment_date)
            if body.assessment_date
            else None
        )
        if body.source_url:
            tenant.sprs_source_url = body.source_url
        tenant.sprs_synced_at = datetime.now(UTC)

        log.info(
            "codex_sprs webhook: tenant=%s score=%d/%d reason=%s",
            tenant.slug,
            body.score,
            body.max,
            body.reason or "unspecified",
        )

        return CodexSprsWebhookAck(
            tenant_slug=tenant.slug,
            score=body.score,
            updated=True,
            reason=body.reason or "sprs_changed",
        )
