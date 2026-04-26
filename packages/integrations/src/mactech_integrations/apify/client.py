"""Apify async client — thin wrapper over the REST API.

Sprint 19. Per docs/APIFY_STRATEGY.md, Apify is the sealed ingest edge
for public-but-unstructured GovCon signal: agency forecast pages,
industry-day calendars, DIBBS, etc. This client exposes the three
operations MacTech needs:

  - run_actor_sync()   — fire an Actor and block (with timeout)
  - run_actor()        — fire an Actor and return immediately (run_id)
  - get_run()          — poll a run by id
  - dataset_items()    — paginate items from a finished run's dataset

For verifying inbound webhooks, `verify_webhook_signature()` is a
constant-time HMAC-SHA256 check using the shared secret stored in env
as APIFY_WEBHOOK_SECRET.

We don't pull in the official `apify-client` SDK because it's sync-only
and we'd just wrap it in a thread executor. The REST surface we use is
small and stable.
"""

from __future__ import annotations

import hashlib
import hmac
import logging
from dataclasses import dataclass, field
from typing import Any, Final

import httpx
from tenacity import (
    AsyncRetrying,
    retry_if_exception_type,
    stop_after_attempt,
    wait_random_exponential,
)

log = logging.getLogger(__name__)

DEFAULT_BASE_URL: Final = "https://api.apify.com/v2"
DEFAULT_TIMEOUT: Final = httpx.Timeout(60.0, connect=10.0)
DEFAULT_RUN_TIMEOUT_SECS: Final = 300


class ApifyError(Exception):
    pass


class ApifyRateLimitError(ApifyError):
    pass


@dataclass(frozen=True)
class ApifyRunInfo:
    id: str
    actor_id: str
    actor_task_id: str | None
    status: str  # READY, RUNNING, SUCCEEDED, FAILED, ABORTED, TIMING_OUT, TIMED_OUT
    started_at: str | None
    finished_at: str | None
    default_dataset_id: str | None
    stats: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class ApifyDatasetItem:
    payload: dict[str, Any]


class ApifyClient:
    def __init__(
        self,
        api_token: str,
        *,
        base_url: str = DEFAULT_BASE_URL,
        timeout: httpx.Timeout = DEFAULT_TIMEOUT,
        http_client: httpx.AsyncClient | None = None,
    ) -> None:
        if not api_token:
            raise ValueError("Apify api_token is required")
        self._api_token = api_token
        self._base_url = base_url.rstrip("/")
        self._owns_client = http_client is None
        self._http = http_client or httpx.AsyncClient(
            timeout=timeout,
            headers={"Authorization": f"Bearer {api_token}"},
        )

    async def __aenter__(self) -> ApifyClient:
        return self

    async def __aexit__(self, *exc: object) -> None:
        if self._owns_client:
            await self._http.aclose()

    async def _request(
        self,
        method: str,
        path: str,
        *,
        json: dict[str, Any] | None = None,
        params: dict[str, str | int] | None = None,
    ) -> dict[str, Any]:
        async for attempt in AsyncRetrying(
            wait=wait_random_exponential(multiplier=1, max=20),
            stop=stop_after_attempt(3),
            retry=retry_if_exception_type(
                (httpx.TransportError, ApifyRateLimitError)
            ),
            reraise=True,
        ):
            with attempt:
                resp = await self._http.request(
                    method, f"{self._base_url}{path}", json=json, params=params
                )
                if resp.status_code == 429:
                    raise ApifyRateLimitError(
                        f"Apify 429 on {method} {path} — backing off"
                    )
                if resp.status_code >= 400:
                    body_preview = resp.text[:300]
                    raise ApifyError(
                        f"Apify {resp.status_code} on {method} {path}: "
                        f"{body_preview}"
                    )
                return resp.json()
        raise ApifyError("retry loop exited unexpectedly")

    async def run_actor(
        self,
        actor_id: str,
        run_input: dict[str, Any],
        *,
        wait_for_finish_secs: int = 0,
        webhooks_b64: str | None = None,
    ) -> ApifyRunInfo:
        """Start an Actor run.

        - `wait_for_finish_secs=0` (default) returns immediately with a
          RUNNING run object. Caller polls or relies on the webhook.
        - `wait_for_finish_secs>0` blocks server-side until the run
          finishes or the deadline expires (Apify's `waitForFinish`).
        - `webhooks_b64` lets a per-run webhook override the actor-level
          schedule (we use the actor-level one for industry-day; this is
          here for future on-demand cases).
        """
        path = f"/acts/{_quote_actor_id(actor_id)}/runs"
        params: dict[str, str | int] = {}
        if wait_for_finish_secs:
            params["waitForFinish"] = wait_for_finish_secs
        if webhooks_b64:
            params["webhooks"] = webhooks_b64
        payload = await self._request("POST", path, json=run_input, params=params)
        return _parse_run(payload.get("data") or payload)

    async def run_actor_sync(
        self,
        actor_id: str,
        run_input: dict[str, Any],
        *,
        wait_for_finish_secs: int = DEFAULT_RUN_TIMEOUT_SECS,
        poll_interval_secs: int = 15,
    ) -> ApifyRunInfo:
        """Start a run and block until it terminates or our deadline expires.

        Apify's per-call `waitForFinish` query parameter caps at 60s. To
        wait longer, we kick the run and poll `get_run()` until the
        status is one of SUCCEEDED / FAILED / ABORTED / TIMED_OUT, or
        until our `wait_for_finish_secs` deadline elapses (in which
        case we return whatever the latest run state is — usually
        RUNNING — and the caller decides what to do).
        """
        import asyncio
        import time

        run = await self.run_actor(actor_id, run_input)
        deadline = time.monotonic() + max(0, wait_for_finish_secs)
        terminal = {"SUCCEEDED", "FAILED", "ABORTED", "TIMED_OUT"}
        while run.status not in terminal:
            if time.monotonic() >= deadline:
                return run
            await asyncio.sleep(poll_interval_secs)
            run = await self.get_run(run.id)
        return run

    async def get_run(self, run_id: str) -> ApifyRunInfo:
        payload = await self._request("GET", f"/actor-runs/{run_id}")
        return _parse_run(payload.get("data") or payload)

    async def dataset_items(
        self,
        dataset_id: str,
        *,
        limit: int = 1000,
        offset: int = 0,
        clean: bool = True,
    ) -> list[ApifyDatasetItem]:
        """Pull items from a dataset. Returns parsed JSON items."""
        path = f"/datasets/{dataset_id}/items"
        params: dict[str, str | int] = {
            "format": "json",
            "limit": limit,
            "offset": offset,
            "clean": "true" if clean else "false",
        }
        async for attempt in AsyncRetrying(
            wait=wait_random_exponential(multiplier=1, max=20),
            stop=stop_after_attempt(3),
            retry=retry_if_exception_type(
                (httpx.TransportError, ApifyRateLimitError)
            ),
            reraise=True,
        ):
            with attempt:
                resp = await self._http.get(
                    f"{self._base_url}{path}", params=params
                )
                if resp.status_code == 429:
                    raise ApifyRateLimitError(
                        "Apify 429 on dataset_items — backing off"
                    )
                if resp.status_code >= 400:
                    raise ApifyError(
                        f"Apify {resp.status_code} on dataset_items: "
                        f"{resp.text[:300]}"
                    )
                items = resp.json()
                if not isinstance(items, list):
                    raise ApifyError(
                        f"Apify dataset_items returned non-list: "
                        f"{type(items).__name__}"
                    )
                return [ApifyDatasetItem(payload=i) for i in items]
        raise ApifyError("dataset_items retry loop exited unexpectedly")


def _parse_run(data: dict[str, Any]) -> ApifyRunInfo:
    return ApifyRunInfo(
        id=str(data.get("id") or ""),
        actor_id=str(data.get("actId") or ""),
        actor_task_id=(data.get("actorTaskId") or None),
        status=str(data.get("status") or ""),
        started_at=(data.get("startedAt") or None),
        finished_at=(data.get("finishedAt") or None),
        default_dataset_id=(data.get("defaultDatasetId") or None),
        stats=data.get("stats") or {},
    )


def _quote_actor_id(actor_id: str) -> str:
    """Apify supports either `username~actorname` or a 17-char id. We
    URL-quote the tilde because some HTTP clients re-encode it."""
    return actor_id.replace("/", "~")


def verify_webhook_signature(
    body: bytes, signature: str | None, secret: str
) -> bool:
    """Constant-time HMAC-SHA256 verification of an Apify webhook.

    Apify lets you set a per-webhook secret which it sends in the
    `Apify-Webhook-Signature` header (`sha256=<hex>`). Reject calls that
    don't match. The Apify webhook config in our account uses our secret;
    this function is the only thing standing between a forged request
    and our ingest pipeline.
    """
    if not signature or not secret:
        return False
    try:
        scheme, sent_hex = signature.split("=", 1)
    except ValueError:
        return False
    if scheme.lower() != "sha256":
        return False
    expected = hmac.new(
        secret.encode("utf-8"), body, hashlib.sha256
    ).hexdigest()
    return hmac.compare_digest(expected, sent_hex.strip())
