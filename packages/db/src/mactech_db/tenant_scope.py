"""Tenant-scoped DB sessions.

Phase 1–3 reality check: cross-tenant leak risk is 0 because there is
exactly one tenant (MacTech). The application layer filters by tenant_id
on every query. RLS migration is deferred to Phase 4 when external
customers actually create the risk — see migration 0006 docstring.

This module ships now anyway because the API auth dependency wants a
tenant-scoped session interface that doesn't change shape when RLS
activates. Today `scoped_session` just SETs `app.tenant_id` (harmless)
and returns a session; in Phase 4, the same call site enforces RLS.
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from mactech_db.session import async_session_factory


@asynccontextmanager
async def scoped_session(tenant_id: UUID | str) -> AsyncIterator[AsyncSession]:
    """Open a tenant-scoped session. Yields a session inside an open
    transaction; commits on exit, rolls back on error.

    Sets `app.tenant_id` for the transaction so when RLS activates in
    Phase 4 nothing at the call site needs to change.
    """
    factory = async_session_factory()
    async with factory() as session:
        async with session.begin():
            await session.execute(
                text("SET LOCAL app.tenant_id = :t").bindparams(t=str(tenant_id))
            )
            yield session


@asynccontextmanager
async def unscoped_session() -> AsyncIterator[AsyncSession]:
    """Open a session for shared-data-only work (no tenant context).

    Use for opportunities_raw, ingestion_state, awards_history,
    exclusions_cache, opportunities_enriched, naics_codes, founders,
    tenants. These tables are not tenant-scoped.
    """
    factory = async_session_factory()
    async with factory() as session:
        async with session.begin():
            yield session
