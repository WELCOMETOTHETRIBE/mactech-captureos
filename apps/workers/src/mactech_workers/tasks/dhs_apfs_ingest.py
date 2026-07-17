"""DHS Acquisition Planning Forecast System (APFS) — direct API ingest.

Sprint 20 follow-up. APFS publishes its full forecast list as a public
JSON document at https://apfs-cloud.dhs.gov/api/forecast/ — ~700
records covering every DHS subcomponent (CBP, ICE, FEMA, TSA, S&T,
Coast Guard, etc.) with structured fields we want anyway:

  - requirements_title, requirement, naics, organization
  - small_business_program, small_business_set_aside
  - dollar_range {display_name}
  - contract_type, contract_vehicle
  - estimated_release_date, anticipated_award_date,
    estimated_solicitation_release_date
  - estimated_period_of_performance_start / _end
  - contractor (incumbent), contract_number
  - place_of_performance_city / _state
  - requirements_contact_*, sbs_coordinator_*

Bypasses Apify entirely — no need for an LLM extractor, no scrape
fragility, no per-page CU cost. Apify's forecasts task can stay for
non-DHS hubs (GSA, VA, USACE, etc.) where they don't expose an API.
"""

from __future__ import annotations

import asyncio
import logging
import re
from dataclasses import asdict, dataclass
from datetime import UTC, date, datetime
from decimal import Decimal
from typing import Any

import httpx
from mactech_db import unscoped_session
from mactech_db.models import ForecastRaw
from sqlalchemy.dialects.postgresql import insert as pg_insert

from mactech_workers.celery_app import celery_app

log = logging.getLogger(__name__)

APFS_API_URL = "https://apfs-cloud.dhs.gov/api/forecast/"
APFS_BASE = "https://apfs-cloud.dhs.gov/forecast/"

# Map APFS dollar_range display strings to (low, high) numeric brackets.
# We keep the raw text in estimated_value_text either way.
_DOLLAR_RANGES: dict[str, tuple[Decimal | None, Decimal | None]] = {
    "Less than $150K": (None, Decimal("150000")),
    "$150K to $250K": (Decimal("150000"), Decimal("250000")),
    "$250K to $500K": (Decimal("250000"), Decimal("500000")),
    "$500K to $1M": (Decimal("500000"), Decimal("1000000")),
    "$1M to $2M": (Decimal("1000000"), Decimal("2000000")),
    "$2M to $5M": (Decimal("2000000"), Decimal("5000000")),
    "$5M to $10M": (Decimal("5000000"), Decimal("10000000")),
    "$10M to $20M": (Decimal("10000000"), Decimal("20000000")),
    "$20M to $50M": (Decimal("20000000"), Decimal("50000000")),
    "$50M to $100M": (Decimal("50000000"), Decimal("100000000")),
    "$100M to $250M": (Decimal("100000000"), Decimal("250000000")),
    "Over $250M": (Decimal("250000000"), None),
    "Greater than $250M": (Decimal("250000000"), None),
}


@dataclass
class ApfsIngestStats:
    fetched: int
    upserted: int
    skipped: int
    error: str | None
    duration_ms: int


@celery_app.task(name="mactech.dhs_apfs.ingest_all")
def dhs_apfs_ingest_task() -> dict[str, Any]:
    return asdict(asyncio.run(_ingest()))


async def _ingest() -> ApfsIngestStats:
    started = datetime.now(UTC)
    try:
        async with httpx.AsyncClient(
            timeout=httpx.Timeout(60.0, connect=15.0),
            headers={"Accept": "application/json"},
        ) as client:
            resp = await client.get(APFS_API_URL)
            if resp.status_code != 200:
                return ApfsIngestStats(
                    fetched=0,
                    upserted=0,
                    skipped=0,
                    error=f"APFS API returned {resp.status_code}",
                    duration_ms=int((datetime.now(UTC) - started).total_seconds() * 1000),
                )
            payload = resp.json()
    except Exception as exc:
        return ApfsIngestStats(
            fetched=0,
            upserted=0,
            skipped=0,
            error=f"APFS fetch failed: {exc.__class__.__name__}: {exc}",
            duration_ms=int((datetime.now(UTC) - started).total_seconds() * 1000),
        )

    if not isinstance(payload, list):
        return ApfsIngestStats(
            fetched=0,
            upserted=0,
            skipped=0,
            error=f"APFS API returned non-list ({type(payload).__name__})",
            duration_ms=int((datetime.now(UTC) - started).total_seconds() * 1000),
        )

    fetched = len(payload)
    upserted = 0
    skipped = 0

    async with unscoped_session() as session:
        for item in payload:
            if not isinstance(item, dict):
                skipped += 1
                continue
            row = _to_row(item)
            if row is None:
                skipped += 1
                continue
            stmt = (
                pg_insert(ForecastRaw)
                .values(**row)
                .on_conflict_do_update(
                    index_elements=["source_url", "title"],
                    set_={
                        k: v
                        for k, v in row.items()
                        # Don't overwrite first_seen_at on update.
                        if k != "first_seen_at"
                    },
                )
            )
            await session.execute(stmt)
            upserted += 1

    duration_ms = int((datetime.now(UTC) - started).total_seconds() * 1000)
    log.info(
        "dhs_apfs ingest: fetched=%d upserted=%d skipped=%d duration=%dms",
        fetched,
        upserted,
        skipped,
        duration_ms,
    )
    return ApfsIngestStats(
        fetched=fetched,
        upserted=upserted,
        skipped=skipped,
        error=None,
        duration_ms=duration_ms,
    )


def _to_row(item: dict[str, Any]) -> dict[str, Any] | None:
    title = (item.get("requirements_title") or "").strip()
    if not title:
        return None

    apfs_number = _str_or_none(item.get("apfs_number"))
    apfs_id = item.get("id")
    # Construct a deep-link source URL so we can dedupe + link out from the UI.
    source_url = APFS_BASE
    if apfs_number:
        source_url = f"{APFS_BASE}?keyword={apfs_number}"
    elif apfs_id is not None:
        source_url = f"{APFS_BASE}?id={apfs_id}"

    naics_full = (item.get("naics") or "").strip()
    naics_code = None
    if naics_full:
        m = re.match(r"^(\d{4,6})\b", naics_full)
        if m:
            naics_code = m.group(1)

    dr = item.get("dollar_range") or {}
    dr_text = dr.get("display_name") if isinstance(dr, dict) else None
    val_low: Decimal | None = None
    val_high: Decimal | None = None
    if dr_text:
        bracket = _DOLLAR_RANGES.get(dr_text.strip())
        if bracket is not None:
            val_low, val_high = bracket

    poc_first = _str_or_none(item.get("requirements_contact_first_name"))
    poc_last = _str_or_none(item.get("requirements_contact_last_name"))
    poc_name: str | None = None
    if poc_first or poc_last:
        poc_name = " ".join(p for p in [poc_first, poc_last] if p) or None

    organization = _str_or_none(item.get("organization"))
    contracting_office = organization
    place_city = _str_or_none(item.get("place_of_performance_city"))
    place_state = _str_or_none(item.get("place_of_performance_state"))
    if place_city or place_state:
        loc = ", ".join(p for p in [place_city, place_state] if p)
        contracting_office = f"{contracting_office} ({loc})" if contracting_office else loc

    return {
        "source_url": source_url[:2000],
        "source_host": "apfs-cloud.dhs.gov",
        "source_run_id": None,
        "agency": "DHS",
        "contracting_office": contracting_office[:512] if contracting_office else None,
        "title": title[:1000],
        "description": _str_or_none(item.get("requirement")),
        "naics_code": naics_code,
        "naics_codes": [naics_code] if naics_code else None,
        "set_aside": _str_or_none(
            item.get("small_business_set_aside") or item.get("small_business_program")
        ),
        "contract_type": _str_or_none(item.get("contract_type")),
        "estimated_value_low": val_low,
        "estimated_value_high": val_high,
        "estimated_value_text": dr_text,
        "expected_solicitation_date": _parse_apfs_date(
            item.get("estimated_solicitation_release_date") or item.get("estimated_release_date")
        ),
        "expected_award_date": _parse_apfs_date(item.get("anticipated_award_date")),
        "period_of_performance_start": _parse_apfs_date(
            item.get("estimated_period_of_performance_start")
        ),
        "period_of_performance_end": _parse_apfs_date(
            item.get("estimated_period_of_performance_end")
        ),
        "incumbent_name": _str_or_none(item.get("contractor")),
        "incumbent_contract_number": _str_or_none(item.get("contract_number")),
        "poc_name": poc_name,
        "poc_email": None,  # APFS exposes phone but not email.
        "forecast_id": apfs_number or (str(apfs_id) if apfs_id else None),
        "raw": item,
        "first_seen_at": datetime.now(UTC),
        "last_seen_at": datetime.now(UTC),
    }


def _str_or_none(v: Any) -> str | None:
    if v is None:
        return None
    s = str(v).strip()
    return s or None


def _parse_apfs_date(v: Any) -> date | None:
    """APFS date format is "MM/DD/YYYY" (sometimes "M/D/YYYY")."""
    if v is None:
        return None
    s = str(v).strip()
    if not s:
        return None
    # ISO 8601 fallback (some fields may already be ISO).
    try:
        if "-" in s and "/" not in s:
            return date.fromisoformat(s[:10])
    except ValueError:
        pass
    # MM/DD/YYYY
    m = re.match(r"^(\d{1,2})/(\d{1,2})/(\d{4})", s)
    if m:
        try:
            return date(int(m.group(3)), int(m.group(1)), int(m.group(2)))
        except ValueError:
            return None
    return None
