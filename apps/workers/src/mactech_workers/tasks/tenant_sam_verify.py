"""Daily SAM verification for every tenant on file.

Closes B1, B2, and B3-on-self from CaptureOS_Requirements.md. For every
tenant with a UEI on file:

* Hits SAM Entity API → updates ``sam_registration_status``,
  ``sam_registration_date``, ``sam_registration_expires_at``, and
  ``sam_registration_last_checked_at``.
* Hits SAM Exclusions API → updates ``is_excluded``,
  ``exclusions_record_count``, and ``exclusions_last_checked_at``.
* Emits one ``tenant.sam_verified`` audit event per tenant (always).
* Emits ``tenant.sam_registration_status_changed`` when the status
  flips (active → expired, or returns from expired → active after a
  renewal).
* Emits ``tenant.sam_exclusion_changed`` when the debarment flag flips.

The worker is fail-soft per tenant — a single tenant's API error or
404 doesn't tank the batch. SAM Entity 404 is treated as "registration
invalid"; the tenant column reflects that and the audit event records
the cause.
"""

from __future__ import annotations

import asyncio
import logging
import os
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from typing import Any

from mactech_db import unscoped_session
from mactech_db.audit import record_event
from mactech_db.models import (
    EVENT_TENANT_SAM_EXCLUSION_CHANGED,
    EVENT_TENANT_SAM_REGISTRATION_STATUS_CHANGED,
    EVENT_TENANT_SAM_VERIFIED,
    Tenant,
)
from mactech_integrations.sam_gov import (
    SamEntityClient,
    SamEntityError,
    SamEntityNotFoundError,
    SamEntityRateLimitError,
    SamExclusionsClient,
    SamExclusionsError,
)
from sqlalchemy import select

from mactech_workers.celery_app import celery_app

log = logging.getLogger(__name__)


@dataclass
class TenantVerifyResult:
    tenant_slug: str
    uei: str | None
    registration_status: str | None
    registration_status_changed: bool
    is_excluded: bool
    exclusion_changed: bool
    error: str | None = None


@dataclass
class SamVerifyStats:
    tenants_seen: int
    tenants_verified: int
    tenants_no_uei: int
    tenants_errored: int
    duration_ms: int
    results: list[TenantVerifyResult]


def _normalize_status(raw: str | None) -> str:
    """Map SAM's ``Active`` / ``Inactive`` / ``Expired`` (and edge cases) to
    our enum-like column. Anything we can't classify falls through to
    ``invalid``, which surfaces a hard banner — better to over-warn than
    under-warn."""
    if not raw:
        return "invalid"
    s = raw.strip().lower()
    if s in ("active", "registered", "current"):
        return "active"
    if s in ("expired", "deactivated"):
        return "expired"
    if s in ("inactive", "submitted"):
        # "Submitted" means the registration is in flight at SAM but not
        # yet active — treat as expired-style for bidding purposes.
        return "expired"
    return "invalid"


def _parse_date(value: Any) -> datetime | None:
    if not value:
        return None
    if isinstance(value, datetime):
        return value
    if isinstance(value, str):
        # SAM returns dates like "2026-04-01" or "2026-04-01T00:00:00".
        try:
            return datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError:
            try:
                return datetime.strptime(value[:10], "%Y-%m-%d")
            except ValueError:
                return None
    return None


async def _verify_one_tenant(
    session,
    tenant: Tenant,
    *,
    entity_client: SamEntityClient,
    exclusions_client: SamExclusionsClient,
) -> TenantVerifyResult:
    if not tenant.uei:
        return TenantVerifyResult(
            tenant_slug=tenant.slug,
            uei=None,
            registration_status=tenant.sam_registration_status,
            registration_status_changed=False,
            is_excluded=tenant.is_excluded,
            exclusion_changed=False,
            error="no_uei_on_file",
        )

    previous_status = tenant.sam_registration_status
    previous_excluded = tenant.is_excluded
    now = datetime.now(UTC)

    new_status: str
    error: str | None = None

    # Entity lookup. 404 → invalid; rate-limit / other → keep prior status,
    # log error so we know the row is stale.
    try:
        profile = await entity_client.lookup_uei(tenant.uei)
    except SamEntityNotFoundError:
        new_status = "invalid"
        tenant.sam_registration_status = new_status
        tenant.sam_registration_date = None
        tenant.sam_registration_expires_at = None
        tenant.sam_registration_last_checked_at = now
        error = "sam_entity_not_found"
    except (SamEntityRateLimitError, SamEntityError) as exc:
        new_status = previous_status or "invalid"
        log.warning(
            "sam entity lookup error for tenant=%s uei=%s err=%s",
            tenant.slug,
            tenant.uei,
            exc,
        )
        error = f"sam_entity_error: {exc!s}"[:200]
    else:
        new_status = _normalize_status(profile.registration_status)
        tenant.sam_registration_status = new_status
        reg_date = _parse_date(profile.registration_date)
        tenant.sam_registration_date = reg_date.date() if reg_date else None
        exp_date = _parse_date(profile.expiration_date)
        tenant.sam_registration_expires_at = exp_date.date() if exp_date else None
        tenant.sam_registration_last_checked_at = now

    # Exclusions check. Failures keep the prior value but log.
    try:
        exclusion = await exclusions_client.check_uei(tenant.uei)
    except SamExclusionsError as exc:
        log.warning(
            "sam exclusions lookup error for tenant=%s uei=%s err=%s",
            tenant.slug,
            tenant.uei,
            exc,
        )
        error = error or f"sam_exclusions_error: {exc!s}"[:200]
        new_excluded = previous_excluded
    else:
        new_excluded = exclusion.is_excluded
        tenant.is_excluded = new_excluded
        tenant.exclusions_record_count = exclusion.record_count
        tenant.exclusions_last_checked_at = now

    status_changed = new_status != previous_status
    excluded_changed = new_excluded != previous_excluded

    # Always emit a "verified" event so the audit trail shows the daily
    # check ran. State-transition events are emitted in addition.
    await record_event(
        session,
        tenant_id=tenant.id,
        event_type=EVENT_TENANT_SAM_VERIFIED,
        entity_type="tenant",
        entity_id=tenant.id,
        actor_label="worker:tenant_sam_verify",
        payload={
            "uei": tenant.uei,
            "status": new_status,
            "is_excluded": new_excluded,
            "expires_at": (
                tenant.sam_registration_expires_at.isoformat()
                if tenant.sam_registration_expires_at
                else None
            ),
            "error": error,
        },
    )
    if status_changed:
        await record_event(
            session,
            tenant_id=tenant.id,
            event_type=EVENT_TENANT_SAM_REGISTRATION_STATUS_CHANGED,
            entity_type="tenant",
            entity_id=tenant.id,
            actor_label="worker:tenant_sam_verify",
            payload={"from": previous_status, "to": new_status},
        )
    if excluded_changed:
        await record_event(
            session,
            tenant_id=tenant.id,
            event_type=EVENT_TENANT_SAM_EXCLUSION_CHANGED,
            entity_type="tenant",
            entity_id=tenant.id,
            actor_label="worker:tenant_sam_verify",
            payload={
                "from": previous_excluded,
                "to": new_excluded,
                "record_count": tenant.exclusions_record_count,
            },
        )

    return TenantVerifyResult(
        tenant_slug=tenant.slug,
        uei=tenant.uei,
        registration_status=new_status,
        registration_status_changed=status_changed,
        is_excluded=new_excluded,
        exclusion_changed=excluded_changed,
        error=error,
    )


async def verify_all_tenants() -> SamVerifyStats:
    started = datetime.now(UTC)
    api_key = os.environ.get("SAM_GOV_API_KEY") or os.environ.get("SAM_API_KEY")
    if not api_key:
        log.warning("verify_all_tenants: no SAM_GOV_API_KEY set; skipping run")
        return SamVerifyStats(
            tenants_seen=0,
            tenants_verified=0,
            tenants_no_uei=0,
            tenants_errored=0,
            duration_ms=0,
            results=[],
        )

    seen = verified = no_uei = errored = 0
    results: list[TenantVerifyResult] = []

    async with unscoped_session() as session:
        tenants = (await session.execute(select(Tenant))).scalars().all()
        async with SamEntityClient(api_key=api_key) as entity_client:  # noqa: SIM117
            async with SamExclusionsClient(api_key=api_key) as exclusions_client:
                for tenant in tenants:
                    seen += 1
                    if not tenant.uei:
                        no_uei += 1
                        results.append(
                            TenantVerifyResult(
                                tenant_slug=tenant.slug,
                                uei=None,
                                registration_status=tenant.sam_registration_status,
                                registration_status_changed=False,
                                is_excluded=tenant.is_excluded,
                                exclusion_changed=False,
                                error="no_uei_on_file",
                            )
                        )
                        continue
                    try:
                        result = await _verify_one_tenant(
                            session,
                            tenant,
                            entity_client=entity_client,
                            exclusions_client=exclusions_client,
                        )
                    except Exception as exc:  # never abort the batch
                        log.exception(
                            "verify_one_tenant unexpected error tenant=%s: %s",
                            tenant.slug,
                            exc,
                        )
                        errored += 1
                        results.append(
                            TenantVerifyResult(
                                tenant_slug=tenant.slug,
                                uei=tenant.uei,
                                registration_status=tenant.sam_registration_status,
                                registration_status_changed=False,
                                is_excluded=tenant.is_excluded,
                                exclusion_changed=False,
                                error=f"unexpected: {exc.__class__.__name__}",
                            )
                        )
                        continue
                    if result.error:
                        errored += 1
                    else:
                        verified += 1
                    results.append(result)
        await session.commit()

    duration_ms = int((datetime.now(UTC) - started).total_seconds() * 1000)
    return SamVerifyStats(
        tenants_seen=seen,
        tenants_verified=verified,
        tenants_no_uei=no_uei,
        tenants_errored=errored,
        duration_ms=duration_ms,
        results=results,
    )


@celery_app.task(name="mactech.tenant.verify_sam")
def verify_tenants_task() -> dict[str, Any]:
    return asdict(asyncio.run(verify_all_tenants()))
