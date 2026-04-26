"""Settings — saved searches, NAICS matrix, founder roster.

Read-only for Phase 2 Week 6. Editing comes when the capability /
saved-search admin UIs ship.
"""

from __future__ import annotations

from typing import Annotated, Any

from fastapi import APIRouter, Depends
from pydantic import BaseModel, ConfigDict
from sqlalchemy import select

from mactech_api.auth import RequestContext, get_request_context
from mactech_db.models import Founder, FounderNaicsMatrix, NaicsCode, SavedSearch

router = APIRouter(tags=["settings"])


class _Out(BaseModel):
    model_config = ConfigDict(from_attributes=True)


class SavedSearchOut(_Out):
    id: str
    name: str
    owner_founder_slug: str | None
    alert_threshold: int
    alert_cadence: str
    alert_channels: list[str]
    naics_codes: list[str]
    keywords: list[str]
    set_asides: list[str]
    created_at: str


class NaicsRow(_Out):
    code: str
    title: str
    tier: str | None
    founder_slugs: list[str]


class FounderOut(_Out):
    id: str
    slug: str
    full_name: str
    title: str
    pillar: str
    email: str | None
    digest_enabled: bool


class TenantOut(_Out):
    slug: str
    name: str
    plan: str
    uei: str | None
    cage_code: str | None
    clerk_org_id: str | None


class SettingsResponse(_Out):
    tenant: TenantOut
    founders: list[FounderOut]
    naics: list[NaicsRow]
    saved_searches: list[SavedSearchOut]


@router.get("/me/settings", response_model=SettingsResponse)
async def get_settings(
    ctx: Annotated[RequestContext, Depends(get_request_context)],
) -> SettingsResponse:
    session = ctx.session
    tenant_id = ctx.tenant.id

    founders = (
        await session.execute(select(Founder).order_by(Founder.full_name))
    ).scalars().all()
    founders_by_id = {f.id: f for f in founders}

    naics_rows = (
        await session.execute(
            select(NaicsCode).order_by(NaicsCode.mactech_tier.desc(), NaicsCode.code)
        )
    ).scalars().all()
    matrix_rows = (
        await session.execute(select(FounderNaicsMatrix))
    ).scalars().all()
    naics_to_founder_slugs: dict[str, list[str]] = {}
    for m in matrix_rows:
        slug = founders_by_id.get(m.founder_id)
        if slug is None:
            continue
        naics_to_founder_slugs.setdefault(m.naics_code, []).append(slug.slug)

    saved = (
        await session.execute(
            select(SavedSearch)
            .where(SavedSearch.tenant_id == tenant_id)
            .order_by(SavedSearch.name)
        )
    ).scalars().all()

    saved_out: list[SavedSearchOut] = []
    for s in saved:
        owner_slug = None
        if s.owner_founder_id and s.owner_founder_id in founders_by_id:
            owner_slug = founders_by_id[s.owner_founder_id].slug
        f: dict[str, Any] = s.filters or {}
        ch = s.alert_channels or []
        if isinstance(ch, dict):
            ch = []  # tolerate bad shape
        saved_out.append(
            SavedSearchOut(
                id=str(s.id),
                name=s.name,
                owner_founder_slug=owner_slug,
                alert_threshold=s.alert_threshold,
                alert_cadence=s.alert_cadence,
                alert_channels=list(ch),
                naics_codes=[str(n) for n in (f.get("naics") or [])],
                keywords=list(f.get("keywords") or []),
                set_asides=list(f.get("set_asides") or []),
                created_at=s.created_at.isoformat(),
            )
        )

    return SettingsResponse(
        tenant=TenantOut(
            slug=ctx.tenant.slug,
            name=ctx.tenant.name,
            plan=ctx.tenant.plan,
            uei=ctx.tenant.uei,
            cage_code=ctx.tenant.cage_code,
            clerk_org_id=ctx.tenant.clerk_org_id,
        ),
        founders=[
            FounderOut(
                id=str(f.id),
                slug=f.slug,
                full_name=f.full_name,
                title=f.title,
                pillar=f.pillar,
                email=f.email,
                digest_enabled=f.digest_enabled,
            )
            for f in founders
        ],
        naics=[
            NaicsRow(
                code=n.code,
                title=n.title,
                tier=n.mactech_tier,
                founder_slugs=naics_to_founder_slugs.get(n.code, []),
            )
            for n in naics_rows
        ],
        saved_searches=saved_out,
    )
