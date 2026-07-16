from datetime import datetime, timedelta, timezone

from mactech_api.routes.opportunities import classify_ingest

NOW = datetime(2026, 7, 15, 12, 0, tzinfo=timezone.utc)
FRESH = NOW - timedelta(hours=1)
STALE = NOW - timedelta(days=19)


def test_all_sources_healthy() -> None:
    assert classify_ingest(20, 0, FRESH, NOW) == "ok"


def test_partial_failure_is_degraded() -> None:
    assert classify_ingest(18, 2, FRESH, NOW) == "degraded"


def test_every_source_failing_outranks_stale() -> None:
    """The June 2026 shape: all 20 NAICS feeds 401ing for 19 days.

    'failing' must win over 'stale' — every-source-down is the actionable
    diagnosis, staleness is only the symptom of it.
    """
    assert classify_ingest(0, 20, STALE, NOW) == "failing"


def test_no_errors_but_nothing_recent_is_stale() -> None:
    assert classify_ingest(20, 0, STALE, NOW) == "stale"


def test_never_succeeded_is_unknown() -> None:
    assert classify_ingest(5, 0, None, NOW) == "unknown"


def test_staleness_boundary() -> None:
    just_inside = NOW - timedelta(hours=11, minutes=59)
    just_outside = NOW - timedelta(hours=12, minutes=1)
    assert classify_ingest(20, 0, just_inside, NOW) == "ok"
    assert classify_ingest(20, 0, just_outside, NOW) == "stale"
