"""Founder CRUD.

Phase 3 Week 14 (UX Sprint 9). Founders were seed-only since Phase 1;
this exposes the same Add/Edit/Delete shape as past performance and
capability statements so the user can manage their team in /settings.

Note on multi-tenancy: founders aren't tenant-scoped at the schema
level (no `tenant_id` column). This is a known limitation tracked for
a future refactor. For now the API treats founders as visible to every
authenticated user; for MacTech this is correct.
"""

from __future__ import annotations

import logging
import re
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from mactech_db.models import Founder
from mactech_db.models.founder import FounderNaicsMatrix
from mactech_db.models.naics import NaicsCode
from mactech_db.models.user import User
from pydantic import BaseModel, ConfigDict, EmailStr, Field
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from mactech_api.auth import RequestContext, get_request_context

log = logging.getLogger(__name__)
router = APIRouter(tags=["founders"])

VALID_PILLARS = {"security", "infrastructure", "quality", "governance", "other"}


class _Out(BaseModel):
    model_config = ConfigDict(from_attributes=True)


class FounderNaics(_Out):
    code: str
    title: str


class FounderOut(_Out):
    id: str
    slug: str
    full_name: str
    title: str
    pillar: str
    bio: str | None
    email: str | None
    digest_enabled: bool
    created_at: str
    # NAICS the founder is matched to, most relevant first. Includes both
    # hand-curated codes and codes projected from the person's GovCon Ops
    # capability profile — the card doesn't distinguish them because the
    # affinity/tier live in the matrix, not here.
    naics: list[FounderNaics] = []
    # True when a signed-in Suite user is linked to this founder, i.e. their
    # capability profile flows in on sign-in. Drives the "Synced from GovCon
    # Ops" affordance so a viewer knows title/bio/NAICS may be managed
    # elsewhere, not just typed here.
    profile_linked: bool = False


class FoundersList(_Out):
    total: int
    items: list[FounderOut]


class CreateFounderRequest(BaseModel):
    full_name: str = Field(min_length=1, max_length=255)
    title: str = Field(min_length=1, max_length=255)
    pillar: str = "other"
    email: EmailStr | None = None
    bio: str | None = None
    digest_enabled: bool = True
    slug: str | None = Field(default=None, max_length=64)


class UpdateFounderRequest(BaseModel):
    full_name: str | None = Field(default=None, min_length=1, max_length=255)
    title: str | None = Field(default=None, min_length=1, max_length=255)
    pillar: str | None = None
    email: EmailStr | None = None
    clear_email: bool = False
    bio: str | None = None
    digest_enabled: bool | None = None


_SLUG_RE = re.compile(r"[^a-z0-9-]+")


def _slugify(name: str) -> str:
    s = name.strip().lower().replace(" ", "-")
    s = _SLUG_RE.sub("", s)
    s = re.sub(r"-+", "-", s).strip("-")
    return s[:64] or "founder"


def _validate_pillar(p: str) -> str:
    if p not in VALID_PILLARS:
        raise HTTPException(
            status_code=400,
            detail=f"invalid pillar '{p}'. Allowed: {sorted(VALID_PILLARS)}",
        )
    return p


def _to_out(
    f: Founder,
    *,
    naics: list[FounderNaics] | None = None,
    profile_linked: bool = False,
) -> FounderOut:
    return FounderOut(
        id=str(f.id),
        slug=f.slug,
        full_name=f.full_name,
        title=f.title,
        pillar=f.pillar,
        bio=f.bio,
        email=f.email,
        digest_enabled=f.digest_enabled,
        created_at=f.created_at.isoformat(),
        naics=naics or [],
        profile_linked=profile_linked,
    )


async def _naics_by_founder(session, founder_ids: list[UUID]) -> dict[UUID, list[FounderNaics]]:
    """One query for the whole page's NAICS, joined to titles. Avoids N+1.

    Ordered by affinity desc so the strongest matches lead — the same ordering
    the matrix routes opportunities on.
    """
    if not founder_ids:
        return {}
    rows = (
        await session.execute(
            select(
                FounderNaicsMatrix.founder_id,
                FounderNaicsMatrix.naics_code,
                NaicsCode.title,
            )
            .join(NaicsCode, NaicsCode.code == FounderNaicsMatrix.naics_code)
            .where(FounderNaicsMatrix.founder_id.in_(founder_ids))
            .order_by(FounderNaicsMatrix.affinity.desc(), FounderNaicsMatrix.naics_code)
        )
    ).all()
    out: dict[UUID, list[FounderNaics]] = {}
    for founder_id, code, title in rows:
        out.setdefault(founder_id, []).append(FounderNaics(code=code, title=title))
    return out


async def _linked_founder_ids(session, founder_ids: list[UUID]) -> set[UUID]:
    """Which of these founders a signed-in Suite user points at.

    A founder is 'profile-linked' when a User with a clerk_user_id has
    founder_id == it — that is exactly the condition under which the sign-in
    sync pulls their capability profile. One query for the page.
    """
    if not founder_ids:
        return set()
    rows = (
        await session.execute(
            select(User.founder_id)
            .where(User.founder_id.in_(founder_ids), User.clerk_user_id.is_not(None))
            .distinct()
        )
    ).scalars().all()
    return set(rows)


@router.get("/founders", response_model=FoundersList)
async def list_founders(
    ctx: Annotated[RequestContext, Depends(get_request_context)],
) -> FoundersList:
    rows = (
        await ctx.session.execute(
            select(Founder)
            .where(Founder.tenant_id == ctx.tenant.id)
            .order_by(Founder.full_name)
        )
    ).scalars().all()
    ids = [r.id for r in rows]
    naics = await _naics_by_founder(ctx.session, ids)
    linked = await _linked_founder_ids(ctx.session, ids)
    return FoundersList(
        total=len(rows),
        items=[
            _to_out(r, naics=naics.get(r.id), profile_linked=r.id in linked) for r in rows
        ],
    )


@router.get("/founders/{founder_id}", response_model=FounderOut)
async def get_founder(
    founder_id: UUID,
    ctx: Annotated[RequestContext, Depends(get_request_context)],
) -> FounderOut:
    f = (
        await ctx.session.execute(
            select(Founder).where(
                Founder.id == founder_id,
                Founder.tenant_id == ctx.tenant.id,
            )
        )
    ).scalar_one_or_none()
    if f is None:
        raise HTTPException(status_code=404, detail="founder not found")
    naics = await _naics_by_founder(ctx.session, [f.id])
    linked = await _linked_founder_ids(ctx.session, [f.id])
    return _to_out(f, naics=naics.get(f.id), profile_linked=f.id in linked)


async def _unique_slug(
    session, tenant_id: UUID, base: str, exclude_id: UUID | None = None
) -> str:
    """Pick a slug not yet used in this tenant. If `base` is taken,
    append -2, -3, etc."""
    slug = base
    suffix = 1
    while True:
        stmt = select(Founder).where(
            Founder.tenant_id == tenant_id, Founder.slug == slug
        )
        if exclude_id is not None:
            stmt = stmt.where(Founder.id != exclude_id)
        existing = (await session.execute(stmt)).scalar_one_or_none()
        if existing is None:
            return slug
        suffix += 1
        slug = f"{base}-{suffix}"
        if suffix > 50:
            raise HTTPException(
                status_code=409,
                detail="couldn't generate a unique founder slug after 50 tries",
            )


@router.post(
    "/founders",
    response_model=FounderOut,
    status_code=status.HTTP_201_CREATED,
)
async def create_founder(
    body: CreateFounderRequest,
    ctx: Annotated[RequestContext, Depends(get_request_context)],
) -> FounderOut:
    _validate_pillar(body.pillar)
    base_slug = body.slug.strip().lower() if body.slug else _slugify(body.full_name)
    slug = await _unique_slug(ctx.session, ctx.tenant.id, base_slug)

    f = Founder(
        tenant_id=ctx.tenant.id,
        slug=slug,
        full_name=body.full_name.strip(),
        title=body.title.strip(),
        pillar=body.pillar,
        bio=body.bio.strip() if body.bio else None,
        email=str(body.email) if body.email else None,
        digest_enabled=body.digest_enabled,
    )
    ctx.session.add(f)
    try:
        await ctx.session.flush()
    except IntegrityError:
        await ctx.session.rollback()
        raise HTTPException(
            status_code=409,
            detail="couldn't create founder (slug or email collision).",
        ) from None
    return _to_out(f)


@router.patch("/founders/{founder_id}", response_model=FounderOut)
async def update_founder(
    founder_id: UUID,
    body: UpdateFounderRequest,
    ctx: Annotated[RequestContext, Depends(get_request_context)],
) -> FounderOut:
    f = (
        await ctx.session.execute(
            select(Founder).where(
                Founder.id == founder_id,
                Founder.tenant_id == ctx.tenant.id,
            )
        )
    ).scalar_one_or_none()
    if f is None:
        raise HTTPException(status_code=404, detail="founder not found")

    if body.full_name is not None:
        f.full_name = body.full_name.strip()
    if body.title is not None:
        f.title = body.title.strip()
    if body.pillar is not None:
        _validate_pillar(body.pillar)
        f.pillar = body.pillar
    if body.bio is not None:
        f.bio = body.bio.strip() or None
    if body.clear_email:
        f.email = None
    elif body.email is not None:
        f.email = str(body.email)
    if body.digest_enabled is not None:
        f.digest_enabled = body.digest_enabled

    await ctx.session.flush()
    return _to_out(f)


@router.delete(
    "/founders/{founder_id}", status_code=status.HTTP_204_NO_CONTENT
)
async def delete_founder(
    founder_id: UUID,
    ctx: Annotated[RequestContext, Depends(get_request_context)],
) -> None:
    f = (
        await ctx.session.execute(
            select(Founder).where(
                Founder.id == founder_id,
                Founder.tenant_id == ctx.tenant.id,
            )
        )
    ).scalar_one_or_none()
    if f is None:
        raise HTTPException(status_code=404, detail="founder not found")
    await ctx.session.delete(f)
    await ctx.session.flush()
