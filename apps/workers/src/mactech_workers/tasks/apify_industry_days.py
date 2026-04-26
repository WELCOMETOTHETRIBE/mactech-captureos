"""Industry-Day calendar via Apify website-content-crawler.

Sprint 19 / strategy doc §3.6. Daily beat 0500 ET fires
`mactech.apify.kick_industry_days_run` which starts a website-content-
crawler run over a curated list of agency event/industry-day pages,
waits for completion (Apify's `waitForFinish` server-side block,
capped at INDUSTRY_DAYS_RUN_TIMEOUT_SECS), then dispatches
`mactech.apify.ingest_industry_days` to pull dataset items, run Claude
Haiku to extract structured event metadata, and upsert into
`agency_events` (dedupe on source_url + title).

The synchronous run-then-ingest path means **no Apify-dashboard
webhook config is required** — activation is just APIFY_API_TOKEN +
the daily beat. The webhook receiver still ships and is HMAC-verified;
it's the right pattern for higher-volume capabilities (forecast
sweep, EDGAR) which we can wire up later without rework.

Agency seed list is small (8 pages) so each daily run is well under
the strategy doc's $5/mo budget for this capability.
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
from dataclasses import asdict, dataclass
from datetime import UTC, date, datetime
from typing import Any
from urllib.parse import urlparse

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert

from mactech_db import unscoped_session
from mactech_db.models import AgencyEvent, ApifyRun
from mactech_intelligence import AnthropicLLMClient
from mactech_integrations.apify import ApifyClient, ApifyError
from mactech_workers.celery_app import celery_app

log = logging.getLogger(__name__)


# Apify Store actor — first-party, well-maintained, no rental sunset risk.
WEBSITE_CONTENT_CRAWLER_ACTOR = "apify/website-content-crawler"

# Wait at most this long for the actor run on the daily beat. Apify's
# server-side waitForFinish blocks server-side until the run resolves
# or the deadline expires. 8 seed pages × maxCrawlDepth=2 finishes in
# ~30-90s in practice; 300s is a comfortable ceiling.
INDUSTRY_DAYS_RUN_TIMEOUT_SECS = 300

# Curated agency event / industry-day pages. Hand-picked from agencies
# whose forecasts already drive MacTech NAICS. Keep this list short so
# the daily Apify spend stays predictable.
INDUSTRY_DAY_SEED_URLS = [
    # DoD OSBP outreach calendar
    "https://business.defense.gov/Small-Business/Events/",
    # NIWC Atlantic + Pacific industry days
    "https://www.niwcatlantic.navy.mil/Industry/",
    "https://www.niwcpacific.navy.mil/Partnerships/Industry-Days/",
    # GSA OSDBU events
    "https://www.gsa.gov/about-us/organization/office-of-small-and-disadvantaged-business-utilization/events",
    # AFCEA chapter calendar (cross-agency)
    "https://events.afcea.org/AFCEAEventCalendar/",
    # DHS S&T Industry Engagement
    "https://www.dhs.gov/science-and-technology/news/industry-day",
    # Air Force AFLCMC industry day index
    "https://www.aflcmc.af.mil/Events/",
    # Army ASA(ALT) OSBP outreach
    "https://www.army.mil/asaalt/osbp/",
]


EXTRACTOR_PROMPT_VERSION = "industry-days-v1"
EXTRACTOR_SYSTEM = (
    "You extract structured event metadata from a federal-agency web "
    "page. Return STRICT JSON: a single object with key 'events' that "
    "is a JSON array. For each event found in the page text, emit "
    "{title, kind, agency, starts_at, ends_at, location, "
    "registration_url, summary, naics_codes}. starts_at/ends_at are "
    "ISO 8601 dates or datetimes; null when not stated. kind is one of "
    "'industry_day', 'pre_solicitation', 'meet_the_buyer', 'symposium', "
    "'conference', 'webinar', 'other'. naics_codes is an array of "
    "strings if the page lists target NAICS, otherwise []. "
    "If the page has no events at all, emit {events: []}. "
    "Do not invent dates, agencies, or NAICS — use null and []. "
    "Output ONLY the JSON object, no prose."
)


@dataclass
class IndustryDayIngestStats:
    audit_id: str | None
    apify_run_id: str | None
    items_seen: int
    events_upserted: int
    extraction_failures: int
    error: str | None


@celery_app.task(name="mactech.apify.kick_industry_days_run")
def kick_industry_days_run_task() -> dict[str, Any]:
    """Daily beat — start a website-content-crawler run, wait for it
    to finish (server-side blocking via Apify's waitForFinish), then
    dispatch the ingest task. No webhook config required."""
    return asyncio.run(_kick_and_ingest())


async def _kick_and_ingest() -> dict[str, Any]:
    api_token = os.environ.get("APIFY_API_TOKEN", "")
    if not api_token:
        log.warning(
            "APIFY_API_TOKEN not set; skipping industry-days kick"
        )
        return {"started": False, "reason": "no_token"}

    run_input = {
        "startUrls": [{"url": u} for u in INDUSTRY_DAY_SEED_URLS],
        "maxCrawlPages": 80,
        "maxCrawlDepth": 2,
        "saveHtml": False,
        "saveMarkdown": True,
        "removeElementsCssSelector": "nav, footer, .ads, .menu",
    }

    async with ApifyClient(api_token) as client:
        try:
            run = await client.run_actor_sync(
                WEBSITE_CONTENT_CRAWLER_ACTOR,
                run_input,
                wait_for_finish_secs=INDUSTRY_DAYS_RUN_TIMEOUT_SECS,
            )
        except ApifyError as exc:
            log.warning("apify kick industry-days failed: %s", exc)
            return {"started": False, "error": str(exc)[:300]}

    log.info(
        "industry-days kick: apify run %s status=%s on %d seed urls",
        run.id,
        run.status,
        len(INDUSTRY_DAY_SEED_URLS),
    )

    if run.status != "SUCCEEDED":
        # The run is still in flight (timeout) or it failed. We don't
        # ingest a partial dataset; tomorrow's beat will try again.
        return {
            "started": True,
            "apify_run_id": run.id,
            "status": run.status,
            "ingested": False,
            "reason": "run_not_succeeded",
        }
    if not run.default_dataset_id:
        return {
            "started": True,
            "apify_run_id": run.id,
            "status": run.status,
            "ingested": False,
            "reason": "no_dataset_id",
        }

    # Persist a synthetic apify_runs audit row + dispatch ingest. The
    # webhook receiver writes the same row shape on RUN.SUCCEEDED — we
    # mirror that here so dashboards and `processed_at` queries don't
    # need to special-case the no-webhook path.
    audit_id = await _record_synthetic_audit(
        capability="industry_days",
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
        "events_upserted": stats.events_upserted,
        "items_seen": stats.items_seen,
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


@celery_app.task(name="mactech.apify.ingest_industry_days")
def ingest_industry_days_task(
    audit_id: str, dataset_id: str, apify_run_id: str
) -> dict[str, Any]:
    return asdict(
        asyncio.run(_ingest(audit_id, dataset_id, apify_run_id))
    )


async def _ingest(
    audit_id: str, dataset_id: str, apify_run_id: str
) -> IndustryDayIngestStats:
    api_token = os.environ.get("APIFY_API_TOKEN", "")
    anthropic_key = os.environ.get("ANTHROPIC_API_KEY", "")

    if not api_token:
        return IndustryDayIngestStats(
            audit_id=audit_id,
            apify_run_id=apify_run_id,
            items_seen=0,
            events_upserted=0,
            extraction_failures=0,
            error="APIFY_API_TOKEN not configured",
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
                "apify dataset_items failed for run=%s: %s",
                apify_run_id,
                exc,
            )
            await _mark_audit_processed(audit_id, error=str(exc)[:1000])
            return IndustryDayIngestStats(
                audit_id=audit_id,
                apify_run_id=apify_run_id,
                items_seen=0,
                events_upserted=0,
                extraction_failures=0,
                error=str(exc),
            )

    if not anthropic_key:
        log.warning(
            "ANTHROPIC_API_KEY not set; skipping LLM extraction "
            "for run=%s (saw %d crawl items)",
            apify_run_id,
            len(items),
        )
        await _mark_audit_processed(
            audit_id, error="ANTHROPIC_API_KEY not configured"
        )
        return IndustryDayIngestStats(
            audit_id=audit_id,
            apify_run_id=apify_run_id,
            items_seen=len(items),
            events_upserted=0,
            extraction_failures=0,
            error="no_anthropic_key",
        )

    llm = AnthropicLLMClient(api_key=anthropic_key)

    upserted = 0
    failures = 0
    async with unscoped_session() as session:
        for item in items:
            url = str(item.get("url") or "").strip()
            text = str(item.get("text") or item.get("markdown") or "").strip()
            if not url or len(text) < 200:
                continue
            try:
                events = await _extract_events(llm, url, text)
            except Exception as exc:  # noqa: BLE001
                failures += 1
                log.info(
                    "industry-days extract failed for %s: %s",
                    url,
                    exc,
                )
                continue
            for ev in events:
                title = (ev.get("title") or "").strip()
                if not title or len(title) > 1000:
                    continue
                stmt = (
                    pg_insert(AgencyEvent)
                    .values(
                        source_url=url[:2000],
                        source_host=_host_of(url),
                        agency=_str_or_none(ev.get("agency")),
                        title=title,
                        kind=_str_or_none(ev.get("kind")),
                        starts_at=_parse_dt(ev.get("starts_at")),
                        ends_at=_parse_dt(ev.get("ends_at")),
                        location=_str_or_none(ev.get("location")),
                        registration_url=_str_or_none(
                            ev.get("registration_url")
                        ),
                        naics_codes=ev.get("naics_codes") or None,
                        summary=_str_or_none(ev.get("summary")),
                        apify_run_id=apify_run_id,
                        raw=ev,
                    )
                    .on_conflict_do_update(
                        index_elements=["source_url", "title"],
                        set_={
                            "agency": _str_or_none(ev.get("agency")),
                            "kind": _str_or_none(ev.get("kind")),
                            "starts_at": _parse_dt(ev.get("starts_at")),
                            "ends_at": _parse_dt(ev.get("ends_at")),
                            "location": _str_or_none(ev.get("location")),
                            "registration_url": _str_or_none(
                                ev.get("registration_url")
                            ),
                            "naics_codes": ev.get("naics_codes") or None,
                            "summary": _str_or_none(ev.get("summary")),
                            "last_seen_at": datetime.now(UTC),
                            "apify_run_id": apify_run_id,
                            "raw": ev,
                        },
                    )
                )
                await session.execute(stmt)
                upserted += 1

    await _mark_audit_processed(audit_id)

    log.info(
        "industry-days ingest: run=%s items=%d upserted=%d failures=%d",
        apify_run_id,
        len(items),
        upserted,
        failures,
    )
    return IndustryDayIngestStats(
        audit_id=audit_id,
        apify_run_id=apify_run_id,
        items_seen=len(items),
        events_upserted=upserted,
        extraction_failures=failures,
        error=None,
    )


async def _extract_events(
    llm: AnthropicLLMClient, url: str, text: str
) -> list[dict[str, Any]]:
    """Extract structured events from one crawled page. Returns [] when
    the page has none. We cap text at ~12k chars — the model's job is
    to find dates and titles, not to read a novel."""
    excerpt = text[:12_000]
    user_prompt = (
        f"Source URL: {url}\n\nPage text:\n\n{excerpt}\n\n"
        "Return the JSON object now."
    )
    resp = await llm.complete(
        system=EXTRACTOR_SYSTEM,
        user=user_prompt,
        complexity="haiku",
        max_tokens=2000,
    )
    text_out = (resp.text or "").strip()
    if text_out.startswith("```"):
        # Strip markdown fences if the model wraps despite instructions.
        text_out = text_out.strip("`")
        if text_out.lower().startswith("json"):
            text_out = text_out[4:].strip()
    try:
        parsed = json.loads(text_out)
    except json.JSONDecodeError as exc:
        raise ValueError(f"non-JSON extractor output: {exc}") from exc
    events = parsed.get("events") if isinstance(parsed, dict) else None
    if not isinstance(events, list):
        return []
    return [e for e in events if isinstance(e, dict)]


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


def _parse_dt(v: Any) -> datetime | None:
    """Accept ISO 8601 with or without time. Apify webhook + Claude
    output is unpredictable; we never raise."""
    if v is None:
        return None
    s = str(v).strip()
    if not s:
        return None
    try:
        if "T" in s:
            return datetime.fromisoformat(s.replace("Z", "+00:00"))
        # date-only: noon UTC so naive comparisons don't TZ-shift.
        d = date.fromisoformat(s[:10])
        return datetime.combine(d, datetime.min.time(), tzinfo=UTC)
    except ValueError:
        return None
