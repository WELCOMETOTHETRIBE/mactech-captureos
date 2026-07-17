"""The decision engine — vector + gates + lane.

Pure and deterministic. ``decide(inputs)`` computes the nine-dimension decision
vector, evaluates the deterministic gates, and selects one authoritative pursuit
lane. Hard gates override the weighted vector; the lane-specific overall_priority
formula is applied last. Golden fixtures in ``tests/test_decision_engine.py``
pin the twelve scenarios from the overhaul brief.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date

from mactech_intelligence.decision.facts import SDVOSB_CODES, DecisionInputs
from mactech_intelligence.decision.gates import Gate, evaluate_gates
from mactech_intelligence.decision.lanes import PursuitLane
from mactech_intelligence.decision.schemas import (
    FORMULA_VERSION,
    DecisionVector,
    GateRecord,
    LaneDecision,
)

# Prime-suppressing gate codes that a named partner can realistically fill
# (scale/surge, a single license) — keeps PRIME_WITH_PARTNER distinct from
# genuine sub-only blocks (vehicle/bonding/construction dominance).
_FILLABLE_BLOCKS = frozenset({"SCOPE_TOO_LARGE", "MANDATORY_LICENSE_GAP"})
_PRIME_LANES = frozenset({"PRIME_NOW", "PRIME_WITH_PARTNER"})
_SUB_LANES = frozenset({"SUB_TO_IDENTIFIED_PRIME", "SUB_TO_PRIME_NOT_YET_IDENTIFIED"})


@dataclass
class DecisionResult:
    pursuit_lane: PursuitLane
    reason_codes: list[str]
    vector: DecisionVector
    gates: list[Gate]
    confidence: str
    lane_weight_profile: str
    needs_human_review: bool
    legacy_pursuit_model: str | None = None
    evidence_note: str = ""
    extras: dict = field(default_factory=dict)

    def to_lane_decision(self) -> LaneDecision:
        return LaneDecision(
            pursuit_lane=self.pursuit_lane,
            reason_codes=self.reason_codes,
            confidence=self.confidence,
            lane_weight_profile=self.lane_weight_profile,
            formula_version=FORMULA_VERSION,
            vector=self.vector,
            gates=[
                GateRecord(
                    gate_code=g.gate_code,
                    status=g.status,
                    severity=g.severity,
                    reason_code=g.reason_code,
                    detail=g.detail,
                    source=g.source,
                )
                for g in self.gates
            ],
        )


def _clamp(x: float) -> int:
    return max(0, min(100, round(x)))


def _days_to_deadline(inp: DecisionInputs) -> int | None:
    if inp.response_deadline is None:
        return None
    as_of = inp.as_of or date.today()
    return (inp.response_deadline - as_of).days


# ---- dimensions ----


def _relevance(inp: DecisionInputs) -> int:
    s = 0
    if inp.has_direct_cyber:
        s += 40
    if inp.has_frcs_ot:
        s += 40
    if inp.has_facility_adjacency:
        s += 25
    if inp.has_training:
        s += 25
    if inp.has_page_evidence:
        s += 15
    return _clamp(s)


def _prime_fit(inp: DecisionInputs, blocked: bool) -> int:
    if not inp.set_aside_eligible:
        return _clamp(20)
    s = 50
    if inp.has_direct_cyber or inp.has_training:
        s += 20
    if inp.estimated_value_high is not None:
        if inp.capacity.prime_value_min <= inp.estimated_value_high <= inp.capacity.prime_value_max:
            s += 15
        elif inp.estimated_value_high > inp.capacity.prime_value_max:
            s -= 25
    if not inp.naics_is_construction:
        s += 10
    if blocked:
        s -= 30
    return _clamp(s)


def _subcontract_fit(inp: DecisionInputs) -> int:
    s = 20
    if inp.has_frcs_ot:
        s += 35
    if inp.has_facility_adjacency:
        s += 20
    if inp.has_construction_context:
        s += 15
    if inp.prime_targets_count > 0:
        s += 15
    if inp.estimated_value_high is not None and (
        inp.capacity.subcontract_value_min <= inp.estimated_value_high
    ):
        s += 10
    return _clamp(s)


def _winability(inp: DecisionInputs) -> int:
    s = 40
    code = (inp.set_aside or "").upper()
    if inp.sdvosb_certified and code in {c.upper() for c in SDVOSB_CODES}:
        s += 20
    if inp.incumbent_excluded is True:
        s += 15
    if inp.is_early_stage:
        s += 10
    if inp.prime_targets_count > 0:
        s += 10
    return _clamp(s)


def _deliverability(inp: DecisionInputs) -> int:
    s = 70
    s -= 20 * len(inp.hard_barriers)
    if (
        inp.estimated_value_high is not None
        and inp.estimated_value_high > inp.capacity.prime_value_max
    ):
        s -= 15
    if inp.naics_is_construction and inp.has_construction_context and not inp.has_direct_cyber:
        s -= 10
    if (
        inp.estimated_value_high is not None
        and inp.estimated_value_high <= inp.capacity.prime_value_max
    ):
        s += 10
    return _clamp(s)


def _strategic_value(inp: DecisionInputs) -> int:
    s = 40
    if inp.has_frcs_ot:
        s += 20
    if inp.has_direct_cyber:
        s += 10
    if inp.prime_targets_count > 0:
        s += 5
    return _clamp(s)


def _urgency(inp: DecisionInputs) -> int:
    days = _days_to_deadline(inp)
    if days is None:
        return 30
    if days < 0:
        return 0
    if days <= 3:
        return 100
    if days <= 7:
        return 85
    if days <= 14:
        return 70
    if days <= 30:
        return 50
    return 30


_COMPLETENESS_LADDER = {
    "metadata_only": 20,
    "description_only": 40,
    "partial_attachments": 60,
    "all_accessible": 90,
}


def _evidence_completeness(inp: DecisionInputs) -> int:
    return _COMPLETENESS_LADDER.get(inp.completeness, 20)


def _overall(vector: DecisionVector, profile: str) -> int:
    v = vector
    if profile == "sub":
        return _clamp(
            0.25 * v.relevance_score
            + 0.30 * v.subcontract_fit_score
            + 0.15 * v.winability_score
            + 0.15 * v.deliverability_score
            + 0.15 * v.strategic_value_score
        )
    return _clamp(
        0.25 * v.relevance_score
        + 0.25 * v.prime_fit_score
        + 0.20 * v.winability_score
        + 0.20 * v.deliverability_score
        + 0.10 * v.strategic_value_score
    )


# ---- lane selection ----


def _prime_blocking_codes(gates: list[Gate]) -> set[str]:
    from mactech_intelligence.decision.gates import PRIME_BLOCKING_BARRIERS

    suppress = PRIME_BLOCKING_BARRIERS | {"CONSTRUCTION_SELF_PERFORM", "SCOPE_TOO_LARGE"}
    return {g.gate_code for g in gates if g.status == "fail" and g.gate_code in suppress}


def _choose_lane(inp: DecisionInputs, gates: list[Gate]) -> tuple[PursuitLane, list[str], str]:
    hard_fails = [g for g in gates if g.is_hard_fail]
    if hard_fails:
        reasons = [g.reason_code for g in hard_fails if g.reason_code]
        return "NO_BID", reasons or ["OTHER"], "prime"

    blocking = _prime_blocking_codes(gates)
    prime_blocked = bool(blocking)
    has_prime_scope = inp.has_direct_cyber or inp.has_training
    value_ok = (
        inp.estimated_value_high is None or inp.estimated_value_high <= inp.capacity.prime_value_max
    )

    # Shape early: an early-stage notice we can influence, with real scope.
    if inp.is_early_stage and inp.has_any_relevant_scope:
        return "SHAPE_EARLY", [], "prime"

    # Prime now: eligible, unblocked, within capacity, MacTech-primeable scope.
    if has_prime_scope and inp.set_aside_eligible and not prime_blocked and value_ok:
        return "PRIME_NOW", [], "prime"

    # Prime with partner: primeable + eligible, blocked only by a fillable gap.
    if (
        has_prime_scope
        and inp.set_aside_eligible
        and prime_blocked
        and blocking <= _FILLABLE_BLOCKS
    ):
        return "PRIME_WITH_PARTNER", sorted(blocking), "prime"

    # Sub path: a bounded work package under a prime.
    if inp.has_sub_work_package and (
        inp.naics_is_construction
        or prime_blocked
        or not has_prime_scope
        or not value_ok
        or not inp.set_aside_eligible
    ):
        if inp.prime_targets_count > 0:
            return "SUB_TO_IDENTIFIED_PRIME", [], "sub"
        return "SUB_TO_PRIME_NOT_YET_IDENTIFIED", [], "sub"

    # Relevant but not yet actionable.
    if inp.has_any_relevant_scope:
        return "WATCH", [], "prime"

    return "NO_BID", ["NO_REAL_MACTECH_SCOPE"], "prime"


def _confidence(inp: DecisionInputs, vector: DecisionVector) -> str:
    if inp.completeness in ("metadata_only", "description_only"):
        return "low"
    if inp.completeness == "all_accessible" and inp.has_page_evidence:
        return "high"
    return "medium"


def decide(inp: DecisionInputs) -> DecisionResult:
    gates = evaluate_gates(inp)
    blocking = _prime_blocking_codes(gates)

    vector = DecisionVector(
        relevance_score=_relevance(inp),
        prime_fit_score=_prime_fit(inp, bool(blocking)),
        subcontract_fit_score=_subcontract_fit(inp),
        winability_score=_winability(inp),
        deliverability_score=_deliverability(inp),
        strategic_value_score=_strategic_value(inp),
        urgency_score=_urgency(inp),
        evidence_completeness_score=_evidence_completeness(inp),
    )

    lane, reasons, profile = _choose_lane(inp, gates)
    vector.overall_priority_score = _overall(vector, profile)
    # A NO_BID / WATCH should not read as high priority regardless of subscores.
    if lane == "NO_BID":
        vector.overall_priority_score = min(vector.overall_priority_score, 15)
    elif lane == "WATCH":
        vector.overall_priority_score = min(vector.overall_priority_score, 45)

    confidence = _confidence(inp, vector)
    needs_review = confidence == "low" or any(g.gate_code == "INCOMPLETE_PACKAGE" for g in gates)

    return DecisionResult(
        pursuit_lane=lane,
        reason_codes=reasons,
        vector=vector,
        gates=gates,
        confidence=confidence,
        lane_weight_profile=profile,
        needs_human_review=needs_review,
        legacy_pursuit_model=inp.legacy_pursuit_model,
    )
