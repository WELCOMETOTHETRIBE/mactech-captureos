"""SAM.gov Interested Vendors List client.

Feeds the high-moat scoring track's "response velocity" component. Logic:
when a solicitation's Interested Vendors List is enabled and has vendors
but zero of them are cyber firms, that's a prime-contractor bottleneck —
the construction prime has no cyber sub lined up. We score 10 pts.

Endpoint:

    GET https://api.sam.gov/opportunities/v1/noticedata/{notice_id}/interestedVendorsList
        ?api_key=<key>

If the solicitation has opted out of the public IVL, the endpoint
returns 404 / 204 / an empty list — we surface that as
``available=False`` and the scorer treats it as the "inactive" tier
(velocity_inactive, 5 pts). We do NOT confuse "list disabled" with
"list active but empty" — both look the same on the wire today, so the
scorer gives them equal credit.

Cyber-firm classification: a vendor counts as cyber when their NAICS
profile intersects {541512, 541513, 541519, 518210}. The NAICS list
field on the IVL response is loose; we accept the vendor-side ``naics``
array, ``naicsCode`` scalar, or ``primaryNaics`` field.
"""

from __future__ import annotations

import logging
from collections.abc import Iterable
from dataclasses import dataclass, field
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

# A vendor is a "cyber firm" if their NAICS profile contains any of these.
# Mirrors MacTech's primary cyber NAICS — Patrick + James's pillars.
CYBER_NAICS: Final[frozenset[str]] = frozenset({"541512", "541513", "541519", "518210"})


class SamInterestedVendorsError(Exception):
    pass


class SamInterestedVendorsRateLimitError(SamInterestedVendorsError):
    pass


@dataclass(frozen=True)
class InterestedVendorsResult:
    notice_id: str
    available: bool  # IVL was enabled and returned a (possibly empty) list
    count: int  # total vendors on the list
    cyber_count: int  # subset whose NAICS profile ∩ CYBER_NAICS
    raw: dict[str, Any] = field(default_factory=dict)


def _vendor_naics(vendor: dict[str, Any]) -> Iterable[str]:
    """Yield the NAICS codes attached to a vendor record, normalising the
    several shapes SAM has used over the API's history."""
    naics_field = vendor.get("naics")
    if isinstance(naics_field, list):
        for n in naics_field:
            if isinstance(n, str):
                yield n.strip()
            elif isinstance(n, dict):
                code = n.get("code") or n.get("naicsCode")
                if isinstance(code, str):
                    yield code.strip()
    for key in ("naicsCode", "primaryNaics"):
        v = vendor.get(key)
        if isinstance(v, str) and v.strip():
            yield v.strip()


def _classify(vendor: dict[str, Any]) -> bool:
    return any(code in CYBER_NAICS for code in _vendor_naics(vendor))


class SamInterestedVendorsClient:
    """Async client for /opportunities/v1/noticedata/{id}/interestedVendorsList.

    Usage:
        async with SamInterestedVendorsClient(api_key=...) as client:
            result = await client.list_for_notice(notice_id)
            if result.available and result.count >= 1 and result.cyber_count == 0:
                ...  # prime bottleneck — score the velocity bonus
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

    async def __aenter__(self) -> SamInterestedVendorsClient:
        return self

    async def __aexit__(self, *exc: object) -> None:
        if self._owns_client:
            await self._http.aclose()

    async def list_for_notice(self, notice_id: str) -> InterestedVendorsResult:
        if not notice_id:
            raise ValueError("notice_id is required")
        url = f"{self._base_url}/opportunities/v1/noticedata/{notice_id}/interestedVendorsList"
        params = {"api_key": self._api_key}

        async for attempt in AsyncRetrying(
            stop=stop_after_attempt(5),
            wait=wait_random_exponential(multiplier=1, max=60),
            retry=retry_if_exception_type(
                (httpx.TransportError, SamInterestedVendorsRateLimitError)
            ),
            reraise=True,
        ):
            with attempt:
                resp = await self._http.get(url, params=params)
                if resp.status_code == 429:
                    log.warning("sam IVL 429 — backing off")
                    raise SamInterestedVendorsRateLimitError("rate limited")
                if 500 <= resp.status_code < 600:
                    raise SamInterestedVendorsRateLimitError(f"server error {resp.status_code}")
                # 404 or 204 → list not enabled for this notice.
                if resp.status_code in (404, 204):
                    return InterestedVendorsResult(
                        notice_id=notice_id,
                        available=False,
                        count=0,
                        cyber_count=0,
                        raw={},
                    )
                if resp.status_code >= 400:
                    raise SamInterestedVendorsError(
                        f"sam IVL error {resp.status_code}: {resp.text[:200]}"
                    )
                payload = resp.json() if resp.content else {}

                # Tolerate the wrapper shapes SAM has used historically:
                # top-level `interestedVendors`, `vendors`, or a bare list.
                vendors: list[dict[str, Any]]
                if isinstance(payload, list):
                    vendors = [v for v in payload if isinstance(v, dict)]
                else:
                    raw_list: Any = (
                        payload.get("interestedVendors")
                        or payload.get("vendors")
                        or payload.get("results")
                        or []
                    )
                    vendors = (
                        [v for v in raw_list if isinstance(v, dict)]
                        if isinstance(raw_list, list)
                        else []
                    )

                cyber = sum(1 for v in vendors if _classify(v))
                return InterestedVendorsResult(
                    notice_id=notice_id,
                    available=True,
                    count=len(vendors),
                    cyber_count=cyber,
                    raw=payload if isinstance(payload, dict) else {},
                )
        raise SamInterestedVendorsError("unreachable")  # pragma: no cover
