"""Pursuit-plan builder tests."""

from __future__ import annotations

from datetime import date, timedelta

from mactech_intelligence.pursuit import PlanInputs, build_pursuit_plan
from mactech_intelligence.pursuit.plan import PrimeRef

TODAY = date(2026, 7, 16)


def test_prime_now_plan_has_dated_actions_before_deadline():
    plan = build_pursuit_plan(PlanInputs(
        pursuit_lane="PRIME_NOW", confidence="high", as_of=TODAY,
        response_deadline=TODAY + timedelta(days=20),
    ))
    assert plan.recommended_lane == "PRIME_NOW"
    assert plan.next_actions, "expected actions from the playbook"
    # Actions are ordered and land on or before the deadline.
    seqs = [a.sequence for a in plan.next_actions]
    assert seqs == sorted(seqs)
    assert all(a.due_at <= TODAY + timedelta(days=20) for a in plan.next_actions)
    # Decision deadline is a few days before response deadline.
    assert plan.decision_deadline == TODAY + timedelta(days=17)


def test_sub_plan_weaves_prime_names_into_outreach():
    plan = build_pursuit_plan(PlanInputs(
        pursuit_lane="SUB_TO_IDENTIFIED_PRIME", as_of=TODAY,
        response_deadline=TODAY + timedelta(days=30),
        prime_targets=(PrimeRef("Clark Construction", "probable"),
                       PrimeRef("Hensel Phelps", "probable")),
    ))
    assert plan.prime_target_names == ["Clark Construction", "Hensel Phelps"]
    joined = " ".join(a.action for a in plan.next_actions)
    assert "Clark Construction" in joined  # named in the contact step


def test_owner_routing_by_pillar():
    plan = build_pursuit_plan(PlanInputs(
        pursuit_lane="SUB_TO_IDENTIFIED_PRIME", as_of=TODAY,
        response_deadline=TODAY + timedelta(days=30),
    ))
    owners = {a.owner_slug for a in plan.next_actions}
    # NDA/teaming routes to John; the rest default to Patrick (security).
    assert "john-milso" in owners
    assert "patrick-caruso" in owners


def test_no_deadline_uses_cadence():
    plan = build_pursuit_plan(PlanInputs(pursuit_lane="SHAPE_EARLY", as_of=TODAY))
    assert plan.next_actions
    assert all(a.due_at > TODAY for a in plan.next_actions)


def test_executive_decision_is_lane_specific():
    plan = build_pursuit_plan(PlanInputs(pursuit_lane="SUB_TO_IDENTIFIED_PRIME", as_of=TODAY))
    assert "sub" in plan.executive_decision.lower()
