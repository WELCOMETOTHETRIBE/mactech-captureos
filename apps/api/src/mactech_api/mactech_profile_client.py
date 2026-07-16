"""MacTech Identity — member capability profile client (read-only).

Reads the Suite-wide capability profile a member built once in bizops and
confirmed field-by-field, from
``${MACTECH_IDENTITY_BASE_URL}/api/hub/profiles/by-clerk/{clerk_user_id}``,
authenticated with ``MACTECH_PROFILE_READ_API_KEY`` (a Hub API key holding the
``profile_read`` scope).

Addressed by **Clerk user id**, which this app already has: ``users.clerk_user_id``
is set from the token's ``sub`` at sign-in, and ``users.founder_id`` already
says which founder that person is. The Suite keys the same person by
``UserProfile.clerkUserId`` (unique). So the join between the two systems is an
identifier both already store — there is no column to add here, nothing to
backfill, and no email matching, which is the only mechanism that could have
attached one person's profile to another.

Why REST and not a shared package: the Hub's own client library is TypeScript
and this API is Python. The Hub exposes profiles over plain HTTP precisely so
both can read the same contract — see ADR-0003 in mactech-suite-platform.

Read-only on purpose. bizops owns the member-facing confirmation flow, and the
profile is only trustworthy *because* a human confirmed each field; this app has
no such flow, so it consumes and never writes. There is deliberately no
``put_member_profile`` here.

What the Hub will not return, so do not look for it: no name, no email (identity
lives on the Suite's UserProfile and is resolved separately), and no clearance.

Failures are logged and never raised — mirroring ``mactech_audit_client``. A Hub
outage must degrade this app to "founder data unchanged", never to an error.
"""

from __future__ import annotations

import logging
import os
from dataclasses import dataclass
from typing import Any

import httpx

logger = logging.getLogger("mactech_profile")

DEFAULT_BASE_URL = "https://www.suite.mactechsolutionsllc.com"


@dataclass(frozen=True)
class MemberProfile:
    """The Suite's view of a member's capability profile.

    ``naics_codes`` is ordered strongest-first — it is the member's own ranking
    of what they are versus what they can also credibly do, and the Hub
    preserves it. Treat position as a signal; never sort it, and never read
    absence from the tail as a negative.
    """

    hub_user_id: str
    headline: str | None
    summary: str | None
    labor_category: str | None
    years_experience: int | None
    naics_codes: tuple[str, ...]
    source_app_key: str | None
    confirmed_at: str | None
    updated_at: str | None


def _resolve_base_url(explicit: str | None) -> str:
    return explicit or os.environ.get("MACTECH_IDENTITY_BASE_URL") or DEFAULT_BASE_URL


def _resolve_api_key(explicit: str | None) -> str | None:
    return explicit or os.environ.get("MACTECH_PROFILE_READ_API_KEY")


def _parse(payload: dict[str, Any]) -> MemberProfile:
    codes = payload.get("naicsCodes") or []
    return MemberProfile(
        hub_user_id=payload["hubUserId"],
        headline=payload.get("headline"),
        summary=payload.get("summary"),
        labor_category=payload.get("laborCategory"),
        years_experience=payload.get("yearsExperience"),
        # Tuple, not list: the ordering is meaningful and callers should have to
        # work to reorder it by accident.
        naics_codes=tuple(str(c) for c in codes),
        source_app_key=payload.get("sourceAppKey"),
        confirmed_at=payload.get("confirmedAt"),
        updated_at=payload.get("updatedAt"),
    )


async def fetch_member_profile(
    clerk_user_id: str,
    *,
    base_url: str | None = None,
    api_key: str | None = None,
    raise_on_error: bool = False,
    # ASYNC109 would prefer asyncio.timeout at the call site. Kept as a
    # parameter to mirror send_audit_log exactly: these two are the app's Hub
    # clients and callers should not have to remember which one takes a timeout
    # differently. Revisit both together, not this one alone.
    timeout: float = 5.0,  # noqa: ASYNC109
    client: httpx.AsyncClient | None = None,
) -> MemberProfile | None:
    """Fetch one member's capability profile by their Clerk user id.

    Returns ``None`` when the member has no profile yet (404), when the Hub is
    unreachable, or when the key is unconfigured. A caller cannot distinguish
    "no profile" from "Hub down" — and must not try to: both mean *leave the
    founder as it is*, which is the only safe response to missing data.
    """

    resolved_key = _resolve_api_key(api_key)
    if not resolved_key:
        msg = "MACTECH_PROFILE_READ_API_KEY is not configured; skipping fetch."
        if raise_on_error:
            raise RuntimeError(msg)
        logger.warning(msg)
        return None

    url = f"{_resolve_base_url(base_url).rstrip('/')}/api/hub/profiles/by-clerk/{clerk_user_id}"
    headers = {"Authorization": f"Bearer {resolved_key}"}

    try:
        if client is None:
            async with httpx.AsyncClient(timeout=timeout) as c:
                response = await c.get(url, headers=headers)
        else:
            response = await client.get(url, headers=headers)

        if response.status_code == 404:
            # Not an error: most people have no profile yet.
            return None
        if response.status_code >= 400:
            msg = f"hub/profiles → {response.status_code} {response.text[:200]}"
            if raise_on_error:
                raise RuntimeError(msg)
            logger.warning("[mactech-profile] %s for %s", msg, clerk_user_id)
            return None
        return _parse(response.json())
    except Exception as exc:
        if raise_on_error:
            raise
        logger.warning("[mactech-profile] fetch failed for %s: %s", clerk_user_id, exc)
        return None
