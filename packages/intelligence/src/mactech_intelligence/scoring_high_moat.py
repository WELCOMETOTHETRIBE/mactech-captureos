"""High-moat (UFGS 25 / FRCS cyber) scoring track.

Parallel to the general score_opportunity in scoring.py. The clause hit
is the dominant signal — 35 (or 20 for broader Division 25) + up to 15
for adjacent OT/ICS clauses = 50 of 100 points. Clearance is a 5-point
capability tag, not a multiplier.

The 100-point rubric:

  Component                Max  Logic
  UFGS 25 clause hit        35  25 05 11 / 25 08 11 → 35; other UFGS 25 → 20
  Adjacent OT/ICS signal    15  +5 per distinct clause family (UFC, NIST 800-82,
                                DoDI 8500.01, FRCS, UMCS, SCADA, OT cyber, PIT,
                                eMASS+ICS, Civil Works+PLC); capped at 15
  Set-aside fit             20  opp set-aside ∈ tenant certs → 20;
                                compatible small-biz → 10
  Agency priority           15  USACE/NAVFAC/DHA/MDA/NRO → 15; other DoD → 8
  Response velocity         10  IVL has vendors but no cyber firms → 10;
                                IVL inactive (unknown) → 5
  Clearance capability       5  TS/SCI → 5; Secret → 2; (capability tag)

Sweet-spot flag is set when an active solicitation has a UFGS 25 hit AND
the prime is likely a traditional construction firm (NAICS in construction
set OR title regex matches construction keywords). Clearance is intentionally
NOT part of the sweet-spot gate — we want to surface the clause hit even
when clearance is unspecified.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

from mactech_intelligence.clause_detector import ClauseFindings


@dataclass(frozen=True)
class HighMoatConfig:
    """Weights + agency lists + construction NAICS, sourced from
    config/mactech_tenant_defaults.yml ``high_moat_scoring`` block."""

    weights: dict[str, int]
    priority_agencies: list[str]
    traditional_construction_naics: set[str]
    sweet_spot_min_score: int = 80


@dataclass(frozen=True)
class HighMoatFacts:
    """Opportunity-side facts the high-moat scorer needs. Kept separate
    from the general OpportunityFacts so the two trackers can evolve
    independently."""

    title: str
    naics_code: str | None
    set_aside: str | None
    agency: str | None
    subagency: str | None
    is_active: bool
    clause_findings: ClauseFindings
    interested_vendors_count: int | None  # None = list endpoint never called
    interested_vendors_cyber_count: int | None
    # Reused from the general ScoringContext — kept here to make the
    # function callable with no implicit ctx mutation.
    tenant_set_aside_certs: frozenset[str]
    compatible_small_biz: frozenset[str]


@dataclass(frozen=True)
class HighMoatResult:
    score: int  # 0..100
    breakdown: dict[str, int]
    is_high_probability_easy_win: bool
    role_triggers: list[str] = field(default_factory=list)
    why_it_matters_seed: str = ""


# Construction-prime title heuristic. We want to surface UFGS 25 inside
# design-build / FA / construction RFPs where the prime is rarely a cyber firm.
_CONSTRUCTION_TITLE_RE = re.compile(
    r"\b(construct(?:ion)?|renovate|renovation|design[- ]build|"
    r"facility|installation|repair|maintenance|MILCON|new\s+building)\b",
    re.IGNORECASE,
)


def _agency_blob(agency: str | None, subagency: str | None) -> str:
    return " | ".join(filter(None, [agency, subagency])).lower()


def _is_dod_agency(blob: str) -> bool:
    if not blob:
        return False
    return any(
        token in blob
        for token in (
            "department of defense",
            "defense ",
            "dod",
            "army",
            "navy",
            "naval",
            "marine corps",
            "marine ",
            "air force",
            "space force",
            "usace",
            "navfac",
            "dla ",
            "defense logistics",
            "niwc",
            "spawar",
            "afmc",
            "afrl",
            "socom",
        )
    )


def _component_ufgs_clause(findings: ClauseFindings, w: dict[str, int]) -> int:
    if findings.has_ufgs_25_exact:
        return int(w.get("ufgs_25_exact", 35))
    if findings.has_ufgs_25_division:
        return int(w.get("ufgs_25_division", 20))
    return 0


# Clause families that contribute to the adjacent OT/ICS bucket (i.e. anything
# in the configured clause_patterns OTHER than the three UFGS 25 buckets).
_UFGS_FAMILIES: frozenset[str] = frozenset({"ufgs_25_05_11", "ufgs_25_08_11", "ufgs_25_other"})


def _component_adjacent_ot(findings: ClauseFindings, w: dict[str, int]) -> int:
    per_hit = int(w.get("adjacent_ot_per_hit", 5))
    cap = int(w.get("adjacent_ot_max", 15))
    distinct = [h for h in findings.clause_hits if h not in _UFGS_FAMILIES]
    return min(cap, per_hit * len(distinct))


def _component_set_aside(facts: HighMoatFacts, w: dict[str, int]) -> int:
    if not facts.set_aside:
        return 0
    code = facts.set_aside.upper()
    if code in facts.tenant_set_aside_certs:
        return int(w.get("set_aside_exact", 20))
    if code in facts.compatible_small_biz:
        return int(w.get("set_aside_compatible", 10))
    return 0


def _component_agency(facts: HighMoatFacts, cfg: HighMoatConfig, w: dict[str, int]) -> int:
    blob = _agency_blob(facts.agency, facts.subagency)
    if not blob:
        return 0
    for priority in cfg.priority_agencies:
        if priority.lower() in blob:
            return int(w.get("agency_priority", 15))
    if _is_dod_agency(blob):
        return int(w.get("agency_dod_other", 8))
    return 0


def _component_velocity(facts: HighMoatFacts, w: dict[str, int]) -> int:
    if facts.interested_vendors_count is None:
        # List endpoint was never called or returned unavailable — treat as
        # inactive tier (the bottleneck signal can't be confirmed either way).
        return int(w.get("velocity_inactive", 5))
    if facts.interested_vendors_count == 0:
        return int(w.get("velocity_inactive", 5))
    cyber = facts.interested_vendors_cyber_count or 0
    if cyber == 0:
        return int(w.get("velocity_bottleneck", 10))
    return 0


def _component_clearance(findings: ClauseFindings, w: dict[str, int]) -> int:
    if findings.top_clearance == "TS_SCI":
        return int(w.get("clearance_ts_sci", 5))
    if findings.top_clearance == "TS":
        return int(w.get("clearance_ts_sci", 5))
    if findings.top_clearance == "S":
        return int(w.get("clearance_secret", 2))
    return 0


def _prime_likely_construction(facts: HighMoatFacts, cfg: HighMoatConfig) -> bool:
    if facts.naics_code and facts.naics_code in cfg.traditional_construction_naics:
        return True
    return bool(facts.title and _CONSTRUCTION_TITLE_RE.search(facts.title))


def _why_it_matters_seed(
    facts: HighMoatFacts, findings: ClauseFindings, *, sweet_spot: bool
) -> str:
    parts: list[str] = []
    if findings.has_ufgs_25_exact:
        clause = "25 05 11" if "ufgs_25_05_11" in findings.clause_hits else "25 08 11"
        parts.append(f"UFGS {clause} cyber clause cited")
    elif findings.has_ufgs_25_division:
        parts.append("UFGS Division 25 referenced")
    adjacent = [h for h in findings.clause_hits if h not in _UFGS_FAMILIES]
    if adjacent:
        parts.append("adjacent OT/ICS signals: " + ", ".join(sorted(adjacent)[:4]))
    if facts.agency:
        parts.append(f"agency: {facts.agency}")
    if findings.role_hits:
        parts.append("roles called out: " + ", ".join(sorted(findings.role_hits)[:3]))
    if findings.top_clearance != "NONE":
        parts.append(f"clearance: {findings.top_clearance.replace('_', '/')}")
    if sweet_spot:
        parts.append("construction prime — cyber sub gap (high-probability easy win)")
    return " · ".join(parts)


def score_high_moat(facts: HighMoatFacts, cfg: HighMoatConfig) -> HighMoatResult:
    w = cfg.weights
    ufgs_pts = _component_ufgs_clause(facts.clause_findings, w)
    adj_pts = _component_adjacent_ot(facts.clause_findings, w)
    set_aside_pts = _component_set_aside(facts, w)
    agency_pts = _component_agency(facts, cfg, w)
    velocity_pts = _component_velocity(facts, w)
    clearance_pts = _component_clearance(facts.clause_findings, w)

    breakdown = {
        "ufgs_25_clause": ufgs_pts,
        "adjacent_ot_ics": adj_pts,
        "set_aside_fit": set_aside_pts,
        "agency_priority": agency_pts,
        "response_velocity": velocity_pts,
        "clearance_capability": clearance_pts,
    }
    score = max(0, min(100, sum(breakdown.values())))

    sweet_spot = bool(
        facts.is_active
        and facts.clause_findings.has_ufgs_25_clause
        and _prime_likely_construction(facts, cfg)
    )

    seed = _why_it_matters_seed(facts, facts.clause_findings, sweet_spot=sweet_spot)

    return HighMoatResult(
        score=score,
        breakdown=breakdown,
        is_high_probability_easy_win=sweet_spot,
        role_triggers=list(facts.clause_findings.role_hits),
        why_it_matters_seed=seed,
    )
