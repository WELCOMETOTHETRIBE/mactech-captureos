"""Shared company directory API (proxy to the bizops Directory).

The MacTech suite's canonical address book lives in bizops; Capture reads and
writes it over the service-token API instead of keeping a second contact
store (see ``directory_client.py``). These endpoints adapt that API to
Capture's auth model: Clerk session in, tenant resolved from the request
context, Hub org id resolved via ICC and cached on ``tenants.hub_org_id``.

Endpoints:
  GET  /directory/contacts        list/search people (q, kind, tag filters)
  POST /directory/contacts        add a person to the shared directory
  GET  /directory/organizations   list/search organizations
  POST /directory/organizations   add an organization
"""

from __future__ import annotations

from typing import Annotated, NoReturn

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, ConfigDict, Field

from mactech_api.auth import CAPTURE_APP_KEY, RequestContext, get_request_context
from mactech_api.directory_client import (
    DirectoryContact,
    DirectoryError,
    DirectoryOrganization,
    create_directory_contact,
    create_directory_organization,
    fetch_directory_contacts,
    fetch_directory_organizations,
)
from mactech_api.mactech_identity_client import check_identity_access

router = APIRouter(tags=["directory"])


async def _resolve_hub_org_id(ctx: RequestContext) -> str:
    """The Directory keys tenants by the Hub CustomerOrganization id. Capture
    stores clerk_org_id, so resolve via the ICC access endpoint the first time
    and cache on the tenant row. 424 (failed dependency) when the mapping
    cannot be established — the caller's directory is unreachable, not empty."""

    cached: str | None = ctx.tenant.hub_org_id
    if cached:
        return cached

    result = await check_identity_access(
        clerk_user_id=ctx.claims.sub,
        app_key=CAPTURE_APP_KEY,
        clerk_org_id=ctx.tenant.clerk_org_id,
    )
    hub_org_id: str | None = None
    for org in result.orgs or []:
        if ctx.tenant.clerk_org_id and org.clerk_org_id == ctx.tenant.clerk_org_id:
            hub_org_id = org.org_id
            break
    if not hub_org_id:
        raise HTTPException(
            status_code=status.HTTP_424_FAILED_DEPENDENCY,
            detail=(
                "Could not resolve this tenant's Hub organization id from the "
                "Identity Command Center, which the shared directory requires. "
                "Verify the org exists in the Hub and try again."
            ),
        )

    ctx.tenant.hub_org_id = hub_org_id
    await ctx.session.flush()
    return hub_org_id


def _raise_from_directory_error(exc: DirectoryError) -> NoReturn:
    # Forward bizops's validation issues verbatim; wrap everything else so a
    # directory outage reads as an upstream failure, not a Capture bug.
    if exc.status == 400:
        raise HTTPException(status_code=400, detail=exc.detail) from exc
    raise HTTPException(
        status_code=status.HTTP_502_BAD_GATEWAY,
        detail=f"shared directory error: {exc}",
    ) from exc


class _Out(BaseModel):
    model_config = ConfigDict(from_attributes=True)


class DirectoryContactOut(_Out):
    id: str
    name: str
    kind: str
    title: str | None
    organization_id: str | None
    organization_name: str | None
    email: str | None
    phone: str | None
    mobile: str | None
    tags: list[str]
    notes: str | None
    status: str
    source_app: str | None
    updated_at: str | None


class DirectoryContactList(_Out):
    total: int
    items: list[DirectoryContactOut]


class DirectoryOrganizationOut(_Out):
    id: str
    name: str
    org_type: str
    abbreviation: str | None
    website: str | None
    email: str | None
    phone: str | None
    uei: str | None
    cage_code: str | None
    tags: list[str]
    status: str
    contact_count: int | None


class DirectoryOrganizationList(_Out):
    total: int
    items: list[DirectoryOrganizationOut]


class CreateDirectoryContactRequest(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    kind: str = "EXTERNAL"
    title: str | None = None
    department: str | None = None
    organization_id: str | None = None
    organization_name: str | None = None
    email: str | None = None
    phone: str | None = None
    mobile: str | None = None
    linkedin_url: str | None = None
    tags: list[str] = Field(default_factory=list)
    notes: str | None = None


class CreateDirectoryOrganizationRequest(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    org_type: str = "OTHER"
    abbreviation: str | None = None
    website: str | None = None
    email: str | None = None
    phone: str | None = None
    uei: str | None = None
    cage_code: str | None = None
    tags: list[str] = Field(default_factory=list)
    notes: str | None = None


def _contact_out(c: DirectoryContact) -> DirectoryContactOut:
    return DirectoryContactOut(
        id=c.id,
        name=c.name,
        kind=c.kind,
        title=c.title,
        organization_id=c.organization_id,
        organization_name=c.organization_name,
        email=c.email,
        phone=c.phone,
        mobile=c.mobile,
        tags=list(c.tags),
        notes=c.notes,
        status=c.status,
        source_app=c.source_app,
        updated_at=c.updated_at,
    )


def _organization_out(o: DirectoryOrganization) -> DirectoryOrganizationOut:
    return DirectoryOrganizationOut(
        id=o.id,
        name=o.name,
        org_type=o.org_type,
        abbreviation=o.abbreviation,
        website=o.website,
        email=o.email,
        phone=o.phone,
        uei=o.uei,
        cage_code=o.cage_code,
        tags=list(o.tags),
        status=o.status,
        contact_count=o.contact_count,
    )


def contact_create_payload(body: CreateDirectoryContactRequest) -> dict[str, object]:
    """Map Capture's snake_case request onto the Directory's camelCase
    contract. Pure function so tests can pin the mapping without HTTP."""

    payload: dict[str, object] = {"name": body.name.strip(), "kind": body.kind}
    if body.title:
        payload["title"] = body.title
    if body.department:
        payload["department"] = body.department
    if body.organization_id:
        payload["organizationId"] = body.organization_id
    if body.organization_name:
        payload["organizationName"] = body.organization_name
    if body.email:
        payload["email"] = body.email
    if body.phone:
        payload["phone"] = body.phone
    if body.mobile:
        payload["mobile"] = body.mobile
    if body.linkedin_url:
        payload["linkedinUrl"] = body.linkedin_url
    if body.tags:
        payload["tags"] = body.tags
    if body.notes:
        payload["notes"] = body.notes
    return payload


def organization_create_payload(body: CreateDirectoryOrganizationRequest) -> dict[str, object]:
    payload: dict[str, object] = {"name": body.name.strip(), "orgType": body.org_type}
    if body.abbreviation:
        payload["abbreviation"] = body.abbreviation
    if body.website:
        payload["website"] = body.website
    if body.email:
        payload["email"] = body.email
    if body.phone:
        payload["phone"] = body.phone
    if body.uei:
        payload["uei"] = body.uei
    if body.cage_code:
        payload["cageCode"] = body.cage_code
    if body.tags:
        payload["tags"] = body.tags
    if body.notes:
        payload["notes"] = body.notes
    return payload


@router.get("/directory/contacts", response_model=DirectoryContactList)
async def list_directory_contacts(
    ctx: Annotated[RequestContext, Depends(get_request_context)],
    q: str | None = None,
    kind: str | None = None,
    tag: str | None = None,
    directory_organization_id: str | None = None,
) -> DirectoryContactList:
    hub_org_id = await _resolve_hub_org_id(ctx)
    contacts = await fetch_directory_contacts(
        hub_org_id,
        q=q,
        kind=kind,
        tag=tag,
        directory_organization_id=directory_organization_id,
    )
    if contacts is None:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="shared directory is unavailable",
        )
    return DirectoryContactList(total=len(contacts), items=[_contact_out(c) for c in contacts])


@router.post(
    "/directory/contacts",
    response_model=DirectoryContactOut,
    status_code=status.HTTP_201_CREATED,
)
async def add_directory_contact(
    body: CreateDirectoryContactRequest,
    ctx: Annotated[RequestContext, Depends(get_request_context)],
) -> DirectoryContactOut:
    hub_org_id = await _resolve_hub_org_id(ctx)
    try:
        created = await create_directory_contact(hub_org_id, contact_create_payload(body))
    except DirectoryError as exc:
        _raise_from_directory_error(exc)
    return _contact_out(created)


@router.get("/directory/organizations", response_model=DirectoryOrganizationList)
async def list_directory_organizations(
    ctx: Annotated[RequestContext, Depends(get_request_context)],
    q: str | None = None,
    org_type: str | None = None,
) -> DirectoryOrganizationList:
    hub_org_id = await _resolve_hub_org_id(ctx)
    organizations = await fetch_directory_organizations(hub_org_id, q=q, org_type=org_type)
    if organizations is None:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="shared directory is unavailable",
        )
    return DirectoryOrganizationList(
        total=len(organizations), items=[_organization_out(o) for o in organizations]
    )


@router.post(
    "/directory/organizations",
    response_model=DirectoryOrganizationOut,
    status_code=status.HTTP_201_CREATED,
)
async def add_directory_organization(
    body: CreateDirectoryOrganizationRequest,
    ctx: Annotated[RequestContext, Depends(get_request_context)],
) -> DirectoryOrganizationOut:
    hub_org_id = await _resolve_hub_org_id(ctx)
    try:
        created = await create_directory_organization(hub_org_id, organization_create_payload(body))
    except DirectoryError as exc:
        _raise_from_directory_error(exc)
    return _organization_out(created)
