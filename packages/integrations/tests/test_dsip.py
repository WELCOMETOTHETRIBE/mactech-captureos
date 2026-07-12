"""Parser + client tests for the DSIP (dodsbirsttr.mil) public API client.

These use synthetic payloads shaped exactly like the live API responses
(captured from real traffic) so the suite is hermetic — no network. Client
HTTP behavior (throttle, retry, pagination) is exercised with a mock
transport.
"""

from __future__ import annotations

import json

import httpx
import pytest
from mactech_integrations.dsip.client import (
    SCOPE_CLOSED,
    SCOPE_OPEN,
    STATUS_CLOSED,
    DsipClient,
    DsipTopicDetail,
    DsipTopicSummary,
    _build_search_param,
    _epoch_ms_to_dt,
    _extract_tpoc,
    _html_to_text,
    _parse_phases,
    _split_keywords,
)

# A search row shaped like the real /topics/search data[] element.
_SEARCH_ROW = {
    "topicStatus": "Pre-Release",
    "cmmcLevel": "Level 1",
    "topicManagers": [
        {
            "center": "ARMY",
            "name": "xTech Team",
            "email": "usarmy.pentagon.mbx.xtechsearch@army.mil",
            "assignmentType": "TPOC",
        }
    ],
    "program": "SBIR",
    "topicTitle": "xTech|Phantum Competition",
    "topicCode": "ARM26BX01-NP003",
    "topicPreReleaseStartDate": 1776117600000,
    "topicQuestionCount": 1,
    "solicitationNumber": "26.BX",
    "topicId": "3f4ca360f47545da8558a294ea8dc36a_86472",
    "component": "ARMY",
    "solicitationTitle": "DoW SBIR 2026 CSO",
    "phaseHierarchy": (
        '{"config": [{"phase": "1", "displayValue": "I", "hasConfiguration": "Y"},'
        ' {"phase": "2", "displayValue": "II", "hasConfiguration": "Y"}]}'
    ),
    "topicStartDate": 1786363200000,
    "topicEndDate": 1787932800000,
    "cycleName": "DOD_SBIR_2026_P1_CBX",
}

_DETAIL = {
    "topicId": "3f4ca360f47545da8558a294ea8dc36a_86472",
    "objective": "<p>Seek <b>quantum</b> sensor solutions.</p>",
    "description": "<p>Line one.</p><p>Line two.</p>",
    "phase1Description": "Phase I scope.",
    "phase2Description": "Phase II scope.",
    "phase3Description": None,
    "keywords": "Quantum Sensors; PNT; RF Sensors",
    "technologyAreas": ["Materials"],
    "focusAreas": ["Quantum Science", "Integrated Sensing and Cyber"],
    "itar": False,
    "cmmcLevel": "Level 1",
    "referenceDocuments": [
        {
            "referenceType": "REFERENCE_TEXT",
            "referenceTitle": "<p><u>https://www.xtech.army.mil/</u></p>",
            "url": None,
        }
    ],
}


def test_html_to_text_collapses_tags_and_breaks() -> None:
    assert _html_to_text("<p>Line one.</p><p>Line two.</p>") == "Line one.\nLine two."
    assert _html_to_text("a<br/>b") == "a\nb"
    assert _html_to_text("<p>x &amp; y</p>") == "x & y"
    assert _html_to_text("   ") is None
    assert _html_to_text(None) is None


def test_epoch_ms_conversion() -> None:
    dt = _epoch_ms_to_dt(1786363200000)
    assert dt is not None
    assert dt.year == 2026
    assert dt.tzinfo is not None
    assert _epoch_ms_to_dt(None) is None
    assert _epoch_ms_to_dt("garbage") is None


def test_parse_phases() -> None:
    assert _parse_phases(_SEARCH_ROW["phaseHierarchy"]) == ["I", "II"]
    assert _parse_phases(None) == []
    assert _parse_phases("not json") == []


def test_split_keywords_semicolon_and_comma() -> None:
    assert _split_keywords("A; B; C") == ["A", "B", "C"]
    assert _split_keywords("A, B, C") == ["A", "B", "C"]
    assert _split_keywords("") == []
    assert _split_keywords(None) == []


def test_extract_tpoc_prefers_tpoc_assignment() -> None:
    tpoc = _extract_tpoc(_SEARCH_ROW["topicManagers"])
    assert tpoc == "xTech Team <usarmy.pentagon.mbx.xtechsearch@army.mil>"
    assert _extract_tpoc([]) is None
    assert _extract_tpoc(None) is None


def test_summary_from_row() -> None:
    s = DsipTopicSummary.from_row(_SEARCH_ROW)
    assert s is not None
    assert s.topic_code == "ARM26BX01-NP003"
    assert s.component == "ARMY"
    assert s.program == "SBIR"
    assert s.status == "Pre-Release"
    assert s.phases == ["I", "II"]
    assert s.tpoc and s.tpoc.startswith("xTech Team")
    assert s.open_date and s.open_date.year == 2026
    assert s.question_count == 1


def test_summary_from_row_requires_id_and_code() -> None:
    assert DsipTopicSummary.from_row({"topicId": "x"}) is None
    assert DsipTopicSummary.from_row({"topicCode": "y"}) is None


def test_detail_from_payload_and_composed_description() -> None:
    d = DsipTopicDetail.from_payload(_DETAIL["topicId"], _DETAIL)
    assert d.objective == "Seek quantum sensor solutions."
    assert d.description == "Line one.\nLine two."
    assert d.keywords == ["Quantum Sensors", "PNT", "RF Sensors"]
    assert d.technology_areas == ["Materials"]
    assert d.focus_areas == ["Quantum Science", "Integrated Sensing and Cyber"]
    assert d.itar is False
    assert len(d.references) == 1
    assert d.references[0].title == "https://www.xtech.army.mil/"

    composed = d.composed_description()
    assert composed is not None
    assert "OBJECTIVE" in composed
    assert "PHASE I" in composed
    assert "PHASE II" in composed
    # phase3 was None → its section is omitted.
    assert "PHASE III" not in composed


def _mock_transport(handler):
    return httpx.MockTransport(handler)


@pytest.mark.asyncio
async def test_search_page_parses_total_and_rows() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert "/topics/search" in request.url.path
        # searchParam is URL-encoded JSON (not base64) — decodable to dict.
        sp = json.loads(request.url.params["searchParam"])
        assert sp["solicitationCycleNames"] == ["openTopics"]
        return httpx.Response(200, json={"total": 2, "data": [_SEARCH_ROW, _SEARCH_ROW]})

    async with httpx.AsyncClient(transport=_mock_transport(handler)) as http:
        client = DsipClient(http_client=http, min_request_interval_seconds=0.0)
        page = await client.search_page(size=50, page=0)
    assert page.total == 2
    assert len(page.topics) == 2


@pytest.mark.asyncio
async def test_get_retries_on_503_then_succeeds() -> None:
    calls = {"n": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        calls["n"] += 1
        if calls["n"] == 1:
            return httpx.Response(503, text="temporarily unavailable")
        return httpx.Response(200, json={"total": 0, "data": []})

    async with httpx.AsyncClient(transport=_mock_transport(handler)) as http:
        client = DsipClient(http_client=http, min_request_interval_seconds=0.0)
        page = await client.search_page()
    assert calls["n"] == 2
    assert page.total == 0


@pytest.mark.asyncio
async def test_iter_topics_paginates_until_total_met() -> None:
    def row(code: str) -> dict:
        r = dict(_SEARCH_ROW)
        r["topicCode"] = code
        r["topicId"] = f"id-{code}"
        return r

    def handler(request: httpx.Request) -> httpx.Response:
        page = int(request.url.params["page"])
        if page == 0:
            return httpx.Response(200, json={"total": 3, "data": [row("A"), row("B")]})
        return httpx.Response(200, json={"total": 3, "data": [row("C")]})

    async with httpx.AsyncClient(transport=_mock_transport(handler)) as http:
        client = DsipClient(http_client=http, min_request_interval_seconds=0.0)
        topics = await client.iter_topics(page_size=2)
    assert [t.topic_code for t in topics] == ["A", "B", "C"]


def test_build_search_param_scopes() -> None:
    op = _build_search_param(SCOPE_OPEN, None)
    assert op["solicitationCycleNames"] == ["openTopics"]
    assert op["sortBy"] == "finalTopicCode,asc"

    cl = _build_search_param(SCOPE_CLOSED, None)
    # Closed topics live in past cycles (cycle names must be null) and sort
    # newest-closed first so a capped pull gets the most recent.
    assert cl["solicitationCycleNames"] is None
    assert cl["topicReleaseStatus"] == [STATUS_CLOSED]
    assert cl["sortBy"] == "topicEndDate,desc"

    with pytest.raises(ValueError):
        _build_search_param("bogus", None)


@pytest.mark.asyncio
async def test_iter_topics_respects_max_topics_cap() -> None:
    def row(i: int) -> dict:
        r = dict(_SEARCH_ROW)
        r["topicCode"] = f"C{i}"
        r["topicId"] = f"id-{i}"
        return r

    def handler(request: httpx.Request) -> httpx.Response:
        page = int(request.url.params["page"])
        data = [row(page * 50 + j) for j in range(50)]
        return httpx.Response(200, json={"total": 1000, "data": data})

    async with httpx.AsyncClient(transport=_mock_transport(handler)) as http:
        client = DsipClient(http_client=http, min_request_interval_seconds=0.0)
        topics = await client.iter_topics(scope=SCOPE_CLOSED, page_size=50, max_topics=120)
    # Cap honored exactly even though 1000 are "available".
    assert len(topics) == 120


@pytest.mark.asyncio
async def test_resolve_topic_id_exact_match() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        sp = json.loads(request.url.params["searchParam"])
        assert sp["searchText"] == "ARM26BX01-NP003"
        return httpx.Response(200, json={"total": 1, "data": [_SEARCH_ROW]})

    async with httpx.AsyncClient(transport=_mock_transport(handler)) as http:
        client = DsipClient(http_client=http, min_request_interval_seconds=0.0)
        s = await client.resolve_topic_id("ARM26BX01-NP003")
    assert s is not None
    assert s.topic_id == "3f4ca360f47545da8558a294ea8dc36a_86472"
