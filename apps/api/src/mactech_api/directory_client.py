"""bizops Directory client — the MacTech shared company address book.

bizops owns the canonical contact store (people + organizations, internal and
external) and exposes it to sibling apps at
``${MACTECH_DIRECTORY_BASE_URL}/api/directory/*``, authenticated with the
dedicated ``MACTECH_DIRECTORY_SERVICE_TOKEN`` (one token per capability, same
blast-radius rationale as ``MACTECH_PROFILE_READ_API_KEY``) plus an
``x-mactech-service-app`` header naming this app. Tenancy: every call carries
``organizationId`` — the **Hub CustomerOrganization id**, NOT the Clerk org id.
Capture resolves and caches that id on ``tenants.hub_org_id`` (see
``routes/directory.py``).

Closed vocabularies are enforced server-side by bizops (kind, org type,
status); this client passes values through and surfaces bizops's 400 payload
verbatim rather than pre-validating, so the two apps cannot drift.

Failure posture differs by direction, deliberately:
  - **Reads** mirror ``mactech_profile_client``: log and return ``None`` —
    a bizops outage degrades the directory page, never breaks Capture.
  - **Writes** raise ``DirectoryError`` — a user who clicked "add contact"
    must see the failure, not a silent no-op.
"""

from __future__ import annotations

import logging
import os
from dataclasses import dataclass
from typing import Any

import httpx

logger = logging.getLogger("mactech_directory")

DEFAULT_BASE_URL = "https://bizops.mactechsolutionsllc.com"
SERVICE_APP_KEY = "capture"


class DirectoryError(Exception):
    """A Directory write failed. ``status`` and ``detail`` carry bizops's
    response so routes can forward real validation messages to the user."""

    def __init__(self, message: str, *, status: int | None = None, detail: Any = None) -> None:
        super().__init__(message)
        self.status = status
        self.detail = detail


@dataclass(frozen=True)
class DirectoryContact:
    id: str
    name: str
    kind: str  # INTERNAL | EXTERNAL
    title: str | None
    organization_id: str | None
    organization_name: str | None
    email: str | None
    phone: str | None
    mobile: str | None
    tags: tuple[str, ...]
    notes: str | None
    status: str  # ACTIVE | ARCHIVED
    source_app: str | None
    updated_at: str | None


@dataclass(frozen=True)
class DirectoryOrganization:
    id: str
    name: str
    org_type: str
    abbreviation: str | None
    website: str | None
    email: str | None
    phone: str | None
    uei: str | None
    cage_code: str | None
    tags: tuple[str, ...]
    status: str
    contact_count: int | None


def _resolve_base_url(explicit: str | None) -> str:
    return explicit or os.environ.get("MACTECH_DIRECTORY_BASE_URL") or DEFAULT_BASE_URL


def _resolve_token(explicit: str | None) -> str | None:
    return explicit or os.environ.get("MACTECH_DIRECTORY_SERVICE_TOKEN")


def _headers(token: str) -> dict[str, str]:
    return {
        "Authorization": f"Bearer {token}",
        "x-mactech-service-app": SERVICE_APP_KEY,
    }


def _parse_contact(payload: dict[str, Any]) -> DirectoryContact:
    org = payload.get("organization") or {}
    return DirectoryContact(
        id=payload["id"],
        name=payload["name"],
        kind=payload.get("kind", "EXTERNAL"),
        title=payload.get("title"),
        organization_id=payload.get("organizationId"),
        # Linked directory org name wins over the free-text fallback field.
        organization_name=org.get("name") or payload.get("organizationName"),
        email=payload.get("email"),
        phone=payload.get("phone"),
        mobile=payload.get("mobile"),
        tags=tuple(str(t) for t in payload.get("tags") or []),
        notes=payload.get("notes"),
        status=payload.get("status", "ACTIVE"),
        source_app=payload.get("sourceApp"),
        updated_at=payload.get("updatedAt"),
    )


def _parse_organization(payload: dict[str, Any]) -> DirectoryOrganization:
    count = payload.get("_count") or {}
    return DirectoryOrganization(
        id=payload["id"],
        name=payload["name"],
        org_type=payload.get("orgType", "OTHER"),
        abbreviation=payload.get("abbreviation"),
        website=payload.get("website"),
        email=payload.get("email"),
        phone=payload.get("phone"),
        uei=payload.get("uei"),
        cage_code=payload.get("cageCode"),
        tags=tuple(str(t) for t in payload.get("tags") or []),
        status=payload.get("status", "ACTIVE"),
        contact_count=count.get("contacts"),
    )


async def _get(
    path: str,
    params: dict[str, str],
    *,
    base_url: str | None,
    token: str | None,
    timeout: float,
    client: httpx.AsyncClient | None,
) -> dict[str, Any] | None:
    resolved = _resolve_token(token)
    if not resolved:
        logger.warning("MACTECH_DIRECTORY_SERVICE_TOKEN not configured; skipping fetch.")
        return None
    url = _resolve_base_url(base_url).rstrip("/") + path
    try:
        if client is None:
            async with httpx.AsyncClient(timeout=timeout) as c:
                response = await c.get(url, params=params, headers=_headers(resolved))
        else:
            response = await client.get(url, params=params, headers=_headers(resolved))
        if response.status_code >= 400:
            logger.warning(
                "[mactech-directory] GET %s → %s %s",
                path,
                response.status_code,
                response.text[:200],
            )
            return None
        body: dict[str, Any] = response.json()
        return body
    except Exception as exc:
        logger.warning("[mactech-directory] GET %s failed: %s", path, exc)
        return None


async def _post(
    path: str,
    body: dict[str, Any],
    *,
    base_url: str | None,
    token: str | None,
    timeout: float,
    client: httpx.AsyncClient | None,
) -> dict[str, Any]:
    resolved = _resolve_token(token)
    if not resolved:
        raise DirectoryError("MACTECH_DIRECTORY_SERVICE_TOKEN is not configured", status=503)
    url = _resolve_base_url(base_url).rstrip("/") + path
    try:
        if client is None:
            async with httpx.AsyncClient(timeout=timeout) as c:
                response = await c.post(url, json=body, headers=_headers(resolved))
        else:
            response = await client.post(url, json=body, headers=_headers(resolved))
    except httpx.HTTPError as exc:
        raise DirectoryError(f"Directory unreachable: {exc}", status=502) from exc
    if response.status_code >= 400:
        detail: Any
        try:
            detail = response.json()
        except ValueError:
            detail = response.text[:200]
        raise DirectoryError(
            f"Directory POST {path} → {response.status_code}",
            status=response.status_code,
            detail=detail,
        )
    body_out: dict[str, Any] = response.json()
    return body_out


async def fetch_directory_contacts(
    hub_org_id: str,
    *,
    q: str | None = None,
    kind: str | None = None,
    tag: str | None = None,
    directory_organization_id: str | None = None,
    base_url: str | None = None,
    token: str | None = None,
    timeout: float = 8.0,
    client: httpx.AsyncClient | None = None,
) -> list[DirectoryContact] | None:
    """List/search directory people. ``None`` means the Directory could not be
    reached (or is unconfigured) — callers should render "unavailable", never
    an empty address book."""

    params: dict[str, str] = {"organizationId": hub_org_id}
    if q:
        params["q"] = q
    if kind:
        params["kind"] = kind
    if tag:
        params["tag"] = tag
    if directory_organization_id:
        params["directoryOrganizationId"] = directory_organization_id
    body = await _get(
        "/api/directory/contacts",
        params,
        base_url=base_url,
        token=token,
        timeout=timeout,
        client=client,
    )
    if body is None:
        return None
    return [_parse_contact(c) for c in body.get("contacts", [])]


async def fetch_directory_organizations(
    hub_org_id: str,
    *,
    q: str | None = None,
    org_type: str | None = None,
    base_url: str | None = None,
    token: str | None = None,
    timeout: float = 8.0,
    client: httpx.AsyncClient | None = None,
) -> list[DirectoryOrganization] | None:
    params: dict[str, str] = {"organizationId": hub_org_id}
    if q:
        params["q"] = q
    if org_type:
        params["orgType"] = org_type
    body = await _get(
        "/api/directory/organizations",
        params,
        base_url=base_url,
        token=token,
        timeout=timeout,
        client=client,
    )
    if body is None:
        return None
    return [_parse_organization(o) for o in body.get("organizations", [])]


async def create_directory_contact(
    hub_org_id: str,
    fields: dict[str, Any],
    *,
    base_url: str | None = None,
    token: str | None = None,
    timeout: float = 8.0,
    client: httpx.AsyncClient | None = None,
) -> DirectoryContact:
    """Create a person in the shared directory. Raises ``DirectoryError`` on
    any failure, carrying bizops's validation payload when there is one."""

    body = await _post(
        "/api/directory/contacts",
        # Merge order matters: the tenant id must never be clobbered by a
        # caller-supplied key. The DirectoryOrganization link travels as
        # "directoryOrganizationId" on this surface, never "organizationId".
        {**fields, "organizationId": hub_org_id},
        base_url=base_url,
        token=token,
        timeout=timeout,
        client=client,
    )
    return _parse_contact(body["contact"])


async def create_directory_organization(
    hub_org_id: str,
    fields: dict[str, Any],
    *,
    base_url: str | None = None,
    token: str | None = None,
    timeout: float = 8.0,
    client: httpx.AsyncClient | None = None,
) -> DirectoryOrganization:
    body = await _post(
        "/api/directory/organizations",
        {**fields, "organizationId": hub_org_id},
        base_url=base_url,
        token=token,
        timeout=timeout,
        client=client,
    )
    return _parse_organization(body["organization"])
