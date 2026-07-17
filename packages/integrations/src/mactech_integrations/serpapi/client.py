"""SerpAPI client — Google Search proxy with structured JSON.

Sprint 19. Used for opportunity-detail web augmentation: given a
solicitation title + agency + (optionally) the incumbent, query Google
and return the top organic results so the founder can see prior-press,
GAO reports, recompete chatter, and CO LinkedIn surfaces without
context-switching.

SerpAPI charges per search. Free tier is 100 searches/mo; paid starts
$75/mo for 5k. We cache aggressively (7-day TTL) per the strategy doc.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Final

import httpx
from tenacity import (
    AsyncRetrying,
    retry_if_exception_type,
    stop_after_attempt,
    wait_random_exponential,
)

log = logging.getLogger(__name__)

DEFAULT_BASE_URL: Final = "https://serpapi.com"
DEFAULT_TIMEOUT: Final = httpx.Timeout(20.0, connect=8.0)
DEFAULT_NUM_RESULTS: Final = 10


class SerpApiError(Exception):
    pass


class SerpApiRateLimitError(SerpApiError):
    pass


@dataclass(frozen=True)
class SerpApiOrganicResult:
    position: int
    title: str
    link: str
    displayed_link: str | None
    snippet: str | None
    source: str | None  # eg "GAO.gov", "DefenseScoop"
    date: str | None  # SerpAPI's "date" string when present


@dataclass(frozen=True)
class SerpApiSearchResponse:
    query: str
    engine: str
    organic_results: list[SerpApiOrganicResult] = field(default_factory=list)
    answer_box: dict | None = None
    knowledge_graph: dict | None = None
    related_questions: list[dict] = field(default_factory=list)


class SerpApiClient:
    def __init__(
        self,
        api_key: str,
        *,
        base_url: str = DEFAULT_BASE_URL,
        timeout: httpx.Timeout = DEFAULT_TIMEOUT,
        http_client: httpx.AsyncClient | None = None,
    ) -> None:
        if not api_key:
            raise ValueError("SerpAPI api_key is required")
        self._api_key = api_key
        self._base_url = base_url.rstrip("/")
        self._owns_client = http_client is None
        self._http = http_client or httpx.AsyncClient(timeout=timeout)

    async def __aenter__(self) -> SerpApiClient:
        return self

    async def __aexit__(self, *exc: object) -> None:
        if self._owns_client:
            await self._http.aclose()

    async def search(
        self,
        query: str,
        *,
        engine: str = "google",
        num: int = DEFAULT_NUM_RESULTS,
        location: str | None = None,
        gl: str = "us",
        hl: str = "en",
    ) -> SerpApiSearchResponse:
        """Run a Google search and return the top organic results.

        Caller is responsible for caching — every call costs.
        """
        params: dict[str, str | int] = {
            "engine": engine,
            "q": query,
            "num": num,
            "gl": gl,
            "hl": hl,
            "api_key": self._api_key,
            "output": "json",
            "no_cache": "false",
        }
        if location:
            params["location"] = location

        async for attempt in AsyncRetrying(
            wait=wait_random_exponential(multiplier=1, max=20),
            stop=stop_after_attempt(3),
            retry=retry_if_exception_type((httpx.TransportError, SerpApiRateLimitError)),
            reraise=True,
        ):
            with attempt:
                resp = await self._http.get(f"{self._base_url}/search.json", params=params)
                if resp.status_code == 429:
                    raise SerpApiRateLimitError("SerpAPI 429 — exceeded plan rate; back off")
                if resp.status_code >= 400:
                    body_preview = resp.text[:300]
                    raise SerpApiError(f"SerpAPI returned {resp.status_code}: {body_preview}")
                payload = resp.json()
                if "error" in payload:
                    raise SerpApiError(f"SerpAPI error: {payload['error']!s}")
                return _parse_response(query, engine, payload)

        # Unreachable — tenacity reraises on exhaustion.
        raise SerpApiError("SerpAPI: retry loop exited unexpectedly")


def _parse_response(query: str, engine: str, payload: dict) -> SerpApiSearchResponse:
    organic_raw = payload.get("organic_results") or []
    organic = [
        SerpApiOrganicResult(
            position=int(r.get("position") or i + 1),
            title=str(r.get("title") or "").strip(),
            link=str(r.get("link") or "").strip(),
            displayed_link=(r.get("displayed_link") or None),
            snippet=(r.get("snippet") or None),
            source=(r.get("source") or None),
            date=(r.get("date") or None),
        )
        for i, r in enumerate(organic_raw)
        if r.get("title") and r.get("link")
    ]
    return SerpApiSearchResponse(
        query=query,
        engine=engine,
        organic_results=organic,
        answer_box=payload.get("answer_box") or None,
        knowledge_graph=payload.get("knowledge_graph") or None,
        related_questions=payload.get("related_questions") or [],
    )
