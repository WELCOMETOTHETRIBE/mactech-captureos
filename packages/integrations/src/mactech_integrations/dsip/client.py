"""DSIP (dodsbirsttr.mil) public API client — direct, no browser, no Apify.

The DoD SBIR/STTR Innovation Portal ships a public Angular SPA at
`/topics-app/`, backed by an unauthenticated JSON API under
`/topics/api/public/`. Despite an old assumption in this codebase that the
API "firewalls direct server-side calls," it does not: plain server-side
requests (no cookies, no browser) return 200 for every endpoint we need.

Endpoints (all GET, all public):

  topics/search?searchParam=<url-encoded JSON>&size=N&page=P
      Paginated topic list. `searchParam` is **URL-encoded JSON, not
      base64**. Returns {"total": <int>, "data": [ ...summary rows... ]}.
      The exact schema matters — a malformed body yields HTTP 400
      "Invalid search request!" and a missing key yields HTTP 500/503.

  topics/{topicId}/details
      Full topic content: objective, description, phase 1/2/3 scope,
      keywords, technology + focus areas, ITAR flag, reference documents.

  topics/{topicId}/questions
      Public SITIS Q&A for the topic.

  topics/{topicId}/download/PDF
      The official topic PDF (application/pdf).

Dates come back as epoch milliseconds. Component is an uppercase code
("ARMY", "USAF", "NAVY", ...). Keywords are a single ';'-joined string.

DSIP is occasionally flaky (intermittent 503 on the search endpoint even
for a valid request), so every call goes through a throttled, retrying
wrapper — same pattern as `usaspending/client.py`.
"""

from __future__ import annotations

import asyncio
import html
import json
import logging
import re
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any, Final

import httpx
from tenacity import (
    AsyncRetrying,
    retry_if_exception_type,
    stop_after_attempt,
    wait_random_exponential,
)

log = logging.getLogger(__name__)

DEFAULT_BASE_URL: Final = "https://www.dodsbirsttr.mil/topics/api/public"
# DSIP does not gate on User-Agent, but it 500s on an empty/absent one from
# some egress IPs — send a normal browser UA for traceability + reliability.
DEFAULT_USER_AGENT: Final = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 14_6) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/130 Safari/537.36"
)
DEFAULT_TIMEOUT: Final = httpx.Timeout(30.0, connect=10.0)

# DSIP release-status codes (from /core/api/public/dropdown/lookup
# ?type=topics.release_status). Open + pre-release are the actionable feed;
# closed is the historical archive (~32k topics back to 2003).
STATUS_PRERELEASE: Final = 592
STATUS_OPEN: Final = 591
STATUS_CLOSED: Final = 593

# Search scopes. "open" = open + pre-release via the SPA's special
# `openTopics` cycle grouping (captured verbatim from live traffic). "closed"
# = closed topics across all past cycles, newest-first by close date. Every
# key must be present or DSIP rejects the body with 400/500.
SCOPE_OPEN: Final = "open"
SCOPE_CLOSED: Final = "closed"

_BASE_PARAM: Final[dict[str, Any]] = {
    "searchText": None,
    "components": None,
    "programYear": None,
    "solicitationCycleNames": ["openTopics"],
    "releaseNumbers": [],
    "topicReleaseStatus": [STATUS_OPEN, STATUS_PRERELEASE],
    "modernizationPriorities": [],
    "sortBy": "finalTopicCode,asc",
    "technologyAreaIds": [],
    "component": None,
    "program": None,
}

# Per-scope overrides layered onto _BASE_PARAM. Closed topics live in past
# cycles (solicitationCycleNames must be null, not "openTopics") and are
# sorted by close date descending so a capped pull gets the most recent.
_SCOPE_OVERRIDES: Final[dict[str, dict[str, Any]]] = {
    SCOPE_OPEN: {},
    SCOPE_CLOSED: {
        "solicitationCycleNames": None,
        "topicReleaseStatus": [STATUS_CLOSED],
        "sortBy": "topicEndDate,desc",
    },
}


def _build_search_param(scope: str, search_text: str | None) -> dict[str, Any]:
    if scope not in _SCOPE_OVERRIDES:
        raise ValueError(f"unknown DSIP scope: {scope!r}")
    param = dict(_BASE_PARAM)
    param.update(_SCOPE_OVERRIDES[scope])
    if search_text:
        param["searchText"] = search_text
    return param


# The details endpoint fields are rich text (HTML fragments). We keep the raw
# HTML in `.raw` but expose cleaned plain text on the dataclass fields.
_TAG_RE = re.compile(r"<[^>]+>")
_BLOCK_CLOSE_RE = re.compile(r"</(p|div|li|ul|ol|tr|h[1-6])\s*>", re.IGNORECASE)
_BR_RE = re.compile(r"<br\s*/?>", re.IGNORECASE)


class DsipError(Exception):
    """Terminal DSIP failure (4xx we won't retry, or exhausted retries)."""


class DsipRetryableError(DsipError):
    """Transient DSIP failure (429/5xx/transport) — retried with backoff."""


def _html_to_text(raw: str | None) -> str | None:
    """Collapse a DSIP HTML fragment to readable plain text.

    Block-close tags and <br> become newlines; remaining tags are stripped;
    HTML entities are unescaped. Returns None for empty/whitespace input.
    """
    if not raw:
        return None
    s = _BR_RE.sub("\n", raw)
    s = _BLOCK_CLOSE_RE.sub("\n", s)
    s = _TAG_RE.sub("", s)
    s = html.unescape(s)
    # Normalize whitespace runs but keep paragraph breaks.
    s = re.sub(r"[ \t]+", " ", s)
    s = re.sub(r"\n\s*\n\s*\n+", "\n\n", s)
    return s.strip() or None


def _epoch_ms_to_dt(v: Any) -> datetime | None:
    if v is None:
        return None
    try:
        return datetime.fromtimestamp(int(v) / 1000, tz=UTC)
    except (TypeError, ValueError, OSError):
        return None


def _str_or_none(v: Any) -> str | None:
    if v is None:
        return None
    s = str(v).strip()
    return s or None


def _parse_phases(phase_hierarchy: Any) -> list[str]:
    """Pull display values ('I', 'II', 'SPII', ...) from the phaseHierarchy
    JSON string carried on each summary row."""
    if not phase_hierarchy:
        return []
    try:
        cfg = json.loads(phase_hierarchy).get("config", [])
    except (TypeError, ValueError, AttributeError):
        return []
    out: list[str] = []
    for c in cfg:
        if isinstance(c, dict):
            dv = _str_or_none(c.get("displayValue"))
            if dv:
                out.append(dv)
    return out


def _extract_tpoc(managers: Any) -> str | None:
    """Format the Technical Point(s) of Contact from `topicManagers`.

    Prefer entries flagged assignmentType == 'TPOC'; fall back to all
    managers. Each rendered as 'Name <email>' where available.
    """
    if not isinstance(managers, list) or not managers:
        return None
    tpocs = [
        m
        for m in managers
        if isinstance(m, dict) and str(m.get("assignmentType") or "").upper() == "TPOC"
    ] or [m for m in managers if isinstance(m, dict)]
    parts: list[str] = []
    for m in tpocs:
        name = _str_or_none(m.get("name"))
        email = _str_or_none(m.get("email"))
        if name and email:
            parts.append(f"{name} <{email}>")
        elif name:
            parts.append(name)
        elif email:
            parts.append(email)
    return "; ".join(parts)[:512] or None


def _split_keywords(raw: Any) -> list[str]:
    """DSIP keywords are one ';'-joined string (occasionally ',' separated)."""
    s = _str_or_none(raw)
    if not s:
        return []
    parts = re.split(r"[;\n]", s)
    if len(parts) == 1:
        parts = s.split(",")
    return [p.strip() for p in parts if p.strip()]


def _str_list(v: Any) -> list[str]:
    if not isinstance(v, list):
        return []
    return [str(x).strip() for x in v if _str_or_none(x)]


@dataclass(frozen=True)
class DsipReference:
    title: str | None
    url: str | None
    reference_type: str | None


@dataclass(frozen=True)
class DsipTopicSummary:
    """A row from the search endpoint — metadata, no long-form content."""

    topic_id: str
    topic_code: str
    title: str | None
    component: str | None  # raw uppercase code, e.g. "ARMY"
    program: str | None
    status: str | None  # raw, e.g. "Pre-Release" | "Open" | "Closed"
    solicitation_number: str | None
    solicitation_title: str | None
    cycle_name: str | None
    prerelease_start: datetime | None
    open_date: datetime | None
    close_date: datetime | None
    cmmc_level: str | None
    phases: list[str]
    tpoc: str | None
    question_count: int | None
    raw: dict[str, Any]

    @classmethod
    def from_row(cls, row: dict[str, Any]) -> DsipTopicSummary | None:
        topic_id = _str_or_none(row.get("topicId"))
        topic_code = _str_or_none(row.get("topicCode"))
        if not topic_id or not topic_code:
            return None
        return cls(
            topic_id=topic_id,
            topic_code=topic_code,
            title=_str_or_none(row.get("topicTitle")),
            component=_str_or_none(row.get("component")),
            program=_str_or_none(row.get("program")),
            status=_str_or_none(row.get("topicStatus")),
            solicitation_number=_str_or_none(row.get("solicitationNumber")),
            solicitation_title=_str_or_none(row.get("solicitationTitle")),
            cycle_name=_str_or_none(row.get("cycleName")),
            prerelease_start=_epoch_ms_to_dt(row.get("topicPreReleaseStartDate")),
            open_date=_epoch_ms_to_dt(row.get("topicStartDate")),
            close_date=_epoch_ms_to_dt(row.get("topicEndDate")),
            cmmc_level=_str_or_none(row.get("cmmcLevel")),
            phases=_parse_phases(row.get("phaseHierarchy")),
            tpoc=_extract_tpoc(row.get("topicManagers")),
            question_count=(
                int(row["topicQuestionCount"])
                if isinstance(row.get("topicQuestionCount"), int)
                else None
            ),
            raw=row,
        )


@dataclass(frozen=True)
class DsipTopicDetail:
    """The /details payload — full long-form content, cleaned to plain text."""

    topic_id: str
    objective: str | None
    description: str | None
    phase1: str | None
    phase2: str | None
    phase3: str | None
    keywords: list[str]
    technology_areas: list[str]
    focus_areas: list[str]
    itar: bool | None
    cmmc_level: str | None
    references: list[DsipReference]
    raw: dict[str, Any]

    @classmethod
    def from_payload(cls, topic_id: str, d: dict[str, Any]) -> DsipTopicDetail:
        refs: list[DsipReference] = []
        for r in d.get("referenceDocuments") or []:
            if not isinstance(r, dict):
                continue
            refs.append(
                DsipReference(
                    title=_html_to_text(r.get("referenceTitle")),
                    url=_str_or_none(r.get("url")),
                    reference_type=_str_or_none(r.get("referenceType")),
                )
            )
        itar_raw = d.get("itar")
        itar = bool(itar_raw) if isinstance(itar_raw, bool) else None
        return cls(
            topic_id=topic_id,
            objective=_html_to_text(d.get("objective")),
            description=_html_to_text(d.get("description")),
            phase1=_html_to_text(d.get("phase1Description")),
            phase2=_html_to_text(d.get("phase2Description")),
            phase3=_html_to_text(d.get("phase3Description")),
            keywords=_split_keywords(d.get("keywords")),
            technology_areas=_str_list(d.get("technologyAreas")),
            focus_areas=_str_list(d.get("focusAreas")),
            itar=itar,
            cmmc_level=_str_or_none(d.get("cmmcLevel")),
            references=refs,
            raw=d,
        )

    def composed_description(self) -> str | None:
        """Objective + description + phase scope, in reading order — the
        single text blob the submission engine consumes."""
        sections = [
            ("OBJECTIVE", self.objective),
            ("DESCRIPTION", self.description),
            ("PHASE I", self.phase1),
            ("PHASE II", self.phase2),
            ("PHASE III / DUAL USE APPLICATIONS", self.phase3),
        ]
        parts = [f"{label}\n{body}" for label, body in sections if body]
        return "\n\n".join(parts) or None


@dataclass(frozen=True)
class DsipSearchPage:
    total: int
    topics: list[DsipTopicSummary]


@dataclass
class DsipFullTopic:
    """A summary merged with its detail (and optionally Q&A)."""

    summary: DsipTopicSummary
    detail: DsipTopicDetail | None = None
    questions: list[dict[str, Any]] = field(default_factory=list)


class DsipClient:
    """Async client for the DSIP public topics API.

    Usage:
        async with DsipClient() as dsip:
            async for topic in dsip.iter_full_topics():
                ...
    """

    def __init__(
        self,
        *,
        base_url: str = DEFAULT_BASE_URL,
        user_agent: str = DEFAULT_USER_AGENT,
        timeout: httpx.Timeout = DEFAULT_TIMEOUT,
        http_client: httpx.AsyncClient | None = None,
        min_request_interval_seconds: float = 0.35,
        max_attempts: int = 5,
    ) -> None:
        self._base_url = base_url.rstrip("/")
        self._owns_client = http_client is None
        self._http = http_client or httpx.AsyncClient(
            timeout=timeout,
            headers={"User-Agent": user_agent, "Accept": "application/json"},
        )
        self._min_interval = min_request_interval_seconds
        self._max_attempts = max_attempts
        self._lock = asyncio.Lock()
        self._last_request_at = 0.0

    async def __aenter__(self) -> DsipClient:
        return self

    async def __aexit__(self, *exc: object) -> None:
        if self._owns_client:
            await self._http.aclose()

    async def _get(self, path: str, *, params: dict[str, Any] | None = None) -> httpx.Response:
        url = f"{self._base_url}{path}"
        async for attempt in AsyncRetrying(
            stop=stop_after_attempt(self._max_attempts),
            wait=wait_random_exponential(multiplier=1, max=30),
            retry=retry_if_exception_type((httpx.TransportError, DsipRetryableError)),
            reraise=True,
        ):
            with attempt:
                # Hold the lock only long enough to space requests, not for
                # the whole round-trip.
                async with self._lock:
                    now = asyncio.get_event_loop().time()
                    elapsed = now - self._last_request_at
                    if elapsed < self._min_interval:
                        await asyncio.sleep(self._min_interval - elapsed)
                    self._last_request_at = asyncio.get_event_loop().time()
                resp = await self._http.get(url, params=params)
                if resp.status_code == 429:
                    log.warning("dsip 429 on %s — backing off", path)
                    raise DsipRetryableError("rate limited")
                if 500 <= resp.status_code < 600:
                    log.warning("dsip %s on %s — retrying", resp.status_code, path)
                    raise DsipRetryableError(f"server error {resp.status_code}")
                if resp.status_code >= 400:
                    raise DsipError(f"dsip {resp.status_code} on {path}: {resp.text[:200]}")
                return resp
        raise DsipError("unreachable")  # pragma: no cover

    async def search_page(
        self,
        *,
        scope: str = SCOPE_OPEN,
        search_text: str | None = None,
        size: int = 50,
        page: int = 0,
    ) -> DsipSearchPage:
        """One page of the topic search for the given scope (open | closed)."""
        param = _build_search_param(scope, search_text)
        # `searchParam` must be URL-encoded JSON. Let httpx encode the value,
        # but pass the compact JSON string as-is.
        resp = await self._get(
            "/topics/search",
            params={
                "searchParam": json.dumps(param, separators=(",", ":")),
                "size": size,
                "page": page,
            },
        )
        body = resp.json()
        total = int(body.get("total") or 0)
        rows = body.get("data") or []
        topics = [
            s
            for s in (DsipTopicSummary.from_row(r) for r in rows if isinstance(r, dict))
            if s is not None
        ]
        return DsipSearchPage(total=total, topics=topics)

    async def iter_topics(
        self,
        *,
        scope: str = SCOPE_OPEN,
        search_text: str | None = None,
        page_size: int = 50,
        max_topics: int | None = None,
    ) -> list[DsipTopicSummary]:
        """Paginate through topic summaries for the given scope.

        `max_topics` caps the pull (used for the huge closed archive, where
        we take the most-recent N rather than all ~32k). The client's caller
        should `log()` when a cap truncates coverage. Returns whatever was
        gathered up to the cap.
        """
        first = await self.search_page(scope=scope, search_text=search_text, size=page_size, page=0)
        out = list(first.topics)
        seen = {t.topic_id for t in out}
        total = first.total
        page = 1
        while len(out) < total and first.topics:
            if max_topics is not None and len(out) >= max_topics:
                break
            nxt = await self.search_page(
                scope=scope, search_text=search_text, size=page_size, page=page
            )
            if not nxt.topics:
                break
            new = [t for t in nxt.topics if t.topic_id not in seen]
            if not new:
                break
            out.extend(new)
            seen.update(t.topic_id for t in new)
            page += 1
        if max_topics is not None and len(out) > max_topics:
            out = out[:max_topics]
        return out

    async def resolve_topic_id(self, topic_code: str) -> DsipTopicSummary | None:
        """Look up a single topic by its code (e.g. 'ARM26BX01-NP003').

        Used by the enrich path, where we hold a topic_number but not the
        opaque topicId the detail/PDF endpoints require.
        """
        page = await self.search_page(search_text=topic_code, size=10, page=0)
        for t in page.topics:
            if t.topic_code.upper() == topic_code.upper():
                return t
        return page.topics[0] if page.topics else None

    async def fetch_details(self, topic_id: str) -> DsipTopicDetail:
        resp = await self._get(f"/topics/{topic_id}/details")
        return DsipTopicDetail.from_payload(topic_id, resp.json())

    async def fetch_questions(self, topic_id: str) -> list[dict[str, Any]]:
        resp = await self._get(f"/topics/{topic_id}/questions")
        body = resp.json()
        return body if isinstance(body, list) else []

    async def fetch_pdf(self, topic_id: str) -> bytes | None:
        """Download the official topic PDF. Returns None if unavailable."""
        try:
            resp = await self._get(f"/topics/{topic_id}/download/PDF")
        except DsipError as exc:
            log.info("dsip pdf fetch failed for %s: %s", topic_id, exc)
            return None
        content = resp.content
        if len(content) < 1000 or not content[:5].startswith(b"%PDF"):
            return None
        return content

    def pdf_url(self, topic_id: str) -> str:
        return f"{self._base_url}/topics/{topic_id}/download/PDF"

    async def fetch_full_topic(
        self, summary: DsipTopicSummary, *, with_questions: bool = False
    ) -> DsipFullTopic:
        detail: DsipTopicDetail | None = None
        try:
            detail = await self.fetch_details(summary.topic_id)
        except DsipError as exc:
            log.warning(
                "dsip details failed for %s (%s): %s",
                summary.topic_code,
                summary.topic_id,
                exc,
            )
        questions: list[dict[str, Any]] = []
        if with_questions and summary.question_count:
            try:
                questions = await self.fetch_questions(summary.topic_id)
            except DsipError as exc:
                log.info("dsip questions failed for %s: %s", summary.topic_code, exc)
        return DsipFullTopic(summary=summary, detail=detail, questions=questions)
