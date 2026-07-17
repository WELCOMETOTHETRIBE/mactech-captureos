"""SAM.gov Entity Management API client.

Phase 3 Week 14 (UX Sprint 8). Used by the onboarding flow to auto-fill
firm identity (legal name, CAGE, business types, set-aside indicators,
NAICS, primary address) from a single UEI.

Endpoint:

    GET https://api.sam.gov/entity-information/v4/entities
        ?api_key=<key>
        &ueiSAM=<uei>
        &registrationStatus=A      (Active only)
        &samRegistered=Yes
        &includeSections=All

Returns a single registration record per UEI, or zero rows if the UEI
isn't in SAM (typo or pending registration). The full record is huge;
we surface a flattened subset suitable for an onboarding form pre-fill.
"""

from __future__ import annotations

import logging
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


class SamEntityError(Exception):
    pass


class SamEntityRateLimitError(SamEntityError):
    pass


class SamEntityNotFoundError(SamEntityError):
    pass


# SAM's "businessTypes" are coded objects with codes like A2/27/etc. We map
# the most common ones the onboarding wizard cares about (set-aside
# certifications + small-business indicators) to friendlier labels. Full
# code list is at https://sam.gov/api/prod/sgs/v1/businessTypes/list.
_BUSINESS_TYPE_CODE_MAP: dict[str, str] = {
    "A2": "Womans Owned Business",
    "23": "Small Business",
    "27": "Self Certified Small Disadvantaged Business",
    "JV": "Joint Venture",
    "QF": "Service Disabled Veteran Owned Small Business",
    "QZ": "Veteran Owned Small Business",
    "OY": "Self-Certified HUBZone Joint Venture",
    "XS": "SBA Certified Small Disadvantaged Business",
    "8W": "Sba Certified 8(a) Joint Venture",
    "OY ": "Self-Certified HUBZone Joint Venture",
    "A6": "Self-Certified Womans Owned Business",
    "JT": "Tribally Owned Firm",
    "27 ": "Self Certified Small Disadvantaged Business",
}

# Canonical short codes the onboarding wizard renders as set-aside chips.
_SHORT_CODES = {
    "SDVOSB": [
        "service disabled veteran owned small business",
        "service-disabled veteran-owned small business",
    ],
    "VOSB": ["veteran owned small business", "veteran-owned small business"],
    "WOSB": ["womans owned business", "women-owned small business"],
    "EDWOSB": ["economically disadvantaged women-owned small business"],
    "8(a)": ["8(a)", "sba 8(a)"],
    "HUBZone": ["hubzone"],
    "SDB": ["small disadvantaged business"],
    "SB": ["small business"],
}


def _short_codes_from_business_types(types: list[dict[str, Any]]) -> list[str]:
    """Reduce SAM's businessTypes list to the canonical short codes the
    UI uses (SDVOSB, 8(a), HUBZone, etc.)."""
    if not types:
        return []
    descriptions: list[str] = []
    for bt in types:
        if not isinstance(bt, dict):
            continue
        desc = bt.get("businessTypeDesc") or bt.get("description") or ""
        if isinstance(desc, str):
            descriptions.append(desc.lower().strip())
    out: list[str] = []
    for short, hints in _SHORT_CODES.items():
        for d in descriptions:
            if any(h in d for h in hints):
                if short not in out:
                    out.append(short)
                break
    return out


@dataclass(frozen=True)
class EntityProfile:
    uei: str
    cage_code: str | None
    legal_business_name: str | None
    dba_name: str | None
    registration_status: str | None
    registration_date: str | None
    expiration_date: str | None
    physical_address_city: str | None
    physical_address_state: str | None
    physical_address_country: str | None
    primary_naics: str | None
    naics_codes: list[str] = field(default_factory=list)
    business_types_raw: list[str] = field(default_factory=list)
    set_aside_short_codes: list[str] = field(default_factory=list)
    pop_email: str | None = None
    pop_first_name: str | None = None
    pop_last_name: str | None = None
    pop_title: str | None = None
    raw: dict[str, Any] | None = None


class SamEntityClient:
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

    async def __aenter__(self) -> SamEntityClient:
        return self

    async def __aexit__(self, *exc: object) -> None:
        if self._owns_client:
            await self._http.aclose()

    async def lookup_uei(self, uei: str) -> EntityProfile:
        if not uei or len(uei.strip()) < 6:
            raise ValueError("uei must be at least 6 characters")
        uei = uei.strip().upper()
        url = f"{self._base_url}/entity-information/v4/entities"
        params: dict[str, Any] = {
            "api_key": self._api_key,
            "ueiSAM": uei,
            "includeSections": "coreData,assertions,pointsOfContact",
        }

        async for attempt in AsyncRetrying(
            stop=stop_after_attempt(5),
            wait=wait_random_exponential(multiplier=1, max=60),
            retry=retry_if_exception_type((httpx.TransportError, SamEntityRateLimitError)),
            reraise=True,
        ):
            with attempt:
                resp = await self._http.get(url, params=params)
                if resp.status_code == 429:
                    log.warning("sam entity 429 — backing off")
                    raise SamEntityRateLimitError("rate limited")
                if 500 <= resp.status_code < 600:
                    raise SamEntityRateLimitError(f"server error {resp.status_code}")
                if resp.status_code >= 400:
                    raise SamEntityError(f"sam entity error {resp.status_code}: {resp.text[:200]}")

                data = resp.json()

                entity_data = data.get("entityData") or []
                if not entity_data:
                    raise SamEntityNotFoundError(
                        f"no SAM entity found for UEI {uei}. "
                        "Either the UEI is wrong or the entity isn't "
                        "active in SAM."
                    )
                return self._flatten(uei, entity_data[0])

        raise SamEntityError("retries exhausted")

    def _flatten(self, uei: str, entity: dict[str, Any]) -> EntityProfile:
        core = entity.get("coreData") or {}
        identification = core.get("entityIdentification") or {}
        registration = core.get("entityRegistration") or {}
        physical = core.get("physicalAddress") or {}

        # NAICS — under "assertions.goodsAndServices.naicsList" or similar.
        assertions = entity.get("assertions") or {}
        gas = assertions.get("goodsAndServices") or {}
        naics_list = gas.get("naicsList") or []
        primary_naics: str | None = None
        naics_codes: list[str] = []
        for n in naics_list if isinstance(naics_list, list) else []:
            if not isinstance(n, dict):
                continue
            code = n.get("naicsCode") or n.get("code")
            if isinstance(code, (str, int)):
                code_s = str(code).strip()
                if code_s and code_s not in naics_codes:
                    naics_codes.append(code_s)
                if n.get("primaryNAICS") in ("Y", True, "true", "True") and primary_naics is None:
                    primary_naics = code_s

        business_types = (
            (assertions.get("businessTypes") or {}).get("businessTypeList")
            or core.get("businessTypes")
            or []
        )
        biz_descs: list[str] = []
        for bt in business_types if isinstance(business_types, list) else []:
            if isinstance(bt, dict):
                d = (
                    bt.get("businessTypeDesc")
                    or bt.get("description")
                    or _BUSINESS_TYPE_CODE_MAP.get(str(bt.get("businessTypeCode") or "").strip())
                )
                if d:
                    biz_descs.append(str(d))

        # POC — the API exposes "pointsOfContact"; pull primary government POC.
        poc = entity.get("pointsOfContact") or {}
        primary = poc.get("governmentBusinessPOC") or poc.get("electronicBusinessPOC") or {}

        return EntityProfile(
            uei=uei,
            cage_code=(identification.get("cageCode") or core.get("cageCode") or None),
            legal_business_name=(
                identification.get("legalBusinessName") or core.get("legalBusinessName")
            ),
            dba_name=identification.get("dbaName") or core.get("dbaName"),
            registration_status=registration.get("registrationStatus"),
            registration_date=registration.get("registrationDate")
            or registration.get("activationDate"),
            expiration_date=registration.get("expirationDate"),
            physical_address_city=physical.get("city"),
            physical_address_state=(physical.get("stateOrProvinceCode") or physical.get("state")),
            physical_address_country=(physical.get("countryCode") or physical.get("country")),
            primary_naics=primary_naics,
            naics_codes=naics_codes,
            business_types_raw=biz_descs,
            set_aside_short_codes=_short_codes_from_business_types(
                business_types if isinstance(business_types, list) else []
            ),
            pop_email=primary.get("email") if isinstance(primary, dict) else None,
            pop_first_name=(primary.get("firstName") if isinstance(primary, dict) else None),
            pop_last_name=(primary.get("lastName") if isinstance(primary, dict) else None),
            pop_title=primary.get("title") if isinstance(primary, dict) else None,
            raw=entity,
        )
