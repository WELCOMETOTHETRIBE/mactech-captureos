"""Prime-target ranker tests."""

from __future__ import annotations

from mactech_intelligence.prime_targets import AwardRow, rank_prime_targets


def _a(name, uei, amt, agency="Department of Defense", naics="236220", award_id=None):
    return AwardRow(
        recipient_name=name, recipient_uei=uei, award_id=award_id or f"{name}-{amt}",
        award_amount=amt, awarding_agency=agency, naics_code=naics,
    )


def test_aggregates_and_ranks_by_dollars():
    awards = [
        _a("Big Prime LLC", "UEI1", 8_000_000, award_id="X1"),
        _a("Big Prime LLC", "UEI1", 4_000_000, award_id="X2"),
        _a("Small Shop Inc", "UEI2", 1_200_000),
    ]
    cands = rank_prime_targets(awards)
    assert [c.name for c in cands] == ["Big Prime LLC", "Small Shop Inc"]
    top = cands[0]
    assert top.total_recent_award_amount == 12_000_000
    assert top.award_count == 2
    assert top.confidence == "probable"
    assert set(top.recent_award_ids) == {"X1", "X2"}


def test_dedupes_by_name_when_uei_missing():
    awards = [_a("Acme Controls", None, 2_000_000), _a("acme controls", None, 3_000_000)]
    cands = rank_prime_targets(awards)
    assert len(cands) == 1
    assert cands[0].award_count == 2


def test_single_award_is_only_possible():
    cands = rank_prime_targets([_a("One Hit Co", "U9", 500_000)])
    assert cands[0].confidence == "possible"


def test_evidence_is_backed_by_real_awards():
    cands = rank_prime_targets([_a("Evidence Co", "U1", 3_000_000, award_id="AW-1")])
    ev = cands[0].evidence
    assert ev and ev[0]["award_id"] == "AW-1" and ev[0]["source"] == "usaspending"


def test_limit_caps_candidates():
    awards = [_a(f"Firm {i}", f"U{i}", 1_000_000 * (i + 1)) for i in range(20)]
    assert len(rank_prime_targets(awards, limit=5)) == 5


def test_empty_awards_yields_nothing():
    assert rank_prime_targets([]) == []
