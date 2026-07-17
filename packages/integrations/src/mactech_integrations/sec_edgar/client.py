"""SEC EDGAR client — incumbent distress signals.

Sprint 22 / strategy doc §3.3. SEC requires a User-Agent identifying
the requester. The data API at data.sec.gov is free + unauthenticated
but rate-limited (10 req/sec).

Two endpoints we use:

  GET https://www.sec.gov/files/company_tickers.json
      One-shot dump of all SEC-registered companies → CIK lookup.
      Cached on disk for the worker process lifetime.

  GET https://data.sec.gov/submissions/CIK{padded}.json
      Recent filings for a CIK. Returns up to ~1000 most-recent.
      Each filing has form ('8-K', '10-K', '10-Q', etc.), filing
      date, accession number, primary document.

We don't fetch filing CONTENT in this client — only filing metadata
(form + date + accession). Distress-signal extraction happens in the
worker via Claude on the filing's primary document, which the worker
fetches via this client's `fetch_primary_document()` helper.
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

DEFAULT_BASE_URL: Final = "https://www.sec.gov"
DATA_BASE_URL: Final = "https://data.sec.gov"
DEFAULT_TIMEOUT: Final = httpx.Timeout(30.0, connect=10.0)

# SEC mandates a User-Agent identifying the requester. The "[email]"
# slot must be a real address. We pull from env in the integration
# layer; default here is a sentinel so misconfiguration is loud.
DEFAULT_USER_AGENT: Final = "MacTech CaptureOS edgar-monitor (please-set-EDGAR_USER_AGENT)"


class EdgarError(Exception):
    pass


class EdgarRateLimitError(EdgarError):
    pass


@dataclass(frozen=True)
class EdgarFiling:
    cik: str  # zero-padded 10-digit
    accession_number: str
    form: str  # e.g. "8-K", "10-K", "10-Q", "DEF 14A"
    filing_date: str  # YYYY-MM-DD
    primary_document: str | None
    primary_doc_url: str | None
    items: list[str] = field(default_factory=list)  # 8-K item codes when present


class EdgarClient:
    def __init__(
        self,
        *,
        user_agent: str | None = None,
        base_url: str = DEFAULT_BASE_URL,
        data_base_url: str = DATA_BASE_URL,
        timeout: httpx.Timeout = DEFAULT_TIMEOUT,
        http_client: httpx.AsyncClient | None = None,
    ) -> None:
        ua = user_agent or DEFAULT_USER_AGENT
        if "please-set" in ua:
            log.warning(
                "EDGAR user-agent not configured. SEC may rate-limit "
                "or block requests. Set EDGAR_USER_AGENT env var."
            )
        self._user_agent = ua
        self._base_url = base_url.rstrip("/")
        self._data_base_url = data_base_url.rstrip("/")
        self._owns_client = http_client is None
        self._http = http_client or httpx.AsyncClient(
            timeout=timeout,
            headers={
                "User-Agent": ua,
                "Accept": "application/json",
                "Accept-Encoding": "gzip, deflate",
            },
        )

    async def __aenter__(self) -> EdgarClient:
        return self

    async def __aexit__(self, *exc: object) -> None:
        if self._owns_client:
            await self._http.aclose()

    async def _request(self, url: str) -> httpx.Response:
        async for attempt in AsyncRetrying(
            wait=wait_random_exponential(multiplier=1, max=20),
            stop=stop_after_attempt(3),
            retry=retry_if_exception_type((httpx.TransportError, EdgarRateLimitError)),
            reraise=True,
        ):
            with attempt:
                resp = await self._http.get(url)
                if resp.status_code == 429:
                    raise EdgarRateLimitError(f"SEC EDGAR 429 on {url} — backing off")
                if resp.status_code >= 400:
                    raise EdgarError(f"SEC EDGAR {resp.status_code} on {url}: {resp.text[:200]}")
                return resp
        raise EdgarError("retry loop exited unexpectedly")

    async def fetch_company_tickers(self) -> dict[str, dict]:
        """Pull SEC's company-ticker dump. Returns dict keyed by ticker
        symbol with values like {cik_str: 320193, ticker: 'AAPL',
        title: 'Apple Inc.'}. ~10,000 entries."""
        resp = await self._request(f"{self._base_url}/files/company_tickers.json")
        payload = resp.json()
        # Format: {"0": {...}, "1": {...}, ...}
        if isinstance(payload, dict):
            out: dict[str, dict] = {}
            for v in payload.values():
                if isinstance(v, dict) and v.get("ticker"):
                    out[v["ticker"]] = v
            return out
        return {}

    async def fetch_recent_filings(
        self, cik: int | str, *, forms: tuple[str, ...] = ("8-K", "10-K", "10-Q")
    ) -> list[EdgarFiling]:
        """Pull recent filings for a CIK. Returns a list of EdgarFiling
        ordered by filing date desc, filtered to the given forms."""
        cik_padded = str(int(str(cik))).zfill(10)
        resp = await self._request(f"{self._data_base_url}/submissions/CIK{cik_padded}.json")
        payload = resp.json()
        recent = (payload.get("filings") or {}).get("recent") or {}
        forms_list = recent.get("form") or []
        dates_list = recent.get("filingDate") or []
        access_list = recent.get("accessionNumber") or []
        primary_docs = recent.get("primaryDocument") or []
        items_list = recent.get("items") or []

        out: list[EdgarFiling] = []
        for i, form in enumerate(forms_list):
            if form not in forms:
                continue
            accession = access_list[i] if i < len(access_list) else ""
            primary_doc = primary_docs[i] if i < len(primary_docs) else None
            primary_doc_url = None
            if accession and primary_doc:
                accession_no_dashes = accession.replace("-", "")
                primary_doc_url = (
                    f"{self._base_url}/Archives/edgar/data/"
                    f"{int(cik_padded)}/{accession_no_dashes}/{primary_doc}"
                )
            items_str = items_list[i] if i < len(items_list) else ""
            items = [s.strip() for s in items_str.split(",") if s.strip()] if items_str else []
            out.append(
                EdgarFiling(
                    cik=cik_padded,
                    accession_number=accession,
                    form=form,
                    filing_date=dates_list[i] if i < len(dates_list) else "",
                    primary_document=primary_doc,
                    primary_doc_url=primary_doc_url,
                    items=items,
                )
            )
        return out

    async def fetch_primary_document(self, filing: EdgarFiling, *, max_chars: int = 30_000) -> str:
        """Fetch the text of a filing's primary document. Strips HTML
        tags coarsely; the worker passes this to Claude for distress
        extraction so cleanup quality matters less than recall."""
        if not filing.primary_doc_url:
            return ""
        resp = await self._request(filing.primary_doc_url)
        # Most primary docs are HTML; some are plain text. Strip tags.
        text = resp.text
        if "<" in text and ">" in text:
            # Coarse but cheap tag strip — good enough for an LLM
            # signal pass. We're not building a parser here.
            import re

            text = re.sub(r"<script[^>]*>.*?</script>", " ", text, flags=re.S | re.I)
            text = re.sub(r"<style[^>]*>.*?</style>", " ", text, flags=re.S | re.I)
            text = re.sub(r"<[^>]+>", " ", text)
            text = re.sub(r"\s+", " ", text).strip()
        return text[:max_chars]
