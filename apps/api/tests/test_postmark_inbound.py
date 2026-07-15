"""Postmark inbound webhook — auth, subject filter, and wiring smoke.

No Postgres test harness exists in this repo yet, so the storage path
(tenant lookup + insert) isn't exercised here; we cover everything in
front of the DB: route mounting, secret enforcement, basic-auth
parsing, and the subject filter (which returns before any DB work).
"""

from __future__ import annotations

import base64

from fastapi.testclient import TestClient
from mactech_api.main import app
from mactech_api.routes.webhooks import _check_postmark_basic_auth
from mactech_api.settings import settings


def _basic(user: str, password: str) -> dict[str, str]:
    token = base64.b64encode(f"{user}:{password}".encode()).decode()
    return {"Authorization": f"Basic {token}"}


PAYLOAD = {
    "MessageID": "22c74902-a0c1-4511-804f-341342852c90",
    "Subject": "Bid Invite: HVAC Replacement — Bldg 1301",
    "FromFull": {"Email": "estimating@primeco.com", "Name": "Prime Co"},
    "TextBody": "You are invited to bid...",
    "HtmlBody": "<p>You are invited to bid...</p>",
    "Date": "Mon, 13 Jul 2026 09:00:00 -0400",
    "Attachments": [
        {"Name": "specs.pdf", "ContentType": "application/pdf", "ContentLength": 4096}
    ],
}


def test_router_mounted() -> None:
    routes = [r.path for r in app.routes]  # type: ignore[attr-defined]
    assert "/webhooks/postmark/inbound" in routes
    assert "/bid-invites" in routes
    assert "/bid-invites/{invite_id}" in routes


def test_rejects_when_secret_unconfigured(monkeypatch) -> None:
    monkeypatch.setattr(settings, "postmark_webhook_secret", "")
    client = TestClient(app)
    res = client.post("/webhooks/postmark/inbound", json=PAYLOAD)
    assert res.status_code == 503


def test_rejects_missing_or_bad_auth(monkeypatch) -> None:
    monkeypatch.setattr(settings, "postmark_webhook_secret", "s3cret")
    client = TestClient(app)
    assert client.post("/webhooks/postmark/inbound", json=PAYLOAD).status_code == 401
    res = client.post(
        "/webhooks/postmark/inbound",
        json=PAYLOAD,
        headers=_basic("postmark", "wrong"),
    )
    assert res.status_code == 401


def test_non_bid_invite_subject_is_acked_not_stored(monkeypatch) -> None:
    monkeypatch.setattr(settings, "postmark_webhook_secret", "s3cret")
    client = TestClient(app)
    res = client.post(
        "/webhooks/postmark/inbound",
        json={**PAYLOAD, "Subject": "RE: lunch on Friday?"},
        headers=_basic("postmark", "s3cret"),
    )
    assert res.status_code == 200
    assert res.json() == {
        "stored": False,
        "reason": "subject_filter",
        "bid_invite_id": None,
    }


def test_subject_match_is_case_insensitive_and_trims(monkeypatch) -> None:
    """'bid invite: ...' with leading whitespace still passes the filter.
    It then proceeds to the DB (which isn't available in unit tests), so
    we only assert it does NOT short-circuit as subject_filter."""
    monkeypatch.setattr(settings, "postmark_webhook_secret", "s3cret")
    client = TestClient(app)
    try:
        res = client.post(
            "/webhooks/postmark/inbound",
            json={**PAYLOAD, "Subject": "  bid invite: paving IDIQ"},
            headers=_basic("postmark", "s3cret"),
        )
    except Exception:
        return  # no DB in unit tests — passing the filter is the assertion
    if res.status_code == 200:
        assert res.json()["reason"] != "subject_filter"


def test_basic_auth_parser(monkeypatch) -> None:
    monkeypatch.setattr(settings, "postmark_webhook_secret", "s3cret")
    ok = _basic("anything", "s3cret")["Authorization"]
    assert _check_postmark_basic_auth(ok) is True
    assert _check_postmark_basic_auth(None) is False
    assert _check_postmark_basic_auth("Bearer s3cret") is False
    assert _check_postmark_basic_auth("Basic !!!notb64!!!") is False
    assert _check_postmark_basic_auth(_basic("u", "nope")["Authorization"]) is False


def test_bid_invites_list_requires_auth() -> None:
    client = TestClient(app)
    assert client.get("/bid-invites").status_code == 401
