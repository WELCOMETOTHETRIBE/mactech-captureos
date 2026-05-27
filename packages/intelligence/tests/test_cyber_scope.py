"""Unit tests for cyber scope parser."""

from __future__ import annotations

from mactech_intelligence.cyber_scope.analyze import analyze_cyber_scope
from mactech_intelligence.cyber_scope.sources import CyberScopeTextSource


def test_tier1_250511_critical() -> None:
    text = """
    UFGS 25 05 11 Cybersecurity for Facility-Related Control Systems.
    Facility-Related Control Systems per UFC 4-010-06. DoDI 8510.01 RMF ATO eMASS SSP SAR.
    """
    src = CyberScopeTextSource.from_paste(text, {"title": "USACE HVAC Modernization"})
    result = analyze_cyber_scope(src)
    assert result.ufgs_tier_1_hit
    assert result.overall_cyber_likelihood in ("HIGH", "CRITICAL")
    assert result.recommended_pursuit_model in ("FRCS_OT_SPECIALIST", "SUBCONTRACTOR_PURSUE")


def test_center_of_gravity() -> None:
    text = "UFGS 25 05 11 and UFGS 23 09 23.02 BACnet DDC for HVAC."
    src = CyberScopeTextSource.from_paste(text)
    result = analyze_cyber_scope(src)
    assert result.ufgs_center_of_gravity


def test_hidden_construction_hvac() -> None:
    text = """
    MILCON facilities renovation. UFGS 23 09 23.02 BACnet Direct Digital Control.
    Division 25 building automation. NAVFAC.
    """
    src = CyberScopeTextSource.from_paste(
        text, {"title": "Electrical and HVAC Upgrades Building 400"}
    )
    result = analyze_cyber_scope(src)
    assert result.hidden_scope_indicators or result.overall_cyber_likelihood in (
        "MEDIUM",
        "HIGH",
        "CRITICAL",
    )


def test_pds_siprnet_tier3() -> None:
    text = "UFGS 27 05 29.00 10 Protected Distribution System for SIPRNET."
    src = CyberScopeTextSource.from_paste(text)
    result = analyze_cyber_scope(src)
    assert any(h.normalized_term == "27 05 29.00 10" for h in result.detected_categories.ufgs)


def test_tier8_only_capped() -> None:
    text = "UFGS 01 91 00.15 Building Commissioning and 01 78 24 Facility Data."
    src = CyberScopeTextSource.from_paste(text)
    result = analyze_cyber_scope(src)
    assert result.overall_cyber_likelihood in ("LOW", "MEDIUM", "NONE")
