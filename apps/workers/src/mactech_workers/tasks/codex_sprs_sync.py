"""Codex SPRS sync — pull NIST 800-171 self-assessment scores per tenant.

Sprint 23. CaptureOS doesn't own the CMMC workflow (Codex does), but
the SPRS score is meaningful eligibility intel for DFARS 7012 / CMMC L2
opportunities. Daily 0610 ET beat iterates every tenant with a Clerk
org id and asks Codex for the latest score; updates tenants.sprs_*.

Identity: both apps share Clerk for auth, so Codex's
organizations.clerkOrgId == CaptureOS tenants.clerk_org_id. We key SPRS
lookup on that shared id.

Failure modes are non-fatal:
  - Codex 404 (no org / no assessment on file) → leave existing fields,
    log info
  - Codex 401 (bad/missing CODEX_API_TOKEN) → log + skip
  - Codex transport error → leave existing fields, log warning
  - tenant has no clerk_org_id → skip
"""

from __future__ import annotations

import asyncio
import logging
import os
from dataclasses import asdict, dataclass
from datetime import UTC, date, datetime
from typing import Any

from mactech_db import unscoped_session
from mactech_db.models import Tenant
from mactech_integrations.codex import CodexClient, CodexError, CodexNotFoundError
from sqlalchemy import select

from mactech_workers.celery_app import celery_app

log = logging.getLogger(__name__)


@dataclass
class CodexSyncStats:
    tenants_seen: int
    tenants_synced: int
    tenants_no_clerk_org: int
    tenants_no_assessment: int
    tenants_errored: int
    duration_ms: int


@celery_app.task(name="mactech.codex.refresh_sprs")
def codex_refresh_sprs_task() -> dict[str, Any]:
    return asdict(asyncio.run(_refresh()))


async def _refresh() -> CodexSyncStats:
    started = datetime.now(UTC)
    base_url = os.environ.get("CODEX_BASE_URL", "https://codex.mactechsolutionsllc.com")
    api_token = os.environ.get("CODEX_API_TOKEN") or None

    seen = synced = no_clerk_org = no_assess = errored = 0
    async with unscoped_session() as session:
        tenants = (await session.execute(select(Tenant))).scalars().all()
        async with CodexClient(base_url=base_url, api_token=api_token) as codex:
            for tenant in tenants:
                seen += 1
                if not tenant.clerk_org_id:
                    no_clerk_org += 1
                    continue
                try:
                    sprs = await codex.get_sprs_by_clerk_org(tenant.clerk_org_id)
                except CodexNotFoundError:
                    no_assess += 1
                    continue
                except CodexError as exc:
                    errored += 1
                    log.warning(
                        "codex_sprs sync: tenant=%s clerk_org=%s err=%s",
                        tenant.slug,
                        tenant.clerk_org_id,
                        exc,
                    )
                    continue

                # Codex returns score=null when the org exists but has no
                # SPRS computed yet — treat as "no_assessment" rather than
                # overwriting an existing manual value with NULL.
                if sprs.score is None:
                    no_assess += 1
                    continue

                tenant.sprs_score = sprs.score
                tenant.sprs_max = sprs.max
                tenant.sprs_assessment_date = (
                    date.fromisoformat(sprs.assessment_date) if sprs.assessment_date else None
                )
                tenant.sprs_source_url = sprs.source_url
                tenant.sprs_synced_at = datetime.now(UTC)
                synced += 1
                log.info(
                    "codex_sprs sync: tenant=%s score=%d/%d assessed=%s",
                    tenant.slug,
                    sprs.score,
                    sprs.max,
                    sprs.assessment_date,
                )

    return CodexSyncStats(
        tenants_seen=seen,
        tenants_synced=synced,
        tenants_no_clerk_org=no_clerk_org,
        tenants_no_assessment=no_assess,
        tenants_errored=errored,
        duration_ms=int((datetime.now(UTC) - started).total_seconds() * 1000),
    )
