"""Tests for cyber scope export helpers."""

from mactech_intelligence.cyber_scope.analyze import analyze_cyber_scope
from mactech_intelligence.cyber_scope.export_formats import feed_rows_to_csv
from mactech_intelligence.cyber_scope.llm_exports import (
    CyberScopeOppContext,
    deterministic_clarification_email,
    deterministic_summary,
)
from mactech_intelligence.cyber_scope.sources import CyberScopeTextSource


def test_feed_csv_header_when_empty():
    csv_text = feed_rows_to_csv([])
    assert "analysis_id" in csv_text
    assert "likelihood" in csv_text


def test_deterministic_summary_and_email():
    text = "UFGS 25 05 11 FRCS hidden HVAC controls"
    source = CyberScopeTextSource.from_paste(
        text, {"title": "Facilities Upgrade", "agency": "USACE"}
    )
    analysis = analyze_cyber_scope(source)
    opp = CyberScopeOppContext(title="Facilities Upgrade", agency="USACE")
    summary = deterministic_summary(analysis, opp)
    assert "Facilities Upgrade" in summary
    email = deterministic_clarification_email(analysis, opp)
    assert email["subject"]
    assert "[CO NAME]" in email["body"]
