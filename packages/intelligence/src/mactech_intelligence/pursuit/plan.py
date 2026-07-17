"""Deterministic pursuit-plan builder.

Given the decision (lane, reason codes, confidence), the named prime targets, and
the notice's deadlines, produce an ordered set of dated actions with owners —
sourced from the knowledge pack's ``pursuit_playbooks`` so the cadence is tunable
without code. Owners route by MacTech pillar (cyber→Patrick, quality→Brian,
governance/teaming→John, infrastructure→James).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, timedelta

from mactech_intelligence.knowledge.pack import load_pack

# Default owner is the security pillar — cyber/FRCS work is the core.
_DEFAULT_OWNER = "patrick-caruso"

# Route an action to a founder by keywords in the action text.
_OWNER_ROUTES: list[tuple[tuple[str, ...], str]] = [
    (("nda", "teaming", "legal", "approve", "posture"), "john-milso"),
    (("capability brief", "capability statement", "past performance", "past-performance",
      "quality"), "brian-macdonald"),
    (("network", "infrastructure", "architecture"), "james-adams"),
]


@dataclass(frozen=True)
class PrimeRef:
    name: str
    confidence: str


@dataclass(frozen=True)
class PlanInputs:
    pursuit_lane: str
    reason_codes: tuple[str, ...] = ()
    confidence: str = "medium"
    why_this_is_real: str = ""
    mactech_work_package: str = ""
    blocking_issues: tuple[str, ...] = ()
    prime_targets: tuple[PrimeRef, ...] = ()
    response_deadline: date | None = None
    as_of: date | None = None
    needs_human_review: bool = False


@dataclass(frozen=True)
class PursuitAction:
    sequence: int
    action: str
    owner_slug: str
    due_at: date
    purpose: str
    completion_criteria: str
    dependency: int | None = None


@dataclass
class PursuitPlan:
    recommended_lane: str
    executive_decision: str
    why_this_is_real: str
    mactech_work_package: str
    blocking_issues: list[str]
    prime_target_names: list[str]
    decision_deadline: date | None
    response_deadline: date | None
    confidence: str
    next_actions: list[PursuitAction] = field(default_factory=list)


_LANE_DECISION = {
    "PRIME_NOW": "Pursue as prime — bid and perform directly.",
    "PRIME_WITH_PARTNER": "Pursue as prime with one named partner to fill a bounded gap.",
    "SUB_TO_IDENTIFIED_PRIME": "Team as a specialty cyber sub under an identified prime.",
    "SUB_TO_PRIME_NOT_YET_IDENTIFIED": "Team as a specialty cyber sub; identify the prime.",
    "SHAPE_EARLY": "Shape the acquisition early — respond and influence scope.",
    "WATCH": "Watch — relevant but not yet actionable.",
    "NO_BID": "No bid.",
}


def _owner_for(action_text: str) -> str:
    low = action_text.lower()
    for keywords, slug in _OWNER_ROUTES:
        if any(k in low for k in keywords):
            return slug
    return _DEFAULT_OWNER


def _playbook_actions(lane: str) -> list[str]:
    playbooks = load_pack().block("pursuit_playbooks", "playbooks", {}) or {}
    steps = playbooks.get(lane) or []
    return [str(s.get("action")) for s in steps if isinstance(s, dict) and s.get("action")]


def _schedule(n: int, as_of: date, deadline: date | None) -> list[date]:
    """Spread n actions between as_of+1 and the decision deadline. When there is
    a deadline, back-load toward it; otherwise cadence at 2-day steps."""
    if n == 0:
        return []
    if deadline is None or deadline <= as_of:
        return [as_of + timedelta(days=2 * (i + 1)) for i in range(n)]
    # Decision should land a few days before the response deadline.
    last = deadline - timedelta(days=2)
    span = max((last - as_of).days, n)
    step = span / n
    return [as_of + timedelta(days=round(step * (i + 1))) for i in range(n)]


def build_pursuit_plan(inp: PlanInputs) -> PursuitPlan:
    as_of = inp.as_of or date.today()
    actions_text = _playbook_actions(inp.pursuit_lane)
    due_dates = _schedule(len(actions_text), as_of, inp.response_deadline)

    # For sub lanes, weave the named primes into the outreach step.
    prime_names = [p.name for p in inp.prime_targets]
    next_actions: list[PursuitAction] = []
    for i, text in enumerate(actions_text):
        action = text
        if prime_names and ("prime target" in text.lower() or ("contact" in text.lower()
                            and "liaison" in text.lower())):
            action = f"{text} — top targets: {', '.join(prime_names[:3])}"
        next_actions.append(
            PursuitAction(
                sequence=i + 1,
                action=action,
                owner_slug=_owner_for(text),
                due_at=due_dates[i],
                purpose=f"Advance the {inp.pursuit_lane.replace('_', ' ').lower()} pursuit.",
                completion_criteria="Recorded in the pursuit record.",
                dependency=i if i > 0 else None,
            )
        )

    decision_deadline = None
    if inp.response_deadline is not None:
        decision_deadline = inp.response_deadline - timedelta(days=3)

    return PursuitPlan(
        recommended_lane=inp.pursuit_lane,
        executive_decision=_LANE_DECISION.get(inp.pursuit_lane, inp.pursuit_lane),
        why_this_is_real=inp.why_this_is_real,
        mactech_work_package=inp.mactech_work_package,
        blocking_issues=list(inp.blocking_issues),
        prime_target_names=prime_names,
        decision_deadline=decision_deadline,
        response_deadline=inp.response_deadline,
        confidence=inp.confidence,
        next_actions=next_actions,
    )
