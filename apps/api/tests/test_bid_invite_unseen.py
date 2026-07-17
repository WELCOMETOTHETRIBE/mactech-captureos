"""Arrival time and the unseen watermark.

No Postgres harness exists in this repo (see test_postmark_inbound.py),
but both rules under test are pure functions over a BidInvite instance,
so they're exercised directly without a session.

These lock down the two bugs that made new invites impossible to spot:
sorting on ingest time (which the mbox backfill collapsed onto one
timestamp), and treating the untriaged backlog as the "new" signal.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from mactech_api.routes.bid_invites import is_unseen
from mactech_db.models import BidInvite

NOW = datetime(2026, 7, 15, 9, 0, tzinfo=UTC)
IMPORT_RUN = datetime(2026, 7, 15, 3, 0, tzinfo=UTC)


def _invite(
    *,
    sent_at: datetime | None,
    received_at: datetime,
    status: str = "new",
) -> BidInvite:
    return BidInvite(
        subject="Bid Invite: Cheatham Hills ES Reno",
        status=status,
        sent_at=sent_at,
        received_at=received_at,
    )


class TestArrivedAt:
    def test_prefers_the_email_date_over_ingest_time(self) -> None:
        date_header = datetime(2026, 6, 2, 14, 30, tzinfo=UTC)
        inv = _invite(sent_at=date_header, received_at=IMPORT_RUN)
        assert inv.arrived_at == date_header

    def test_falls_back_to_ingest_when_date_header_unparseable(self) -> None:
        inv = _invite(sent_at=None, received_at=IMPORT_RUN)
        assert inv.arrived_at == IMPORT_RUN

    def test_backfilled_corpus_sorts_by_true_chronology(self) -> None:
        """The regression: every mbox-imported row shares received_at.

        Sorting on received_at leaves them in import order; sorting on
        arrived_at restores the order the mail actually came in.
        """
        june = _invite(sent_at=datetime(2026, 6, 2, 9, 0, tzinfo=UTC), received_at=IMPORT_RUN)
        july = _invite(sent_at=datetime(2026, 7, 15, 6, 11, tzinfo=UTC), received_at=IMPORT_RUN)
        may = _invite(sent_at=datetime(2026, 5, 20, 8, 0, tzinfo=UTC), received_at=IMPORT_RUN)

        assert len({i.received_at for i in (june, july, may)}) == 1
        newest_first = sorted([june, july, may], key=lambda i: i.arrived_at, reverse=True)
        assert newest_first == [july, june, may]


class TestIsUnseen:
    def test_arrived_after_the_watermark(self) -> None:
        inv = _invite(sent_at=NOW, received_at=NOW)
        assert is_unseen(inv, NOW - timedelta(hours=1)) is True

    def test_arrived_before_the_watermark(self) -> None:
        inv = _invite(sent_at=NOW - timedelta(days=3), received_at=NOW)
        assert is_unseen(inv, NOW - timedelta(hours=1)) is False

    def test_backlog_does_not_count_merely_because_it_is_untriaged(self) -> None:
        """The 58-of-63 problem: status='new' is a backlog, not a signal."""
        old = _invite(sent_at=datetime(2026, 5, 1, tzinfo=UTC), received_at=IMPORT_RUN)
        assert old.status == "new"
        assert is_unseen(old, NOW - timedelta(hours=24)) is False

    def test_triaged_mail_is_never_unseen_even_if_it_just_arrived(self) -> None:
        for status in ("reviewed", "archived"):
            inv = _invite(sent_at=NOW, received_at=NOW, status=status)
            assert is_unseen(inv, NOW - timedelta(hours=1)) is False

    def test_no_watermark_resolves_to_seen_not_to_the_whole_backlog(self) -> None:
        """A user with no founder profile gets silence, not 58 alarms."""
        inv = _invite(sent_at=NOW, received_at=NOW)
        assert is_unseen(inv, None) is False

    def test_watermark_is_exclusive_so_acknowledging_clears_everything(self) -> None:
        """POST /seen stamps now(); mail at exactly that instant is cleared."""
        inv = _invite(sent_at=NOW, received_at=NOW)
        assert is_unseen(inv, NOW) is False
