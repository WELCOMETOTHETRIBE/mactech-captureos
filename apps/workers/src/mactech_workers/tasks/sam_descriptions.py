"""SAM.gov chained noticedesc fetch.

Per docs/SAM_GOV_API.md §4 chain 1: opportunities_raw.description from
the search endpoint is a URL pointing to /prod/opportunities/v1/noticedesc.
That URL returns {"description": "..."} (often "See attachment" when the
real SOW is a PDF, but sometimes substantive text).

This worker walks rows where description_url is set and description_text
is null, fetches the noticedesc endpoint with the SAM API key, and fills
description_text.

Beat cadence: every 30 minutes, batch of 50. Counts toward the 1k/day
SAM rate limit but at our ingest volume this stays comfortably under.
"""

from __future__ import annotations

import asyncio
import logging
import os
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from typing import Any

import httpx
from mactech_db import async_session_factory
from sqlalchemy import text
from tenacity import (
    AsyncRetrying,
    retry_if_exception_type,
    stop_after_attempt,
    wait_random_exponential,
)

from mactech_workers.celery_app import celery_app

log = logging.getLogger(__name__)

DEFAULT_BATCH_SIZE = 50
# SAM's noticedesc endpoint has a low burst limit; fire requests back-to-back
# and every one throttles at once. A per-request spacing keeps us under the
# limit. Overridable via env for tuning without a redeploy.
DEFAULT_THROTTLE_SECONDS = float(os.environ.get("SAM_DESC_THROTTLE_SECONDS", "0.8"))
# Longer, dedicated backoff when SAM explicitly says "rate limited" (429), so a
# throttle event doesn't just exhaust the retry budget in a few hundred ms.
_RATE_LIMIT_WAIT = wait_random_exponential(multiplier=2, max=60)


@dataclass
class DescStats:
    fetched: int
    skipped: int
    errors: int
    duration_ms: int


async def _fetch_noticedesc(client: httpx.AsyncClient, url: str, api_key: str) -> str | None:
    """Returns the description text if the endpoint returned valid JSON,
    None if the response was empty or parseable-but-empty. Raises on
    transport / 5xx errors after retries are exhausted."""
    sep = "&" if "?" in url else "?"
    full = f"{url}{sep}api_key={api_key}"

    async for attempt in AsyncRetrying(
        stop=stop_after_attempt(5),
        wait=_RATE_LIMIT_WAIT,
        retry=retry_if_exception_type(httpx.TransportError),
        reraise=True,
    ):
        with attempt:
            resp = await client.get(full)
            if resp.status_code == 404:
                return None
            if resp.status_code == 429:
                # Treat as transient; tenacity will retry.
                raise httpx.TransportError("rate limited")
            if 500 <= resp.status_code < 600:
                raise httpx.TransportError(f"server error {resp.status_code}")
            if resp.status_code >= 400:
                log.warning(
                    "noticedesc %s returned %d: %s",
                    url,
                    resp.status_code,
                    resp.text[:200],
                )
                return None
            try:
                payload = resp.json()
            except ValueError:
                # Some old notice descriptions return plain text without JSON.
                return resp.text.strip() or None
            if isinstance(payload, dict):
                desc = payload.get("description")
                if isinstance(desc, str):
                    return desc.strip() or None
            return None
    return None  # pragma: no cover


async def fetch_descriptions_batch(
    *,
    batch_size: int = DEFAULT_BATCH_SIZE,
    throttle_seconds: float = DEFAULT_THROTTLE_SECONDS,
    opportunity_ids: list[str] | None = None,
) -> DescStats:
    """Fill description_text for rows missing it.

    ``throttle_seconds`` spaces requests so SAM's low burst limit doesn't
    throttle the whole batch at once. ``opportunity_ids`` targets a specific set
    (e.g., only the actionable candidates) and re-fetches them even if a prior
    run stamped the empty-body sentinel.
    """
    started = datetime.now(UTC)
    api_key = os.environ.get("SAM_API_KEY", "")
    if not api_key:
        raise RuntimeError("SAM_API_KEY not set")

    session_factory = async_session_factory()
    fetched = 0
    skipped = 0
    errors = 0

    if opportunity_ids:
        query = text(
            """
            select id::text, description_url
            from opportunities_raw
            where description_url is not null
              and id = any(cast(:ids as uuid[]))
            order by posted_at desc nulls last
            limit :n
            """
        )
        params: dict[str, Any] = {"ids": opportunity_ids, "n": batch_size}
    else:
        query = text(
            """
            select id::text, description_url
            from opportunities_raw
            where description_url is not null
              and description_text is null
            order by posted_at desc nulls last
            limit :n
            """
        )
        params = {"n": batch_size}

    async with (
        httpx.AsyncClient(timeout=httpx.Timeout(30.0)) as client,
        session_factory() as session,
        session.begin(),
    ):
        rows = (await session.execute(query, params)).all()

        for i, (row_id, url) in enumerate(rows):
            if i > 0 and throttle_seconds > 0:
                await asyncio.sleep(throttle_seconds)
            try:
                body = await _fetch_noticedesc(client, url, api_key)
            except Exception as exc:
                log.warning("noticedesc fetch failed for %s: %s", row_id, exc)
                errors += 1
                continue
            if body is None or not body.strip():
                # Mark as fetched-but-empty so we don't keep retrying.
                # Use a sentinel that's unambiguously empty: a single
                # space. UI treats whitespace-only as "no body".
                await session.execute(
                    text(
                        "update opportunities_raw set description_text = ' '"
                        " where id = CAST(:id AS uuid)"
                    ),
                    {"id": row_id},
                )
                skipped += 1
                continue
            await session.execute(
                text(
                    "update opportunities_raw set description_text = :t"
                    " where id = CAST(:id AS uuid)"
                ),
                {"id": row_id, "t": body[:200000]},  # 200kb cap
            )
            fetched += 1

    duration_ms = int((datetime.now(UTC) - started).total_seconds() * 1000)
    return DescStats(fetched=fetched, skipped=skipped, errors=errors, duration_ms=duration_ms)


@celery_app.task(name="mactech.sam.fetch_descriptions")
def fetch_descriptions_task(batch_size: int = DEFAULT_BATCH_SIZE) -> dict[str, Any]:
    return asdict(asyncio.run(fetch_descriptions_batch(batch_size=batch_size)))
