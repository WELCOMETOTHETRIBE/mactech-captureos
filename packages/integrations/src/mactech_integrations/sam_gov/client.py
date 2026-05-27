"""SAM.gov Get Opportunities Public API client.

Implementation rules (per docs/SAM_GOV_API.md):
  - GET https://api.sam.gov/opportunities/v2/search
  - postedFrom / postedTo required, MM/dd/yyyy, 1-year max range
  - 1000/day rate limit at our key tier — caller batches by NAICS, ~30 calls/day
  - Pagination by limit (default 1000) + offset
  - Exponential backoff on 429 / 5xx, max 60s, jittered

Phase 1 Week 2 surfaces only `search_opportunities`. The chained noticedesc
fetch (Chain 1 in the docs) is added in Week 2 stretch / Week 3 firm.
"""

from __future__ import annotations

import logging
from collections.abc import AsyncIterator
from datetime import date
from typing import Final

import httpx
from tenacity import (
    AsyncRetrying,
    retry_if_exception_type,
    stop_after_attempt,
    wait_random_exponential,
)

from mactech_integrations.sam_gov.models import OpportunitySearchResponse

log = logging.getLogger(__name__)

DEFAULT_BASE_URL: Final = "https://api.sam.gov"
DEFAULT_TIMEOUT: Final = httpx.Timeout(30.0, connect=10.0)


class SamGovError(Exception):
    """Raised when SAM.gov returns a non-retryable error."""


class SamGovRateLimitError(SamGovError):
    """Raised when we hit a 429 even after retries."""


class SamGovOpportunitiesClient:
    """Async typed client for /opportunities/v2/search.

    Usage:
        async with SamGovOpportunitiesClient(api_key=...) as client:
            page = await client.search_opportunities(
                posted_from=date(2026, 4, 1),
                posted_to=date(2026, 4, 24),
                ncode="541519",
                type_of_set_aside="SDVOSBC",
                limit=100,
            )
            for opp in page.opportunities_data:
                ...
    """

    def __init__(
        self,
        api_key: str,
        *,
        base_url: str = DEFAULT_BASE_URL,
        timeout: httpx.Timeout = DEFAULT_TIMEOUT,
        http_client: httpx.AsyncClient | None = None,
    ) -> None:
        if not api_key:
            raise ValueError("SAM.gov api_key is required")
        self._api_key = api_key
        self._base_url = base_url.rstrip("/")
        self._owns_client = http_client is None
        self._http = http_client or httpx.AsyncClient(timeout=timeout)

    async def __aenter__(self) -> SamGovOpportunitiesClient:
        return self

    async def __aexit__(self, *exc: object) -> None:
        if self._owns_client:
            await self._http.aclose()

    async def search_opportunities(
        self,
        *,
        posted_from: date,
        posted_to: date,
        ncode: str | None = None,
        type_of_set_aside: str | None = None,
        ptype: str | None = None,
        organization_name: str | None = None,
        state: str | None = None,
        zip_code: str | None = None,
        response_deadline_from: date | None = None,
        response_deadline_to: date | None = None,
        title: str | None = None,
        limit: int = 1000,
        offset: int = 0,
    ) -> OpportunitySearchResponse:
        """Single page fetch. See iter_opportunities for paginated iteration."""
        params: dict[str, str | int] = {
            "api_key": self._api_key,
            "postedFrom": _fmt_date(posted_from),
            "postedTo": _fmt_date(posted_to),
            "limit": limit,
            "offset": offset,
        }
        if ncode:
            params["ncode"] = ncode
        if type_of_set_aside:
            params["typeOfSetAside"] = type_of_set_aside
        if ptype:
            params["ptype"] = ptype
        if organization_name:
            params["organizationName"] = organization_name
        if state:
            params["state"] = state
        if zip_code:
            params["zip"] = zip_code
        if response_deadline_from:
            params["rdlfrom"] = _fmt_date(response_deadline_from)
        if response_deadline_to:
            params["rdlto"] = _fmt_date(response_deadline_to)
        if title:
            params["title"] = title

        url = f"{self._base_url}/opportunities/v2/search"

        async for attempt in AsyncRetrying(
            stop=stop_after_attempt(5),
            wait=wait_random_exponential(multiplier=1, max=60),
            retry=retry_if_exception_type((httpx.TransportError, SamGovRateLimitError)),
            reraise=True,
        ):
            with attempt:
                resp = await self._http.get(url, params=params)
                if resp.status_code == 429:
                    log.warning("sam.gov 429 — backing off")
                    raise SamGovRateLimitError("rate limited")
                if 500 <= resp.status_code < 600:
                    log.warning("sam.gov %s — retrying", resp.status_code)
                    raise SamGovRateLimitError(f"server error {resp.status_code}")
                if resp.status_code >= 400:
                    raise SamGovError(
                        f"sam.gov error {resp.status_code}: {resp.text[:200]}"
                    )
                return OpportunitySearchResponse.model_validate(resp.json())
        raise SamGovError("unreachable")  # pragma: no cover

    async def iter_opportunities(
        self,
        *,
        posted_from: date,
        posted_to: date,
        ncode: str | None = None,
        type_of_set_aside: str | None = None,
        page_size: int = 1000,
        max_pages: int | None = None,
        **kwargs: object,
    ) -> AsyncIterator[OpportunitySearchResponse]:
        """Yield successive pages until exhausted or max_pages reached."""
        offset = 0
        page_count = 0
        while True:
            page = await self.search_opportunities(
                posted_from=posted_from,
                posted_to=posted_to,
                ncode=ncode,
                type_of_set_aside=type_of_set_aside,
                limit=page_size,
                offset=offset,
                **kwargs,  # type: ignore[arg-type]
            )
            yield page
            page_count += 1
            offset += page_size
            if offset >= page.total_records:
                return
            if max_pages is not None and page_count >= max_pages:
                return


def _fmt_date(d: date) -> str:
    """SAM.gov requires MM/dd/yyyy — ISO will return HTTP 400."""
    return d.strftime("%m/%d/%Y")
