"""Unit tests for score_high_moat.

Five fixtures across rubric corners:
  1. Full sweet-spot: UFGS 25 05 11 + USACE + SDVOSB set-aside + TS/SCI +
     no cyber firms on IVL + construction NAICS → score 95+, sweet-spot True
  2. UFGS hit + construction NAICS + NO clearance — must still flag sweet-spot
  3. TS/SCI only, no UFGS — sweet-spot False, modest score
  4. Set-aside mismatch — full UFGS + USACE but wrong set-aside → no SA pts
  5. No signals — score 5–15 (just velocity_inactive floor)
"""

from __future__ import annotations

import pytest
from mactech_intelligence import HighMoatConfig, HighMoatFacts, score_high_moat
from mactech_intelligence.clause_detector import ClauseFindings


@pytest.fixture
def cfg() -> HighMoatConfig:
    return HighMoatConfig(
        weights={
            "ufgs_25_exact": 35,
            "ufgs_25_division": 20,
            "adjacent_ot_per_hit": 5,
            "adjacent_ot_max": 15,
            "set_aside_exact": 20,
            "set_aside_compatible": 10,
            "agency_priority": 15,
            "agency_dod_other": 8,
            "velocity_bottleneck": 10,
            "velocity_inactive": 5,
            "clearance_ts_sci": 5,
            "clearance_secret": 2,
        },
        priority_agencies=[
            "U.S. Army Corps of Engineers",
            "USACE",
            "Naval Facilities Engineering Command",
            "NAVFAC",
            "Defense Health Agency",
            "Missile Defense Agency",
            "National Reconnaissance Office",
        ],
        traditional_construction_naics={
            "236220",
            "237310",
            "237990",
            "238210",
            "562910",
        },
        sweet_spot_min_score=80,
    )


SDVOSB_CERTS = frozenset({"SDVOSBC", "SDVOSBS", "VSA", "VSS"})
SMALL_BIZ = frozenset({"SBA", "SBP", "SB"})


def _facts(
    *,
    title: str = "Test Opp",
    naics: str | None = "236220",
    set_aside: str | None = "SDVOSBC",
    agency: str | None = "U.S. Army Corps of Engineers",
    findings: ClauseFindings,
    iv_count: int | None = 3,
    iv_cyber: int | None = 0,
    is_active: bool = True,
) -> HighMoatFacts:
    return HighMoatFacts(
        title=title,
        naics_code=naics,
        set_aside=set_aside,
        agency=agency,
        subagency=None,
        is_active=is_active,
        clause_findings=findings,
        interested_vendors_count=iv_count,
        interested_vendors_cyber_count=iv_cyber,
        tenant_set_aside_certs=SDVOSB_CERTS,
        compatible_small_biz=SMALL_BIZ,
    )


def test_full_sweet_spot(cfg: HighMoatConfig) -> None:
    findings = ClauseFindings(
        clause_hits=["ufgs_25_05_11", "frcs", "scada_sec"],
        clearance_hits=["ts_sci"],
        role_hits=["issm"],
        top_clearance="TS_SCI",
        has_ufgs_25_exact=True,
    )
    facts = _facts(
        title="Design-Build Fort Bragg Communications Renovation",
        findings=findings,
    )
    result = score_high_moat(facts, cfg)
    # 35 (ufgs exact) + 10 (adjacent: frcs+scada, capped at 15) + 20 (set-aside)
    # + 15 (USACE) + 10 (velocity bottleneck) + 5 (TS/SCI) = 95
    assert result.score == 95
    assert result.breakdown["ufgs_25_clause"] == 35
    assert result.breakdown["adjacent_ot_ics"] == 10
    assert result.breakdown["set_aside_fit"] == 20
    assert result.breakdown["agency_priority"] == 15
    assert result.breakdown["response_velocity"] == 10
    assert result.breakdown["clearance_capability"] == 5
    assert result.is_high_probability_easy_win is True
    assert "issm" in result.role_triggers


def test_ufgs_hit_no_clearance_still_sweet_spot(cfg: HighMoatConfig) -> None:
    """The headline edge case — clause hit + construction prime, even when
    the spec is clearance-silent, must still flag as a sweet-spot."""
    findings = ClauseFindings(
        clause_hits=["ufgs_25_08_11"],
        clearance_hits=[],
        role_hits=[],
        top_clearance="NONE",
        has_ufgs_25_exact=True,
    )
    facts = _facts(
        title="USACE Lock & Dam Cyber Modernization",
        naics="237990",
        set_aside="SDVOSBC",
        findings=findings,
    )
    result = score_high_moat(facts, cfg)
    # 35 (ufgs) + 0 (no adjacent) + 20 (sa) + 15 (USACE) + 10 (velocity)
    # + 0 (no clearance) = 80
    assert result.score == 80
    assert result.is_high_probability_easy_win is True
    assert result.breakdown["clearance_capability"] == 0


def test_ts_sci_no_ufgs_not_sweet_spot(cfg: HighMoatConfig) -> None:
    """TS/SCI requirement alone — without a UFGS 25 hit — must NOT be a
    sweet-spot. Score should be modest (capability + agency + maybe SA)."""
    findings = ClauseFindings(
        clause_hits=[],
        clearance_hits=["ts_sci", "scif"],
        role_hits=[],
        top_clearance="TS_SCI",
        has_ufgs_25_exact=False,
    )
    facts = _facts(
        title="NIWC Intelligence Cyber Support",
        naics="541519",
        agency="Naval Information Warfare Center Atlantic",
        findings=findings,
    )
    result = score_high_moat(facts, cfg)
    # 0 (clause) + 0 (adjacent) + 20 (SA) + 8 (DoD non-priority) + 10 (velocity)
    # + 5 (TS/SCI) = 43
    assert result.score == 43
    assert result.is_high_probability_easy_win is False


def test_set_aside_mismatch(cfg: HighMoatConfig) -> None:
    """Full UFGS hit + USACE but unrestricted competition — set-aside
    contributes zero. Sweet-spot still fires because the construction
    NAICS + clause + active conditions hold."""
    findings = ClauseFindings(
        clause_hits=["ufgs_25_05_11"],
        clearance_hits=[],
        role_hits=[],
        top_clearance="NONE",
        has_ufgs_25_exact=True,
    )
    facts = _facts(
        set_aside=None,
        findings=findings,
    )
    result = score_high_moat(facts, cfg)
    # 35 (clause) + 0 + 0 (no SA) + 15 (USACE) + 10 (velocity) + 0 = 60
    assert result.breakdown["set_aside_fit"] == 0
    assert result.score == 60
    assert result.is_high_probability_easy_win is True


def test_no_signals_floor(cfg: HighMoatConfig) -> None:
    """An opportunity with no clause, no clearance, no priority agency,
    no IVL fetch, and no set-aside fit should still score the velocity
    inactive floor (5) — nothing else."""
    findings = ClauseFindings(
        clause_hits=[],
        clearance_hits=[],
        role_hits=[],
        top_clearance="NONE",
        has_ufgs_25_exact=False,
    )
    facts = _facts(
        title="Office Supplies",
        naics="453210",
        set_aside="WOSB",  # not in SDVOSB or small-biz frozensets
        agency="GSA",
        findings=findings,
        iv_count=None,
        iv_cyber=None,
    )
    result = score_high_moat(facts, cfg)
    assert result.score == 5  # only velocity_inactive
    assert result.is_high_probability_easy_win is False


def test_ufgs_division_only_half_credit(cfg: HighMoatConfig) -> None:
    """Bare 'UFGS Division 25' mention without the 25 05 11 / 25 08 11 numbers
    gets the half-weight (20), not the headline 35."""
    findings = ClauseFindings(
        clause_hits=["ufgs_25_other"],
        clearance_hits=[],
        role_hits=[],
        top_clearance="NONE",
        has_ufgs_25_exact=False,
        has_ufgs_25_division=True,
    )
    facts = _facts(findings=findings, set_aside=None, agency="GSA")
    result = score_high_moat(facts, cfg)
    assert result.breakdown["ufgs_25_clause"] == 20
    # Sweet-spot also fires here — construction NAICS + UFGS division ref.
    assert result.is_high_probability_easy_win is True


def test_inactive_solicitation_no_sweet_spot(cfg: HighMoatConfig) -> None:
    findings = ClauseFindings(
        clause_hits=["ufgs_25_05_11"],
        clearance_hits=["ts_sci"],
        role_hits=[],
        top_clearance="TS_SCI",
        has_ufgs_25_exact=True,
    )
    facts = _facts(findings=findings, is_active=False)
    result = score_high_moat(facts, cfg)
    assert result.is_high_probability_easy_win is False
    # Score still computes (inactive doesn't zero the score) — just the flag flips.
    assert result.score >= 80
