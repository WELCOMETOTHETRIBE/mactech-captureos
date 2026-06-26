"""Parser tests for sbirdashboard.com.

The dashboard's topic JSON lives inside Next.js RSC stream chunks,
escape-encoded into JavaScript string literals. The parser unescapes
and regex-matches every `{...}` object with a `topic_number`.

These tests use synthetic HTML fragments so the suite is hermetic — no
network. The shape (escape encoding, sibling fields) mirrors what the
real dashboard ships today.
"""

from __future__ import annotations

from mactech_integrations.sbirdashboard.client import (
    _extract_topics_from_html,
)

_REAL_SHAPED_FRAGMENT = (
    'self.__next_f.push([1,"…some preamble…'
    '{\\"topic_number\\":\\"DAF26BZ03-DV019\\",'
    '\\"topic_title\\":\\"Safe Falling and Failing For Humanoid Robots\\",'
    '\\"topic_status\\":\\"Open\\",'
    '\\"submission_window_open\\":\\"2026-06-24T12:00:00.000Z\\",'
    '\\"submission_deadline\\":\\"2026-07-22T16:00:00.000Z\\",'
    '\\"component\\":\\"USAF\\",'
    '\\"solicitation_number\\":\\"26.BZ\\",'
    '\\"solicitation_title\\":\\"DoW SBIR 2026 BAA\\",'
    '\\"program\\":\\"SBIR\\"},'
    '{\\"topic_number\\":\\"ARM26BX03-DP007\\",'
    '\\"topic_title\\":\\"xTech|Kinetic Reach Competition\\",'
    '\\"topic_status\\":\\"Pre-Release\\",'
    '\\"submission_deadline\\":\\"2026-12-23T17:00:00.000Z\\",'
    '\\"component\\":\\"ARMY\\",'
    '\\"program\\":\\"SBIR\\"}"])'
)


def test_extracts_multiple_topics_with_full_fields() -> None:
    topics = _extract_topics_from_html(_REAL_SHAPED_FRAGMENT)
    assert len(topics) == 2
    by_num = {t.topic_number: t for t in topics}
    assert "DAF26BZ03-DV019" in by_num
    assert "ARM26BX03-DP007" in by_num

    daf = by_num["DAF26BZ03-DV019"]
    assert daf.topic_title == "Safe Falling and Failing For Humanoid Robots"
    assert daf.component == "USAF"
    assert daf.program == "SBIR"
    assert daf.topic_status == "Open"
    assert daf.submission_deadline is not None
    assert daf.submission_deadline.year == 2026
    assert daf.submission_deadline.month == 7

    arm = by_num["ARM26BX03-DP007"]
    assert arm.component == "ARMY"
    assert arm.topic_status == "Pre-Release"
    assert arm.submission_window_open is None  # missing in fragment


def test_dedupes_repeated_topic_objects() -> None:
    # The real RSC stream emits each topic multiple times across chunks.
    # Parser keeps one row per topic_number.
    doubled = _REAL_SHAPED_FRAGMENT + _REAL_SHAPED_FRAGMENT
    topics = _extract_topics_from_html(doubled)
    assert len(topics) == 2


def test_empty_or_topicless_html_returns_empty() -> None:
    assert _extract_topics_from_html("") == []
    assert _extract_topics_from_html("<html><body>no topics here</body></html>") == []


def test_topic_with_missing_number_is_dropped() -> None:
    fragment = (
        'noise {\\"topic_number\\":\\"\\",\\"topic_title\\":\\"empty id\\"} '
        '{\\"topic_number\\":\\"VALID-001\\",\\"topic_title\\":\\"good\\"}'
    )
    topics = _extract_topics_from_html(fragment)
    assert [t.topic_number for t in topics] == ["VALID-001"]
