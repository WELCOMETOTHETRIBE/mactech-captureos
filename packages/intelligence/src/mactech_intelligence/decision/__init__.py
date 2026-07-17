"""The decision engine (Slice 4).

Turns detected signals + eligibility facts into an auditable decision: a
9-dimension decision vector, deterministic hard/soft gates that override the
weighted score, and one of seven authoritative pursuit lanes (with NO_BID reason
codes). All deterministic — the LLM adjudication layer (Slice 5) sits *above*
this and may explain but never overrule a hard gate.

See ``docs/CAPTURE_RULEBOOK.md`` for the lane definitions, gate logic, and the
lane-specific scoring formulas this module implements.
"""

from mactech_intelligence.decision.engine import DecisionInputs, DecisionResult, decide
from mactech_intelligence.decision.gates import Gate, evaluate_gates
from mactech_intelligence.decision.lanes import (
    NO_BID_REASON_CODES,
    PURSUIT_LANES,
    PursuitLane,
    lane_from_legacy_model,
)
from mactech_intelligence.decision.schemas import DecisionVector

__all__ = [
    "NO_BID_REASON_CODES",
    "PURSUIT_LANES",
    "DecisionInputs",
    "DecisionResult",
    "DecisionVector",
    "Gate",
    "PursuitLane",
    "decide",
    "evaluate_gates",
    "lane_from_legacy_model",
]
