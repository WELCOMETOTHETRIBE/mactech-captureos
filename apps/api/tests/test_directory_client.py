"""Directory client + route payload mapping tests.

Hermetic: HTTP goes through httpx.MockTransport, never the network, mirroring
packages/integrations/tests/test_dsip.py. The payload-mapping tests pin the
snake_case → camelCase contract with bizops so a rename on either side fails
here first.
"""

from __future__ import annotations

import json
from collections.abc import Callable

import httpx
import pytest
from mactech_api.directory_client import (
    DirectoryError,
    create_directory_contact,
    fetch_directory_contacts,
    fetch_directory_organizations,
)
from mactech_api.routes.directory import (
    CreateDirectoryContactRequest,
    CreateDirectoryOrganizationRequest,
    contact_create_payload,
    organization_create_payload,
)

TOKEN = "test-token"
ORG = "hub_org_123"

CONTACT_PAYLOAD = {
    "id": "c1",
    "name": "Jane Doe",
    "kind": "EXTERNAL",
    "title": "KO",
    "organizationId": "o1",
    "organization": {"id": "o1", "name": "NAVAIR"},
    "organizationName": "free-text ignored when linked",
    "email": "jane@navy.mil",
    "tags": ["contracting", "ko"],
    "status": "ACTIVE",
    "sourceApp": "bizops",
    "updatedAt": "2026-07-20T00:00:00Z",
}


def _client(handler: Callable[[httpx.Request], httpx.Response]) -> httpx.AsyncClient:
    return httpx.AsyncClient(transport=httpx.MockTransport(handler))


@pytest.mark.asyncio
async def test_fetch_contacts_sends_auth_and_parses() -> None:
    seen: dict[str, str] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["auth"] = request.headers.get("authorization", "")
        seen["app"] = request.headers.get("x-mactech-service-app", "")
        seen["org"] = request.url.params.get("organizationId", "")
        seen["kind"] = request.url.params.get("kind", "")
        return httpx.Response(200, json={"contacts": [CONTACT_PAYLOAD]})

    async with _client(handler) as http:
        contacts = await fetch_directory_contacts(ORG, kind="EXTERNAL", token=TOKEN, client=http)

    assert seen == {
        "auth": f"Bearer {TOKEN}",
        "app": "capture",
        "org": ORG,
        "kind": "EXTERNAL",
    }
    assert contacts is not None and len(contacts) == 1
    contact = contacts[0]
    assert contact.name == "Jane Doe"
    # Linked directory org name wins over the free-text field.
    assert contact.organization_name == "NAVAIR"
    assert contact.tags == ("contracting", "ko")


@pytest.mark.asyncio
async def test_fetch_returns_none_on_error_and_missing_token() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(500, text="boom")

    async with _client(handler) as http:
        assert await fetch_directory_contacts(ORG, token=TOKEN, client=http) is None
        assert await fetch_directory_organizations(ORG, token=TOKEN, client=http) is None
    # Unconfigured token: degrade, don't raise.
    assert await fetch_directory_contacts(ORG, token=None, client=None) is None


@pytest.mark.asyncio
async def test_create_contact_posts_tenant_and_raises_with_detail() -> None:
    def ok_handler(request: httpx.Request) -> httpx.Response:
        body = json.loads(request.content)
        assert body["organizationId"] == ORG
        assert body["name"] == "Jane Doe"
        return httpx.Response(201, json={"contact": CONTACT_PAYLOAD})

    async with _client(ok_handler) as http:
        created = await create_directory_contact(
            ORG, {"name": "Jane Doe"}, token=TOKEN, client=http
        )
    assert created.id == "c1"

    def bad_handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            400, json={"error": "validation", "issues": {"kind": ["Invalid input"]}}
        )

    async with _client(bad_handler) as http:
        with pytest.raises(DirectoryError) as exc_info:
            await create_directory_contact(
                ORG, {"name": "X", "kind": "BAD"}, token=TOKEN, client=http
            )
    assert exc_info.value.status == 400
    assert exc_info.value.detail["issues"]["kind"] == ["Invalid input"]

    # Write with no token configured must raise, never silently no-op.
    with pytest.raises(DirectoryError):
        await create_directory_contact(ORG, {"name": "X"}, token=None)


def test_contact_payload_maps_snake_to_camel_and_drops_empty() -> None:
    body = CreateDirectoryContactRequest(
        name="  Jane Doe  ",
        kind="EXTERNAL",
        organization_id="o1",
        linkedin_url="https://linkedin.com/in/jane",
        tags=["ko"],
        email=None,
    )
    payload = contact_create_payload(body)
    assert payload == {
        "name": "Jane Doe",
        "kind": "EXTERNAL",
        # The org LINK must never be named "organizationId" — that key means
        # the Hub tenant on the M2M surface (regression: a linked contact was
        # once mis-scoped to a "tenant" that was actually the org's row id).
        "directoryOrganizationId": "o1",
        "linkedinUrl": "https://linkedin.com/in/jane",
        "tags": ["ko"],
    }


async def test_create_contact_tenant_id_survives_link_field() -> None:
    """Regression: fields carrying a directoryOrganizationId link (or even a
    stray organizationId) must not clobber the tenant id in the POST body."""

    seen: dict[str, str] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        body = json.loads(request.content)
        seen["tenant"] = body["organizationId"]
        seen["link"] = body.get("directoryOrganizationId", "")
        return httpx.Response(201, json={"contact": CONTACT_PAYLOAD})

    async with _client(handler) as http:
        await create_directory_contact(
            ORG,
            {"name": "Linked", "directoryOrganizationId": "dir_org_1", "organizationId": "evil"},
            token=TOKEN,
            client=http,
        )
    assert seen == {"tenant": ORG, "link": "dir_org_1"}


def test_organization_payload_maps_cage_and_org_type() -> None:
    body = CreateDirectoryOrganizationRequest(
        name="NAVAIR", org_type="GOVERNMENT", cage_code="0ABCD", tags=[]
    )
    payload = organization_create_payload(body)
    assert payload == {"name": "NAVAIR", "orgType": "GOVERNMENT", "cageCode": "0ABCD"}
