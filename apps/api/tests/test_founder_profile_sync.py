"""What the Suite profile sync will and will not touch.

No Postgres harness exists in this repo (see test_bid_invite_unseen.py), so the
rules live in `plan_founder_sync`, a pure function over the founder's current
state plus the profile — exercised directly here.

The additive guarantee is the point of these tests. `founder_naics_matrix` and
its registry encode judgement a resume cannot produce: *why* a code fits, whether
it is primary or secondary, and who it routes to. The obvious sync — delete the
founder's rows, re-insert from the profile — would trade that for an LLM's read
of a PDF, and nothing would flag it. Opportunity routing would just quietly stop
matching. If a future change makes any of these fail, the sync has become
destructive; fix the sync, not the test.
"""

from __future__ import annotations

from mactech_api.auth import _profile_sync_last_fire, _should_sync_profile
from mactech_api.mactech_profile_client import MemberProfile
from mactech_api.services.founder_profile_sync import plan_founder_sync


def _profile(
    *,
    headline: str | None = "Cyber Systems Engineering Manager",
    summary: str | None = "Leads RMF and ATO outcomes for DoD systems.",
    naics: tuple[str, ...] = ("541512", "541519"),
) -> MemberProfile:
    return MemberProfile(
        hub_user_id="usr_patrick",
        headline=headline,
        summary=summary,
        labor_category="ISSM",
        years_experience=19,
        naics_codes=naics,
        source_app_key="bizops",
        confirmed_at="2026-07-15T12:00:00.000Z",
        updated_at="2026-07-16T00:00:00.000Z",
    )


def test_a_curated_code_the_profile_omits_is_never_removed() -> None:
    # 611430 was added by a human and routed to Brian and John. Patrick's resume
    # says nothing about it. Silence is not a reason to un-route anyone.
    plan = plan_founder_sync(
        current_title="Cyber Systems Engineering Manager",
        current_bio="Leads RMF and ATO outcomes for DoD systems.",
        existing_codes={"611430"},
        known_codes={"541512", "541519"},
        profile=_profile(naics=("541512", "541519")),
    )
    assert plan.naics_to_add == ("541512", "541519")
    # There is no "remove" bucket at all — that is the guarantee.
    assert not hasattr(plan, "naics_to_remove")


def test_an_existing_pair_is_left_alone_not_restated() -> None:
    # An existing pair carries a hand-tuned affinity. Re-writing it at the
    # default would silently flatten the routing weight back to neutral.
    plan = plan_founder_sync(
        current_title="t",
        current_bio="b",
        existing_codes={"541519"},
        known_codes={"541512", "541519"},
        profile=_profile(naics=("541519", "541512")),
    )
    assert plan.naics_already_present == ("541519",)
    assert plan.naics_to_add == ("541512",)


def test_a_code_this_app_does_not_curate_is_skipped_not_invented() -> None:
    # naics_code is a FK to the curated naics_codes table. Inserting an unknown
    # code raises; auto-creating one would put an uncurated row in a curated
    # table. Skip and report.
    plan = plan_founder_sync(
        current_title="t",
        current_bio="b",
        existing_codes=set(),
        known_codes={"541512"},
        profile=_profile(naics=("541512", "999999")),
    )
    assert plan.naics_to_add == ("541512",)
    assert plan.naics_skipped_unknown == ("999999",)


def test_profile_order_is_preserved_when_adding() -> None:
    # The member's ranking is the signal CaptureOS routes on. A trainer-first
    # profile is a real assertion; re-ordering it here would invert the claim.
    plan = plan_founder_sync(
        current_title="t",
        current_bio="b",
        existing_codes=set(),
        known_codes={"541512", "611420"},
        profile=_profile(naics=("611420", "541512")),
    )
    assert plan.naics_to_add == ("611420", "541512")


def test_an_empty_profile_field_does_not_blank_a_human_written_one() -> None:
    # Absence of a claim is not a claim of absence. A member who hasn't written
    # a headline must not wipe the title someone typed on the founder card.
    plan = plan_founder_sync(
        current_title="Chief Growth Officer",
        current_bio="Hand-written bio.",
        existing_codes=set(),
        known_codes=set(),
        profile=_profile(headline=None, summary=None, naics=()),
    )
    assert plan.title is None
    assert plan.bio is None
    assert not plan.changes_anything


def test_matching_values_are_not_rewritten() -> None:
    plan = plan_founder_sync(
        current_title="Cyber Systems Engineering Manager",
        current_bio="Leads RMF and ATO outcomes for DoD systems.",
        existing_codes={"541512", "541519"},
        known_codes={"541512", "541519"},
        profile=_profile(),
    )
    assert not plan.changes_anything


def test_a_changed_headline_updates_the_title() -> None:
    plan = plan_founder_sync(
        current_title="Old Title",
        current_bio="b",
        existing_codes=set(),
        known_codes=set(),
        profile=_profile(naics=()),
    )
    assert plan.title == "Cyber Systems Engineering Manager"
    assert plan.changes_anything


def test_profile_sync_throttle_fires_once_per_window() -> None:
    # The trigger runs inside a dependency that executes on every authenticated
    # request. Without the throttle, every API call would hit the Hub — the
    # whole point of mirroring the audit-session dedup is to make "on sign-in"
    # mean roughly that, not "on every request".
    _profile_sync_last_fire.pop("user_throttle_probe", None)
    assert _should_sync_profile("user_throttle_probe") is True
    assert _should_sync_profile("user_throttle_probe") is False  # within the window
    _profile_sync_last_fire.pop("user_throttle_probe", None)
