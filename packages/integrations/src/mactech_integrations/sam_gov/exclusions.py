"""SAM.gov Exclusions API client.

Mandatory pre-submit check per docs/SAM_GOV_API.md §5 and the playbook's
exclusions gate. Endpoint:

    GET https://api.sam.gov/entity-information/v4/exclusions
        ?api_key=<key>
        &ueiSAM=<uei>

Returns a list of active exclusion records for the entity, or empty if
clean. We treat any non-empty result list as 'excluded'. Cache TTL: 24h
(applied at the persistence layer via exclusions_cache.checked_at).

Phase 1 Week 3 surfaces only the per-UEI lookup. Bulk searches (by
classification, by date range) are not used by MacTech.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any, Final

import httpx
from tenacity import (
    AsyncRetrying,
    retry_if_exception_type,
    stop_after_attempt,
    wait_random_exponential,
)

log = logging.getLogger(__name__)

DEFAULT_BASE_URL: Final = "https://api.sam.gov"
DEFAULT_TIMEOUT: Final = httpx.Timeout(30.0, connect=10.0)


class SamExclusionsError(Exception):
    pass


class SamExclusionsRateLimitError(SamExclusionsError):
    pass


@dataclass(frozen=True)
class ExclusionResult:
    uei: str
    is_excluded: bool
    record_count: int
    raw: dict[str, Any]


class SamExclusionsClient:
    def __init__(
        self,
        api_key: str,
        *,
        base_url: str = DEFAULT_BASE_URL,
        timeout: httpx.Timeout = DEFAULT_TIMEOUT,
        http_client: httpx.AsyncClient | None = None,
    ) -> None:
        if not api_key:
            raise ValueError("SAM api_key is required")
        self._api_key = api_key
        self._base_url = base_url.rstrip("/")
        self._owns_client = http_client is None
        self._http = http_client or httpx.AsyncClient(timeout=timeout)

    async def __aenter__(self) -> SamExclusionsClient:
        return self

    async def __aexit__(self, *exc: object) -> None:
        if self._owns_client:
            await self._http.aclose()

    async def check_uei(self, uei: str) -> ExclusionResult:
        if not uei:
            raise ValueError("uei is required")
        url = f"{self._base_url}/entity-information/v4/exclusions"
        params = {"api_key": self._api_key, "ueiSAM": uei}

        async for attempt in AsyncRetrying(
            stop=stop_after_attempt(5),
            wait=wait_random_exponential(multiplier=1, max=60),
            retry=retry_if_exception_type(
                (httpx.TransportError, SamExclusionsRateLimitError)
            ),
            reraise=True,
        ):
            with attempt:
                resp = await self._http.get(url, params=params)
                if resp.status_code == 429:
                    log.warning("sam exclusions 429 — backing off")
                    raise SamExclusionsRateLimitError("rate limited")
                if 500 <= resp.status_code < 600:
                    raise SamExclusionsRateLimitError(f"server error {resp.status_code}")
                if resp.status_code >= 400:
                    raise SamExclusionsError(
                        f"sam exclusions error {resp.status_code}: {resp.text[:200]}"
                    )
                payload = resp.json()
                # Response envelope wraps records in either `excludedEntity` or
                # the v4 `exclusionDetails` array; tolerate either by counting
                # any list-like value at top level.
                records: list[Any] = []
                for key in ("excludedEntity", "exclusionDetails", "results"):
                    val = payload.get(key)
                    if isinstance(val, list):
                        records = val
                        break
                total = payload.get("totalRecords")
                if isinstance(total, int):
                    record_count = total
                else:
                    record_count = len(records)
                return ExclusionResult(
                    uei=uei,
                    is_excluded=record_count > 0,
                    record_count=record_count,
                    raw=payload,
                )
        raise SamExclusionsError("unreachable")  # pragma: no cover
