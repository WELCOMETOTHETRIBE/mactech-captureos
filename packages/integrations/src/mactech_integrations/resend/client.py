"""Resend transactional email client.

Send-only restricted-key compatible. Until a domain is verified at
resend.com/domains, sends to addresses other than the account owner's
fail with HTTP 403; we surface that as ResendError("validation_error").
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

DEFAULT_BASE_URL: Final = "https://api.resend.com"
DEFAULT_TIMEOUT: Final = httpx.Timeout(30.0, connect=10.0)


class ResendError(Exception):
    pass


class ResendRateLimitError(ResendError):
    pass


@dataclass(frozen=True)
class ResendSendResult:
    message_id: str
    to: list[str]
    subject: str


class ResendClient:
    def __init__(
        self,
        api_key: str,
        *,
        base_url: str = DEFAULT_BASE_URL,
        timeout: httpx.Timeout = DEFAULT_TIMEOUT,
        http_client: httpx.AsyncClient | None = None,
    ) -> None:
        if not api_key:
            raise ValueError("Resend api_key is required")
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

    async def __aenter__(self) -> ResendClient:
        return self

    async def __aexit__(self, *exc: object) -> None:
        if self._owns_client:
            await self._http.aclose()

    async def send_email(
        self,
        *,
        from_addr: str,
        to: list[str],
        subject: str,
        html: str | None = None,
        text: str | None = None,
        reply_to: str | None = None,
        tags: list[dict[str, str]] | None = None,
    ) -> ResendSendResult:
        if not to:
            raise ValueError("at least one recipient is required")
        if not html and not text:
            raise ValueError("either html or text body is required")

        body: dict[str, object] = {
            "from": from_addr,
            "to": to,
            "subject": subject,
        }
        if html:
            body["html"] = html
        if text:
            body["text"] = text
        if reply_to:
            body["reply_to"] = reply_to
        if tags:
            body["tags"] = tags

        url = f"{self._base_url}/emails"
        async for attempt in AsyncRetrying(
            stop=stop_after_attempt(4),
            wait=wait_random_exponential(multiplier=1, max=30),
            retry=retry_if_exception_type((httpx.TransportError, ResendRateLimitError)),
            reraise=True,
        ):
            with attempt:
                resp = await self._http.post(url, json=body)
                if resp.status_code == 429:
                    raise ResendRateLimitError("rate limited")
                if 500 <= resp.status_code < 600:
                    raise ResendRateLimitError(f"server error {resp.status_code}")
                if resp.status_code >= 400:
                    raise ResendError(f"resend error {resp.status_code}: {resp.text[:300]}")
                d = resp.json()
                return ResendSendResult(
                    message_id=d.get("id", ""),
                    to=to,
                    subject=subject,
                )
        raise ResendError("unreachable")  # pragma: no cover
