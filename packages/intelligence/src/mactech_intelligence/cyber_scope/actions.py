"""Suggested actions and SAM search query generation."""

from __future__ import annotations

from mactech_intelligence.cyber_scope.schemas import (
    CyberScopeAnalysis,
    SuggestedAction,
)


def generate_suggested_actions(analysis: CyberScopeAnalysis) -> list[SuggestedAction]:
    actions: list[SuggestedAction] = []
    likelihood = analysis.overall_cyber_likelihood
    model = analysis.recommended_pursuit_model

    if likelihood in ("HIGH", "CRITICAL"):
        actions.append(
            SuggestedAction(
                action_type="CREATE_BID_NO_BID_REVIEW",
                title="Run bid/no-bid review",
                rationale=f"Cyber likelihood {likelihood}; pursuit model {model}.",
                priority="HIGH",
            )
        )
        actions.append(
            SuggestedAction(
                action_type="CREATE_CLAUSE_RISK_LOG",
                title="Draft clause risk log",
                rationale="High-confidence cyber/FRCS/OT signals detected.",
                priority="HIGH",
            )
        )

    if analysis.hidden_scope_indicators:
        actions.append(
            SuggestedAction(
                action_type="REQUEST_CLARIFICATION_FROM_CO_COR",
                title="Request clarification on FRCS/RMF scope",
                rationale="Hidden control-system scope detected without explicit cyber title.",
                priority="URGENT",
            )
        )

    if model == "SUBCONTRACTOR_PURSUE":
        actions.append(
            SuggestedAction(
                action_type="MARK_AS_SUBCONTRACTING_TARGET",
                title="Mark as subcontracting target",
                rationale="Construction/facilities prime scope with embedded cyber/FRCS requirements.",
                priority="HIGH",
            )
        )

    if model == "WATCHLIST" or likelihood == "LOW":
        actions.append(
            SuggestedAction(
                action_type="WATCH_FOR_AMENDMENTS",
                title="Watch for amendments",
                rationale="Weak or emerging cyber indicators — monitor spec amendments.",
                priority="LOW",
            )
        )

    tier8 = any(h.ufgs_tier == 8 for h in analysis.detected_categories.ufgs)
    if tier8 and not analysis.ufgs_tier_1_hit:
        actions.append(
            SuggestedAction(
                action_type="CREATE_TEAM_REVIEW_TASK",
                title="Review submittal / commissioning cyber artifacts",
                rationale="Tier 8 UFGS suggests buried cyber deliverables in closeout package.",
                priority="MEDIUM",
            )
        )

    return actions


def generate_search_queries(analysis: CyberScopeAnalysis) -> dict[str, str]:
    """Ready-to-copy SAM.gov / FPDS / internal search strings."""
    return {
        "sam_ufgs_bullseye": (
            '"UFC 4-010-06" OR "UFGS 25 05 11" OR "25 05 11" OR '
            '"25 08 11.00 20" OR "Cybersecurity for Facility-Related Control Systems"'
        ),
        "sam_ufgs_shortlist": (
            '"25 05 11" OR "25 08 11.00 20" OR "25 10 10" OR "25 08 10" OR '
            '"23 09 00" OR "23 09 23.02" OR "28 10 05" OR "28 08 10" OR '
            '"27 05 29.00 10" OR "26 37 13" OR "40 60 00" OR '
            '"33 09 52" OR "33 09 53" OR "33 09 54" OR "33 09 55"'
        ),
        "sam_rmf_ato": (
            '"DoDI 8510.01" OR "Risk Management Framework" OR "Authority to Operate" OR '
            '"eMASS" OR "System Security Plan" OR "Security Assessment Report"'
        ),
        "sam_ot_ics": (
            '"Operational Technology" OR "Industrial Control Systems" OR "SCADA" OR '
            '"Platform Information Technology" OR "UMCS" OR "BACnet" OR "Direct Digital Control"'
        ),
        "sam_hidden_construction": (
            '("HVAC controls" OR "building automation" OR "UMCS" OR "microgrid" OR '
            '"electronic security systems") AND ("25 05 11" OR "FRCS" OR "RMF" OR "UFGS")'
        ),
        "fpds_companion": (
            '"25 05 11" OR "Facility-Related Control Systems" OR "UFGS 25" OR "RMF" OR "FRCS"'
        ),
        "internal_captureos": "cyber_scope_min:65 OR ufgs_center_of_gravity:true",
    }
