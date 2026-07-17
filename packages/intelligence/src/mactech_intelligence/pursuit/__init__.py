"""Pursuit-plan generation (Slice 6).

Turns a decision (lane + gates + prime targets) into a structured, dated pursuit
plan — the ordered "who does what, by when" that answers the last capture
question. Deterministic and pure: action templates come from the knowledge
pack's ``pursuit_playbooks`` family; the worker persists.
"""

from mactech_intelligence.pursuit.plan import (
    PlanInputs,
    PursuitAction,
    PursuitPlan,
    build_pursuit_plan,
)

__all__ = ["PlanInputs", "PursuitAction", "PursuitPlan", "build_pursuit_plan"]
