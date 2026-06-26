"""Direct fetch of sbirdashboard.com — no Apify required.

The dashboard is a Next.js app that streams its initial topic data inline
in the served HTML as React Server Component chunks (`self.__next_f.push(...)`
calls). Each chunk carries a JSON-escaped payload that includes the raw
topic objects with their full structure:

  {
    "topic_number":          "DAF26BZ03-DV019",
    "topic_title":           "Safe Falling and Failing For Humanoid Robots",
    "topic_status":          "Open" | "Pre-Release" | "Closed",
    "submission_window_open": "2026-06-24T12:00:00.000Z",
    "submission_deadline":   "2026-07-22T16:00:00.000Z",
    "component":             "USAF" | "USA" | "USN" | "DARPA" | "DLA" | ...
    "solicitation_number":   "26.BX",
    "solicitation_title":    "DoW SBIR 2026 CSO",
    "program":               "SBIR" | "STTR",
  }

We pull the page, regex out every JSON object that has both `topic_number`
and `topic_title`, and parse them. No browser, no Apify credits, no LLM
extraction — sub-second from anywhere with network egress.

This is the primary path for sbirdashboard.com. The Apify worker keeps
the other (less structured) sources covered.
"""

from __future__ import annotations

import json
import logging
import re
from dataclasses import dataclass
from datetime import datetime
from typing import Any

import httpx

log = logging.getLogger(__name__)

DEFAULT_URL = "https://www.sbirdashboard.com/"
DEFAULT_TIMEOUT_SECS = 8.0

_USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 14_6_0) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130 Safari/537.36"
)

# The HTML carries the topic JSON multiple times (once per RSC chunk that
# references it). We dedupe by topic_number when returning.
#
# Match every `{...}` object whose body contains `"topic_number"`. The
# bodies are simple — no nested braces in any topic field — so a non-
# greedy match between matching braces holds.
_TOPIC_OBJ_RE = re.compile(
    r'\{[^{}]*"topic_number"\s*:\s*"[^"]+"[^{}]*\}'
)


class SBIRDashboardError(RuntimeError):
    """Raised when the dashboard cannot be fetched or parsed."""


@dataclass(frozen=True)
class SBIRDashboardTopic:
    topic_number: str
    topic_title: str | None
    topic_status: str | None
    submission_window_open: datetime | None
    submission_deadline: datetime | None
    component: str | None
    solicitation_number: str | None
    solicitation_title: str | None
    program: str | None
    raw: dict[str, Any]


def _parse_dt(s: str | None) -> datetime | None:
    if not s:
        return None
    try:
        return datetime.fromisoformat(s.replace("Z", "+00:00"))
    except (TypeError, ValueError):
        return None


def _parse_topic(raw: dict[str, Any]) -> SBIRDashboardTopic | None:
    topic_number = str(raw.get("topic_number") or "").strip()
    if not topic_number:
        return None
    return SBIRDashboardTopic(
        topic_number=topic_number,
        topic_title=_str_or_none(raw.get("topic_title")),
        topic_status=_str_or_none(raw.get("topic_status")),
        submission_window_open=_parse_dt(_str_or_none(raw.get("submission_window_open"))),
        submission_deadline=_parse_dt(_str_or_none(raw.get("submission_deadline"))),
        component=_str_or_none(raw.get("component")),
        solicitation_number=_str_or_none(raw.get("solicitation_number")),
        solicitation_title=_str_or_none(raw.get("solicitation_title")),
        program=_str_or_none(raw.get("program")),
        raw=raw,
    )


def _str_or_none(v: Any) -> str | None:
    if v is None:
        return None
    s = str(v).strip()
    return s or None


def _extract_topics_from_html(html: str) -> list[SBIRDashboardTopic]:
    """Pull every topic object out of the Next.js RSC stream.

    Topic JSON appears inside `self.__next_f.push(...)` chunks as escaped
    strings ('\\"topic_number\\":\\"DAF…\\"'). We unescape the whole HTML
    once so the regex can see the raw object boundaries, then dedupe by
    topic_number.
    """
    # The RSC stream encodes JSON as a JavaScript string literal — `\"`
    # for quotes, `\\n` for newlines, etc. Unescape both forms so the
    # object boundaries become real braces our regex can match.
    unescaped = html.encode("utf-8").decode("unicode_escape", errors="replace")
    seen: dict[str, SBIRDashboardTopic] = {}
    for match in _TOPIC_OBJ_RE.finditer(unescaped):
        chunk = match.group(0)
        try:
            obj = json.loads(chunk)
        except json.JSONDecodeError:
            continue
        if not isinstance(obj, dict):
            continue
        parsed = _parse_topic(obj)
        if parsed is None:
            continue
        # Last write wins — later occurrences tend to carry the same
        # data, so this is a no-op in practice. Dedupe is what matters.
        seen[parsed.topic_number] = parsed
    return list(seen.values())


async def fetch_sbirdashboard_topics(
    *,
    url: str = DEFAULT_URL,
    timeout_secs: float = DEFAULT_TIMEOUT_SECS,
    client: httpx.AsyncClient | None = None,
) -> list[SBIRDashboardTopic]:
    """Fetch the dashboard and return its current open-topic list.

    Raises SBIRDashboardError on network / HTTP / parse failure. Empty
    list is a valid result (the dashboard could legitimately be empty
    between solicitation cycles); callers can distinguish via the
    exception path.
    """
    headers = {
        "User-Agent": _USER_AGENT,
        "Accept": "text/html",
    }
    own_client = client is None
    actual = client or httpx.AsyncClient(timeout=timeout_secs, headers=headers)
    try:
        try:
            res = await actual.get(url, follow_redirects=True)
        except httpx.HTTPError as exc:
            raise SBIRDashboardError(f"fetch failed: {exc}") from exc
        if res.status_code != 200:
            raise SBIRDashboardError(
                f"unexpected status {res.status_code} from {url}"
            )
        html = res.text
        if not html or len(html) < 1000:
            raise SBIRDashboardError("response was empty or too short")
    finally:
        if own_client:
            await actual.aclose()

    topics = _extract_topics_from_html(html)
    log.info(
        "sbirdashboard fetch: %d unique topics from %d bytes of HTML",
        len(topics),
        len(html),
    )
    return topics
