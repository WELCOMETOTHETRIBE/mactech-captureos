"""DSIP per-topic lookup via Apify Playwright scraper — FALLBACK ONLY.

The primary enrichment path is now `dsip_ingest.enrich_dsip_topic`, which
hits DSIP's public JSON API directly (no browser, no Apify, no LLM). DSIP
does not actually firewall server-side calls — the earlier assumption that
it did is why this Playwright path existed. It is kept only as a fallback
for the rare case the direct API path fails (schema change, egress block).

When invoked, it uses `apify/playwright-scraper`'s `pageFunction` to drive
Playwright server-side: navigate to the SPA, fill the search filter with
the topic_number, expand the matching row, capture rendered text + the
topic PDF link. Claude Haiku then extracts structured fields from the
rendered text and we best-effort fetch the PDF for decoding.

Cost: ~$0.01/topic (Apify Playwright actor minute). Only reached when the
direct path fails, so in practice this rarely runs.
"""

from __future__ import annotations

import asyncio
import contextlib
import json
import logging
import os
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from typing import Any

import httpx
from mactech_db import unscoped_session
from mactech_db.models import ApifyRun, SBIRTopic
from mactech_integrations.apify import ApifyClient, ApifyError
from mactech_intelligence import AnthropicLLMClient
from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert

from mactech_workers.celery_app import celery_app

log = logging.getLogger(__name__)


PLAYWRIGHT_SCRAPER_ACTOR = "apify/playwright-scraper"
DSIP_URL = "https://www.dodsbirsttr.mil/topics-app/"

# A single per-topic render is fast (10-30s) but Playwright cold-start
# adds overhead. Give the actor 90s.
DSIP_RUN_TIMEOUT_SECS = 90

# The pageFunction runs INSIDE the headless browser session. It receives
# `context.request.userData.topicNumber` from the actor input. Returns
# `{topic_number, rendered_text, pdf_url, raw_html_excerpt, error}`.
#
# Selector strategy: DSIP's SPA uses Angular Material; the search field
# is the first <input> with placeholder containing "search", and topic
# rows are <tr> elements containing the topic_number text. PDF links are
# any <a> whose href contains "/details/pdf".
_PAGE_FUNCTION = r"""
async function pageFunction(context) {
    const { page, request, log } = context;
    const topicNumber = request.userData.topicNumber;
    if (!topicNumber) {
        return { error: 'topic_number missing from request userData' };
    }
    log.info(`DSIP lookup for ${topicNumber}`);

    try {
        await page.waitForLoadState('networkidle', { timeout: 30000 });
    } catch (e) {
        log.info('networkidle wait timed out, proceeding');
    }

    // Find the search box — DSIP labels it 'Filter By'. Try common selectors.
    const searchSelectors = [
        'input[placeholder*="Filter" i]',
        'input[placeholder*="Search" i]',
        'input[aria-label*="Search" i]',
        'input[type="search"]',
        'mat-form-field input',
    ];
    let searchInput = null;
    for (const sel of searchSelectors) {
        const found = await page.$(sel);
        if (found) { searchInput = found; break; }
    }
    if (!searchInput) {
        const html = await page.content();
        return {
            topic_number: topicNumber,
            error: 'search input not found on DSIP page',
            raw_html_excerpt: html.slice(0, 2000),
        };
    }

    await searchInput.click();
    await searchInput.fill(topicNumber);
    // DSIP filters client-side as you type. Wait for the table to settle.
    await page.waitForTimeout(2500);

    // Expand any caret/chevron in the matching row so the details panel renders.
    const rowSelectors = [
        `tr:has-text("${topicNumber}") button`,
        `tr:has-text("${topicNumber}") mat-icon`,
        `tr:has-text("${topicNumber}") svg`,
    ];
    for (const sel of rowSelectors) {
        const expand = await page.$(sel);
        if (expand) {
            try {
                await expand.click({ timeout: 3000 });
                break;
            } catch (e) {
                log.info(`row expand click failed for ${sel}`);
            }
        }
    }
    await page.waitForTimeout(2000);

    // Capture the rendered text — innerText collapses whitespace and gives
    // us what a human sees, which is what Claude extracts best from.
    const rendered_text = await page.evaluate(() => document.body.innerText);

    // Find a PDF link in the details panel. DSIP uses
    // /topics/api/public/topics/{id}/details/pdf for the official download.
    let pdf_url = null;
    const pdfLinks = await page.$$eval('a[href]', as =>
        as.map(a => a.href).filter(h => /\.pdf|details\/pdf/i.test(h))
    );
    if (pdfLinks.length > 0) pdf_url = pdfLinks[0];

    return {
        topic_number: topicNumber,
        rendered_text: rendered_text.slice(0, 60000),
        pdf_url,
    };
}
"""


EXTRACTOR_PROMPT_VERSION = "dsip-topic-v1"
EXTRACTOR_SYSTEM = """You extract structured DoD SBIR/STTR topic detail from
DSIP-rendered page text. The page is the dodsbirsttr.mil topic detail panel.

Return STRICT JSON: an object with these keys (use null when absent):

  {
    "topic_number":          string,
    "title":                 string | null,
    "component":             "Army" | "Navy" | "Air Force" | "DLA" | "DARPA"
                             | "SOCOM" | "Space Force" | "MDA" | "DHA" | "OSD"
                             | "Other" | null,
    "program":               "SBIR" | "STTR" | null,
    "phase":                 "I" | "II" | "DP2" | "III" | null,
    "status":                "open" | "prerelease" | "closed" | null,
    "open_date":             ISO 8601 date or null,
    "close_date":            ISO 8601 date or null,
    "description":           string — concatenated objective + description +
                             phase-by-phase scope. Preserve verbatim wording.
                             Up to ~4000 characters. Null if absent.
    "technology_areas":      array of strings or [],
    "modernization_priorities": array of strings or [],
    "keywords":              array of strings or [],
    "itar_export_status":    "yes" | "may be" | "no" | null,
    "phase_i_ceiling":       integer dollars or null,
    "phase_i_duration_months": integer or null,
    "tpoc":                  string | null — Technical Point of Contact name
                             or email or both (e.g. "Army xTech Mailbox" or
                             "Jane Doe, jane.doe@example.mil")
  }

Rules:
  - Never invent values. Set null when genuinely absent.
  - Output ONLY the JSON object. No prose, no markdown fences.
"""


@dataclass
class DSIPLookupResult:
    topic_number: str
    apify_run_id: str | None
    success: bool
    error: str | None
    pdf_url: str | None
    pdf_text: str | None
    extracted: dict[str, Any] | None
    rendered_text_len: int


@celery_app.task(name="mactech.apify.dsip_lookup")
def dsip_lookup_task(topic_number: str) -> dict[str, Any]:
    return asdict(asyncio.run(run_dsip_lookup(topic_number)))


async def run_dsip_lookup(topic_number: str) -> DSIPLookupResult:
    """End-to-end: Apify Playwright render → Haiku extract → DB upsert.

    Returns a populated `DSIPLookupResult` either way; failures land in
    `error` and the caller can decide what to do (typically: proceed with
    the topic's existing metadata and show a notice).
    """
    api_token = os.environ.get("APIFY_API_TOKEN", "")
    if not api_token:
        return DSIPLookupResult(
            topic_number=topic_number,
            apify_run_id=None,
            success=False,
            error="APIFY_API_TOKEN not configured",
            pdf_url=None,
            pdf_text=None,
            extracted=None,
            rendered_text_len=0,
        )

    run_input = {
        "startUrls": [
            {"url": DSIP_URL, "userData": {"topicNumber": topic_number}}
        ],
        "pageFunction": _PAGE_FUNCTION,
        "headless": True,
        "useChrome": True,
        "ignoreSslErrors": False,
        # Don't follow links — we only need the start URL rendered with our
        # custom interaction.
        "linkSelector": "",
        "maxRequestsPerCrawl": 1,
        # Give Playwright cold-start enough headroom.
        "pageLoadTimeoutSecs": 60,
    }

    items: list[dict[str, Any]] = []
    apify_run_id: str | None = None
    async with ApifyClient(api_token) as client:
        try:
            run = await client.run_actor_sync(
                PLAYWRIGHT_SCRAPER_ACTOR,
                run_input,
                wait_for_finish_secs=DSIP_RUN_TIMEOUT_SECS,
                memory_mbytes=2048,
            )
            apify_run_id = run.id
        except ApifyError as exc:
            log.warning("dsip apify kick failed for %s: %s", topic_number, exc)
            return DSIPLookupResult(
                topic_number=topic_number,
                apify_run_id=None,
                success=False,
                error=f"apify kick: {exc}"[:300],
                pdf_url=None,
                pdf_text=None,
                extracted=None,
                rendered_text_len=0,
            )

        if run.status != "SUCCEEDED" or not run.default_dataset_id:
            return DSIPLookupResult(
                topic_number=topic_number,
                apify_run_id=run.id,
                success=False,
                error=f"apify run did not succeed (status={run.status})",
                pdf_url=None,
                pdf_text=None,
                extracted=None,
                rendered_text_len=0,
            )

        await _record_apify_audit(
            apify_run_id=run.id,
            actor_id=run.actor_id,
            status=run.status,
            dataset_id=run.default_dataset_id,
        )

        try:
            page = await client.dataset_items(
                run.default_dataset_id, limit=10, clean=True
            )
            items = [p.payload for p in page]
        except ApifyError as exc:
            return DSIPLookupResult(
                topic_number=topic_number,
                apify_run_id=run.id,
                success=False,
                error=f"apify dataset: {exc}"[:300],
                pdf_url=None,
                pdf_text=None,
                extracted=None,
                rendered_text_len=0,
            )

    if not items:
        return DSIPLookupResult(
            topic_number=topic_number,
            apify_run_id=apify_run_id,
            success=False,
            error="empty Apify dataset (pageFunction produced no result)",
            pdf_url=None,
            pdf_text=None,
            extracted=None,
            rendered_text_len=0,
        )

    item = items[0]
    if "error" in item and item.get("error"):
        return DSIPLookupResult(
            topic_number=topic_number,
            apify_run_id=apify_run_id,
            success=False,
            error=f"pageFunction error: {item['error']}"[:300],
            pdf_url=None,
            pdf_text=None,
            extracted=None,
            rendered_text_len=0,
        )

    rendered = str(item.get("rendered_text") or "")
    pdf_url = item.get("pdf_url")
    pdf_text: str | None = None

    # Best-effort PDF download. DSIP serves PDFs from the same WAF-gated
    # domain; if it blocks our direct httpx fetch, we degrade silently.
    if pdf_url:
        pdf_text = await _try_fetch_pdf_text(pdf_url)

    # Haiku extract structured fields from the rendered text + (if obtained)
    # PDF text. PDF text is preferred when present because it's the canonical
    # source. Rendered text is the fallback.
    anthropic_key = os.environ.get("ANTHROPIC_API_KEY", "")
    extracted: dict[str, Any] | None = None
    if anthropic_key and (rendered or pdf_text):
        try:
            extracted = await _extract_topic(
                AnthropicLLMClient(api_key=anthropic_key),
                topic_number=topic_number,
                rendered_text=rendered,
                pdf_text=pdf_text,
            )
        except Exception as exc:
            log.warning("dsip extract failed for %s: %s", topic_number, exc)

    await _persist_enrichment(
        topic_number=topic_number,
        extracted=extracted,
        pdf_url=pdf_url,
        pdf_text=pdf_text,
        apify_run_id=apify_run_id,
    )

    return DSIPLookupResult(
        topic_number=topic_number,
        apify_run_id=apify_run_id,
        success=True,
        error=None,
        pdf_url=pdf_url,
        pdf_text=pdf_text[:200] if pdf_text else None,
        extracted=extracted,
        rendered_text_len=len(rendered),
    )


async def _try_fetch_pdf_text(pdf_url: str) -> str | None:
    """Try to download + decode the PDF directly. If the WAF blocks us,
    return None and let the caller carry on with rendered-text only."""
    try:
        import fitz  # type: ignore[import-untyped]
    except ImportError:
        log.warning("pymupdf not available; skipping PDF decode")
        return None
    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 14_6_0) "
            "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130 Safari/537.36"
        ),
        "Accept": "application/pdf,*/*",
        "Referer": "https://www.dodsbirsttr.mil/topics-app/",
    }
    try:
        async with httpx.AsyncClient(timeout=15.0, headers=headers) as c:
            res = await c.get(pdf_url, follow_redirects=True)
    except httpx.HTTPError as exc:
        log.info("dsip pdf fetch failed (%s): %s", pdf_url, exc)
        return None
    if res.status_code != 200 or len(res.content) < 1000:
        log.info(
            "dsip pdf fetch returned status=%s len=%d, skipping decode",
            res.status_code,
            len(res.content),
        )
        return None
    try:
        with fitz.open(stream=res.content, filetype="pdf") as doc:
            text = "\n".join(page.get_text() for page in doc)
    except Exception as exc:
        log.info("dsip pdf decode failed: %s", exc)
        return None
    return text.strip()[:80_000] or None


async def _extract_topic(
    llm: AnthropicLLMClient,
    *,
    topic_number: str,
    rendered_text: str,
    pdf_text: str | None,
) -> dict[str, Any] | None:
    excerpt_parts: list[str] = [f"Topic number being looked up: {topic_number}"]
    if pdf_text:
        excerpt_parts.append("--- OFFICIAL PDF (preferred source) ---")
        excerpt_parts.append(pdf_text[:30_000])
    if rendered_text:
        excerpt_parts.append("--- RENDERED DSIP PAGE TEXT ---")
        excerpt_parts.append(rendered_text[:20_000])
    user_prompt = "\n\n".join(excerpt_parts) + "\n\nReturn the JSON object now."

    resp = await llm.complete(
        system=EXTRACTOR_SYSTEM,
        user=user_prompt,
        complexity="fast",
        max_tokens=4000,
    )
    raw = (resp.text or "").strip()
    if raw.startswith("```"):
        raw = raw.strip("`")
        if raw.lower().startswith("json"):
            raw = raw[4:].strip()
    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError as exc:
        log.info("dsip extractor non-JSON output: %s", exc)
        return None
    if not isinstance(parsed, dict):
        return None
    return parsed


async def _record_apify_audit(
    *,
    apify_run_id: str,
    actor_id: str,
    status: str | None,
    dataset_id: str | None,
) -> None:
    async with unscoped_session() as session:
        stmt = (
            pg_insert(ApifyRun)
            .values(
                apify_run_id=apify_run_id,
                apify_actor_id=actor_id,
                capability="sbir_dsip_lookup",
                event_type="WORKER.RUN.SUCCEEDED",
                apify_status=status,
                dataset_id=dataset_id,
                items_count=1,
                payload={"source": "worker_inline"},
            )
            .on_conflict_do_update(
                index_elements=["apify_run_id", "event_type"],
                set_={
                    "apify_status": status,
                    "dataset_id": dataset_id,
                },
            )
        )
        await session.execute(stmt)


async def _persist_enrichment(
    *,
    topic_number: str,
    extracted: dict[str, Any] | None,
    pdf_url: str | None,
    pdf_text: str | None,
    apify_run_id: str | None,
) -> None:
    """Update every row that matches this topic_number across sources.

    Enriching by topic_number (rather than a single row id) keeps any rows
    that share the number — e.g. a direct-DSIP row and an Apify-crawled row
    — in sync so the submitter sees the same data regardless of which row's
    id was passed.
    """
    async with unscoped_session() as session:
        rows = (
            await session.execute(
                select(SBIRTopic).where(SBIRTopic.topic_number == topic_number)
            )
        ).scalars().all()

        if not rows:
            log.info(
                "dsip enrichment for %s — no matching row, skipping persist",
                topic_number,
            )
            return

        now = datetime.now(UTC)
        for row in rows:
            row.dsip_enriched_at = now
            row.dsip_apify_run_id = apify_run_id
            if pdf_url:
                row.dsip_pdf_url = pdf_url
            if pdf_text:
                row.dsip_pdf_text = pdf_text
            if extracted:
                # Only overwrite fields when the extractor produced a value,
                # so an empty extraction never wipes existing content.
                if extracted.get("description"):
                    row.description = extracted["description"]
                if extracted.get("title"):
                    row.title = extracted["title"]
                if extracted.get("component"):
                    row.component = extracted["component"]
                if extracted.get("program"):
                    row.program = extracted["program"]
                if extracted.get("phase"):
                    row.phase = extracted["phase"]
                tech = extracted.get("technology_areas")
                if isinstance(tech, list) and tech:
                    row.technology_areas = tech
                mods = extracted.get("modernization_priorities")
                if isinstance(mods, list) and mods:
                    row.modernization_priorities = mods
                kws = extracted.get("keywords")
                if isinstance(kws, list) and kws:
                    row.keywords = kws
                if extracted.get("itar_export_status"):
                    row.itar_export_status = extracted["itar_export_status"]
                if extracted.get("phase_i_ceiling") is not None:
                    with contextlib.suppress(TypeError, ValueError):
                        row.phase_i_ceiling = int(extracted["phase_i_ceiling"])
                if extracted.get("phase_i_duration_months") is not None:
                    with contextlib.suppress(TypeError, ValueError):
                        row.phase_i_duration_months = int(
                            extracted["phase_i_duration_months"]
                        )
                if extracted.get("tpoc"):
                    row.dsip_tpoc = str(extracted["tpoc"])[:512]
