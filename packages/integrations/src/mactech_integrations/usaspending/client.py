"""USASpending.gov API client (no auth, polite throttle).

Implementation rules per docs/USASPENDING_API.md:
  - No API key. Set User-Agent for traceability.
  - Throttle to 1 req/sec, exponential backoff with jitter on 429/5xx.
  - Date format ISO YYYY-MM-DD (not SAM's MM/dd/yyyy).
  - Pagination: page-based for first 10 pages, then cursor-based.
  - Idempotent upsert key on `generated_internal_id`, never `internal_id`.

Phase 1 Week 3 surfaces:
  - search_awards         POST /search/spending_by_award/
  - search_recipient      POST /recipient/
  - get_recipient_profile GET  /recipient/duns/<HASH>/

Subaward + IDV endpoints are designed in the doc but deferred until Phase
2 / 3 when those workflows actually fire.
"""

from __future__ import annotations

import asyncio
import logging
from datetime import date
from typing import Any, Final

import httpx
from tenacity import (
    AsyncRetrying,
    retry_if_exception_type,
    stop_after_attempt,
    wait_random_exponential,
)

from mactech_integrations.usaspending.models import (
    AwardSearchPage,
    RecipientProfile,
    RecipientSearchPage,
)

log = logging.getLogger(__name__)

DEFAULT_BASE_URL: Final = "https://api.usaspending.gov/api/v2"
DEFAULT_USER_AGENT: Final = "MacTechCaptureOS/0.1 (+https://www.mactechsolutionsllc.com)"
DEFAULT_TIMEOUT: Final = httpx.Timeout(60.0, connect=10.0)
# USASpending's /search/spending_by_award/ requires award_type_codes on every
# call — it determines the response shape (contracts vs grants vs loans). For
# MacTech (DoD-focused) the relevant codes are the four contract types.
DEFAULT_AWARD_TYPE_CODES: Final[tuple[str, ...]] = ("A", "B", "C", "D")
DEFAULT_FIELDS: Final[tuple[str, ...]] = (
    "Award ID",
    "Recipient Name",
    "Recipient UEI",
    "Award Amount",
    "Period of Performance Start Date",
    "Period of Performance Current End Date",
    "Description",
    "Awarding Agency",
    "Awarding Sub Agency",
    "Contract Award Type",
    "NAICS",
    "PSC",
)


class UsaSpendingError(Exception):
    pass


class UsaSpendingRateLimitError(UsaSpendingError):
    pass


class UsaSpendingClient:
    def __init__(
        self,
        *,
        base_url: str = DEFAULT_BASE_URL,
        user_agent: str = DEFAULT_USER_AGENT,
        timeout: httpx.Timeout = DEFAULT_TIMEOUT,
        http_client: httpx.AsyncClient | None = None,
        min_request_interval_seconds: float = 1.0,
    ) -> None:
        self._base_url = base_url.rstrip("/")
        self._owns_client = http_client is None
        self._http = http_client or httpx.AsyncClient(
            timeout=timeout, headers={"User-Agent": user_agent}
        )
        self._min_interval = min_request_interval_seconds
        self._lock = asyncio.Lock()
        self._last_request_at = 0.0

    async def __aenter__(self) -> UsaSpendingClient:
        return self

    async def __aexit__(self, *exc: object) -> None:
        if self._owns_client:
            await self._http.aclose()

    async def _throttled_post(self, path: str, json: dict[str, Any]) -> httpx.Response:
        return await self._throttled("POST", path, json=json)

    async def _throttled_get(self, path: str) -> httpx.Response:
        return await self._throttled("GET", path)

    async def _throttled(
        self, method: str, path: str, *, json: dict[str, Any] | None = None
    ) -> httpx.Response:
        url = f"{self._base_url}{path}"
        async for attempt in AsyncRetrying(
            stop=stop_after_attempt(5),
            wait=wait_random_exponential(multiplier=1, max=60),
            retry=retry_if_exception_type((httpx.TransportError, UsaSpendingRateLimitError)),
            reraise=True,
        ):
            with attempt:
                # Hold the lock just long enough to space requests; do not block
                # other coroutines through the entire HTTP round-trip.
                async with self._lock:
                    elapsed = asyncio.get_event_loop().time() - self._last_request_at
                    if elapsed < self._min_interval:
                        await asyncio.sleep(self._min_interval - elapsed)
                    self._last_request_at = asyncio.get_event_loop().time()
                resp = await self._http.request(method, url, json=json)
                if resp.status_code == 429:
                    log.warning("usaspending 429 — backing off")
                    raise UsaSpendingRateLimitError("rate limited")
                if 500 <= resp.status_code < 600:
                    log.warning("usaspending %s — retrying", resp.status_code)
                    raise UsaSpendingRateLimitError(f"server error {resp.status_code}")
                if resp.status_code >= 400:
                    raise UsaSpendingError(
                        f"usaspending error {resp.status_code}: {resp.text[:200]}"
                    )
                return resp
        raise UsaSpendingError("unreachable")  # pragma: no cover

    async def search_awards(
        self,
        *,
        naics_codes: list[str] | None = None,
        awarding_agency_name: str | None = None,
        time_period_start: date | None = None,
        time_period_end: date | None = None,
        award_type_codes: list[str] | None = None,
        award_amount_min: int | None = None,
        recipient_uei: str | None = None,
        fields: list[str] | None = None,
        sort: str = "Award Amount",  # valid USASpending sort key (PoP date is response-only)
        order: str = "desc",
        limit: int = 25,
        page: int = 1,
    ) -> AwardSearchPage:
        body: dict[str, Any] = {
            "filters": {},
            "fields": list(fields or DEFAULT_FIELDS),
            "limit": limit,
            "page": page,
            "sort": sort,
            "order": order,
        }
        f = body["filters"]
        if naics_codes:
            f["naics_codes"] = list(naics_codes)
        if awarding_agency_name:
            f["agencies"] = [{"type": "awarding", "tier": "toptier", "name": awarding_agency_name}]
        if time_period_start and time_period_end:
            f["time_period"] = [
                {
                    "start_date": time_period_start.isoformat(),
                    "end_date": time_period_end.isoformat(),
                }
            ]
        f["award_type_codes"] = list(award_type_codes or DEFAULT_AWARD_TYPE_CODES)
        if award_amount_min is not None:
            f["award_amounts"] = [{"lower_bound": award_amount_min}]
        if recipient_uei:
            f["recipient_search_text"] = [recipient_uei]

        resp = await self._throttled_post("/search/spending_by_award/", json=body)
        return AwardSearchPage.model_validate(resp.json())

    async def search_recipient(
        self,
        *,
        keyword: str,
        order: str = "desc",
        sort: str = "amount",
        limit: int = 5,
        page: int = 1,
    ) -> RecipientSearchPage:
        body = {
            "keyword": keyword,
            "order": order,
            "sort": sort,
            "limit": limit,
            "page": page,
        }
        resp = await self._throttled_post("/recipient/", json=body)
        return RecipientSearchPage.model_validate(resp.json())

    async def get_recipient_profile(self, recipient_hash: str) -> RecipientProfile:
        """Pass the <uuid>-<level> hash from search_recipient.id, NOT the SAM UEI."""
        resp = await self._throttled_get(f"/recipient/duns/{recipient_hash}/")
        return RecipientProfile.model_validate(resp.json())
