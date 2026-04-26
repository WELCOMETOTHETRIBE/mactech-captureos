"""Agency procurement forecasts via Apify website-content-crawler.

Sprint 20 / strategy doc §3.1. Federal agencies publish acquisition
forecasts (DHS APFS, VA FCO, USACE, Air Force BES SMART Guide, etc.)
30-180 days before the matching SAM.gov solicitation appears. Capturing
these gives MacTech a multi-month head start — especially on incumbent
recompetes.

Same flow as industry-days:
  1. Daily 0530 ET beat → kick `apify/website-content-crawler` with a
     curated set of forecast hub URLs, depth=3, browser rendering.
  2. Wait for Apify run to complete (poll-based; bypasses the 60s
     waitForFinish cap).
  3. Pull dataset items, prefilter to forecast-y pages, run Claude
     Haiku to extract structured forecast records (one page can hold
     dozens of forecast rows).
  4. Upsert into forecasts_raw, dedupe on (source_url, title).

Strategy doc says: "a 90-day head start on a $2M opportunity is worth
more than every other capability on this list combined." This is the
single highest-ROI Apify capability.
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
from dataclasses import asdict, dataclass
from datetime import UTC, date, datetime
from decimal import Decimal, InvalidOperation
from typing import Any
from urllib.parse import urlparse

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert

from mactech_db import unscoped_session
from mactech_db.models import ApifyRun, ForecastRaw
from mactech_intelligence import AnthropicLLMClient
from mactech_integrations.apify import ApifyClient, ApifyError
from mactech_workers.celery_app import celery_app

log = logging.getLogger(__name__)

WEBSITE_CONTENT_CRAWLER_ACTOR = "apify/website-content-crawler"
FORECASTS_RUN_TIMEOUT_SECS = 1500  # forecasts hubs are heavy; 25 min ceiling

# Verified-live forecast hubs sourced via SerpAPI 2026-04-26.
FORECAST_SEED_URLS = [
    # DHS Acquisition Planning Forecast System (APFS) — gold-standard.
    "https://apfs-cloud.dhs.gov/forecast/",
    "https://www.dhs.gov/advance-acquisition-planning-forecast-contract-opportunities",
    # VA Forecast of Contracting Opportunities (FY26).
    "https://www.vendorportal.ecms.va.gov/eVP/FCO/",
    # USACE forecast hubs.
    "https://www.usace.army.mil/Strategic-Partnerships/Small-Business/Upcoming-Contract-Opportunities/",
    "https://www.nwd.usace.army.mil/business-with-us/opportunities-forecast/",
    # Army SMDC Virtual Industry Exchange.
    "https://www.smdc.army.mil/VIE_FIR/",
    # Air Force BES SMART Guide (most recent FY26 PDF — the crawler
    # extracts text from PDFs out of the box).
    "https://www.airforcebes.af.mil/Portals/23/BES%20SMART%20Guide_Fall%202025_10%20December%202025.pdf",
    "https://www.airforcebes.af.mil/",
    # Air Force small biz opportunities.
    "https://www.airforcesmallbiz.af.mil/Small-Business/Business-Opportunities/",
    # GSA find-opportunities hub.
    "https://www.gsa.gov/small-business/find-opportunities",
    # HHS contract opportunities.
    "https://www.hhs.gov/grants-contracts/small-business-support/contract-opportunities/index.html",
    # Army OSBP.
    "https://www.army.mil/osbp",
    # DoD OSBP archived (still has cross-DoD pointers).
    "https://business.defense.gov/Archived-Pages/Acquisition-Forecasts/",
]


EXTRACTOR_PROMPT_VERSION = "forecasts-v1"
EXTRACTOR_SYSTEM = """You extract federal *acquisition forecast* records from a web page.
A forecast is an agency's published intent to procure a good or service —
distinct from a solicitation (which lives in SAM.gov).

Return STRICT JSON: an object with one key, "forecasts", which is a JSON array.
For each distinct forecast on the page, emit:

  {
    "title":                          string — the program/contract name
    "agency":                         string | null — sponsoring agency / office
    "contracting_office":             string | null — sub-bureau / district
    "description":                    string | null — 1-3 sentence scope summary
    "naics_code":                     string | null — primary NAICS, 6 digits
    "naics_codes":                    array of NAICS strings if multiple are listed
    "set_aside":                      string | null — e.g. "SDVOSB", "8(a)", "Total Small Business", "HUBZone", "Full and Open"
    "contract_type":                  string | null — e.g. "IDIQ", "MAC", "FFP", "BPA"
    "estimated_value_low":            number | null — dollars
    "estimated_value_high":           number | null — dollars
    "estimated_value_text":           string | null — verbatim if a range like "$2M-$5M"
    "expected_solicitation_date":     ISO 8601 date | null — when the RFP is expected to post
    "expected_award_date":            ISO 8601 date | null
    "period_of_performance_start":    ISO 8601 date | null
    "period_of_performance_end":      ISO 8601 date | null
    "incumbent_name":                 string | null — current contractor if listed
    "incumbent_contract_number":      string | null
    "poc_name":                       string | null
    "poc_email":                      string | null
    "forecast_id":                    string | null — agency-internal id when present
  }

Counts as a forecast when:
  - The page lists a planned procurement with at least a title AND one of:
    NAICS code, expected solicitation/award date, contract type, or
    estimated value
  - It is clearly intent (not yet posted to SAM)

Do NOT emit:
  - Currently-open solicitations (those belong in SAM)
  - General agency descriptions or boilerplate ("about USACE", "what is APFS")
  - Past awards (those are in USASpending)
  - Page navigation, calls-to-action, or links to external systems

Examples:

INPUT (excerpt from DHS APFS):
"Cybersecurity Operations Support Services
NAICS: 541512
Estimated Value: $25,000,000 - $50,000,000
Set-Aside: SDVOSB
Solicitation Expected: Q2 FY2026
Award Expected: Q4 FY2026
Component: TSA
POC: contracts@tsa.dhs.gov"

OUTPUT: {"forecasts": [{"title": "Cybersecurity Operations Support Services",
"agency": "DHS", "contracting_office": "TSA", "description": null,
"naics_code": "541512", "naics_codes": ["541512"], "set_aside": "SDVOSB",
"contract_type": null, "estimated_value_low": 25000000, "estimated_value_high":
50000000, "estimated_value_text": "$25,000,000 - $50,000,000",
"expected_solicitation_date": "2026-03-31", "expected_award_date": "2026-09-30",
"period_of_performance_start": null, "period_of_performance_end": null,
"incumbent_name": null, "incumbent_contract_number": null, "poc_name": null,
"poc_email": "contracts@tsa.dhs.gov", "forecast_id": null}]}

INPUT: "Welcome to the GSA Small Business Page. Click here to find opportunities."

OUTPUT: {"forecasts": []}

Rules:
  - Never invent dates, NAICS codes, or POCs. Use null when missing.
  - Quarter-of-fiscal-year dates: convert "Q1 FY2026" → "2025-12-31",
    "Q2 FY2026" → "2026-03-31", "Q3 FY2026" → "2026-06-30",
    "Q4 FY2026" → "2026-09-30".
  - Output ONLY the JSON object. No prose, no markdown fences.
"""


@dataclass
class ForecastIngestStats:
    audit_id: str | None
    apify_run_id: str | None
    items_seen: int
    skipped_low_signal: int
    forecasts_upserted: int
    extraction_failures: int
    error: str | None


_FORECAST_URL_HINTS = (
    "forecast", "acquisition", "opportunity", "opportunities",
    "smart-guide", "smart_guide", "fco", "apfs", "vie",
    "small-business", "smallbusiness", "osbp",
)
_FORECAST_TEXT_HINTS = (
    "naics", "set-aside", "set aside", "solicitation", "anticipated award",
    "expected award", "estimated value", "contract type",
    "period of performance", "forecast", "fy2026", "fy 2026",
)


def _looks_like_forecast_page(url: str, text: str) -> bool:
    u = url.lower()
    if any(h in u for h in _FORECAST_URL_HINTS):
        return True
    t = text.lower()
    return any(h in t for h in _FORECAST_TEXT_HINTS)


@celery_app.task(name="mactech.apify.kick_forecasts_run")
def kick_forecasts_run_task() -> dict[str, Any]:
    return asyncio.run(_kick_and_ingest())


async def _kick_and_ingest() -> dict[str, Any]:
    api_token = os.environ.get("APIFY_API_TOKEN", "")
    if not api_token:
        log.warning("APIFY_API_TOKEN not set; skipping forecasts kick")
        return {"started": False, "reason": "no_token"}

    run_input = {
        "startUrls": [{"url": u} for u in FORECAST_SEED_URLS],
        "crawlerType": "playwright:adaptive",
        "maxCrawlDepth": 3,
        "maxCrawlPages": 400,
        "saveHtml": False,
        "saveMarkdown": True,
        "removeElementsCssSelector": (
            "nav, footer, header, .ads, .menu, .skip-link, .breadcrumbs, "
            "form, aside, .sidebar"
        ),
        "keepUrlFragments": False,
    }

    async with ApifyClient(api_token) as client:
        try:
            run = await client.run_actor_sync(
                WEBSITE_CONTENT_CRAWLER_ACTOR,
                run_input,
                wait_for_finish_secs=FORECASTS_RUN_TIMEOUT_SECS,
            )
        except ApifyError as exc:
            log.warning("apify kick forecasts failed: %s", exc)
            return {"started": False, "error": str(exc)[:300]}

    log.info(
        "forecasts kick: apify run %s status=%s on %d seed urls",
        run.id,
        run.status,
        len(FORECAST_SEED_URLS),
    )

    if run.status != "SUCCEEDED" or not run.default_dataset_id:
        return {
            "started": True,
            "apify_run_id": run.id,
            "status": run.status,
            "ingested": False,
            "reason": "run_not_succeeded" if run.status != "SUCCEEDED" else "no_dataset_id",
        }

    audit_id = await _record_synthetic_audit(
        capability="forecasts",
        apify_run_id=run.id,
        apify_actor_id=run.actor_id,
        apify_status=run.status,
        dataset_id=run.default_dataset_id,
        items_count=int(run.stats.get("requestsFinished") or 0) or None,
    )

    stats = await _ingest(
        audit_id=audit_id,
        dataset_id=run.default_dataset_id,
        apify_run_id=run.id,
    )
    return {
        "started": True,
        "apify_run_id": run.id,
        "status": run.status,
        "ingested": True,
        "forecasts_upserted": stats.forecasts_upserted,
        "items_seen": stats.items_seen,
        "skipped": stats.skipped_low_signal,
        "extraction_failures": stats.extraction_failures,
    }


async def _record_synthetic_audit(
    *,
    capability: str,
    apify_run_id: str,
    apify_actor_id: str,
    apify_status: str | None,
    dataset_id: str | None,
    items_count: int | None,
) -> str:
    async with unscoped_session() as session:
        stmt = (
            pg_insert(ApifyRun)
            .values(
                apify_run_id=apify_run_id,
                apify_actor_id=apify_actor_id,
                capability=capability,
                event_type="WORKER.RUN.SUCCEEDED",
                apify_status=apify_status,
                dataset_id=dataset_id,
                items_count=items_count,
                payload={"source": "worker_inline"},
            )
            .on_conflict_do_update(
                index_elements=["apify_run_id", "event_type"],
                set_={
                    "apify_status": apify_status,
                    "dataset_id": dataset_id,
                    "items_count": items_count,
                },
            )
            .returning(ApifyRun.id)
        )
        result = await session.execute(stmt)
        return str(result.scalar_one())


@celery_app.task(name="mactech.apify.ingest_forecasts")
def ingest_forecasts_task(
    audit_id: str, dataset_id: str, apify_run_id: str
) -> dict[str, Any]:
    return asdict(asyncio.run(_ingest(audit_id, dataset_id, apify_run_id)))


async def _ingest(
    audit_id: str, dataset_id: str, apify_run_id: str
) -> ForecastIngestStats:
    api_token = os.environ.get("APIFY_API_TOKEN", "")
    anthropic_key = os.environ.get("ANTHROPIC_API_KEY", "")

    if not api_token or not anthropic_key:
        return ForecastIngestStats(
            audit_id=audit_id,
            apify_run_id=apify_run_id,
            items_seen=0,
            skipped_low_signal=0,
            forecasts_upserted=0,
            extraction_failures=0,
            error="missing APIFY_API_TOKEN or ANTHROPIC_API_KEY",
        )

    items: list[dict[str, Any]] = []
    async with ApifyClient(api_token) as client:
        try:
            offset = 0
            while True:
                page = await client.dataset_items(
                    dataset_id, limit=200, offset=offset, clean=True
                )
                if not page:
                    break
                items.extend(p.payload for p in page)
                if len(page) < 200:
                    break
                offset += 200
        except ApifyError as exc:
            log.warning(
                "apify dataset_items failed for forecasts run=%s: %s",
                apify_run_id,
                exc,
            )
            await _mark_audit_processed(audit_id, error=str(exc)[:1000])
            return ForecastIngestStats(
                audit_id=audit_id,
                apify_run_id=apify_run_id,
                items_seen=0,
                skipped_low_signal=0,
                forecasts_upserted=0,
                extraction_failures=0,
                error=str(exc),
            )

    llm = AnthropicLLMClient(api_key=anthropic_key)
    upserted = 0
    failures = 0
    skipped_low_signal = 0

    async with unscoped_session() as session:
        for item in items:
            url = str(item.get("url") or "").strip()
            text = str(item.get("text") or item.get("markdown") or "").strip()
            if not url or len(text) < 200:
                skipped_low_signal += 1
                continue
            if not _looks_like_forecast_page(url, text):
                skipped_low_signal += 1
                continue

            try:
                forecasts = await _extract_forecasts(llm, url, text)
            except Exception as exc:  # noqa: BLE001
                failures += 1
                log.info(
                    "forecasts extract failed for %s: %s", url, exc
                )
                continue

            for fc in forecasts:
                title = (fc.get("title") or "").strip()
                if not title or len(title) > 1000:
                    continue
                stmt = (
                    pg_insert(ForecastRaw)
                    .values(
                        source_url=url[:2000],
                        source_host=_host_of(url),
                        source_run_id=apify_run_id,
                        agency=_str_or_none(fc.get("agency")),
                        contracting_office=_str_or_none(
                            fc.get("contracting_office")
                        ),
                        title=title,
                        description=_str_or_none(fc.get("description")),
                        naics_code=_naics_or_none(fc.get("naics_code")),
                        naics_codes=fc.get("naics_codes") or None,
                        set_aside=_str_or_none(fc.get("set_aside")),
                        contract_type=_str_or_none(fc.get("contract_type")),
                        estimated_value_low=_money_or_none(
                            fc.get("estimated_value_low")
                        ),
                        estimated_value_high=_money_or_none(
                            fc.get("estimated_value_high")
                        ),
                        estimated_value_text=_str_or_none(
                            fc.get("estimated_value_text")
                        ),
                        expected_solicitation_date=_parse_date(
                            fc.get("expected_solicitation_date")
                        ),
                        expected_award_date=_parse_date(
                            fc.get("expected_award_date")
                        ),
                        period_of_performance_start=_parse_date(
                            fc.get("period_of_performance_start")
                        ),
                        period_of_performance_end=_parse_date(
                            fc.get("period_of_performance_end")
                        ),
                        incumbent_name=_str_or_none(fc.get("incumbent_name")),
                        incumbent_contract_number=_str_or_none(
                            fc.get("incumbent_contract_number")
                        ),
                        poc_name=_str_or_none(fc.get("poc_name")),
                        poc_email=_str_or_none(fc.get("poc_email")),
                        forecast_id=_str_or_none(fc.get("forecast_id")),
                        raw=fc,
                    )
                    .on_conflict_do_update(
                        index_elements=["source_url", "title"],
                        set_={
                            "source_run_id": apify_run_id,
                            "agency": _str_or_none(fc.get("agency")),
                            "contracting_office": _str_or_none(
                                fc.get("contracting_office")
                            ),
                            "description": _str_or_none(fc.get("description")),
                            "naics_code": _naics_or_none(fc.get("naics_code")),
                            "naics_codes": fc.get("naics_codes") or None,
                            "set_aside": _str_or_none(fc.get("set_aside")),
                            "contract_type": _str_or_none(
                                fc.get("contract_type")
                            ),
                            "estimated_value_low": _money_or_none(
                                fc.get("estimated_value_low")
                            ),
                            "estimated_value_high": _money_or_none(
                                fc.get("estimated_value_high")
                            ),
                            "estimated_value_text": _str_or_none(
                                fc.get("estimated_value_text")
                            ),
                            "expected_solicitation_date": _parse_date(
                                fc.get("expected_solicitation_date")
                            ),
                            "expected_award_date": _parse_date(
                                fc.get("expected_award_date")
                            ),
                            "period_of_performance_start": _parse_date(
                                fc.get("period_of_performance_start")
                            ),
                            "period_of_performance_end": _parse_date(
                                fc.get("period_of_performance_end")
                            ),
                            "incumbent_name": _str_or_none(
                                fc.get("incumbent_name")
                            ),
                            "incumbent_contract_number": _str_or_none(
                                fc.get("incumbent_contract_number")
                            ),
                            "poc_name": _str_or_none(fc.get("poc_name")),
                            "poc_email": _str_or_none(fc.get("poc_email")),
                            "forecast_id": _str_or_none(fc.get("forecast_id")),
                            "raw": fc,
                            "last_seen_at": datetime.now(UTC),
                        },
                    )
                )
                await session.execute(stmt)
                upserted += 1

    await _mark_audit_processed(audit_id)
    log.info(
        "forecasts ingest: run=%s items=%d skipped=%d upserted=%d failures=%d",
        apify_run_id,
        len(items),
        skipped_low_signal,
        upserted,
        failures,
    )
    return ForecastIngestStats(
        audit_id=audit_id,
        apify_run_id=apify_run_id,
        items_seen=len(items),
        skipped_low_signal=skipped_low_signal,
        forecasts_upserted=upserted,
        extraction_failures=failures,
        error=None,
    )


async def _extract_forecasts(
    llm: AnthropicLLMClient, url: str, text: str
) -> list[dict[str, Any]]:
    excerpt = text[:14_000]
    today = datetime.now(UTC).date().isoformat()
    user_prompt = (
        f"Today's date: {today}.\n"
        f"Source URL: {url}\n\nPage text:\n\n{excerpt}\n\n"
        "Return the JSON object now."
    )
    resp = await llm.complete(
        system=EXTRACTOR_SYSTEM,
        user=user_prompt,
        complexity="fast",
        max_tokens=4000,
    )
    text_out = (resp.text or "").strip()
    if text_out.startswith("```"):
        text_out = text_out.strip("`")
        if text_out.lower().startswith("json"):
            text_out = text_out[4:].strip()
    try:
        parsed = json.loads(text_out)
    except json.JSONDecodeError as exc:
        raise ValueError(f"non-JSON extractor output: {exc}") from exc
    forecasts = parsed.get("forecasts") if isinstance(parsed, dict) else None
    if not isinstance(forecasts, list):
        return []
    return [f for f in forecasts if isinstance(f, dict)]


async def _mark_audit_processed(
    audit_id: str, *, error: str | None = None
) -> None:
    async with unscoped_session() as session:
        row = (
            await session.execute(
                select(ApifyRun).where(ApifyRun.id == audit_id)
            )
        ).scalar_one_or_none()
        if row is None:
            return
        row.processed_at = datetime.now(UTC)
        if error:
            row.ingest_error = error[:1000]


def _str_or_none(v: Any) -> str | None:
    if v is None:
        return None
    s = str(v).strip()
    return s or None


def _host_of(url: str) -> str | None:
    try:
        return urlparse(url).netloc or None
    except Exception:  # noqa: BLE001
        return None


def _naics_or_none(v: Any) -> str | None:
    s = _str_or_none(v)
    if s and s.isdigit() and 4 <= len(s) <= 6:
        return s.zfill(6) if len(s) < 6 else s
    return s  # accept agency-formatted strings as-is


def _money_or_none(v: Any) -> Decimal | None:
    if v is None:
        return None
    if isinstance(v, (int, float, Decimal)):
        try:
            return Decimal(str(v))
        except (InvalidOperation, ValueError):
            return None
    s = str(v).strip()
    if not s:
        return None
    # Strip currency symbols, commas, spaces.
    cleaned = s.replace("$", "").replace(",", "").strip()
    try:
        return Decimal(cleaned)
    except (InvalidOperation, ValueError):
        return None


def _parse_date(v: Any) -> date | None:
    if v is None:
        return None
    s = str(v).strip()
    if not s:
        return None
    try:
        if "T" in s:
            return datetime.fromisoformat(s.replace("Z", "+00:00")).date()
        return date.fromisoformat(s[:10])
    except ValueError:
        return None
