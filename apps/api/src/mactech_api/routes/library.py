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

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from mactech_api.auth import RequestContext, get_request_context
from mactech_api.embed_helpers import embed_capability_inline
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
    keywords: list[str]
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
                keywords=list(r.keywords or []),
                related_naics=list(r.related_naics or []),
                related_founders=related,
                has_embedding=str(r.id) in embedded_ids,
                created_at=r.created_at.isoformat(),
                updated_at=r.updated_at.isoformat(),
            )
        )

    return CapabilityStatementsResponse(total=len(items), items=items)


# ── CRUD on capability statements ─────────────────────────────────────


class CreateCapabilityStatementRequest(BaseModel):
    title: str = Field(min_length=1, max_length=255)
    summary: str = Field(min_length=1)
    keywords: list[str] = Field(default_factory=list)
    related_naics: list[str] = Field(default_factory=list)
    related_founder_slugs: list[str] = Field(default_factory=list)


class UpdateCapabilityStatementRequest(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=255)
    summary: str | None = Field(default=None, min_length=1)
    keywords: list[str] | None = None
    related_naics: list[str] | None = None
    related_founder_slugs: list[str] | None = None


async def _resolve_founder_refs(
    session: Any, slugs: list[str]
) -> list[CapabilityFounderRef]:
    if not slugs:
        return []
    founders = (
        await session.execute(select(Founder).where(Founder.slug.in_(slugs)))
    ).scalars().all()
    by_slug = {f.slug: f for f in founders}
    out: list[CapabilityFounderRef] = []
    for slug in slugs:
        f = by_slug.get(slug)
        if f is not None:
            out.append(
                CapabilityFounderRef(
                    slug=f.slug, full_name=f.full_name, pillar=f.pillar
                )
            )
    return out


def _related_founders_payload(slugs: list[str]) -> list[dict[str, str]]:
    """Persist as the same JSONB shape the seed config writes:
    [{"slug": "patrick-caruso"}, ...].
    """
    return [{"slug": s} for s in slugs if s]


async def _to_out(
    cs: CapabilityStatement,
    session: Any,
    *,
    has_embedding: bool | None = None,
) -> CapabilityStatementOut:
    if has_embedding is None:
        from sqlalchemy import text as _text

        embed_check = (
            await session.execute(
                _text(
                    "select 1 from capability_statements "
                    "where id = :id and embedding is not null"
                ),
                {"id": str(cs.id)},
            )
        ).scalar_one_or_none()
        has_embedding = embed_check is not None
    slugs: list[str] = []
    for entry in cs.related_founders or []:
        if isinstance(entry, dict):
            slug = entry.get("slug")
            if isinstance(slug, str):
                slugs.append(slug)
        elif isinstance(entry, str):
            slugs.append(entry)
    related = await _resolve_founder_refs(session, slugs)
    return CapabilityStatementOut(
        id=str(cs.id),
        title=cs.title,
        summary=cs.summary,
        keywords=list(cs.keywords or []),
        related_naics=list(cs.related_naics or []),
        related_founders=related,
        has_embedding=bool(has_embedding),
        created_at=cs.created_at.isoformat(),
        updated_at=cs.updated_at.isoformat(),
    )


@router.get("/capability-statements/{cs_id}", response_model=CapabilityStatementOut)
async def get_capability_statement(
    cs_id: UUID,
    ctx: Annotated[RequestContext, Depends(get_request_context)],
) -> CapabilityStatementOut:
    cs = (
        await ctx.session.execute(
            select(CapabilityStatement).where(
                CapabilityStatement.id == cs_id,
                CapabilityStatement.tenant_id == ctx.tenant.id,
            )
        )
    ).scalar_one_or_none()
    if cs is None:
        raise HTTPException(status_code=404, detail="capability statement not found")
    return await _to_out(cs, ctx.session)


@router.post(
    "/capability-statements",
    response_model=CapabilityStatementOut,
    status_code=status.HTTP_201_CREATED,
)
async def create_capability_statement(
    body: CreateCapabilityStatementRequest,
    ctx: Annotated[RequestContext, Depends(get_request_context)],
) -> CapabilityStatementOut:
    cs = CapabilityStatement(
        tenant_id=ctx.tenant.id,
        title=body.title.strip(),
        summary=body.summary.strip(),
        keywords=body.keywords or None,
        related_naics=body.related_naics or None,
        related_founders=_related_founders_payload(body.related_founder_slugs)
        if body.related_founder_slugs
        else None,
    )
    ctx.session.add(cs)
    try:
        await ctx.session.flush()
    except IntegrityError:
        await ctx.session.rollback()
        raise HTTPException(
            status_code=409,
            detail=(
                f"a capability statement titled '{body.title}' already exists "
                "in this tenant. Pick a unique title."
            ),
        ) from None
    # Embed inline so the new capability is immediately live in opportunity
    # scoring. Fail-soft: if Voyage is unavailable, the worker picks it up
    # on its next 15-min tick.
    has_embedding = await embed_capability_inline(
        ctx.session,
        capability_id=str(cs.id),
        title=cs.title,
        summary=cs.summary,
    )
    return await _to_out(cs, ctx.session, has_embedding=has_embedding)


@router.patch(
    "/capability-statements/{cs_id}", response_model=CapabilityStatementOut
)
async def update_capability_statement(
    cs_id: UUID,
    body: UpdateCapabilityStatementRequest,
    ctx: Annotated[RequestContext, Depends(get_request_context)],
) -> CapabilityStatementOut:
    cs = (
        await ctx.session.execute(
            select(CapabilityStatement).where(
                CapabilityStatement.id == cs_id,
                CapabilityStatement.tenant_id == ctx.tenant.id,
            )
        )
    ).scalar_one_or_none()
    if cs is None:
        raise HTTPException(status_code=404, detail="capability statement not found")

    summary_changed = False
    if body.title is not None:
        cs.title = body.title.strip()
    if body.summary is not None:
        cs.summary = body.summary.strip()
        summary_changed = True
    if body.keywords is not None:
        cs.keywords = body.keywords or None
    if body.related_naics is not None:
        cs.related_naics = body.related_naics or None
    if body.related_founder_slugs is not None:
        cs.related_founders = (
            _related_founders_payload(body.related_founder_slugs)
            if body.related_founder_slugs
            else None
        )

    try:
        await ctx.session.flush()
    except IntegrityError:
        await ctx.session.rollback()
        raise HTTPException(
            status_code=409,
            detail="another capability statement with that title already exists",
        ) from None

    # If the summary text changed, the existing embedding is stale. Embed
    # inline; if that fails, leave the embedding null so the worker
    # re-embeds on its next tick.
    if summary_changed:
        from sqlalchemy import text as _text

        await ctx.session.execute(
            _text(
                "update capability_statements set embedding = null "
                "where id = :id"
            ),
            {"id": str(cs.id)},
        )
        await embed_capability_inline(
            ctx.session,
            capability_id=str(cs.id),
            title=cs.title,
            summary=cs.summary,
        )
    return await _to_out(cs, ctx.session)


@router.delete(
    "/capability-statements/{cs_id}", status_code=status.HTTP_204_NO_CONTENT
)
async def delete_capability_statement(
    cs_id: UUID,
    ctx: Annotated[RequestContext, Depends(get_request_context)],
) -> None:
    cs = (
        await ctx.session.execute(
            select(CapabilityStatement).where(
                CapabilityStatement.id == cs_id,
                CapabilityStatement.tenant_id == ctx.tenant.id,
            )
        )
    ).scalar_one_or_none()
    if cs is None:
        raise HTTPException(status_code=404, detail="capability statement not found")
    await ctx.session.delete(cs)
    await ctx.session.flush()
