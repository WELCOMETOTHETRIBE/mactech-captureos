"""Founder routing + group key for bid invites."""

from __future__ import annotations

from mactech_intelligence.bid_invite_routing import (
    project_group_key,
    suggest_founder,
)


def test_security_scope_routes_to_patrick() -> None:
    slug, reason = suggest_founder(
        "Emergency Responder Communications Enhancement System (ERCES)",
        "Riverbend County Jail Expansion",
        None,
    )
    assert slug == "patrick-caruso"
    assert "erces" in reason


def test_testing_scope_routes_to_brian() -> None:
    slug, _ = suggest_founder("Third Party Materials Testing", None, None)
    assert slug == "brian-macdonald"


def test_bms_scope_routes_to_james() -> None:
    slug, _ = suggest_founder("Building Management Systems", None, None)
    assert slug == "james-adams"


def test_security_outranks_infrastructure_keywords() -> None:
    slug, _ = suggest_founder("Security Upgrades: Data & Telecom", None, None)
    assert slug == "patrick-caruso"


def test_no_match_returns_none() -> None:
    assert suggest_founder("Sitework and Paving", None, None) is None
    assert suggest_founder(None, None, None) is None


def test_group_key_normalizes_project_suffix_and_case() -> None:
    a = project_group_key("Kings Bay Project", "whatever")
    b = project_group_key("Kings Bay", "whatever")
    c = project_group_key(None, "Re: Kings  Bay — project")
    assert a == b == "kings bay"
    assert c == "re kings bay"  # subject fallback keeps its own prefix


def test_group_key_never_empty() -> None:
    assert project_group_key("Project", "Project") != ""
