"""Unit tests for clause_detector.detect.

Six fixtures spanning the corner cases:
  1. UFGS 25 05 11 hit + TS/SCI required
  2. UFGS 25 08 11 hit + no clearance mention (must still flag the clause)
  3. FRCS standalone (adjacent OT signal, no UFGS 25)
  4. Role-only — ISSM/ISSE/RMF Validator with no clause and no clearance
  5. eMASS without ICS/Industrial — must NOT count as OT signal
  6. Civil Works without PLC/cyber — must NOT count as OT signal
"""

from __future__ import annotations

import pytest
from mactech_intelligence import detect_clauses
from mactech_intelligence.clause_detector import ClauseFindings


@pytest.fixture
def patterns() -> dict[str, dict[str, list[str]]]:
    """Mirror of the high_moat_scoring patterns in
    config/mactech_tenant_defaults.yml — kept inline so the unit tests
    don't depend on the YAML loader."""
    return {
        "clause": {
            "ufgs_25_05_11": ["UFGS 25 05 11", "25 05 11"],
            "ufgs_25_08_11": ["UFGS 25 08 11", "25 08 11"],
            "ufgs_25_other": ["UFGS 25", "UFGS Division 25"],
            "ufc_4_010_06": ["UFC 4-010-06"],
            "nist_800_82": ["NIST SP 800-82", "NIST 800-82"],
            "dodi_8500_01": ["DoDI 8500.01"],
            "frcs": ["FRCS", "Facility-Related Control Systems"],
            "umcs": ["UMCS", "Utility Monitoring and Control"],
            "scada_sec": ["SCADA Security", "SCADA cybersecurity"],
            "ot_cyber": ["OT Cybersecurity", "Operational Technology Cyber"],
            "pit_cyber": ["Platform Information Technology", "PIT Cyber"],
            "emass_ics": ["eMASS"],
            "civil_works_plc": ["Civil Works"],
        },
        "clearance": {
            "ts_sci": [
                "TS/SCI",
                "Top Secret/SCI",
                "Top Secret / Sensitive Compartmented",
            ],
            "secret_only": ["Secret clearance"],
            "scif": ["SCIF", "Sensitive Compartmented Information Facility"],
            "polygraph": ["Polygraph", "Full Scope Poly", "CI Poly"],
            "fcl_ts": ["Facility Clearance", "FCL"],
        },
        "role": {
            "csa": ["Cybersecurity Systems Authority"],
            "issm": ["Information System Security Manager", "ISSM"],
            "isse": ["Information System Security Engineer", "ISSE"],
            "rmf_validator": [
                "RMF Validator",
                "Authorized Cybersecurity Professional",
            ],
            "threpao": ["Third-Party Assessment Organization", "3PAO"],
        },
    }


def _detect(text: str, patterns: dict[str, dict[str, list[str]]]) -> ClauseFindings:
    return detect_clauses(
        title=text,
        clause_patterns=patterns["clause"],
        clearance_patterns=patterns["clearance"],
        role_patterns=patterns["role"],
    )


def test_ufgs_25_05_11_with_ts_sci(patterns: dict[str, dict[str, list[str]]]) -> None:
    text = (
        "Design-Build, Fort Bragg Communications Facility — includes UFGS 25 05 11 "
        "cybersecurity for control systems. TS/SCI personnel required."
    )
    findings = _detect(text, patterns)
    assert "ufgs_25_05_11" in findings.clause_hits
    assert findings.has_ufgs_25_exact is True
    assert findings.has_ufgs_25_clause is True
    assert "ts_sci" in findings.clearance_hits
    assert findings.top_clearance == "TS_SCI"


def test_ufgs_25_08_11_clearance_silent(
    patterns: dict[str, dict[str, list[str]]],
) -> None:
    """Critical edge case — UFGS 25 08 11 hit with no clearance language
    must still register as a sweet-spot-eligible clause. Per user direction
    we surface the OT clause even when the spec is clearance-silent."""
    text = (
        "USACE Civil Works dam upgrade — references UFGS 25 08 11 for SCADA security "
        "of the control systems. Award to traditional construction prime."
    )
    findings = _detect(text, patterns)
    assert "ufgs_25_08_11" in findings.clause_hits
    assert findings.has_ufgs_25_exact is True
    assert findings.top_clearance == "NONE"
    # Civil Works + SCADA → civil_works_plc should match the conjunction.
    assert "civil_works_plc" in findings.clause_hits
    # Scada itself doesn't fire because "SCADA security" matches; check
    # the scada_sec family also fires.
    assert "scada_sec" in findings.clause_hits


def test_frcs_standalone_no_ufgs(patterns: dict[str, dict[str, list[str]]]) -> None:
    text = (
        "NAVFAC Pearl Harbor facility — Facility-Related Control Systems integration. "
        "No clearance required."
    )
    findings = _detect(text, patterns)
    assert "frcs" in findings.clause_hits
    assert findings.has_ufgs_25_clause is False
    assert findings.top_clearance == "NONE"


def test_role_only_no_clause_no_clearance(
    patterns: dict[str, dict[str, list[str]]],
) -> None:
    text = (
        "Cyber support services. Need ISSM, ISSE, and RMF Validator staffing. "
        "Generic IT support, no specific control systems work."
    )
    findings = _detect(text, patterns)
    assert findings.clause_hits == []
    assert set(findings.role_hits) >= {"issm", "isse", "rmf_validator"}
    assert findings.top_clearance == "NONE"


def test_emass_without_ics_does_not_count(
    patterns: dict[str, dict[str, list[str]]],
) -> None:
    """eMASS alone is too broad — only counts as an OT signal when paired
    with ICS / Industrial / Control Systems language in the same blob."""
    text = "Standard ATO documentation in eMASS — IT systems boundary."
    findings = _detect(text, patterns)
    assert "emass_ics" not in findings.clause_hits


def test_civil_works_alone_does_not_count(
    patterns: dict[str, dict[str, list[str]]],
) -> None:
    """Civil Works alone is a USACE construction category — not OT signal."""
    text = "USACE Civil Works dredging contract, traditional dredging scope only."
    findings = _detect(text, patterns)
    assert "civil_works_plc" not in findings.clause_hits


def test_ts_sci_word_boundary(patterns: dict[str, dict[str, list[str]]]) -> None:
    """`TSA` should not match `TS`. Word-boundary guard."""
    text = "TSA Aviation Security regulatory compliance — no cyber scope."
    findings = _detect(text, patterns)
    assert findings.top_clearance == "NONE"
