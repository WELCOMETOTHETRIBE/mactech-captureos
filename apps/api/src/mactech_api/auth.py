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

import httpx
import jwt
from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jwt import PyJWKClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from mactech_api.mactech_audit_client import send_audit_log
from mactech_db import scoped_session
from mactech_db.models import Founder, Tenant, User

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
    if tenant is None:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"no MacTech tenant linked to Clerk org {claims.tenant_org_id}",
        )

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
        user = User(
            tenant_id=tenant.id,
            clerk_user_id=claims.sub,
            email=claims.raw.get("email", ""),
            full_name=claims.raw.get("name"),
            founder_id=founder_id,
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
            asyncio.create_task(
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

        yield RequestContext(
            user=user_attached,
            tenant=tenant_attached,
            founder=founder_attached,
            claims=claims,
            session=session,
        )
