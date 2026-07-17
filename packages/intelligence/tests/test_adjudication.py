"""Adjudication evidence-ID validation + evidence assembly tests (pure)."""

from __future__ import annotations

from mactech_intelligence.decision.evidence import (
    _evidence_id,
    assemble_evidence,
    evidence_id_set,
)
from mactech_intelligence.detection import detect_signals
from mactech_intelligence.schemas.adjudication import (
    AdjudicationResult,
    WorkPackage,
    validate_evidence_ids,
)


def test_evidence_id_is_stable_and_prefixed():
    a = _evidence_id("hash1", 0, "FRCS")
    b = _evidence_id("hash1", 0, "FRCS")
    assert a == b and a.startswith("ev:")
    assert _evidence_id("hash1", 1, "FRCS") != a  # ordinal changes id


def test_assemble_evidence_from_real_detection():
    report = detect_signals(
        "UFGS 25 05 11 Cybersecurity for Facility-Related Control Systems; BACnet building automation."
    )
    items = assemble_evidence(report, doc_hash="doc-abc")
    assert items
    ids = evidence_id_set(items)
    assert all(i.startswith("ev:") for i in ids)
    # Ranked by weight (highest first).
    assert items[0].weight >= items[-1].weight


def test_validator_drops_hallucinated_ids_and_empty_packages():
    allowed = {"ev:aaaaaaaaaa", "ev:bbbbbbbbbb"}
    result = AdjudicationResult(
        work_packages=[
            WorkPackage(title="Real WP", evidence_ids=["ev:aaaaaaaaaa", "ev:ZZZ_fake"]),
            WorkPackage(title="Fabricated WP", evidence_ids=["ev:nope1", "ev:nope2"]),
        ]
    )
    cleaned, rejected = validate_evidence_ids(result, allowed)
    # The fabricated-only package is dropped entirely.
    assert [wp.title for wp in cleaned.work_packages] == ["Real WP"]
    # The surviving package keeps only the valid id.
    assert cleaned.work_packages[0].evidence_ids == ["ev:aaaaaaaaaa"]
    # Every hallucinated id is reported.
    assert set(rejected) == {"ev:ZZZ_fake", "ev:nope1", "ev:nope2"}


def test_validator_keeps_fully_valid_packages():
    allowed = {"ev:aaaaaaaaaa"}
    result = AdjudicationResult(
        work_packages=[WorkPackage(title="Good", evidence_ids=["ev:aaaaaaaaaa"])]
    )
    cleaned, rejected = validate_evidence_ids(result, allowed)
    assert len(cleaned.work_packages) == 1 and rejected == []
