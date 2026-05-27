"""Tests for cyber scope SAM search job builder."""

from mactech_intelligence.cyber_scope.sam_search import (
    build_sam_cyber_jobs,
    is_cyber_scope_saved_search,
    record_matches_keywords,
)


def test_is_cyber_scope_saved_search_by_score_field():
    assert is_cyber_scope_saved_search({"score_field": "cyber_scope_score"})
    assert is_cyber_scope_saved_search({"cyber_scope_search": True})
    assert not is_cyber_scope_saved_search({"score_field": "score"})


def test_build_jobs_naics_and_title_group():
    filters = {
        "cyber_scope_search": True,
        "sam_query_group": "ufgs_tier1",
        "naics": ["541519", "236220"],
        "keywords": ["25 05 11", "FRCS"],
    }
    jobs = build_sam_cyber_jobs(
        saved_search_id="abc",
        saved_search_name="Test",
        tenant_id="tenant-1",
        filters=filters,
    )
    assert len(jobs) >= 3
    naics_jobs = [j for j in jobs if j.naics_code and not j.title_query]
    title_jobs = [j for j in jobs if j.title_query]
    assert len(naics_jobs) == 2
    assert len(title_jobs) >= 1


def test_keyword_match():
    assert record_matches_keywords(
        title="HVAC Controls Upgrade",
        solicitation_number="W912HQ-26-R-0001",
        keywords=("BACnet", "UMCS"),
    )
    assert not record_matches_keywords(
        title="Generic office supplies",
        solicitation_number=None,
        keywords=("UFGS 25",),
    )
