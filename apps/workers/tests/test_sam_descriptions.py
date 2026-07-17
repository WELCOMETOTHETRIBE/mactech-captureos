"""Tests for the throttled noticedesc fetch (rate-limit resilience)."""

from __future__ import annotations

import httpx
import pytest
from mactech_workers.tasks import sam_descriptions as sd


async def _run(handler) -> str | None:
    transport = httpx.MockTransport(handler)
    async with httpx.AsyncClient(transport=transport) as client:
        return await sd._fetch_noticedesc(client, "https://api.sam.gov/desc?id=1", "KEY")


async def test_returns_description_on_200():
    def handler(request: httpx.Request) -> httpx.Response:
        assert "api_key=KEY" in str(request.url)
        return httpx.Response(200, json={"description": "FRCS cybersecurity scope"})

    assert await _run(handler) == "FRCS cybersecurity scope"


async def test_404_returns_none():
    assert await _run(lambda r: httpx.Response(404)) is None


async def test_429_is_retried_then_succeeds(monkeypatch):
    # No real waiting — make tenacity's backoff instant.
    async def _no_sleep(_seconds):
        return None

    monkeypatch.setattr(sd.asyncio, "sleep", _no_sleep)

    calls = {"n": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        calls["n"] += 1
        if calls["n"] < 3:
            return httpx.Response(429, text="Message throttled out")
        return httpx.Response(200, json={"description": "recovered after throttle"})

    assert await _run(handler) == "recovered after throttle"
    assert calls["n"] == 3  # two 429s, third succeeds


async def test_429_exhausts_and_raises(monkeypatch):
    async def _no_sleep(_seconds):
        return None

    monkeypatch.setattr(sd.asyncio, "sleep", _no_sleep)

    with pytest.raises(httpx.TransportError):
        await _run(lambda r: httpx.Response(429, text="throttled"))


async def test_empty_description_returns_none():
    assert await _run(lambda r: httpx.Response(200, json={"description": "   "})) is None


def test_throttle_default_is_positive():
    # The whole point: some spacing between requests by default.
    assert sd.DEFAULT_THROTTLE_SECONDS > 0
