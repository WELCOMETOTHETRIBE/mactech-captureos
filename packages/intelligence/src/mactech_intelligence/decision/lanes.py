"""Pursuit lanes + NO_BID reason codes + legacy-model mapping."""

from __future__ import annotations

from typing import Literal

PursuitLane = Literal[
    "PRIME_NOW",
    "PRIME_WITH_PARTNER",
    "SUB_TO_IDENTIFIED_PRIME",
    "SUB_TO_PRIME_NOT_YET_IDENTIFIED",
    "SHAPE_EARLY",
    "WATCH",
    "NO_BID",
]

PURSUIT_LANES: tuple[PursuitLane, ...] = (
    "PRIME_NOW",
    "PRIME_WITH_PARTNER",
    "SUB_TO_IDENTIFIED_PRIME",
    "SUB_TO_PRIME_NOT_YET_IDENTIFIED",
    "SHAPE_EARLY",
    "WATCH",
    "NO_BID",
)

NO_BID_REASON_CODES: tuple[str, ...] = (
    "INELIGIBLE_SET_ASIDE",
    "VEHICLE_UNAVAILABLE",
    "SCOPE_TOO_LARGE",
    "STAFFING_UNREALISTIC",
    "PAST_PERFORMANCE_GAP",
    "MANDATORY_LICENSE_GAP",
    "MANDATORY_CLEARANCE_GAP",
    "BONDING_GAP",
    "GEOGRAPHIC_MISMATCH",
    "DEADLINE_UNWORKABLE",
    "NO_REAL_MACTECH_SCOPE",
    "LOW_MARGIN_COMMODITY",
    "OEM_RESTRICTION",
    "DUPLICATE",
    "EXPIRED",
    "OTHER",
)

# The legacy cyber_scope PursuitModel values (kept populated for back-compat).
LegacyPursuitModel = Literal[
    "NO_ACTION",
    "WATCHLIST",
    "PRIME_PURSUE",
    "SUBCONTRACTOR_PURSUE",
    "CYBER_SUPPORT_ONLY",
    "FRCS_OT_SPECIALIST",
    "CMMC_COMPLIANCE_SUPPORT",
    "CLARIFICATION_REQUIRED",
]


def lane_from_legacy_model(model: str | None) -> PursuitLane:
    """A coarse prior lane from the legacy detector's recommendation, before the
    gates + decision vector refine it. Never authoritative on its own."""
    mapping: dict[str, PursuitLane] = {
        "NO_ACTION": "WATCH",
        "WATCHLIST": "WATCH",
        "CLARIFICATION_REQUIRED": "SHAPE_EARLY",
        "PRIME_PURSUE": "PRIME_NOW",
        "CMMC_COMPLIANCE_SUPPORT": "PRIME_NOW",
        "CYBER_SUPPORT_ONLY": "PRIME_NOW",
        "SUBCONTRACTOR_PURSUE": "SUB_TO_PRIME_NOT_YET_IDENTIFIED",
        "FRCS_OT_SPECIALIST": "SUB_TO_PRIME_NOT_YET_IDENTIFIED",
    }
    return mapping.get(model or "", "WATCH")
