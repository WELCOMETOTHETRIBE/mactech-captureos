"""Codex client — read-only consumer of the CMMC Readiness Engine.

Sprint 23. CaptureOS deliberately doesn't own the CMMC assessment
workflow — that lives in a sibling product at codex.mactechsolutionsllc.com
which manages NIST 800-171 control self-attestations, evidence collection,
and the SPRS submission ladder.

CaptureOS just consumes the published SPRS score + assessment date
per tenant Clerk org so we can:
  - surface "SPRS 95/110 · last assessed 2026-04-01" on the dashboard
  - gate (eventually) DFARS 7012 / CMMC L2 opportunities to tenants
    whose SPRS score clears the agency-set threshold
  - link out to Codex for the actual assessment workflow

Identity: both apps share Clerk for auth, so `tenants.clerk_org_id` in
CaptureOS == `organizations.clerkOrgId` in Codex. We key SPRS lookup
on that shared id rather than UEI (which Codex doesn't store).

Codex API contract:
  GET https://codex.mactechsolutionsllc.com/api/sprs/by-clerk-org/{clerkOrgId}
  Authorization: Bearer <CODEX_API_TOKEN>
  -> 200 {
       clerkOrgId, organizationId, score, max,
       assessment_date, source_url, last_updated
     }
  -> 401 if bearer token missing / wrong
  -> 404 if no organization for that Clerk org
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Final

import httpx

log = logging.getLogger(__name__)

DEFAULT_BASE_URL: Final = "https://codex.mactechsolutionsllc.com"
DEFAULT_TIMEOUT: Final = httpx.Timeout(15.0, connect=5.0)


class CodexError(Exception):
    pass


class CodexNotFoundError(CodexError):
    pass


@dataclass(frozen=True)
class CodexSprsAssessment:
    clerk_org_id: str
    organization_id: str | None
    score: int | None
    max: int
    assessment_date: str | None  # ISO YYYY-MM-DD
    source_url: str | None
    last_updated: str | None  # ISO 8601 timestamp


class CodexClient:
    def __init__(
        self,
        *,
        base_url: str = DEFAULT_BASE_URL,
        api_token: str | None = None,
        timeout: httpx.Timeout = DEFAULT_TIMEOUT,
        http_client: httpx.AsyncClient | None = None,
    ) -> None:
        self._base_url = base_url.rstrip("/")
        headers: dict[str, str] = {"Accept": "application/json"}
        if api_token:
            headers["Authorization"] = f"Bearer {api_token}"
        self._owns_client = http_client is None
        self._http = http_client or httpx.AsyncClient(timeout=timeout, headers=headers)

    async def __aenter__(self) -> CodexClient:
        return self

    async def __aexit__(self, *exc: object) -> None:
        if self._owns_client:
            await self._http.aclose()

    async def get_sprs_by_clerk_org(self, clerk_org_id: str) -> CodexSprsAssessment:
        if not clerk_org_id:
            raise CodexError("clerk_org_id is required")
        url = f"{self._base_url}/api/sprs/by-clerk-org/{clerk_org_id.strip()}"
        try:
            resp = await self._http.get(url)
        except httpx.TransportError as exc:
            raise CodexError(f"Codex transport error: {exc}") from exc

        if resp.status_code == 404:
            raise CodexNotFoundError(f"no organization in Codex for clerk_org_id={clerk_org_id}")
        if resp.status_code == 401:
            raise CodexError(
                "Codex 401 — set CODEX_API_TOKEN to a value matching Codex's CAPTUREOS_API_TOKEN"
            )
        if resp.status_code == 503:
            raise CodexError("Codex 503 — CAPTUREOS_API_TOKEN not configured on Codex")
        if resp.status_code >= 400:
            raise CodexError(f"Codex {resp.status_code} on {url}: {resp.text[:200]}")

        data = resp.json()
        if not isinstance(data, dict):
            raise CodexError(f"Codex returned non-dict ({type(data).__name__})")
        score = data.get("score")
        if score is not None and not isinstance(score, int):
            raise CodexError(f"Codex returned non-int score: {score!r}")
        return CodexSprsAssessment(
            clerk_org_id=clerk_org_id.strip(),
            organization_id=data.get("organizationId"),
            score=score,
            max=int(data.get("max") or 110),
            assessment_date=data.get("assessment_date"),
            source_url=data.get("source_url"),
            last_updated=data.get("last_updated"),
        )
