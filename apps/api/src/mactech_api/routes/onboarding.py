"""Onboarding endpoints — SAM Entity lookup + tenant identity bootstrap.

Phase 3 Week 14 (UX Sprint 8). The /onboarding wizard hits these from
the web layer to:

  GET  /onboarding/sam-entity/{uei}    SAM.gov Entity API lookup
  POST /me/onboarding/firm-details     persist UEI/CAGE/set-asides
  POST /me/onboarding/complete         set onboarding_completed_at
  POST /me/onboarding/reset            null onboarding_completed_at (admin)

Onboarding is opt-in: the dashboard surfaces a "Finish setup" banner
while `tenant.onboarding_completed_at` is null. Routes are not gated
on completion — users can browse the app while the banner persists.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, ConfigDict, Field

from mactech_api.auth import RequestContext, get_request_context
from mactech_api.settings import settings
from mactech_integrations.sam_gov import (
    EntityProfile,
    SamEntityClient,
    SamEntityError,
    SamEntityNotFoundError,
    SamEntityRateLimitError,
)

log = logging.getLogger(__name__)
router = APIRouter(tags=["onboarding"])


class _Out(BaseModel):
    model_config = ConfigDict(from_attributes=True)


class SamEntityOut(_Out):
    uei: str
    cage_code: str | None
    legal_business_name: str | None
    dba_name: str | None
    registration_status: str | None
    registration_date: str | None
    expiration_date: str | None
    physical_address_city: str | None
    physical_address_state: str | None
    physical_address_country: str | None
    primary_naics: str | None
    naics_codes: list[str]
    business_types_raw: list[str]
    set_aside_short_codes: list[str]
    pop_email: str | None
    pop_first_name: str | None
    pop_last_name: str | None
    pop_title: str | None


class FirmDetailsRequest(BaseModel):
    uei: str | None = Field(default=None, max_length=16)
    cage_code: str | None = Field(default=None, max_length=8)
    legal_name: str | None = Field(default=None, max_length=255)
    set_aside_certifications: list[str] = Field(default_factory=list)


class TenantHeaderOut(_Out):
    id: str
    slug: str
    name: str
    plan: str
    uei: str | None
    cage_code: str | None
    set_aside_certifications: list[str]
    onboarding_completed_at: str | None


def _profile_to_out(p: EntityProfile) -> SamEntityOut:
    return SamEntityOut(
        uei=p.uei,
        cage_code=p.cage_code,
        legal_business_name=p.legal_business_name,
        dba_name=p.dba_name,
        registration_status=p.registration_status,
        registration_date=p.registration_date,
        expiration_date=p.expiration_date,
        physical_address_city=p.physical_address_city,
        physical_address_state=p.physical_address_state,
        physical_address_country=p.physical_address_country,
        primary_naics=p.primary_naics,
        naics_codes=p.naics_codes,
        business_types_raw=p.business_types_raw,
        set_aside_short_codes=p.set_aside_short_codes,
        pop_email=p.pop_email,
        pop_first_name=p.pop_first_name,
        pop_last_name=p.pop_last_name,
        pop_title=p.pop_title,
    )


def _tenant_to_out(t) -> TenantHeaderOut:
    return TenantHeaderOut(
        id=str(t.id),
        slug=t.slug,
        name=t.name,
        plan=t.plan,
        uei=t.uei,
        cage_code=t.cage_code,
        set_aside_certifications=list(t.set_aside_certifications or []),
        onboarding_completed_at=(
            t.onboarding_completed_at.isoformat()
            if t.onboarding_completed_at
            else None
        ),
    )


@router.get(
    "/onboarding/sam-entity/{uei}",
    response_model=SamEntityOut,
)
async def sam_entity_lookup(
    uei: str,
    ctx: Annotated[RequestContext, Depends(get_request_context)],
) -> SamEntityOut:
    """Public-facing SAM.gov Entity API lookup. Authenticated so the
    SAM API key never leaves the server, and so we can rate-limit per
    tenant later.
    """
    if not settings.sam_api_key:
        raise HTTPException(
            status_code=503,
            detail="SAM_API_KEY not configured on the API service.",
        )
    uei = uei.strip().upper()
    if len(uei) < 6:
        raise HTTPException(status_code=400, detail="UEI is too short")

    try:
        async with SamEntityClient(settings.sam_api_key) as client:
            profile = await client.lookup_uei(uei)
    except SamEntityNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except SamEntityRateLimitError as exc:
        raise HTTPException(
            status_code=503,
            detail=f"SAM rate-limited the lookup: {exc}. Try again in a minute.",
        ) from exc
    except SamEntityError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    except Exception as exc:
        log.exception("sam entity lookup failed: %s", exc)
        raise HTTPException(
            status_code=502,
            detail=f"SAM lookup failed: {exc.__class__.__name__}",
        ) from exc

    # Suppress unused-name (tenant context preserved for future per-tenant
    # rate limits + audit).
    _ = ctx.tenant
    return _profile_to_out(profile)


@router.post(
    "/me/onboarding/firm-details",
    response_model=TenantHeaderOut,
)
async def save_firm_details(
    body: FirmDetailsRequest,
    ctx: Annotated[RequestContext, Depends(get_request_context)],
) -> TenantHeaderOut:
    """Save UEI / CAGE / legal name / set-aside certifications.

    Idempotent: each PATCH-style update; null inputs preserve existing
    values. Doesn't flip onboarding_completed_at — that's a separate
    explicit step so partial saves don't dismiss the banner.
    """
    tenant = ctx.tenant

    if body.uei is not None:
        uei = body.uei.strip().upper() or None
        if uei and len(uei) > 16:
            raise HTTPException(status_code=400, detail="UEI too long")
        tenant.uei = uei
    if body.cage_code is not None:
        cage = body.cage_code.strip().upper() or None
        if cage and len(cage) > 8:
            raise HTTPException(status_code=400, detail="CAGE too long")
        tenant.cage_code = cage
    if body.legal_name is not None:
        ln = body.legal_name.strip()
        if ln:
            tenant.name = ln[:255]
    # Always overwrite the certifications list — empty list means "I
    # don't have any" which is a real state.
    tenant.set_aside_certifications = body.set_aside_certifications or None

    await ctx.session.flush()
    return _tenant_to_out(tenant)


@router.post(
    "/me/onboarding/complete",
    response_model=TenantHeaderOut,
)
async def complete_onboarding(
    ctx: Annotated[RequestContext, Depends(get_request_context)],
) -> TenantHeaderOut:
    tenant = ctx.tenant
    tenant.onboarding_completed_at = datetime.now(timezone.utc)
    await ctx.session.flush()
    return _tenant_to_out(tenant)


@router.post(
    "/me/onboarding/reset",
    response_model=TenantHeaderOut,
    status_code=status.HTTP_200_OK,
)
async def reset_onboarding(
    ctx: Annotated[RequestContext, Depends(get_request_context)],
) -> TenantHeaderOut:
    """Reset the onboarding flag so the wizard banner reappears. Useful
    for "actually I want to redo this" or admin reset."""
    tenant = ctx.tenant
    tenant.onboarding_completed_at = None
    await ctx.session.flush()
    return _tenant_to_out(tenant)
