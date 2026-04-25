"""Library endpoints — capability statements + past performance.

Phase 2 Week 6 surfaces the read-only list of capability statements that
the founders are matching opportunities against. Past performance is a
later-phase table (Phase 2 Week 8) and currently empty; we still expose
the endpoint so the UI doesn't 404.
"""

from __future__ import annotations

from datetime import datetime
from typing import Annotated, Any
from uuid import UUID

from fastapi import APIRouter, Depends
from pydantic import BaseModel, ConfigDict
from sqlalchemy import select

from mactech_api.auth import RequestContext, get_request_context
from mactech_db.models import CapabilityStatement, Founder

router = APIRouter(tags=["library"])


class _Out(BaseModel):
    model_config = ConfigDict(from_attributes=True)


class CapabilityFounderRef(_Out):
    slug: str
    full_name: str
    pillar: str


class CapabilityStatementOut(_Out):
    id: str
    title: str
    summary: str
    related_naics: list[str]
    related_founders: list[CapabilityFounderRef]
    has_embedding: bool
    created_at: str
    updated_at: str


class CapabilityStatementsResponse(_Out):
    total: int
    items: list[CapabilityStatementOut]


@router.get("/capability-statements", response_model=CapabilityStatementsResponse)
async def list_capability_statements(
    ctx: Annotated[RequestContext, Depends(get_request_context)],
) -> CapabilityStatementsResponse:
    session = ctx.session
    tenant_id = ctx.tenant.id

    rows = (
        await session.execute(
            select(CapabilityStatement)
            .where(CapabilityStatement.tenant_id == tenant_id)
            .order_by(CapabilityStatement.title)
        )
    ).scalars().all()

    # Pull founders once for the related_founders join.
    founders_by_id: dict[UUID, Founder] = {
        f.id: f
        for f in (await session.execute(select(Founder))).scalars().all()
    }
    founders_by_slug: dict[str, Founder] = {f.slug: f for f in founders_by_id.values()}

    items: list[CapabilityStatementOut] = []
    # Detect embedding presence with a single follow-up query rather than
    # bringing the giant vector column into the ORM.
    has_emb_rows = await session.execute(
        select(CapabilityStatement.id).where(
            CapabilityStatement.tenant_id == tenant_id,
            # `embedding is not null` via raw text fragment
        )
    )
    embedded_ids = set()
    from sqlalchemy import text as _text
    embedded_rows = await session.execute(
        _text(
            "select id::text from capability_statements "
            "where tenant_id = :t and embedding is not null"
        ),
        {"t": str(tenant_id)},
    )
    embedded_ids = {row[0] for row in embedded_rows}

    for r in rows:
        related: list[CapabilityFounderRef] = []
        for entry in r.related_founders or []:
            slug: str | None = None
            if isinstance(entry, dict):
                slug = entry.get("slug")
            elif isinstance(entry, str):
                slug = entry
            if slug and slug in founders_by_slug:
                f = founders_by_slug[slug]
                related.append(
                    CapabilityFounderRef(
                        slug=f.slug, full_name=f.full_name, pillar=f.pillar
                    )
                )
        items.append(
            CapabilityStatementOut(
                id=str(r.id),
                title=r.title,
                summary=r.summary,
                related_naics=list(r.related_naics or []),
                related_founders=related,
                has_embedding=str(r.id) in embedded_ids,
                created_at=r.created_at.isoformat(),
                updated_at=r.updated_at.isoformat(),
            )
        )

    return CapabilityStatementsResponse(total=len(items), items=items)
