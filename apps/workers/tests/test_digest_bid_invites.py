"""Bid-invite block in the morning digest.

The loader itself needs a session, so these cover the pure pieces around
it: thread flattening, urgency labels, and the rendered email. Invites
are in the digest because they were previously reachable only by opening
the app — an invite forwarded in at 2am sat unseen until someone looked.
"""

from __future__ import annotations

import datetime as dt

from mactech_db.models import BidInvite, Founder
from mactech_workers.tasks.digest import (
    BidInviteDigestRow,
    _due_label,
    _first,
    _render_bid_invites_html,
    _render_bid_invites_text,
    _render_html,
)

TODAY = dt.date(2026, 7, 15)
NOW = dt.datetime(2026, 7, 15, 10, 0, tzinfo=dt.UTC)


def _row(**kw) -> BidInviteDigestRow:
    base = dict(
        project_name="Heartland Dental TI Middleburg",
        gc_company="MEC General Contractors",
        bid_package="Third Party Materials Testing",
        lead_name="Kevin Borja",
        bid_due_on=dt.date(2026, 7, 20),
        arrived_at=NOW,
        is_recent=False,
        email_count=1,
        url="https://capture.mactechsolutionsllc.com/bid-invites/abc",
    )
    base.update(kw)
    return BidInviteDigestRow(**base)


class TestDueLabel:
    def test_matches_the_ui_urgency_thresholds(self) -> None:
        cases = [
            (dt.date(2026, 7, 15), "due today"),
            (dt.date(2026, 7, 16), "due tomorrow"),
            (dt.date(2026, 7, 18), "due in 3d"),
            (dt.date(2026, 7, 22), "due in 7d"),
            (dt.date(2026, 8, 20), "due Aug 20"),
            (dt.date(2026, 6, 1), "closed Jun 1"),
        ]
        for due, expected in cases:
            assert _due_label(due, TODAY) == expected

    def test_undated_invites_get_no_label(self) -> None:
        assert _due_label(None, TODAY) is None


class TestFirst:
    def test_falls_down_the_thread_for_sparse_reminders(self) -> None:
        """Reminders parse sparsely; the invite behind them carries the facts."""
        reminder = BidInvite(subject="Reminder", gc_company=None)
        invite = BidInvite(subject="Bid Invite", gc_company="MEC General Contractors")
        assert _first([reminder, invite], "gc_company") == "MEC General Contractors"

    def test_newest_wins_when_both_populated(self) -> None:
        newest = BidInvite(subject="Due Date Extended", bid_due_on=dt.date(2026, 8, 1))
        original = BidInvite(subject="Bid Invite", bid_due_on=dt.date(2026, 7, 20))
        # A "Due Date Extended" must supersede the original invite's date.
        assert _first([newest, original], "bid_due_on") == dt.date(2026, 8, 1)

    def test_returns_none_when_nothing_populated(self) -> None:
        assert _first([BidInvite(subject="x", location=None)], "location") is None


class TestRendering:
    def test_empty_list_renders_nothing_at_all(self) -> None:
        assert _render_bid_invites_html([]) == ""
        assert _render_bid_invites_text([]) == []

    def test_overnight_arrivals_are_marked(self) -> None:
        html = _render_bid_invites_html([_row(is_recent=True)])
        assert "New overnight" in html
        text = "\n".join(_render_bid_invites_text([_row(is_recent=True)]))
        assert "[New overnight]" in text

    def test_settled_invites_are_not_marked(self) -> None:
        html = _render_bid_invites_html([_row(is_recent=False)])
        assert "New overnight" not in html

    def test_row_carries_a_deep_link_into_the_app(self) -> None:
        html = _render_bid_invites_html([_row()])
        assert "/bid-invites/abc" in html
        assert "Review in CaptureOS" in html

    def test_html_is_escaped(self) -> None:
        html = _render_bid_invites_html([_row(project_name="Smith & Sons <script>")])
        assert "<script>" not in html
        assert "Smith &amp; Sons" in html

    def test_no_emoji_per_the_playbook_copy_rules(self) -> None:
        html = _render_bid_invites_html([_row(is_recent=True)])
        assert all(ord(ch) < 0x2190 for ch in html)

    def test_invites_lead_the_digest_ahead_of_scored_opps(self) -> None:
        """A named GC on a short fuse outranks a scored SAM notice."""
        founder = Founder(
            slug="brian",
            full_name="Brian MacDonald",
            title="Managing Member",
            pillar="quality",
        )
        html = _render_html(founder, [], [], [_row()])
        assert html.index("Bid invites in your lane") < html.index(
            "No opportunities scored above the threshold"
        )

    def test_digest_with_no_invites_is_unchanged(self) -> None:
        founder = Founder(
            slug="brian",
            full_name="Brian MacDonald",
            title="Managing Member",
            pillar="quality",
        )
        assert "Bid invites in your lane" not in _render_html(founder, [], [], [])
