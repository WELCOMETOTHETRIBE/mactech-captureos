"""Deterministic gates.

Gates are computed in code and OVERRIDE the weighted decision vector. A
``severity="hard"`` gate with ``status="fail"`` forces NO_BID (or suppresses
PRIME_NOW, for the prime-only barriers). Soft gates only lower confidence. The
LLM layer may explain a gate but cannot overrule it. Each gate is a structured,
auditable record (persisted to ``opportunity_gates``).
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date

from mactech_intelligence.decision.facts import DecisionInputs

# Barrier gate_codes that block PRIME_NOW but leave a sub path open.
PRIME_BLOCKING_BARRIERS = frozenset(
    {"BONDING_GAP", "MANDATORY_LICENSE_GAP", "MANDATORY_CLEARANCE_GAP", "VEHICLE_UNAVAILABLE"}
)


@dataclass(frozen=True)
class Gate:
    gate_code: str
    status: str  # pass | fail | unknown | waived
    severity: str  # hard | soft
    reason_code: str | None = None
    detail: str = ""
    source: str = "deterministic"

    @property
    def is_hard_fail(self) -> bool:
        return self.severity == "hard" and self.status == "fail"


def evaluate_gates(inp: DecisionInputs) -> list[Gate]:
    as_of = inp.as_of or date.today()
    gates: list[Gate] = []

    # 1. Expired deadline — hard NO_BID.
    if inp.response_deadline is not None and inp.response_deadline < as_of:
        gates.append(
            Gate(
                "EXPIRED",
                "fail",
                "hard",
                reason_code="EXPIRED",
                detail=f"response deadline {inp.response_deadline} < {as_of}",
            )
        )

    # 2. Ineligible set-aside. Hard only when there is NO sub path.
    if not inp.set_aside_eligible:
        if inp.has_sub_work_package:
            gates.append(
                Gate(
                    "INELIGIBLE_SET_ASIDE",
                    "fail",
                    "soft",
                    reason_code="INELIGIBLE_SET_ASIDE",
                    detail=f"set-aside {inp.set_aside!r} blocks prime; sub path remains",
                )
            )
        else:
            gates.append(
                Gate(
                    "INELIGIBLE_SET_ASIDE",
                    "fail",
                    "hard",
                    reason_code="INELIGIBLE_SET_ASIDE",
                    detail=f"set-aside {inp.set_aside!r} ineligible, no sub path",
                )
            )

    # 3. No real MacTech scope — hard NO_BID (unless FRCS carve-out applies).
    if not inp.has_any_relevant_scope:
        gates.append(
            Gate(
                "NO_REAL_MACTECH_SCOPE",
                "fail",
                "hard",
                reason_code="NO_REAL_MACTECH_SCOPE",
                detail="no direct-cyber, FRCS/OT, training, or facility-adjacency signal",
            )
        )

    # 4. Prime-blocking barriers (bonding / license / clearance / vehicle).
    for code in sorted(inp.hard_barriers & PRIME_BLOCKING_BARRIERS):
        # Hard fail only when there is also no sub path; otherwise it just
        # suppresses PRIME_NOW (recorded soft, engine routes to sub).
        no_sub = not inp.has_sub_work_package
        if code == "VEHICLE_UNAVAILABLE" and no_sub:
            gates.append(
                Gate(
                    code, "fail", "hard", reason_code=code, detail="mandatory vehicle, no sub path"
                )
            )
        else:
            gates.append(
                Gate(
                    code,
                    "fail",
                    "soft",
                    reason_code=code,
                    detail="prime suppressed; sub path evaluated",
                )
            )

    # 5. Construction self-performance dominates → suppress PRIME_NOW, go SUB.
    if inp.naics_is_construction and inp.has_construction_context and not inp.has_direct_cyber:
        gates.append(
            Gate(
                "CONSTRUCTION_SELF_PERFORM",
                "fail",
                "soft",
                reason_code="SCOPE_TOO_LARGE",
                detail="construction-dominant scope; prime suppressed, sub path evaluated",
            )
        )

    # 6. Value beyond prime capacity → suppress PRIME_NOW (soft).
    if (
        inp.estimated_value_high is not None
        and inp.estimated_value_high > inp.capacity.prime_value_max
    ):
        gates.append(
            Gate(
                "SCOPE_TOO_LARGE",
                "fail",
                "soft",
                reason_code="SCOPE_TOO_LARGE",
                detail=f"est. value {inp.estimated_value_high:,.0f} > prime max "
                f"{inp.capacity.prime_value_max:,.0f}",
            )
        )

    # 7. Incumbent exclusion — INFORMATIONAL soft gate (recompete signal; boosts
    #    winability). This is where the incumbent_excluded wiring lands: it is
    #    NOT a MacTech disqualifier, so it never blocks.
    if inp.incumbent_excluded is True:
        gates.append(
            Gate(
                "INCUMBENT_EXCLUDED",
                "fail",
                "soft",
                reason_code=None,
                detail="incumbent is on the SAM exclusions list — strong recompete signal",
                source="exclusions_cache",
            )
        )

    # 8. Incomplete package → soft gate, lowers confidence + triggers a
    #    missing-information action downstream.
    if inp.completeness in ("metadata_only", "description_only"):
        gates.append(
            Gate(
                "INCOMPLETE_PACKAGE",
                "unknown",
                "soft",
                reason_code=None,
                detail=f"analysis based on {inp.completeness}; attachments not fully parsed",
            )
        )

    return gates


def has_hard_fail(gates: list[Gate]) -> bool:
    return any(g.is_hard_fail for g in gates)


def prime_suppressed(gates: list[Gate]) -> bool:
    codes = {g.gate_code for g in gates if g.status == "fail"}
    return bool(
        codes & (PRIME_BLOCKING_BARRIERS | {"CONSTRUCTION_SELF_PERFORM", "SCOPE_TOO_LARGE"})
    )
