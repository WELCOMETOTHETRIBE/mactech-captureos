"""Golden-fixture tests for the decision engine (brief §21).

Twelve canonical scenarios pin the lane classification, gates, and vector
behavior. Inputs are constructed facts (the DB-decoupled ``DecisionInputs``),
so these are pure and fast.
"""

from __future__ import annotations

from datetime import date, timedelta

import pytest
from mactech_intelligence.decision import decide
from mactech_intelligence.decision.facts import DecisionInputs

TODAY = date(2026, 7, 16)
SOON = TODAY + timedelta(days=10)
PAST = TODAY - timedelta(days=5)


# 1 — small SDVOSB CMMC readiness -> PRIME_NOW
def test_fixture_1_cmmc_readiness_prime_now():
    r = decide(DecisionInputs(
        set_aside="SDVOSBC", response_deadline=SOON, as_of=TODAY, notice_type="Solicitation",
        has_direct_cyber=True, relevance_weight=40, estimated_value_high=150_000,
        completeness="all_accessible", has_page_evidence=True,
    ))
    assert r.pursuit_lane == "PRIME_NOW"
    assert r.vector.prime_fit_score >= 60


# 2 — cyber tabletop + AAR -> PRIME_NOW
def test_fixture_2_tabletop_aar_prime_now():
    r = decide(DecisionInputs(
        set_aside="SBA", response_deadline=SOON, as_of=TODAY, notice_type="Combined Synopsis/Solicitation",
        has_direct_cyber=True, estimated_value_high=90_000, completeness="all_accessible",
    ))
    assert r.pursuit_lane == "PRIME_NOW"


# 3 — broad enterprise SOC, above prime capacity -> PRIME_WITH_PARTNER
def test_fixture_3_enterprise_soc_prime_with_partner():
    r = decide(DecisionInputs(
        set_aside="SDVOSBC", response_deadline=SOON, as_of=TODAY, notice_type="Solicitation",
        has_direct_cyber=True, estimated_value_high=2_500_000, completeness="all_accessible",
    ))
    assert r.pursuit_lane == "PRIME_WITH_PARTNER"
    assert "SCOPE_TOO_LARGE" in r.reason_codes


# 4 — $50M design-build with UFGS 25 05 11, primes identified -> SUB_TO_IDENTIFIED_PRIME
def test_fixture_4_design_build_frcs_sub_identified():
    r = decide(DecisionInputs(
        set_aside=None, response_deadline=SOON, as_of=TODAY, notice_type="Solicitation",
        has_frcs_ot=True, has_construction_context=True, naics_is_construction=True,
        estimated_value_high=50_000_000, prime_targets_count=3, completeness="all_accessible",
        has_page_evidence=True, hard_barriers=frozenset({"BONDING_GAP"}),
    ))
    assert r.pursuit_lane == "SUB_TO_IDENTIFIED_PRIME"
    assert r.lane_weight_profile == "sub"


# 5 — HVAC/BAS/BACnet, no explicit cyber phrase -> investigate, not discard
def test_fixture_5_hvac_bas_not_discarded():
    r = decide(DecisionInputs(
        set_aside=None, response_deadline=SOON, as_of=TODAY, notice_type="Solicitation",
        has_facility_adjacency=True, has_construction_context=True, naics_is_construction=True,
        estimated_value_high=8_000_000, completeness="description_only",
    ))
    assert r.pursuit_lane != "NO_BID"
    assert r.pursuit_lane == "SUB_TO_PRIME_NOT_YET_IDENTIFIED"


# 6 — construction, no networked controls, no MacTech work -> NO_BID / NO_REAL_MACTECH_SCOPE
def test_fixture_6_no_scope_no_bid():
    r = decide(DecisionInputs(
        set_aside=None, response_deadline=SOON, as_of=TODAY, notice_type="Solicitation",
        naics_is_construction=True, has_construction_context=True, estimated_value_high=5_000_000,
    ))
    assert r.pursuit_lane == "NO_BID"
    assert "NO_REAL_MACTECH_SCOPE" in r.reason_codes


# 7 — expired but relevant -> NO_BID / EXPIRED
def test_fixture_7_expired_no_bid():
    r = decide(DecisionInputs(
        set_aside="SDVOSBC", response_deadline=PAST, as_of=TODAY, notice_type="Solicitation",
        has_direct_cyber=True, estimated_value_high=200_000, completeness="all_accessible",
    ))
    assert r.pursuit_lane == "NO_BID"
    assert "EXPIRED" in r.reason_codes


# 8 — mandatory vehicle-holder task order -> prime blocked; sub path evaluated
def test_fixture_8_vehicle_blocked_sub_path():
    r = decide(DecisionInputs(
        set_aside=None, response_deadline=SOON, as_of=TODAY, notice_type="Solicitation",
        has_direct_cyber=True, estimated_value_high=1_000_000, completeness="all_accessible",
        hard_barriers=frozenset({"VEHICLE_UNAVAILABLE"}),
    ))
    assert r.pursuit_lane not in ("PRIME_NOW", "PRIME_WITH_PARTNER")
    assert r.pursuit_lane in ("SUB_TO_IDENTIFIED_PRIME", "SUB_TO_PRIME_NOT_YET_IDENTIFIED")


# 9 — restricted / missing attachments -> reduced completeness + human review
def test_fixture_9_incomplete_package_human_review():
    r = decide(DecisionInputs(
        set_aside="SDVOSBC", response_deadline=SOON, as_of=TODAY, notice_type="Solicitation",
        has_direct_cyber=True, estimated_value_high=300_000, completeness="metadata_only",
    ))
    assert r.needs_human_review is True
    assert r.confidence == "low"
    assert r.vector.evidence_completeness_score <= 40
    assert any(g.gate_code == "INCOMPLETE_PACKAGE" for g in r.gates)


# 10 — amendment adds cyber scope + near deadline -> urgent, actionable
def test_fixture_10_amendment_urgent():
    near = TODAY + timedelta(days=2)
    r = decide(DecisionInputs(
        set_aside="SDVOSBC", response_deadline=near, as_of=TODAY, notice_type="Solicitation",
        has_direct_cyber=True, estimated_value_high=250_000, completeness="all_accessible",
    ))
    assert r.vector.urgency_score >= 85
    assert r.pursuit_lane == "PRIME_NOW"


# 11 — false-positive CUI, unrelated to contractor cyber work -> low relevance / NO_BID
def test_fixture_11_false_positive_cui():
    r = decide(DecisionInputs(
        set_aside=None, response_deadline=SOON, as_of=TODAY, notice_type="Grant",
        estimated_value_high=500_000, completeness="description_only",
    ))
    assert r.vector.relevance_score == 0
    assert r.pursuit_lane == "NO_BID"


# 12 — Division 25 spec with real FRCS deliverables + page evidence -> high sub relevance
def test_fixture_12_division_25_high_sub_relevance():
    r = decide(DecisionInputs(
        set_aside=None, response_deadline=SOON, as_of=TODAY, notice_type="Solicitation",
        has_frcs_ot=True, has_construction_context=True, naics_is_construction=True,
        has_page_evidence=True, estimated_value_high=12_000_000, prime_targets_count=0,
        completeness="all_accessible",
    ))
    assert r.pursuit_lane == "SUB_TO_PRIME_NOT_YET_IDENTIFIED"
    assert r.vector.relevance_score >= 55
    assert r.vector.evidence_completeness_score >= 80


# ---- cross-cutting guards ----

def test_hard_gate_overrides_attractive_vector():
    # Attractive scope but expired: NO_BID must win, overall priority capped low.
    r = decide(DecisionInputs(
        set_aside="SDVOSBC", response_deadline=PAST, as_of=TODAY,
        has_direct_cyber=True, has_frcs_ot=True, estimated_value_high=150_000,
        completeness="all_accessible", has_page_evidence=True,
    ))
    assert r.pursuit_lane == "NO_BID"
    assert r.vector.overall_priority_score <= 15


def test_lane_decision_serializes():
    r = decide(DecisionInputs(has_direct_cyber=True, set_aside="SDVOSBC", as_of=TODAY,
                              response_deadline=SOON, completeness="all_accessible"))
    ld = r.to_lane_decision()
    dumped = ld.model_dump()
    assert dumped["pursuit_lane"] == "PRIME_NOW"
    assert "relevance_score" in dumped["vector"]


@pytest.mark.parametrize("completeness,expected", [
    ("metadata_only", 20), ("description_only", 40),
    ("partial_attachments", 60), ("all_accessible", 90),
])
def test_evidence_completeness_ladder(completeness, expected):
    r = decide(DecisionInputs(has_direct_cyber=True, completeness=completeness, as_of=TODAY))
    assert r.vector.evidence_completeness_score == expected
