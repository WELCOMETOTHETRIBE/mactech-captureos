"""Voyage AI embeddings client.

Per docs/ARCHITECTURE.md §2.6: voyage-3 native 1024-dim, matches our
`vector(1024)` schema. Voyage charges per token; at MacTech volumes the
monthly bill is in cents, but we still cap input length per item to
~8k characters (~2k tokens) to keep per-call latency predictable.

Rate limits (Voyage starter tier): 300 RPM and 1M TPM. We don't try to
saturate them — calls are batched per-document up to 128 inputs and
the worker runs every 30 minutes.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Final

import httpx
from tenacity import (
    AsyncRetrying,
    retry_if_exception_type,
    stop_after_attempt,
    wait_random_exponential,
)

log = logging.getLogger(__name__)

DEFAULT_BASE_URL: Final = "https://api.voyageai.com/v1"
DEFAULT_MODEL: Final = "voyage-3"
DEFAULT_TIMEOUT: Final = httpx.Timeout(60.0, connect=10.0)
MAX_BATCH_SIZE: Final = 128
MAX_INPUT_CHARS: Final = 8000


class VoyageError(Exception):
    pass


class VoyageRateLimitError(VoyageError):
    pass


@dataclass(frozen=True)
class VoyageEmbeddingResponse:
    model: str
    embeddings: list[list[float]]
    total_tokens: int


class VoyageClient:
    def __init__(
        self,
        api_key: str,
        *,
        base_url: str = DEFAULT_BASE_URL,
        timeout: httpx.Timeout = DEFAULT_TIMEOUT,
        http_client: httpx.AsyncClient | None = None,
    ) -> None:
        if not api_key:
            raise ValueError("Voyage api_key is required")
        self._api_key = api_key
        self._base_url = base_url.rstrip("/")
        self._owns_client = http_client is None
        self._http = http_client or httpx.AsyncClient(
            timeout=timeout,
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            },
        )

    async def __aenter__(self) -> VoyageClient:
        return self

    async def __aexit__(self, *exc: object) -> None:
        if self._owns_client:
            await self._http.aclose()

    async def embed(
        self,
        inputs: list[str],
        *,
        model: str = DEFAULT_MODEL,
        input_type: str = "document",
    ) -> VoyageEmbeddingResponse:
        if not inputs:
            return VoyageEmbeddingResponse(model=model, embeddings=[], total_tokens=0)
        if len(inputs) > MAX_BATCH_SIZE:
            raise ValueError(f"Voyage caps inputs at {MAX_BATCH_SIZE} per call; got {len(inputs)}")
        # Truncate per input to bound per-call cost and latency.
        trimmed = [(s or "")[:MAX_INPUT_CHARS] for s in inputs]
        body = {"input": trimmed, "model": model, "input_type": input_type}

        url = f"{self._base_url}/embeddings"
        async for attempt in AsyncRetrying(
            stop=stop_after_attempt(5),
            wait=wait_random_exponential(multiplier=1, max=60),
            retry=retry_if_exception_type((httpx.TransportError, VoyageRateLimitError)),
            reraise=True,
        ):
            with attempt:
                resp = await self._http.post(url, json=body)
                if resp.status_code == 429:
                    log.warning("voyage 429 — backing off")
                    raise VoyageRateLimitError("rate limited")
                if 500 <= resp.status_code < 600:
                    raise VoyageRateLimitError(f"server error {resp.status_code}")
                if resp.status_code >= 400:
                    raise VoyageError(f"voyage error {resp.status_code}: {resp.text[:200]}")
                payload = resp.json()
                data = payload.get("data") or []
                # Sort by index in case the API doesn't preserve order; safe even
                # when it does.
                data_sorted = sorted(data, key=lambda d: d.get("index", 0))
                embeddings = [row["embedding"] for row in data_sorted]
                tokens = (payload.get("usage") or {}).get("total_tokens", 0)
                return VoyageEmbeddingResponse(
                    model=payload.get("model", model),
                    embeddings=embeddings,
                    total_tokens=tokens,
                )
        raise VoyageError("unreachable")  # pragma: no cover
