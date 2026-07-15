"""SBIR topic discovery via Apify website-content-crawler.

Pulls open DoD SBIR/STTR topics by rendering a curated list of topic-
landing pages with `apify/website-content-crawler` (playwright:adaptive)
and running Claude Haiku over the rendered markdown to extract structured
topic metadata into `sbir_topics`.

DSIP (dodsbirsttr.mil) is now pulled directly via its public JSON API by
the `dsip_ingest` worker — that is the primary DoD SBIR/STTR source. This
Apify crawl is a secondary net for the non-DSIP landing pages (sbir.gov,
AFWERX, DLA, Navy, Army, DARPA, SOFWERX) that don't expose a clean API.

Mirrors `apify_industry_days.py` so the operator surface is identical:
no webhook config required, just APIFY_API_TOKEN + an on-demand kick
(plus a daily Celery beat we'll add when the topic feed stabilizes).
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

from mactech_db import unscoped_session
from mactech_db.models import ApifyRun, SBIRTopic
from mactech_integrations.apify import ApifyClient, ApifyError
from mactech_intelligence import AnthropicLLMClient
from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert

from mactech_workers.celery_app import celery_app

log = logging.getLogger(__name__)


WEBSITE_CONTENT_CRAWLER_ACTOR = "apify/website-content-crawler"

# DSIP renders 50+ topics per page; the crawler has to load JS so allow
# a longer window than the industry-days beat. Apify caps waitForFinish
# at 600s; we use 540s.
SBIR_TOPICS_RUN_TIMEOUT_SECS = 540

# Curated SBIR topic discovery surface. Mix of DSIP (the canonical DoD
# source) and component-specific landing pages that show what topics are
# open. The crawler walks depth=2 from each so it follows into individual
# topic detail pages.
SBIR_TOPIC_SEED_URLS = [
    # DSIP — canonical, but JS-heavy. playwright:adaptive renders it.
    # (The primary DSIP feed is now the direct-API dsip_ingest worker; this
    # Apify crawl remains as a secondary net for the other landing pages.)
    "https://www.dodsbirsttr.mil/topics-app/",
    # SBIR.gov topic + solicitation lists.
    "https://www.sbir.gov/topics",
    "https://www.sbir.gov/solicitations",
    # AFWERX SBIR/STTR landing.
    "https://afwerx.com/divisions/afventures/sbir-sttr/",
    # DLA small-business / SBIR outreach.
    "https://www.dla.mil/Small-Business/Programs/SBIR-STTR/",
    # Navy / NavalX SBIR.
    "https://www.navalx.navy.mil/sbir",
    # Army SBIR.
    "https://www.armysbir.army.mil/",
    # DARPA small business SBIR portal.
    "https://www.darpa.mil/work-with-us/for-small-businesses",
    # SOCOM SOFWERX SBIR.
    "https://www.sofwerx.org/work-with-us/sbir-sttr/",
]


EXTRACTOR_PROMPT_VERSION = "sbir-topics-v1"
EXTRACTOR_SYSTEM = """You extract DoD SBIR/STTR topic metadata from a web page.

Return STRICT JSON: an object with one key, "topics", which is an array.
For each distinct topic on the page, emit one object:

  {
    "topic_number":   string — canonical topic id. Accept all DoD SBIR/STTR
                      naming conventions, including the newer
                      department-prefixed style: e.g. "DAF26BX03-DV505",
                      "DAF26BZ03-DV019" (Department of Air Force),
                      "DON26BX03-NP002", "DON26BZ03-NV054" (Department of
                      Navy), "DPA26BZ03-DV011" (DARPA), "ARM26BX01-NP003"
                      (Army), "DHA26BZ03-NV006" (Defense Health Agency),
                      "DLA26BZ03-NV011" (DLA); and the older style:
                      "DLA26BZ02-NV007", "AF254-D001", "N252-001",
                      "ARMY26-001", "SOCOM254-001", "DARPA254-001"
    "title":          string — the topic title
    "component":      "Army" | "Navy" | "Air Force" | "DLA" | "DARPA"
                      | "SOCOM" | "Space Force" | "MDA" | "DHA" | "OSD"
                      | "Other" | null
                      — map prefixes: DAF→"Air Force", DON→"Navy",
                      DPA→"DARPA", ARM→"Army", DHA→"DHA", DLA→"DLA"
    "program":        "SBIR" | "STTR" | null
    "phase":          "I" | "II" | "DP2" | "III" | null
    "status":         "prerelease" | "open" | "closed" | null
                      — "open" if the page says the topic is currently
                      accepting proposals; "prerelease" if dates show
                      pre-release window; "closed" if past close date
    "prerelease_date": ISO 8601 date or null
    "open_date":      ISO 8601 date or null
    "close_date":     ISO 8601 date or null
    "description":    string — 1-3 sentence plain-English summary
                      capturing what DoD wants built; null if absent
    "url":            string | null — direct link to the topic page if
                      this listing carries one
    "technology_areas": array of strings (e.g. ["Cybersecurity",
                      "Autonomy"]) or []
    "modernization_priorities": array of strings (e.g. ["Cybersecurity",
                      "AI/ML"]) or []
    "keywords":       array of strings (DSIP's keyword list, max 8) or []
    "itar_export_status": "yes" | "may be" | "no" | null
    "phase_i_ceiling": integer dollars (e.g. 100000) or null
    "phase_i_duration_months": integer (e.g. 6, 12) or null
  }

Counts as a topic when:
  - The page lists a topic identifier matching a DoD SBIR/STTR pattern
    (component code + year + sequence: e.g. DLA26BZ02-NV007, AF254-D001,
    N252-001, ARMY26-001, SOCOM254-001, DARPA254-001), AND
  - The page carries at least a title or a brief description tied to
    that identifier.

Do NOT emit:
  - Generic SBIR program overviews ("about the SBIR program")
  - Past awarded topics labeled as awards (only open/prerelease/recent
    closed topics)
  - Duplicates of the same topic (same topic_number)
  - News articles or press releases that merely mention a topic

Rules:
  - Never invent topic numbers, titles, or dates.
  - If a field is genuinely absent, set it to null (or [] for the array
    fields). Do not guess.
  - Output ONLY the JSON object. No prose, no markdown fences, no commentary.
"""


@dataclass
class SBIRTopicsIngestStats:
    audit_id: str | None
    apify_run_id: str | None
    items_seen: int
    topics_upserted: int
    extraction_failures: int
    error: str | None


@celery_app.task(name="mactech.apify.kick_sbir_topics_run")
def kick_sbir_topics_run_task() -> dict[str, Any]:
    """On-demand or scheduled kick — start a render+crawl over the SBIR
    topic landing pages, wait for completion (server-side blocking via
    Apify's waitForFinish), then dispatch the ingest task."""
    return asyncio.run(_kick_and_ingest())


async def _kick_and_ingest() -> dict[str, Any]:
    api_token = os.environ.get("APIFY_API_TOKEN", "")
    if not api_token:
        log.warning("APIFY_API_TOKEN not set; skipping sbir-topics kick")
        await _record_skipped_run(
            capability="sbir_topics",
            actor_id=WEBSITE_CONTENT_CRAWLER_ACTOR,
            reason="APIFY_API_TOKEN not set on the workers service",
        )
        return {"started": False, "reason": "no_token"}

    run_input = {
        "startUrls": [{"url": u} for u in SBIR_TOPIC_SEED_URLS],
        # DSIP is a JS-rendered SPA, sbir.gov is mostly static.
        # Adaptive mode picks the right tool per page.
        "crawlerType": "playwright:adaptive",
        "maxCrawlDepth": 2,
        "maxCrawlPages": 200,
        "saveHtml": False,
        "saveMarkdown": True,
        "removeElementsCssSelector": (
            "nav, footer, header, .ads, .menu, .skip-link, .breadcrumbs, "
            "form, aside, .sidebar"
        ),
        "keepUrlFragments": False,
    }
    run_options = {"memoryMbytes": 4096}

    async with ApifyClient(api_token) as client:
        try:
            run = await client.run_actor_sync(
                WEBSITE_CONTENT_CRAWLER_ACTOR,
                run_input,
                wait_for_finish_secs=SBIR_TOPICS_RUN_TIMEOUT_SECS,
                memory_mbytes=run_options["memoryMbytes"],
            )
        except ApifyError as exc:
            log.warning("apify kick sbir-topics failed: %s", exc)
            return {"started": False, "error": str(exc)[:300]}

    log.info(
        "sbir-topics kick: apify run %s status=%s on %d seed urls",
        run.id,
        run.status,
        len(SBIR_TOPIC_SEED_URLS),
    )

    if run.status != "SUCCEEDED":
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

    audit_id = await _record_synthetic_audit(
        capability="sbir_topics",
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
        "topics_upserted": stats.topics_upserted,
        "items_seen": stats.items_seen,
        "extraction_failures": stats.extraction_failures,
    }


async def _record_skipped_run(
    *,
    capability: str,
    actor_id: str,
    reason: str,
) -> None:
    sentinel_run_id = f"worker-skipped-{capability}-{date.today().isoformat()}"
    async with unscoped_session() as session:
        stmt = (
            pg_insert(ApifyRun)
            .values(
                apify_run_id=sentinel_run_id,
                apify_actor_id=actor_id,
                capability=capability,
                event_type="WORKER.RUN.SKIPPED",
                apify_status="SKIPPED",
                dataset_id=None,
                items_count=0,
                ingest_error=reason[:1000],
                payload={"reason": reason, "source": "worker_inline"},
            )
            .on_conflict_do_update(
                index_elements=["apify_run_id", "event_type"],
                set_={
                    "ingest_error": reason[:1000],
                    "received_at": datetime.now(UTC),
                },
            )
        )
        await session.execute(stmt)


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


@celery_app.task(name="mactech.apify.ingest_sbir_topics")
def ingest_sbir_topics_task(
    audit_id: str, dataset_id: str, apify_run_id: str
) -> dict[str, Any]:
    return asdict(asyncio.run(_ingest(audit_id, dataset_id, apify_run_id)))


async def _ingest(
    audit_id: str, dataset_id: str, apify_run_id: str
) -> SBIRTopicsIngestStats:
    api_token = os.environ.get("APIFY_API_TOKEN", "")
    anthropic_key = os.environ.get("ANTHROPIC_API_KEY", "")

    if not api_token:
        return SBIRTopicsIngestStats(
            audit_id=audit_id,
            apify_run_id=apify_run_id,
            items_seen=0,
            topics_upserted=0,
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
                "apify dataset_items failed for run=%s: %s", apify_run_id, exc
            )
            await _mark_audit_processed(audit_id, error=str(exc)[:1000])
            return SBIRTopicsIngestStats(
                audit_id=audit_id,
                apify_run_id=apify_run_id,
                items_seen=0,
                topics_upserted=0,
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
        await _mark_audit_processed(audit_id, error="ANTHROPIC_API_KEY not configured")
        return SBIRTopicsIngestStats(
            audit_id=audit_id,
            apify_run_id=apify_run_id,
            items_seen=len(items),
            topics_upserted=0,
            extraction_failures=0,
            error="no_anthropic_key",
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
            if not _looks_like_topic_page(url, text):
                skipped_low_signal += 1
                continue
            try:
                topics = await _extract_topics(llm, url, text)
            except Exception as exc:
                failures += 1
                log.info("sbir-topics extract failed for %s: %s", url, exc)
                continue
            for t in topics:
                topic_number = (t.get("topic_number") or "").strip()
                if not topic_number or len(topic_number) > 64:
                    continue
                source = _source_for(url)
                values = {
                    "source": source,
                    "topic_number": topic_number,
                    "title": _str_or_none(t.get("title")),
                    "component": _str_or_none(t.get("component")),
                    "program": _str_or_none(t.get("program")),
                    "phase": _str_or_none(t.get("phase")),
                    "status": _normalize_status(t.get("status")),
                    "prerelease_date": _parse_dt(t.get("prerelease_date")),
                    "open_date": _parse_dt(t.get("open_date")),
                    "close_date": _parse_dt(t.get("close_date")),
                    "description": _str_or_none(t.get("description")),
                    "url": _str_or_none(t.get("url")) or url,
                    "technology_areas": _string_list(t.get("technology_areas")),
                    "modernization_priorities": _string_list(
                        t.get("modernization_priorities")
                    ),
                    "keywords": _string_list(t.get("keywords")),
                    "itar_export_status": _str_or_none(t.get("itar_export_status")),
                    "phase_i_ceiling": _int_or_none(t.get("phase_i_ceiling")),
                    "phase_i_duration_months": _int_or_none(
                        t.get("phase_i_duration_months")
                    ),
                    "raw": t,
                    "apify_run_id": apify_run_id,
                    "last_seen_at": datetime.now(UTC),
                }
                stmt = (
                    pg_insert(SBIRTopic)
                    .values(**values)
                    .on_conflict_do_update(
                        index_elements=["source", "topic_number"],
                        set_={
                            k: v
                            for k, v in values.items()
                            if k not in ("source", "topic_number")
                        },
                    )
                )
                await session.execute(stmt)
                upserted += 1

    await _mark_audit_processed(audit_id)

    log.info(
        "sbir-topics ingest: run=%s items=%d skipped=%d upserted=%d failures=%d",
        apify_run_id,
        len(items),
        skipped_low_signal,
        upserted,
        failures,
    )
    return SBIRTopicsIngestStats(
        audit_id=audit_id,
        apify_run_id=apify_run_id,
        items_seen=len(items),
        topics_upserted=upserted,
        extraction_failures=failures,
        error=None,
    )


async def _extract_topics(
    llm: AnthropicLLMClient, url: str, text: str
) -> list[dict[str, Any]]:
    excerpt = text[:16_000]
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
    topics = parsed.get("topics") if isinstance(parsed, dict) else None
    if not isinstance(topics, list):
        return []
    return [t for t in topics if isinstance(t, dict)]


async def _mark_audit_processed(
    audit_id: str, *, error: str | None = None
) -> None:
    async with unscoped_session() as session:
        row = (
            await session.execute(select(ApifyRun).where(ApifyRun.id == audit_id))
        ).scalar_one_or_none()
        if row is None:
            return
        row.processed_at = datetime.now(UTC)
        if error:
            row.ingest_error = error[:1000]


_TOPIC_URL_HINTS = (
    "topic", "sbir", "sttr", "solicitation", "afwerx", "navalx",
    "sofwerx", "darpa", "dla", "afventures", "armysbir",
)
_TOPIC_TEXT_HINTS = (
    "topic number", "sbir", "sttr", "solicitation", "phase i",
    "phase ii", "topic title", "open topics", "pre-release",
)


def _looks_like_topic_page(url: str, text: str) -> bool:
    u = url.lower()
    if any(h in u for h in _TOPIC_URL_HINTS):
        return True
    t = text.lower()
    return any(h in t for h in _TOPIC_TEXT_HINTS)


_DSIP_HOST = "dodsbirsttr.mil"
_SBIRGOV_HOST = "sbir.gov"


def _source_for(url: str) -> str:
    host = (_host_of(url) or "").lower()
    if _DSIP_HOST in host:
        return "dsip"
    if _SBIRGOV_HOST in host:
        return "sbir.gov"
    return host or "unknown"


def _normalize_status(v: Any) -> str:
    if v is None:
        return "unknown"
    s = str(v).strip().lower()
    if s in ("prerelease", "pre-release", "pre_release"):
        return "prerelease"
    if s == "open":
        return "open"
    if s == "closed":
        return "closed"
    return "unknown"


def _str_or_none(v: Any) -> str | None:
    if v is None:
        return None
    s = str(v).strip()
    return s or None


def _int_or_none(v: Any) -> int | None:
    if v is None:
        return None
    try:
        return int(float(str(v).replace(",", "").replace("$", "").strip()))
    except (TypeError, ValueError):
        return None


def _string_list(v: Any) -> list[str] | None:
    if not isinstance(v, list):
        return None
    out = [str(x).strip() for x in v if x is not None and str(x).strip()]
    return out or None


def _host_of(url: str) -> str | None:
    try:
        return urlparse(url).netloc or None
    except Exception:
        return None


def _parse_dt(v: Any) -> datetime | None:
    if v is None:
        return None
    s = str(v).strip()
    if not s:
        return None
    try:
        if "T" in s:
            return datetime.fromisoformat(s.replace("Z", "+00:00"))
        d = date.fromisoformat(s[:10])
        return datetime.combine(d, datetime.min.time(), tzinfo=UTC)
    except ValueError:
        return None
