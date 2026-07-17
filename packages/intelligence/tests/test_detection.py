"""Slice 3 multi-family detection + identifier normalization tests."""

from __future__ import annotations

import pytest
from mactech_intelligence.detection import (
    canonical_dfars,
    canonical_ufgs,
    detect_signals,
    find_identifiers,
)

# ---- identifier normalization ----

@pytest.mark.parametrize(
    "text,expected",
    [
        ("UFGS 25 05 11", "25 05 11"),
        ("Section 25-05-11 applies", "25 05 11"),
        ("see 25 05 11 for cyber", "25 05 11"),
        ("UFGS 25 08 11.00 20", "25 08 11.00 20"),
    ],
)
def test_ufgs_variants_normalize(text, expected):
    hits = [h for h in find_identifiers(text) if h.kind == "ufgs"]
    assert hits, f"no ufgs hit in {text!r}"
    assert hits[0].canonical == expected


@pytest.mark.parametrize(
    "text,expected",
    [
        ("DFARS 252.204-7012", "252.204-7012"),
        ("clause 252.204-7012 applies", "252.204-7012"),
        ("DFARS 252.204–7012 (en dash)", "252.204-7012"),  # noqa: RUF001 - en dash is the point
    ],
)
def test_dfars_variants_normalize(text, expected):
    hits = [h for h in find_identifiers(text) if h.kind == "dfars"]
    assert hits, f"no dfars hit in {text!r}"
    assert hits[0].canonical == expected


def test_canonical_helpers_direct():
    assert canonical_ufgs("UFGS 25 05 11") == "25 05 11"
    assert canonical_dfars("252 204 7012") == "252.204-7012"


def test_bare_six_digits_not_a_false_ufgs():
    # A bare 250511 with no separators / context word must NOT be a UFGS hit.
    hits = [h for h in find_identifiers("invoice number 250511 total") if h.kind == "ufgs"]
    assert not hits


# ---- multi-family detection ----

def test_direct_cyber_signals_detected():
    text = "The contractor shall perform a CMMC Level 2 gap assessment, SSP and POA&M review."
    report = detect_signals(text)
    ids = {h.concept_id for h in report.hits}
    assert "cmmc" in ids and "ssp" in ids and "poam" in ids


def test_dfars_assessment_clauses_detected():
    text = "Offerors must comply with DFARS 252.204-7019 and 252.204-7020 and report to SPRS."
    report = detect_signals(text)
    ids = {h.concept_id for h in report.hits}
    assert "dfars_252_204_7019" in ids
    assert "sprs" in ids
    assert report.has_family("clauses_frameworks")


def test_facility_adjacency_without_cyber_phrase():
    # HVAC/BAS project with no explicit cyber word — must still surface the
    # facility-adjacency signal (the "hidden scope" case).
    text = "Repair the central utility plant chiller controls and BACnet building automation."
    report = detect_signals(text)
    fams = report.families_present()
    assert "construction_systems" in fams or "frcs_ot" in fams
    ids = {h.concept_id for h in report.hits}
    assert "central_plant_controls" in ids or "bacnet" in ids


def test_disqualifier_detection_carries_gate_code():
    text = "Offeror must possess a Top Secret facility clearance and provide payment and performance bonds."
    report = detect_signals(text)
    dq_gates = {h.gate_code for h in report.disqualifiers}
    assert "MANDATORY_CLEARANCE_GAP" in dq_gates
    assert "BONDING_GAP" in dq_gates


def test_false_positive_cui_low_relevance():
    # A CUI mention unrelated to contractor cybersecurity WORK should not light
    # up direct-cyber delivery signals like RMF/CMMC/assessment.
    text = "Recipients must protect Controlled Unclassified Information per agency policy on this grant."
    report = detect_signals(text)
    ids = {h.concept_id for h in report.hits}
    assert "cmmc" not in ids
    assert "rmf" not in ids
    assert "security_controls_assessment" not in ids


def test_pack_version_stamped_on_report():
    report = detect_signals("CMMC")
    assert "cyber_services=" in report.pack_version
