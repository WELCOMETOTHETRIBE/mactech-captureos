"""Clerk JWT verification + tenant resolution.

The Next.js app obtains a session token from Clerk, signed with the
`mactech` JWT template. The token carries:

  - `sub`           Clerk user id (e.g. "user_2abc...")
  - `tenant_org_id` Clerk org id ("org_2abc...")
  - `tenant_org_slug`
  - `founder_slug`  populated from Clerk user public_metadata

We verify the token's signature against Clerk's published JWKS, look
up the MacTech tenant by clerk_org_id, and yield a `RequestContext`
that includes the User row + Tenant + a tenant-scoped DB session.
"""

from __future__ import annotations

import asyncio
import logging
import os
import time
from collections.abc import AsyncIterator
from dataclasses import dataclass
from typing import Annotated, Any
from uuid import UUID

import jwt
from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jwt import PyJWKClient
from mactech_db import scoped_session
from mactech_db.models import Founder, Tenant, User
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from mactech_api.mactech_audit_client import send_audit_log
from mactech_api.mactech_identity_client import (
    check_identity_access,
    find_active_access_for_app,
)
from mactech_api.services.founder_profile_sync import sync_one_user_in_background

CAPTURE_APP_KEY = "capture"


def _map_icc_role_to_capture_role(icc_role: str, is_internal: bool) -> str:
    """Capture's ``users.role`` is a free-form string with conventions
    ``owner`` / ``admin`` / ``member``. Internal MacTech operators
    always become owner. Customer roles map: customer_owner → owner,
    customer_admin → admin, everything else → member."""

    if is_internal:
        return "owner"
    if icc_role == "customer_owner":
        return "owner"
    if icc_role == "customer_admin":
        return "admin"
    return "member"

log = logging.getLogger(__name__)

# In-memory dedup so we fire at most one capture.session.opened event per
# Clerk user per process per hour. Per-process state, not shared across
# replicas — acceptable noise for a session-level signal.
_AUDIT_SESSION_DEDUP_S = 60 * 60
_audit_session_last_fire: dict[str, float] = {}


def _should_fire_audit_session(clerk_user_id: str) -> bool:
    now = time.time()
    last = _audit_session_last_fire.get(clerk_user_id)
    if last and now - last < _AUDIT_SESSION_DEDUP_S:
        return False
    _audit_session_last_fire[clerk_user_id] = now
    return True


# Same shape as the audit throttle, separate window and dict. A capability
# profile changes rarely — a member re-uploads a resume now and then — so
# pulling it once per user per process per hour keeps founder cards fresh
# without turning every request into a Hub round trip. Per-process, so each
# replica syncs independently; the sync is idempotent, so overlap is harmless.
_PROFILE_SYNC_DEDUP_S = 60 * 60
_profile_sync_last_fire: dict[str, float] = {}


def _should_sync_profile(clerk_user_id: str) -> bool:
    now = time.time()
    last = _profile_sync_last_fire.get(clerk_user_id)
    if last and now - last < _PROFILE_SYNC_DEDUP_S:
        return False
    _profile_sync_last_fire[clerk_user_id] = now
    return True


# asyncio only holds a weak reference to a bare task, so a fire-and-forget
# coroutine can be garbage-collected mid-flight (RUF006). Hold a strong
# reference until it finishes, then drop it.
_background_tasks: set[asyncio.Task[Any]] = set()


def _fire_and_forget(coro: Any) -> None:
    task = asyncio.create_task(coro)
    _background_tasks.add(task)
    task.add_done_callback(_background_tasks.discard)

# Clerk publishes the JWKS at <frontend-api>/.well-known/jwks.json. Frontend API
# host comes from CLERK_FRONTEND_API or, on dev, can be inferred from the
# publishable key. We require the env var to be set explicitly in production.
_JWKS_CLIENTS: dict[str, PyJWKClient] = {}


def _get_jwks_client() -> PyJWKClient:
    frontend_api = os.environ.get("CLERK_FRONTEND_API", "")
    if not frontend_api:
        raise RuntimeError(
            "CLERK_FRONTEND_API not set. Get this from your Clerk dashboard's "
            "API Keys page; it looks like 'something-12.clerk.accounts.dev' "
            "or your custom Clerk domain."
        )
    if frontend_api not in _JWKS_CLIENTS:
        url = (
            frontend_api
            if frontend_api.startswith("http")
            else f"https://{frontend_api}"
        )
        if not url.endswith("/.well-known/jwks.json"):
            url = url.rstrip("/") + "/.well-known/jwks.json"
        _JWKS_CLIENTS[frontend_api] = PyJWKClient(url, cache_keys=True)
    return _JWKS_CLIENTS[frontend_api]


@dataclass
class ClerkClaims:
    sub: str  # Clerk user id
    tenant_org_id: str | None
    tenant_org_slug: str | None
    founder_slug: str | None
    raw: dict[str, Any]


@dataclass
class RequestContext:
    user: User
    tenant: Tenant
    founder: Founder | None
    claims: ClerkClaims
    session: AsyncSession


_bearer = HTTPBearer(auto_error=False)


async def _verify_clerk_jwt(token: str) -> ClerkClaims:
    try:
        signing_key = _get_jwks_client().get_signing_key_from_jwt(token)
        decoded = jwt.decode(
            token,
            signing_key.key,
            algorithms=["RS256"],
            options={"verify_aud": False},
        )
    except jwt.ExpiredSignatureError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="token expired"
        ) from exc
    except jwt.PyJWTError as exc:
        log.warning("jwt verification failed: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="invalid token"
        ) from exc
    return ClerkClaims(
        sub=decoded.get("sub", ""),
        tenant_org_id=decoded.get("tenant_org_id"),
        tenant_org_slug=decoded.get("tenant_org_slug"),
        founder_slug=decoded.get("founder_slug"),
        raw=decoded,
    )


async def _resolve_tenant_and_user(
    claims: ClerkClaims, session: AsyncSession
) -> tuple[Tenant, User, Founder | None]:
    if not claims.tenant_org_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="token missing tenant_org_id claim — verify Clerk JWT template",
        )
    tenant = (
        await session.execute(
            select(Tenant).where(Tenant.clerk_org_id == claims.tenant_org_id)
        )
    ).scalar_one_or_none()

    # If no local tenant exists for this Clerk org, ask the central
    # Identity Command Center whether the user has access to capture.
    # On a hit, JIT-create the tenant from ICC metadata. This replaces
    # the old hard-error path that required manual tenant onboarding.
    icc_org_role: str | None = None
    icc_is_internal = False
    if tenant is None:
        icc_result = await check_identity_access(
            clerk_user_id=claims.sub,
            app_key=CAPTURE_APP_KEY,
            clerk_org_id=claims.tenant_org_id,
        )
        access = find_active_access_for_app(icc_result, CAPTURE_APP_KEY)
        if access is None:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=(
                    "Your Clerk org isn't linked to a CaptureOS tenant and "
                    "the central Identity Command Center has not granted "
                    "your user access to Capture. Ask a MacTech admin to "
                    "enable Capture in your org's product entitlements."
                ),
            )
        _user, icc_org, _entitlement = access
        icc_org_role = icc_org.role
        icc_is_internal = access[0].is_internal_mactech_user

        slug = (
            (icc_org.clerk_org_id or "")
            .lower()
            .replace("_", "-")[:50]
            or f"tenant-{claims.tenant_org_id[-12:].lower()}"
        )
        tenant = Tenant(
            slug=slug,
            name=icc_org.org_name,
            clerk_org_id=icc_org.clerk_org_id,
        )
        session.add(tenant)
        await session.flush()

    user = (
        await session.execute(
            select(User).where(User.clerk_user_id == claims.sub)
        )
    ).scalar_one_or_none()
    if user is None:
        # Just-in-time user provisioning. Email goes in `users.email`; founder
        # mapping comes from claims.founder_slug if present.
        founder_id: UUID | None = None
        if claims.founder_slug:
            f = (
                await session.execute(
                    select(Founder).where(
                        Founder.tenant_id == tenant.id,
                        Founder.slug == claims.founder_slug,
                    )
                )
            ).scalar_one_or_none()
            founder_id = f.id if f else None

        # Pick the role for the new user. If we already consulted ICC
        # above (because the tenant was JIT-created), reuse that role.
        # Otherwise consult ICC now so the user lands with the right role
        # even when their tenant existed before this rollout.
        if icc_org_role is None:
            icc_result_for_user = await check_identity_access(
                clerk_user_id=claims.sub,
                app_key=CAPTURE_APP_KEY,
                clerk_org_id=claims.tenant_org_id,
            )
            user_access = find_active_access_for_app(icc_result_for_user, CAPTURE_APP_KEY)
            if user_access is not None:
                icc_org_role = user_access[1].role
                icc_is_internal = user_access[0].is_internal_mactech_user
        role = _map_icc_role_to_capture_role(
            icc_org_role or "member", icc_is_internal
        )

        user = User(
            tenant_id=tenant.id,
            clerk_user_id=claims.sub,
            email=claims.raw.get("email", ""),
            full_name=claims.raw.get("name"),
            founder_id=founder_id,
            role=role,
        )
        session.add(user)
        await session.flush()

    founder: Founder | None = None
    if user.founder_id:
        founder = (
            await session.execute(
                select(Founder).where(Founder.id == user.founder_id)
            )
        ).scalar_one_or_none()
    elif claims.founder_slug:
        founder = (
            await session.execute(
                select(Founder).where(
                    Founder.tenant_id == tenant.id,
                    Founder.slug == claims.founder_slug,
                )
            )
        ).scalar_one_or_none()
        if founder is not None:
            user.founder_id = founder.id

    return tenant, user, founder


async def get_request_context(
    request: Request,
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(_bearer)],
) -> AsyncIterator[RequestContext]:
    """FastAPI dependency: verify Clerk token, open tenant-scoped session, yield context.

    Use as: `ctx: RequestContext = Depends(get_request_context)` on
    authenticated endpoints. The session is committed on exit; rollback
    happens automatically on exception.
    """
    if credentials is None or not credentials.credentials:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="missing bearer token"
        )

    claims = await _verify_clerk_jwt(credentials.credentials)

    # First open an unscoped tx purely to resolve tenant + user JIT, because
    # the Tenant lookup itself is on a non-scoped table. Then re-open a
    # tenant-scoped session for the request body. This is two transactions,
    # which is fine — JIT user provisioning is idempotent.
    from mactech_db import unscoped_session

    async with unscoped_session() as bootstrap:
        tenant, user, founder = await _resolve_tenant_and_user(claims, bootstrap)
        tenant_id = tenant.id
        user_id = user.id
        founder_id = founder.id if founder else None

    async with scoped_session(tenant_id) as session:
        # Re-fetch into the scoped session so caller sees attached objects.
        tenant_attached = (
            await session.execute(select(Tenant).where(Tenant.id == tenant_id))
        ).scalar_one()
        user_attached = (
            await session.execute(select(User).where(User.id == user_id))
        ).scalar_one()
        founder_attached: Founder | None = None
        if founder_id:
            founder_attached = (
                await session.execute(select(Founder).where(Founder.id == founder_id))
            ).scalar_one_or_none()
        request.state.tenant_id = tenant_id

        # Fire-and-forget capture.session.opened to the central Identity hub.
        # Throttled to once per Clerk user per process per hour. Errors are
        # swallowed inside send_audit_log so a hub outage cannot break auth.
        if _should_fire_audit_session(claims.sub):
            _fire_and_forget(
                send_audit_log(
                    {
                        "appKey": "capture",
                        "eventType": "capture.session.opened",
                        "eventCategory": "auth",
                        "action": "Opened MacTech Capture",
                        "actorClerkUserId": claims.sub,
                        "customerOrgClerkId": claims.tenant_org_id,
                        "actorEmail": user_attached.email,
                        "metadata": {"path": str(request.url.path)},
                    }
                )
            )

        # Pull this founder's Suite capability profile and project it onto their
        # founder card — title, bio, NAICS. Same fire-and-forget shape as the
        # audit event above and throttled the same way, but only for a user who
        # is actually a founder: a non-founder user has no card to update. The
        # task owns its own session (see sync_one_user_in_background) because
        # this request's session closes the moment the response is sent.
        if founder_id is not None and _should_sync_profile(claims.sub):
            _fire_and_forget(sync_one_user_in_background(str(tenant_id), str(user_id)))

        yield RequestContext(
            user=user_attached,
            tenant=tenant_attached,
            founder=founder_attached,
            claims=claims,
            session=session,
        )
