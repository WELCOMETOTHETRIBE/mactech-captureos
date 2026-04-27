"""Codex SPRS sync — pull NIST 800-171 self-assessment scores per tenant.

Sprint 23. CaptureOS doesn't own the CMMC workflow (Codex does), but
the SPRS score is meaningful eligibility intel for DFARS 7012 / CMMC L2
opportunities. Daily 0610 ET beat iterates every tenant with a UEI and
asks Codex for the latest score; updates tenants.sprs_*.

Failure modes are non-fatal:
  - Codex 404 (no assessment on file) → leave existing fields, log info
  - Codex transport error → leave existing fields, log warning
  - tenant has no UEI → skip
"""

from __future__ import annotations

import asyncio
import logging
import os
from dataclasses import asdict, dataclass
from datetime import UTC, date, datetime
from typing import Any

from sqlalchemy import select

from mactech_db import unscoped_session
from mactech_db.models import Tenant
from mactech_integrations.codex import CodexClient, CodexError, CodexNotFoundError
from mactech_workers.celery_app import celery_app

log = logging.getLogger(__name__)


@dataclass
class CodexSyncStats:
    tenants_seen: int
    tenants_synced: int
    tenants_no_uei: int
    tenants_no_assessment: int
    tenants_errored: int
    duration_ms: int


@celery_app.task(name="mactech.codex.refresh_sprs")
def codex_refresh_sprs_task() -> dict[str, Any]:
    return asdict(asyncio.run(_refresh()))


async def _refresh() -> CodexSyncStats:
    started = datetime.now(UTC)
    base_url = os.environ.get(
        "CODEX_BASE_URL", "https://codex.mactechsolutionsllc.com"
    )
    api_token = os.environ.get("CODEX_API_TOKEN") or None

    seen = synced = no_uei = no_assess = errored = 0
    async with unscoped_session() as session:
        tenants = (await session.execute(select(Tenant))).scalars().all()
        async with CodexClient(base_url=base_url, api_token=api_token) as codex:
            for tenant in tenants:
                seen += 1
                if not tenant.uei:
                    no_uei += 1
                    continue
                try:
                    sprs = await codex.get_sprs(tenant.uei)
                except CodexNotFoundError:
                    no_assess += 1
                    continue
                except CodexError as exc:
                    errored += 1
                    log.warning(
                        "codex_sprs sync: tenant=%s uei=%s err=%s",
                        tenant.slug, tenant.uei, exc,
                    )
                    continue

                tenant.sprs_score = sprs.score
                tenant.sprs_max = sprs.max
                tenant.sprs_assessment_date = (
                    date.fromisoformat(sprs.assessment_date)
                    if sprs.assessment_date
                    else None
                )
                tenant.sprs_source_url = sprs.source_url
                tenant.sprs_synced_at = datetime.now(UTC)
                synced += 1
                log.info(
                    "codex_sprs sync: tenant=%s score=%d/%d assessed=%s",
                    tenant.slug, sprs.score, sprs.max, sprs.assessment_date,
                )

    return CodexSyncStats(
        tenants_seen=seen,
        tenants_synced=synced,
        tenants_no_uei=no_uei,
        tenants_no_assessment=no_assess,
        tenants_errored=errored,
        duration_ms=int((datetime.now(UTC) - started).total_seconds() * 1000),
    )
