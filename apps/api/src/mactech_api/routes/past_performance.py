"""Past performance catalogue API.

Phase 2 Week 8. Tenant-scoped CRUD over the firm's prior contract
narratives. The Phase 3 Sources Sought drafter cites these.

Endpoints:
  GET    /past-performance                    list (newest first)
  GET    /past-performance/{id}               single record
  POST   /past-performance                    create
  PATCH  /past-performance/{id}               partial update
  DELETE /past-performance/{id}               remove
"""

from __future__ import annotations

from datetime import date
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from mactech_api.auth import RequestContext, get_request_context
from mactech_db.models import PastPerformance
from mactech_db.models.library import PAST_PERFORMANCE_ROLES

router = APIRouter(tags=["past-performance"])


class _Out(BaseModel):
    model_config = ConfigDict(from_attributes=True)


class PastPerformanceOut(_Out):
    id: str
    title: str
    customer_agency: str | None
    customer_office: str | None
    contract_number: str | None
    role: str
    period_start: str | None
    period_end: str | None
    contract_value: float | None
    naics_code: str | None
    summary: str
    keywords: list[str]
    related_capability_slugs: list[str]
    related_founder_slugs: list[str]
    created_at: str
    updated_at: str


class PastPerformanceList(_Out):
    total: int
    items: list[PastPerformanceOut]


class CreatePastPerformanceRequest(BaseModel):
    title: str = Field(min_length=1, max_length=255)
    customer_agency: str | None = Field(default=None, max_length=255)
    customer_office: str | None = Field(default=None, max_length=255)
    contract_number: str | None = Field(default=None, max_length=64)
    role: str = "prime"
    period_start: date | None = None
    period_end: date | None = None
    contract_value: float | None = None
    naics_code: str | None = Field(default=None, max_length=8)
    summary: str = Field(min_length=1)
    keywords: list[str] = Field(default_factory=list)
    related_capability_slugs: list[str] = Field(default_factory=list)
    related_founder_slugs: list[str] = Field(default_factory=list)


class UpdatePastPerformanceRequest(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=255)
    customer_agency: str | None = None
    customer_office: str | None = None
    contract_number: str | None = None
    role: str | None = None
    period_start: date | None = None
    period_end: date | None = None
    clear_period_start: bool = False
    clear_period_end: bool = False
    contract_value: float | None = None
    clear_contract_value: bool = False
    naics_code: str | None = None
    summary: str | None = Field(default=None, min_length=1)
    keywords: list[str] | None = None
    related_capability_slugs: list[str] | None = None
    related_founder_slugs: list[str] | None = None


def _validate_role(role: str) -> str:
    if role not in PAST_PERFORMANCE_ROLES:
        raise HTTPException(
            status_code=400,
            detail=f"invalid role '{role}'. Allowed: {list(PAST_PERFORMANCE_ROLES)}",
        )
    return role


def _to_out(pp: PastPerformance) -> PastPerformanceOut:
    return PastPerformanceOut(
        id=str(pp.id),
        title=pp.title,
        customer_agency=pp.customer_agency,
        customer_office=pp.customer_office,
        contract_number=pp.contract_number,
        role=pp.role,
        period_start=pp.period_start.isoformat() if pp.period_start else None,
        period_end=pp.period_end.isoformat() if pp.period_end else None,
        contract_value=float(pp.contract_value) if pp.contract_value is not None else None,
        naics_code=pp.naics_code,
        summary=pp.summary,
        keywords=pp.keywords or [],
        related_capability_slugs=pp.related_capability_slugs or [],
        related_founder_slugs=pp.related_founder_slugs or [],
        created_at=pp.created_at.isoformat(),
        updated_at=pp.updated_at.isoformat(),
    )


@router.get("/past-performance", response_model=PastPerformanceList)
async def list_past_performance(
    ctx: Annotated[RequestContext, Depends(get_request_context)],
) -> PastPerformanceList:
    rows = (
        await ctx.session.execute(
            select(PastPerformance)
            .where(PastPerformance.tenant_id == ctx.tenant.id)
            .order_by(
                PastPerformance.period_end.desc().nulls_last(),
                PastPerformance.created_at.desc(),
            )
        )
    ).scalars().all()
    return PastPerformanceList(total=len(rows), items=[_to_out(r) for r in rows])


@router.get("/past-performance/{pp_id}", response_model=PastPerformanceOut)
async def get_past_performance(
    pp_id: UUID,
    ctx: Annotated[RequestContext, Depends(get_request_context)],
) -> PastPerformanceOut:
    pp = (
        await ctx.session.execute(
            select(PastPerformance).where(
                PastPerformance.id == pp_id,
                PastPerformance.tenant_id == ctx.tenant.id,
            )
        )
    ).scalar_one_or_none()
    if pp is None:
        raise HTTPException(status_code=404, detail="past-performance record not found")
    return _to_out(pp)


@router.post(
    "/past-performance",
    response_model=PastPerformanceOut,
    status_code=status.HTTP_201_CREATED,
)
async def create_past_performance(
    body: CreatePastPerformanceRequest,
    ctx: Annotated[RequestContext, Depends(get_request_context)],
) -> PastPerformanceOut:
    _validate_role(body.role)

    pp = PastPerformance(
        tenant_id=ctx.tenant.id,
        title=body.title.strip(),
        customer_agency=body.customer_agency,
        customer_office=body.customer_office,
        contract_number=body.contract_number,
        role=body.role,
        period_start=body.period_start,
        period_end=body.period_end,
        contract_value=body.contract_value,
        naics_code=body.naics_code,
        summary=body.summary.strip(),
        keywords=body.keywords or None,
        related_capability_slugs=body.related_capability_slugs or None,
        related_founder_slugs=body.related_founder_slugs or None,
    )
    ctx.session.add(pp)
    try:
        await ctx.session.flush()
    except IntegrityError:
        await ctx.session.rollback()
        raise HTTPException(
            status_code=409,
            detail=f"a past-performance record with title '{body.title}' already exists",
        ) from None
    return _to_out(pp)


@router.patch("/past-performance/{pp_id}", response_model=PastPerformanceOut)
async def update_past_performance(
    pp_id: UUID,
    body: UpdatePastPerformanceRequest,
    ctx: Annotated[RequestContext, Depends(get_request_context)],
) -> PastPerformanceOut:
    pp = (
        await ctx.session.execute(
            select(PastPerformance).where(
                PastPerformance.id == pp_id,
                PastPerformance.tenant_id == ctx.tenant.id,
            )
        )
    ).scalar_one_or_none()
    if pp is None:
        raise HTTPException(status_code=404, detail="past-performance record not found")

    if body.title is not None:
        pp.title = body.title.strip()
    if body.customer_agency is not None:
        pp.customer_agency = body.customer_agency
    if body.customer_office is not None:
        pp.customer_office = body.customer_office
    if body.contract_number is not None:
        pp.contract_number = body.contract_number
    if body.role is not None:
        _validate_role(body.role)
        pp.role = body.role
    if body.clear_period_start:
        pp.period_start = None
    elif body.period_start is not None:
        pp.period_start = body.period_start
    if body.clear_period_end:
        pp.period_end = None
    elif body.period_end is not None:
        pp.period_end = body.period_end
    if body.clear_contract_value:
        pp.contract_value = None
    elif body.contract_value is not None:
        pp.contract_value = body.contract_value
    if body.naics_code is not None:
        pp.naics_code = body.naics_code
    if body.summary is not None:
        pp.summary = body.summary.strip()
    if body.keywords is not None:
        pp.keywords = body.keywords or None
    if body.related_capability_slugs is not None:
        pp.related_capability_slugs = body.related_capability_slugs or None
    if body.related_founder_slugs is not None:
        pp.related_founder_slugs = body.related_founder_slugs or None

    try:
        await ctx.session.flush()
    except IntegrityError:
        await ctx.session.rollback()
        raise HTTPException(
            status_code=409,
            detail="another past-performance record with that title already exists",
        ) from None
    return _to_out(pp)


@router.delete(
    "/past-performance/{pp_id}", status_code=status.HTTP_204_NO_CONTENT
)
async def delete_past_performance(
    pp_id: UUID,
    ctx: Annotated[RequestContext, Depends(get_request_context)],
) -> None:
    pp = (
        await ctx.session.execute(
            select(PastPerformance).where(
                PastPerformance.id == pp_id,
                PastPerformance.tenant_id == ctx.tenant.id,
            )
        )
    ).scalar_one_or_none()
    if pp is None:
        raise HTTPException(status_code=404, detail="past-performance record not found")

    await ctx.session.delete(pp)
    await ctx.session.flush()
