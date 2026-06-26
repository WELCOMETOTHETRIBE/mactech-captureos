"""SBIR route wiring + auth smoke.

The full happy-path SSE test would need an LLM mock and a Postgres test
harness — neither exists in this repo today, so we exercise just what's
testable without spinning up either: the router is mounted and rejects
unauthenticated requests as 401.
"""

from __future__ import annotations

from fastapi.testclient import TestClient
from mactech_api.main import app


def test_router_mounted_listing() -> None:
    routes = [r.path for r in app.routes]  # type: ignore[attr-defined]
    assert "/sbir/submissions" in routes
    assert "/sbir/generate/stream" in routes


def test_list_submissions_requires_auth() -> None:
    client = TestClient(app)
    res = client.get("/sbir/submissions")
    assert res.status_code == 401
    detail = res.json().get("detail", "")
    assert "bearer" in detail.lower() or "token" in detail.lower()


def test_generate_stream_requires_auth() -> None:
    client = TestClient(app)
    res = client.post(
        "/sbir/generate/stream",
        json={
            "topic_number": "DLA26BZ02-NV999",
            "component": "DLA",
            "topic_source_kind": "text",
            "topic_payload": "Synthetic topic body for the smoke test.",
            "synergy_hypothesis": "Synthetic synergy framing for smoke.",
            "depth": "scaffold",
        },
    )
    assert res.status_code == 401


def test_generate_stream_validates_depth() -> None:
    """Pydantic rejects bogus depth before auth runs (422 from FastAPI's
    request-body validation). We can't easily exercise the in-body 422 path
    without a token, but the schema constraint is enforced at the model
    layer — see SBIRGenerateRequest.depth's regex pattern."""
    from mactech_api.routes.sbir import SBIRGenerateRequest

    # Valid value passes.
    SBIRGenerateRequest(
        topic_number="DLA26BZ02-NV999",
        component="DLA",
        topic_source_kind="text",
        topic_payload="Synthetic topic body for the smoke test.",
        synergy_hypothesis="Synthetic synergy framing for smoke.",
        depth="standard",
    )

    import pytest
    from pydantic import ValidationError

    with pytest.raises(ValidationError):
        SBIRGenerateRequest(
            topic_number="DLA26BZ02-NV999",
            component="DLA",
            topic_source_kind="text",
            topic_payload="Synthetic topic body for the smoke test.",
            synergy_hypothesis="Synthetic synergy framing for smoke.",
            depth="bogus",  # type: ignore[arg-type]
        )
