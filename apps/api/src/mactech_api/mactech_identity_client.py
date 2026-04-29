"""MacTech Identity client (Python, drop-in).

Asks the central Identity Command Center hub at
``${MACTECH_IDENTITY_BASE_URL}/api/v1/users/{clerk_user_id}/access`` whether
a Clerk user has access to THIS app via any of their customer-org
memberships. Returns a structured access record on yes, an explicit
``not_authorized`` / ``transient`` reason on no.

Pattern: the FastAPI auth dependency calls ``check_identity_access`` after
verifying the Clerk JWT. On a hit, it JIT-creates (or refreshes) the local
user row and lets the request through. On a miss, it raises a 403 with a
clear message so the user knows to ask their MacTech admin.
"""

from __future__ import annotations

import logging
import os
from dataclasses import dataclass
from typing import Any

import httpx

logger = logging.getLogger("mactech_identity")

DEFAULT_BASE_URL = "https://www.suite.mactechsolutionsllc.com"


@dataclass
class IdentityUser:
    clerk_user_id: str
    email: str
    first_name: str | None
    last_name: str | None
    is_internal_mactech_user: bool
    platform_role: str
    status: str


@dataclass
class IdentityOrgAccess:
    org_id: str
    clerk_org_id: str | None
    org_name: str
    org_status: str
    member_status: str
    role: str
    permissions: list[str]
    enabled_apps: list[dict[str, Any]]


@dataclass
class IdentityAccessResult:
    ok: bool
    user: IdentityUser | None = None
    orgs: list[IdentityOrgAccess] | None = None
    reason: str | None = None
    status: int | None = None


def _resolve_base_url(explicit: str | None) -> str:
    return explicit or os.environ.get("MACTECH_IDENTITY_BASE_URL") or DEFAULT_BASE_URL


def _resolve_api_key(explicit: str | None) -> str | None:
    return explicit or os.environ.get("MACTECH_AUDIT_INGEST_API_KEY")


async def check_identity_access(
    clerk_user_id: str,
    *,
    app_key: str | None = None,
    clerk_org_id: str | None = None,
    base_url: str | None = None,
    api_key: str | None = None,
    timeout: float = 5.0,
    client: httpx.AsyncClient | None = None,
) -> IdentityAccessResult:
    """Look up a user's central access. Returns a structured result for every
    success + failure path; never raises (transient failures return
    ``ok=False, reason='transient'`` so the caller can pick fail-closed vs
    fail-open per app)."""

    resolved_key = _resolve_api_key(api_key)
    if not resolved_key:
        logger.warning(
            "MACTECH_AUDIT_INGEST_API_KEY not configured; cannot reach ICC."
        )
        return IdentityAccessResult(ok=False, reason="transient")

    url = (
        _resolve_base_url(base_url).rstrip("/")
        + f"/api/v1/users/{clerk_user_id}/access"
    )
    params: dict[str, str] = {}
    if app_key:
        params["appKey"] = app_key
    if clerk_org_id:
        params["clerkOrgId"] = clerk_org_id

    headers = {"X-MacTech-Audit-Key": resolved_key}

    async def _do_request(c: httpx.AsyncClient) -> httpx.Response:
        return await c.get(url, params=params, headers=headers)

    try:
        if client is None:
            async with httpx.AsyncClient(timeout=timeout) as c:
                response = await _do_request(c)
        else:
            response = await _do_request(client)

        if response.status_code == 404:
            return IdentityAccessResult(ok=False, reason="user_not_found", status=404)
        if response.status_code == 401:
            return IdentityAccessResult(ok=False, reason="unauthorized", status=401)
        if response.status_code >= 400:
            logger.error(
                "ICC returned %s for user %s", response.status_code, clerk_user_id
            )
            return IdentityAccessResult(
                ok=False, reason="transient", status=response.status_code
            )

        body = response.json()
        user_data = body["user"]
        user = IdentityUser(
            clerk_user_id=user_data["clerkUserId"],
            email=user_data["email"],
            first_name=user_data.get("firstName"),
            last_name=user_data.get("lastName"),
            is_internal_mactech_user=user_data["isInternalMacTechUser"],
            platform_role=user_data["platformRole"],
            status=user_data["status"],
        )
        orgs = [
            IdentityOrgAccess(
                org_id=o["orgId"],
                clerk_org_id=o.get("clerkOrgId"),
                org_name=o["orgName"],
                org_status=o["orgStatus"],
                member_status=o["memberStatus"],
                role=o["role"],
                permissions=o.get("permissions", []),
                enabled_apps=o.get("enabledApps", []),
            )
            for o in body.get("orgs", [])
        ]
        return IdentityAccessResult(ok=True, user=user, orgs=orgs)
    except httpx.HTTPError as exc:
        logger.warning("[mactech-identity] check failed for %s: %s", clerk_user_id, exc)
        return IdentityAccessResult(ok=False, reason="transient")
    except Exception as exc:  # noqa: BLE001
        logger.exception("[mactech-identity] unexpected error: %s", exc)
        return IdentityAccessResult(ok=False, reason="transient")


def find_active_access_for_app(
    result: IdentityAccessResult, app_key: str
) -> tuple[IdentityUser, IdentityOrgAccess, dict[str, Any]] | None:
    """Return the first (user, org, entitlement) tuple where the user's
    access to ``app_key`` is fully active. Internal MacTech users get a
    synthetic match. Returns None if no active path exists."""

    if not result.ok or result.user is None:
        return None
    if result.user.status != "active":
        return None

    if result.user.is_internal_mactech_user:
        synthetic_org = IdentityOrgAccess(
            org_id="mactech-internal",
            clerk_org_id=None,
            org_name="MacTech Solutions",
            org_status="active",
            member_status="active",
            role=result.user.platform_role,
            permissions=[],
            enabled_apps=[],
        )
        synthetic_entitlement = {
            "appKey": app_key,
            "appName": app_key,
            "plan": "internal",
            "status": "active",
            "expiresAt": None,
        }
        return result.user, synthetic_org, synthetic_entitlement

    for org in result.orgs or []:
        if org.member_status != "active":
            continue
        if org.org_status != "active":
            continue
        for entitlement in org.enabled_apps:
            if entitlement.get("appKey") != app_key:
                continue
            if entitlement.get("status") not in ("active", "trialing"):
                continue
            return result.user, org, entitlement
    return None
