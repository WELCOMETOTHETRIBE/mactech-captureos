"""Weighted scoring and pursuit model recommendation."""

from __future__ import annotations

import re

from mactech_intelligence.cyber_scope.schemas import (
    CyberLikelihood,
    CyberScopeAnalysis,
    DetectionResult,
    PursuitModel,
)
from mactech_intelligence.cyber_scope.ufgs_tiers import check_center_of_gravity

PARSER_VERSION = "1.0.0"

CENTER_OF_GRAVITY_BONUS = 15
HIDDEN_SCOPE_BONUS = 10


def _likelihood_from_score(score: int) -> CyberLikelihood:
    if score >= 85:
        return "CRITICAL"
    if score >= 65:
        return "HIGH"
    if score >= 40:
        return "MEDIUM"
    if score >= 15:
        return "LOW"
    return "NONE"


def _all_weighted_hits(analysis: CyberScopeAnalysis) -> list[DetectionResult]:
    hits: list[DetectionResult] = []
    cats = analysis.detected_categories
    for field in (
        cats.ufc_frcs,
        cats.ufgs,
        cats.rmf_ato_emass,
        cats.nist_cnssi_fips,
        cats.ot_ics_scada_pit,
        cats.branch_specific,
        cats.far_dfars_cmmc,
    ):
        hits.extend(field)
    return hits


def compute_score(
    *,
    dict_hits: dict[str, list[DetectionResult]],
    ufgs_hits: list[DetectionResult],
    hidden_indicators: list[DetectionResult],
    center_of_gravity: bool,
    title: str | None,
) -> int:
    seen: set[str] = set()
    total = 0

    def add(h: DetectionResult) -> None:
        nonlocal total
        key = f"{h.category}:{h.normalized_term}"
        if key in seen:
            return
        seen.add(key)
        total += h.weight

    for hits in dict_hits.values():
        for h in hits:
            if h.category == "rmf_ato_emass" and h.normalized_term == "ATO":
                if not re.search(
                    r"\b(ICS|RMF|FRCS|UFGS|cyber|control\s+system|DoD)\b",
                    " ".join(x.surrounding_text for x in hits),
                    re.I,
                ):
                    continue
            add(h)

    for h in ufgs_hits:
        add(h)

    if center_of_gravity:
        total += CENTER_OF_GRAVITY_BONUS
    if hidden_indicators:
        total += HIDDEN_SCOPE_BONUS

    tier8_only = (
        ufgs_hits
        and all(h.ufgs_tier == 8 for h in ufgs_hits if h.ufgs_tier)
        and not any(h.ufgs_tier and h.ufgs_tier <= 4 for h in ufgs_hits)
    )
    if tier8_only:
        total = min(total, 39)

    return min(100, total)


def recommend_pursuit_model(
    analysis: CyberScopeAnalysis,
    *,
    title: str | None,
) -> PursuitModel:
    likelihood = analysis.overall_cyber_likelihood
    if likelihood == "NONE":
        return "NO_ACTION"
    if likelihood == "LOW":
        return "WATCHLIST"

    tier1 = any(h.ufgs_tier == 1 for h in analysis.detected_categories.ufgs)
    has_250511 = any(h.normalized_term == "25 05 11" for h in analysis.detected_categories.ufgs)
    has_frcs = bool(analysis.detected_categories.ufc_frcs)
    has_rmf = bool(analysis.detected_categories.rmf_ato_emass)
    has_pds = any(
        h.normalized_term == "27 05 29.00 10" for h in analysis.detected_categories.ufgs
    )
    hidden = bool(analysis.hidden_scope_indicators)
    milcon = bool(
        re.search(r"\b(MILCON|construction|facilities)\b", (title or ""), re.I)
        or analysis.detected_categories.branch_specific
    )

    if has_250511 or (tier1 and has_frcs):
        if milcon and hidden:
            return "SUBCONTRACTOR_PURSUE"
        return "FRCS_OT_SPECIALIST"

    if analysis.ufgs_center_of_gravity:
        return "SUBCONTRACTOR_PURSUE"

    if has_rmf and has_pds:
        return "CYBER_SUPPORT_ONLY"

    if has_rmf and milcon:
        return "CYBER_SUPPORT_ONLY"

    tier2_only = (
        any(h.ufgs_tier == 2 for h in analysis.detected_categories.ufgs)
        and not tier1
    )
    if tier2_only or hidden:
        return "CLARIFICATION_REQUIRED"

    if likelihood in ("HIGH", "CRITICAL"):
        return "FRCS_OT_SPECIALIST"

    return "WATCHLIST"


def build_top_signals(all_hits: list[DetectionResult], limit: int = 12) -> list[DetectionResult]:
    ranked = sorted(all_hits, key=lambda h: h.weight, reverse=True)
    seen: set[str] = set()
    out: list[DetectionResult] = []
    for h in ranked:
        key = f"{h.category}:{h.normalized_term}"
        if key in seen:
            continue
        seen.add(key)
        out.append(h)
        if len(out) >= limit:
            break
    return out


def missing_likely_requirements(analysis: CyberScopeAnalysis) -> list[str]:
    missing: list[str] = []
    has_ot = bool(analysis.detected_categories.ot_ics_scada_pit)
    has_tier1 = analysis.ufgs_tier_1_hit
    has_rmf = bool(analysis.detected_categories.rmf_ato_emass)
    if has_ot and not has_tier1:
        missing.append("UFGS 25 05 11 may apply but was not cited — confirm FRCS boundary.")
    if has_tier1 and not has_rmf:
        missing.append("RMF/ATO deliverables (SSP, SAR, eMASS) likely required under DoDI 8510.01.")
    if analysis.hidden_scope_indicators and not has_tier1:
        missing.append("Hidden control-system scope — request explicit UFC 4-010-06 / UFGS 25 05 11 flowdown.")
    return missing
