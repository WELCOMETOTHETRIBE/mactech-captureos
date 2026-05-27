"""Tests for cyber scope downstream prefill builders."""

from mactech_intelligence.cyber_scope.analyze import analyze_cyber_scope
from mactech_intelligence.cyber_scope.downstream import (
    build_bid_no_bid_review,
    build_clause_risk_entries,
    build_proposal_outline,
)
from mactech_intelligence.cyber_scope.sources import CyberScopeTextSource


def test_clause_risk_entries_from_ufgs_bullseye():
    text = """
    UFGS 25 05 11 Cybersecurity for Facility-Related Control Systems.
    UFGS 25 08 11.00 20 RMF for Facility-Related Control Systems.
    eMASS Authority to Operate System Security Plan.
    """
    source = CyberScopeTextSource.from_paste(
        text,
        {"title": "HVAC Controls Upgrade", "agency": "USACE"},
    )
    analysis = analyze_cyber_scope(source)
    entries = build_clause_risk_entries(analysis)
    assert len(entries) >= 2
    severities = {e["severity"] for e in entries}
    assert "CRITICAL" in severities or "HIGH" in severities
    assert all("sort_order" in e for e in entries)


def test_bid_no_bid_review_prefill():
    text = "UFGS 25 05 11 FRCS DoDI 8510.01 RMF ATO eMASS"
    source = CyberScopeTextSource.from_paste(text, {"title": "Test Opp"})
    analysis = analyze_cyber_scope(source)
    review = build_bid_no_bid_review(analysis, opportunity_title="Test Opp", agency="USACE")
    assert review["recommended_decision"] in ("pending", "no_bid", "bid")
    assert "Cyber Scope Parser" in review["rationale_draft"]
    assert len(review["factors"]) >= 2
    assert review["score"] == analysis.score


def test_proposal_outline_sections():
    text = "UFGS 25 05 11 UFC 4-010-06 FRCS BACnet UMCS"
    source = CyberScopeTextSource.from_paste(text, {"title": "Building Automation"})
    analysis = analyze_cyber_scope(source)
    outline = build_proposal_outline(analysis, opportunity_title="Building Automation")
    assert outline["title"].startswith("Cyber technical outline")
    assert len(outline["sections"]) >= 4
    assert outline["sections"][0]["id"] == "exec"
