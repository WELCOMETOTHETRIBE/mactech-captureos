"""DOE OSBP Acquisition Forecast — direct XLSX ingest.

Sprint 20 follow-up. The Department of Energy's Office of Small
Business Programs publishes their entire acquisition forecast as a
public XLSX at energy.gov, refreshed monthly. The URL is date-stamped
(e.g. `OSBP Acquisition Forecast Public 2026-04-11.xlsx`) so we scrape
the OSBP page each run to find the current file.

XLSX schema (DOE's columns, as of 2026-04):
  0  Performance End Date          → period_of_performance_end
  1  NAICS Code                    → naics_code
  2  NAICS Description
  3  Program Office                → contracting_office
  4  Current Incumbent             → incumbent_name
  5  Current Contract Number       → incumbent_contract_number
  6  Acquisition Description       → title (DOE doesn't publish a separate title)
  7  Estimated Value Range         → estimated_value_text + low/high
  8  Contracting Officers Business Size Selection
  9  Type of Set Aside             → set_aside
  10 Contract Type                 → contract_type
  11 Principal Place of Performance State
  12 Small Business Program Manager → poc_email

DOE doesn't publish expected solicitation/award dates — only the
performance-end date. So this feeds the recompete-watch use case (we
know when current contracts expire) more than the "coming-to-SAM"
timeline use case that DHS APFS covers.
"""

from __future__ import annotations

import asyncio
import io
import logging
import re
from dataclasses import asdict, dataclass
from datetime import UTC, date, datetime
from decimal import Decimal
from typing import Any

import httpx
import openpyxl
from sqlalchemy.dialects.postgresql import insert as pg_insert

from mactech_db import unscoped_session
from mactech_db.models import ForecastRaw
from mactech_workers.celery_app import celery_app

log = logging.getLogger(__name__)

DOE_OSBP_PAGE = "https://www.energy.gov/osbp/acquisition-forecast"

# DOE value-range strings → (low, high). Codes like "R1", "R5" appear
# alongside dollar ranges in the data; we keep the verbatim text and
# map to numeric brackets where parseable.
_DOE_VALUE_RE = re.compile(
    r"\$?([\d,.]+)\s*([KMB])\s*[-–—]\s*\$?([\d,.]+)\s*([KMB])",
    re.IGNORECASE,
)
_MULTIPLIER = {"K": 1_000, "M": 1_000_000, "B": 1_000_000_000}


@dataclass
class DoeIngestStats:
    xlsx_url: str | None
    fetched_rows: int
    upserted: int
    skipped: int
    error: str | None
    duration_ms: int


@celery_app.task(name="mactech.doe.ingest_forecast")
def doe_ingest_task() -> dict[str, Any]:
    return asdict(asyncio.run(_ingest()))


async def _ingest() -> DoeIngestStats:
    started = datetime.now(UTC)
    try:
        xlsx_url = await _resolve_xlsx_url()
        if not xlsx_url:
            return DoeIngestStats(
                xlsx_url=None,
                fetched_rows=0,
                upserted=0,
                skipped=0,
                error="DOE XLSX link not found on OSBP page",
                duration_ms=_ms_since(started),
            )

        async with httpx.AsyncClient(
            timeout=httpx.Timeout(60.0, connect=15.0),
            follow_redirects=True,
        ) as client:
            resp = await client.get(xlsx_url)
            if resp.status_code != 200:
                return DoeIngestStats(
                    xlsx_url=xlsx_url,
                    fetched_rows=0,
                    upserted=0,
                    skipped=0,
                    error=f"DOE XLSX returned {resp.status_code}",
                    duration_ms=_ms_since(started),
                )
            xlsx_bytes = resp.content
    except Exception as exc:  # noqa: BLE001
        return DoeIngestStats(
            xlsx_url=None,
            fetched_rows=0,
            upserted=0,
            skipped=0,
            error=f"DOE fetch failed: {exc.__class__.__name__}: {exc}",
            duration_ms=_ms_since(started),
        )

    try:
        wb = openpyxl.load_workbook(
            io.BytesIO(xlsx_bytes), read_only=True, data_only=True
        )
    except Exception as exc:  # noqa: BLE001
        return DoeIngestStats(
            xlsx_url=xlsx_url,
            fetched_rows=0,
            upserted=0,
            skipped=0,
            error=f"DOE XLSX parse failed: {exc}",
            duration_ms=_ms_since(started),
        )

    ws = wb.active
    rows_iter = ws.iter_rows(values_only=True)
    header_row, header_idx = _find_header_row(rows_iter)
    if not header_row:
        return DoeIngestStats(
            xlsx_url=xlsx_url,
            fetched_rows=0,
            upserted=0,
            skipped=0,
            error="DOE XLSX header row not found",
            duration_ms=_ms_since(started),
        )

    fetched = 0
    upserted = 0
    skipped = 0
    async with unscoped_session() as session:
        for row in rows_iter:
            fetched += 1
            mapped = _map_row(row, source_url=xlsx_url)
            if mapped is None:
                skipped += 1
                continue
            stmt = (
                pg_insert(ForecastRaw)
                .values(**mapped)
                .on_conflict_do_update(
                    index_elements=["source_url", "title"],
                    set_={k: v for k, v in mapped.items() if k != "first_seen_at"},
                )
            )
            await session.execute(stmt)
            upserted += 1

    log.info(
        "doe forecast ingest: rows=%d upserted=%d skipped=%d url=%s",
        fetched,
        upserted,
        skipped,
        xlsx_url,
    )
    return DoeIngestStats(
        xlsx_url=xlsx_url,
        fetched_rows=fetched,
        upserted=upserted,
        skipped=skipped,
        error=None,
        duration_ms=_ms_since(started),
    )


async def _resolve_xlsx_url() -> str | None:
    """Scrape the OSBP page and return the most recent XLSX href."""
    async with httpx.AsyncClient(
        timeout=httpx.Timeout(30.0, connect=10.0),
        follow_redirects=True,
    ) as client:
        resp = await client.get(DOE_OSBP_PAGE)
        if resp.status_code != 200:
            log.warning("DOE OSBP page returned %d", resp.status_code)
            return None
    html = resp.text
    matches = re.findall(
        r'href="(https?://[^"]+/[^"]*Acquisition[^"]*Forecast[^"]*\.xlsx)"',
        html,
    )
    return matches[0] if matches else None


def _find_header_row(rows_iter):
    """DOE puts ~16 rows of instructions before the header. Scan for
    a row with 'NAICS Code' to locate the actual header."""
    for i, row in enumerate(rows_iter):
        if any(c == "NAICS Code" for c in row if c):
            return row, i
        if i > 30:
            return None, -1
    return None, -1


def _map_row(row: tuple, *, source_url: str) -> dict[str, Any] | None:
    if not row or len(row) < 13:
        return None
    title = _str_or_none(row[6])
    if not title:
        return None
    naics_code = _naics_or_none(row[1])
    naics_desc = _str_or_none(row[2])

    program_office = _str_or_none(row[3])
    state = _str_or_none(row[11]) if len(row) > 11 else None
    contracting_office = program_office
    if state and state.lower() != "unavailable":
        contracting_office = (
            f"{program_office} ({state})" if program_office else state
        )

    value_text = _str_or_none(row[7])
    val_low, val_high = _parse_value_range(value_text)

    set_aside = _str_or_none(row[9])
    if set_aside in ("N/A", "TBD", "Unavailable", "No set aside used."):
        set_aside = None

    poc_email_or_name = _str_or_none(row[12])
    poc_email = poc_email_or_name if poc_email_or_name and "@" in poc_email_or_name else None
    poc_name = poc_email_or_name if poc_email_or_name and "@" not in poc_email_or_name else None

    perf_end = _to_date(row[0])

    incumbent_raw = _str_or_none(row[4])
    if incumbent_raw and incumbent_raw.lower() in ("n/a", "tbd", "unavailable", "none"):
        incumbent_raw = None
    incumbent_contract = _str_or_none(row[5])
    if incumbent_contract and incumbent_contract.lower() in ("n/a", "tbd", "unavailable"):
        incumbent_contract = None

    # Synthetic deep-link source: keep the XLSX URL but append a row
    # anchor based on contract number so each row is dedupe-able.
    src = source_url
    if incumbent_contract:
        src = f"{source_url}#{incumbent_contract.replace(' ', '_')[:60]}"

    return {
        "source_url": src[:2000],
        "source_host": "www.energy.gov",
        "source_run_id": None,
        "agency": "DOE",
        "contracting_office": (contracting_office or "")[:512] or None,
        "title": title[:1000],
        "description": naics_desc,
        "naics_code": naics_code,
        "naics_codes": [naics_code] if naics_code else None,
        "set_aside": set_aside,
        "contract_type": _str_or_none(row[10]),
        "estimated_value_low": val_low,
        "estimated_value_high": val_high,
        "estimated_value_text": value_text,
        "expected_solicitation_date": None,
        "expected_award_date": None,
        "period_of_performance_start": None,
        "period_of_performance_end": perf_end,
        "incumbent_name": incumbent_raw,
        "incumbent_contract_number": incumbent_contract,
        "poc_name": poc_name,
        "poc_email": poc_email,
        "forecast_id": incumbent_contract,
        "raw": {
            "perf_end": str(row[0]) if row[0] is not None else None,
            "naics_code": str(row[1]) if row[1] is not None else None,
            "naics_desc": naics_desc,
            "program_office": program_office,
            "incumbent": incumbent_raw,
            "contract_number": incumbent_contract,
            "description": title,
            "value_range": value_text,
            "co_business_size": _str_or_none(row[8]),
            "set_aside_raw": _str_or_none(row[9]),
            "contract_type": _str_or_none(row[10]),
            "state": state,
            "sb_program_manager": poc_email_or_name,
        },
        "first_seen_at": datetime.now(UTC),
        "last_seen_at": datetime.now(UTC),
    }


def _parse_value_range(s: str | None) -> tuple[Decimal | None, Decimal | None]:
    if not s:
        return None, None
    m = _DOE_VALUE_RE.search(s)
    if not m:
        return None, None
    low_n, low_u, high_n, high_u = m.groups()
    try:
        low = Decimal(low_n.replace(",", "")) * _MULTIPLIER[low_u.upper()]
        high = Decimal(high_n.replace(",", "")) * _MULTIPLIER[high_u.upper()]
        return low, high
    except Exception:  # noqa: BLE001
        return None, None


def _str_or_none(v: Any) -> str | None:
    if v is None:
        return None
    s = str(v).strip()
    return s or None


def _naics_or_none(v: Any) -> str | None:
    if v is None:
        return None
    s = str(v).strip()
    if not s:
        return None
    if "." in s:
        s = s.split(".", 1)[0]
    if s.isdigit() and 4 <= len(s) <= 6:
        return s.zfill(6) if len(s) < 6 else s
    return None


def _to_date(v: Any) -> date | None:
    if v is None:
        return None
    if isinstance(v, datetime):
        return v.date()
    if isinstance(v, date):
        return v
    s = str(v).strip()
    if not s:
        return None
    try:
        if "T" in s:
            return datetime.fromisoformat(s.replace("Z", "+00:00")).date()
        return date.fromisoformat(s[:10])
    except ValueError:
        return None


def _ms_since(started: datetime) -> int:
    return int((datetime.now(UTC) - started).total_seconds() * 1000)
