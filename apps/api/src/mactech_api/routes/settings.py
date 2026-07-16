"""Settings — saved searches, NAICS matrix, founder roster.

Read-only for Phase 2 Week 6. Editing comes when the capability /
saved-search admin UIs ship.
"""

from __future__ import annotations

import logging
from datetime import UTC, datetime
from datetime import date as _date
from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException
from mactech_db.models import Founder, FounderNaicsMatrix, NaicsCode, SavedSearch, User
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import select

from mactech_api.auth import RequestContext, get_request_context

log = logging.getLogger(__name__)

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


class FounderNaics(_Out):
    code: str
    title: str


class FounderOut(_Out):
    id: str
    slug: str
    full_name: str
    title: str
    pillar: str
    email: str | None
    digest_enabled: bool
    bio: str | None = None
    # This founder's own NAICS, strongest first. The tenant-wide `naics` matrix
    # below shows the same data by code; this shows it by person, which is what
    # a "who is this founder" card wants.
    naics: list[FounderNaics] = []
    # True when a signed-in Suite user is linked, so title/bio/NAICS arrive from
    # their GovCon Ops capability profile on sign-in. Drives the card's "Synced
    # from GovCon Ops" affordance.
    profile_linked: bool = False


class TenantOut(_Out):
    slug: str
    name: str
    plan: str
    uei: str | None
    cage_code: str | None
    clerk_org_id: str | None
    sprs_score: int | None = None
    sprs_max: int = 110
    sprs_assessment_date: str | None = None
    sprs_source_url: str | None = None
    sprs_synced_at: str | None = None


class SprsPatchRequest(BaseModel):
    """Manual SPRS override — used when Codex hasn't synced yet or the
    tenant wants to record a value pending Codex coming online."""

    sprs_score: int | None = Field(default=None, ge=0, le=200)
    sprs_max: int | None = Field(default=None, ge=1, le=200)
    sprs_assessment_date: str | None = None  # ISO YYYY-MM-DD
    sprs_source_url: str | None = Field(default=None, max_length=2000)


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
        await session.execute(
            select(Founder)
            .where(Founder.tenant_id == tenant_id)
            .order_by(Founder.full_name)
        )
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

    # Per-founder NAICS, built from the matrix rows already loaded above — no
    # extra query. Titles come from naics_rows (also already loaded); a matrix
    # row whose code isn't in the table is skipped rather than shown untitled.
    # Sorted by affinity desc to lead with the strongest match, matching the
    # /founders route and how the matrix routes opportunities.
    naics_title_by_code = {n.code: n.title for n in naics_rows}
    naics_by_founder_id: dict[Any, list[FounderNaics]] = {}
    for m in sorted(matrix_rows, key=lambda r: (-(r.affinity or 0), r.naics_code)):
        title = naics_title_by_code.get(m.naics_code)
        if title is None:
            continue
        naics_by_founder_id.setdefault(m.founder_id, []).append(
            FounderNaics(code=m.naics_code, title=title)
        )

    # Which founders a signed-in Suite user is linked to — the condition under
    # which the sign-in sync pulls their capability profile.
    linked_founder_ids = set(
        (
            await session.execute(
                select(User.founder_id).where(
                    User.tenant_id == tenant_id,
                    User.founder_id.is_not(None),
                    User.clerk_user_id.is_not(None),
                )
            )
        )
        .scalars()
        .all()
    )

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
            sprs_score=ctx.tenant.sprs_score,
            sprs_max=ctx.tenant.sprs_max or 110,
            sprs_assessment_date=(
                ctx.tenant.sprs_assessment_date.isoformat()
                if ctx.tenant.sprs_assessment_date
                else None
            ),
            sprs_source_url=ctx.tenant.sprs_source_url,
            sprs_synced_at=(
                ctx.tenant.sprs_synced_at.isoformat()
                if ctx.tenant.sprs_synced_at
                else None
            ),
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
                bio=f.bio,
                naics=naics_by_founder_id.get(f.id, []),
                profile_linked=f.id in linked_founder_ids,
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


@router.patch("/me/settings/sprs", response_model=TenantOut)
async def patch_sprs(
    body: SprsPatchRequest,
    ctx: Annotated[RequestContext, Depends(get_request_context)],
) -> TenantOut:
    """Manual SPRS override. Codex (codex.mactechsolutionsllc.com) is
    the authoritative source via the daily mactech.codex.refresh_sprs
    beat — but until Codex publishes the API, founders can record their
    score here. The next Codex sync will overwrite this."""
    tenant = ctx.tenant
    if body.sprs_score is not None:
        tenant.sprs_score = body.sprs_score
    if body.sprs_max is not None:
        tenant.sprs_max = body.sprs_max
    if body.sprs_assessment_date is not None:
        s = body.sprs_assessment_date.strip()
        if not s:
            tenant.sprs_assessment_date = None
        else:
            try:
                tenant.sprs_assessment_date = _date.fromisoformat(s[:10])
            except ValueError as exc:
                raise HTTPException(
                    status_code=400,
                    detail=f"sprs_assessment_date must be YYYY-MM-DD: {exc}",
                ) from exc
    if body.sprs_source_url is not None:
        tenant.sprs_source_url = (body.sprs_source_url.strip() or None)
    tenant.sprs_synced_at = datetime.now(UTC)
    await ctx.session.flush()
    return TenantOut(
        slug=tenant.slug,
        name=tenant.name,
        plan=tenant.plan,
        uei=tenant.uei,
        cage_code=tenant.cage_code,
        clerk_org_id=tenant.clerk_org_id,
        sprs_score=tenant.sprs_score,
        sprs_max=tenant.sprs_max or 110,
        sprs_assessment_date=(
            tenant.sprs_assessment_date.isoformat()
            if tenant.sprs_assessment_date
            else None
        ),
        sprs_source_url=tenant.sprs_source_url,
        sprs_synced_at=(
            tenant.sprs_synced_at.isoformat()
            if tenant.sprs_synced_at
            else None
        ),
    )
