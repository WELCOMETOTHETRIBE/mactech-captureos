"""MacTech Identity — Audit log client (Python, drop-in).

Sends audit events to the central Identity Command Center hub at
``${MACTECH_IDENTITY_BASE_URL}/api/audit/ingest``, authenticated with
``MACTECH_AUDIT_INGEST_API_KEY``. The payload schema mirrors the Zod schema in
``mactech-suite-platform/lib/validations/audit.ts``.

Usage::

    from mactech_audit_client import send_audit_log

    await send_audit_log({
        "appKey": "capture",
        "eventType": "capture.opportunity.submitted",
        "eventCategory": "capture",
        "severity": "info",
        "action": f"Submitted opportunity #{opportunity_id} to bid review",
        "customerOrgClerkId": clerk_org_id,
        "actorClerkUserId": user_id,
        "resourceType": "opportunity",
        "resourceId": str(opportunity_id),
        "metadata": {"naics": "541512", "agency": "DoD"},
    })

Failures are logged via ``logging.warning`` and never raised — a downstream
outage in the hub must not take down the calling app. Pass
``raise_on_error=True`` if you need stricter delivery semantics.
"""

from __future__ import annotations

import json
import logging
import os
from typing import Any

import httpx

logger = logging.getLogger("mactech_audit")

DEFAULT_BASE_URL = "https://www.suite.mactechsolutionsllc.com"


def _resolve_base_url(explicit: str | None) -> str:
    return explicit or os.environ.get("MACTECH_IDENTITY_BASE_URL") or DEFAULT_BASE_URL


def _resolve_api_key(explicit: str | None) -> str | None:
    return explicit or os.environ.get("MACTECH_AUDIT_INGEST_API_KEY")


async def send_audit_log(
    payload: dict[str, Any],
    *,
    base_url: str | None = None,
    api_key: str | None = None,
    raise_on_error: bool = False,
    timeout: float = 5.0,
    client: httpx.AsyncClient | None = None,
) -> dict[str, Any] | None:
    """Send a single audit event. Returns ``{"id": ..., "ok": True}`` or ``None``.

    Required payload keys: ``appKey``, ``eventType``, ``action``.
    See the module docstring for the full shape.
    """

    resolved_key = _resolve_api_key(api_key)
    if not resolved_key:
        msg = "MACTECH_AUDIT_INGEST_API_KEY is not configured; skipping send."
        if raise_on_error:
            raise RuntimeError(msg)
        logger.warning(msg)
        return None

    url = _resolve_base_url(base_url).rstrip("/") + "/api/audit/ingest"
    headers = {
        "Content-Type": "application/json",
        "X-MacTech-Audit-Key": resolved_key,
    }

    try:
        if client is None:
            async with httpx.AsyncClient(timeout=timeout) as c:
                response = await c.post(url, headers=headers, content=json.dumps(payload))
        else:
            response = await client.post(url, headers=headers, content=json.dumps(payload))
        if response.status_code >= 400:
            text = response.text[:200]
            msg = f"audit/ingest → {response.status_code} {text}"
            if raise_on_error:
                raise RuntimeError(msg)
            logger.warning("[mactech-audit] %s for %s", msg, payload.get("eventType"))
            return None
        return response.json()
    except Exception as exc:
        if raise_on_error:
            raise
        logger.warning("[mactech-audit] send failed for %s: %s", payload.get("eventType"), exc)
        return None


def send_audit_log_sync(
    payload: dict[str, Any],
    *,
    base_url: str | None = None,
    api_key: str | None = None,
    raise_on_error: bool = False,
    timeout: float = 5.0,
) -> dict[str, Any] | None:
    """Synchronous variant for non-async call sites (CLI, scripts, sync workers)."""

    resolved_key = _resolve_api_key(api_key)
    if not resolved_key:
        msg = "MACTECH_AUDIT_INGEST_API_KEY is not configured; skipping send."
        if raise_on_error:
            raise RuntimeError(msg)
        logger.warning(msg)
        return None

    url = _resolve_base_url(base_url).rstrip("/") + "/api/audit/ingest"
    headers = {
        "Content-Type": "application/json",
        "X-MacTech-Audit-Key": resolved_key,
    }

    try:
        response = httpx.post(url, headers=headers, content=json.dumps(payload), timeout=timeout)
        if response.status_code >= 400:
            msg = f"audit/ingest → {response.status_code} {response.text[:200]}"
            if raise_on_error:
                raise RuntimeError(msg)
            logger.warning("[mactech-audit] %s for %s", msg, payload.get("eventType"))
            return None
        return response.json()
    except Exception as exc:
        if raise_on_error:
            raise
        logger.warning("[mactech-audit] send failed for %s: %s", payload.get("eventType"), exc)
        return None
