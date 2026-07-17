"""Query-family builder tests (Slice 1 retrieval)."""

from __future__ import annotations

from mactech_intelligence.cyber_scope.sam_search import all_query_groups
from mactech_intelligence.knowledge.query_families import (
    all_family_naics,
    notice_types,
    query_families,
    query_family_groups,
)


def test_five_families_present():
    keys = {f.key for f in query_families()}
    for expected in (
        "family_a_direct_cyber",
        "family_b_training_exercise",
        "family_c_facility_construction",
        "family_d_prime_teaming",
        "family_e_early_stage",
    ):
        assert expected in keys


def test_pipeline_b_leads_with_construction_naics():
    fam = {f.key: f for f in query_families()}
    c = fam["family_c_facility_construction"]
    assert c.pipeline == "B"
    # Recall-first: the broad construction NAICS are present without requiring
    # any cyber language at the API.
    for naics in ("236220", "237310", "238210", "541330"):
        assert naics in c.naics


def test_family_naics_union_is_deduped():
    union = all_family_naics()
    assert len(union) == len(set(union))
    assert "236220" in union and "541512" in union


def test_family_groups_merge_into_sam_query_groups():
    groups = all_query_groups()
    # Static legacy groups still resolve.
    assert "ufgs_shortlist" in groups
    # Family groups are now addressable by key.
    for key in query_family_groups():
        assert key in groups


def test_early_stage_notice_types():
    early = notice_types("early_stage")
    assert "Sources Sought" in early
