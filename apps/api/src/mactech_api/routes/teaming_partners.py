"""Teaming partners catalogue API.

Phase 2 Week 8. Tenant-scoped CRUD over the firm's relationship roster
of primes/subs MacTech might team with on multi-vendor pursuits.

Endpoints:
  GET    /teaming-partners              list (active first, then inactive)
  GET    /teaming-partners/{id}         single record
  POST   /teaming-partners              create
  PATCH  /teaming-partners/{id}         partial update (incl. status flip)
  DELETE /teaming-partners/{id}         remove
"""

from __future__ import annotations

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from mactech_db.models import TeamingPartner
from pydantic import BaseModel, ConfigDict, EmailStr, Field
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from mactech_api.auth import RequestContext, get_request_context

router = APIRouter(tags=["teaming-partners"])

PARTNER_STATUSES = ("active", "inactive")


class _Out(BaseModel):
    model_config = ConfigDict(from_attributes=True)


class TeamingPartnerOut(_Out):
    id: str
    name: str
    uei: str | None
    cage_code: str | None
    capabilities: list[str]
    naics_codes: list[str]
    set_aside_certifications: list[str]
    contact_name: str | None
    contact_email: str | None
    notes: str | None
    status: str
    created_at: str
    updated_at: str


class TeamingPartnerList(_Out):
    total: int
    active_count: int
    items: list[TeamingPartnerOut]


class CreateTeamingPartnerRequest(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    uei: str | None = Field(default=None, max_length=16)
    cage_code: str | None = Field(default=None, max_length=8)
    capabilities: list[str] = Field(default_factory=list)
    naics_codes: list[str] = Field(default_factory=list)
    set_aside_certifications: list[str] = Field(default_factory=list)
    contact_name: str | None = Field(default=None, max_length=255)
    contact_email: EmailStr | None = None
    notes: str | None = None
    status: str = "active"


class UpdateTeamingPartnerRequest(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=255)
    uei: str | None = None
    cage_code: str | None = None
    capabilities: list[str] | None = None
    naics_codes: list[str] | None = None
    set_aside_certifications: list[str] | None = None
    contact_name: str | None = None
    contact_email: EmailStr | None = None
    clear_contact_email: bool = False
    notes: str | None = None
    status: str | None = None


def _validate_status(status: str) -> str:
    if status not in PARTNER_STATUSES:
        raise HTTPException(
            status_code=400,
            detail=f"invalid status '{status}'. Allowed: {list(PARTNER_STATUSES)}",
        )
    return status


def _to_out(p: TeamingPartner) -> TeamingPartnerOut:
    return TeamingPartnerOut(
        id=str(p.id),
        name=p.name,
        uei=p.uei,
        cage_code=p.cage_code,
        capabilities=p.capabilities or [],
        naics_codes=p.naics_codes or [],
        set_aside_certifications=p.set_aside_certifications or [],
        contact_name=p.contact_name,
        contact_email=p.contact_email,
        notes=p.notes,
        status=p.status,
        created_at=p.created_at.isoformat(),
        updated_at=p.updated_at.isoformat(),
    )


@router.get("/teaming-partners", response_model=TeamingPartnerList)
async def list_teaming_partners(
    ctx: Annotated[RequestContext, Depends(get_request_context)],
) -> TeamingPartnerList:
    rows = (
        (
            await ctx.session.execute(
                select(TeamingPartner)
                .where(TeamingPartner.tenant_id == ctx.tenant.id)
                .order_by(
                    # active first
                    TeamingPartner.status,
                    TeamingPartner.name,
                )
            )
        )
        .scalars()
        .all()
    )
    active_count = sum(1 for r in rows if r.status == "active")
    return TeamingPartnerList(
        total=len(rows),
        active_count=active_count,
        items=[_to_out(r) for r in rows],
    )


@router.get("/teaming-partners/{partner_id}", response_model=TeamingPartnerOut)
async def get_teaming_partner(
    partner_id: UUID,
    ctx: Annotated[RequestContext, Depends(get_request_context)],
) -> TeamingPartnerOut:
    p = (
        await ctx.session.execute(
            select(TeamingPartner).where(
                TeamingPartner.id == partner_id,
                TeamingPartner.tenant_id == ctx.tenant.id,
            )
        )
    ).scalar_one_or_none()
    if p is None:
        raise HTTPException(status_code=404, detail="teaming partner not found")
    return _to_out(p)


@router.post(
    "/teaming-partners",
    response_model=TeamingPartnerOut,
    status_code=status.HTTP_201_CREATED,
)
async def create_teaming_partner(
    body: CreateTeamingPartnerRequest,
    ctx: Annotated[RequestContext, Depends(get_request_context)],
) -> TeamingPartnerOut:
    _validate_status(body.status)

    p = TeamingPartner(
        tenant_id=ctx.tenant.id,
        name=body.name.strip(),
        uei=body.uei,
        cage_code=body.cage_code,
        capabilities=body.capabilities or None,
        naics_codes=body.naics_codes or None,
        set_aside_certifications=body.set_aside_certifications or None,
        contact_name=body.contact_name,
        contact_email=str(body.contact_email) if body.contact_email else None,
        notes=body.notes,
        status=body.status,
    )
    ctx.session.add(p)
    try:
        await ctx.session.flush()
    except IntegrityError:
        await ctx.session.rollback()
        raise HTTPException(
            status_code=409,
            detail=f"a teaming partner named '{body.name}' already exists",
        ) from None
    return _to_out(p)


@router.patch("/teaming-partners/{partner_id}", response_model=TeamingPartnerOut)
async def update_teaming_partner(
    partner_id: UUID,
    body: UpdateTeamingPartnerRequest,
    ctx: Annotated[RequestContext, Depends(get_request_context)],
) -> TeamingPartnerOut:
    p = (
        await ctx.session.execute(
            select(TeamingPartner).where(
                TeamingPartner.id == partner_id,
                TeamingPartner.tenant_id == ctx.tenant.id,
            )
        )
    ).scalar_one_or_none()
    if p is None:
        raise HTTPException(status_code=404, detail="teaming partner not found")

    if body.name is not None:
        p.name = body.name.strip()
    if body.uei is not None:
        p.uei = body.uei
    if body.cage_code is not None:
        p.cage_code = body.cage_code
    if body.capabilities is not None:
        p.capabilities = body.capabilities or None
    if body.naics_codes is not None:
        p.naics_codes = body.naics_codes or None
    if body.set_aside_certifications is not None:
        p.set_aside_certifications = body.set_aside_certifications or None
    if body.contact_name is not None:
        p.contact_name = body.contact_name
    if body.clear_contact_email:
        p.contact_email = None
    elif body.contact_email is not None:
        p.contact_email = str(body.contact_email)
    if body.notes is not None:
        p.notes = body.notes
    if body.status is not None:
        _validate_status(body.status)
        p.status = body.status

    try:
        await ctx.session.flush()
    except IntegrityError:
        await ctx.session.rollback()
        raise HTTPException(
            status_code=409,
            detail="another teaming partner with that name already exists",
        ) from None
    return _to_out(p)


@router.delete("/teaming-partners/{partner_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_teaming_partner(
    partner_id: UUID,
    ctx: Annotated[RequestContext, Depends(get_request_context)],
) -> None:
    p = (
        await ctx.session.execute(
            select(TeamingPartner).where(
                TeamingPartner.id == partner_id,
                TeamingPartner.tenant_id == ctx.tenant.id,
            )
        )
    ).scalar_one_or_none()
    if p is None:
        raise HTTPException(status_code=404, detail="teaming partner not found")

    await ctx.session.delete(p)
    await ctx.session.flush()
