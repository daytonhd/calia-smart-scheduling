"""Availability-rule conflict tests.

Validates OUTSIDE_AVAILABILITY behavior: a proposed time must be fully contained
within some active availability window for its weekday, otherwise the rule
conflicts.
"""

from datetime import datetime, time

from app.services.conflict_detection import check_all_conflicts

from .factories import make_availability


def test_fully_within_availability_no_conflict(session):
    make_availability(session, weekday=0, start=time(9, 0), end=time(17, 0))

    conflicts = check_all_conflicts(
        start_time=datetime(2026, 4, 20, 10, 0),
        end_time=datetime(2026, 4, 20, 11, 0),
        session=session,
    )

    assert conflicts == []


def test_exactly_at_availability_boundary_no_conflict(session):
    """Proposed interval equal to the window (09:00–17:00) is fully contained."""
    make_availability(session, weekday=0, start=time(9, 0), end=time(17, 0))

    conflicts = check_all_conflicts(
        start_time=datetime(2026, 4, 20, 9, 0),
        end_time=datetime(2026, 4, 20, 17, 0),
        session=session,
    )

    assert conflicts == []


def test_no_availability_for_weekday_is_conflict(session):
    """Tuesday 2026-04-21 has no availability configured."""
    make_availability(session, weekday=0, start=time(9, 0), end=time(17, 0))

    conflicts = check_all_conflicts(
        start_time=datetime(2026, 4, 21, 10, 0),
        end_time=datetime(2026, 4, 21, 11, 0),
        session=session,
    )

    codes = [c.reason_code for c in conflicts]
    assert "OUTSIDE_AVAILABILITY" in codes


def test_start_before_availability_window_is_conflict(session):
    make_availability(session, weekday=0, start=time(9, 0), end=time(17, 0))

    conflicts = check_all_conflicts(
        start_time=datetime(2026, 4, 20, 8, 0),
        end_time=datetime(2026, 4, 20, 10, 0),
        session=session,
    )

    assert any(c.reason_code == "OUTSIDE_AVAILABILITY" for c in conflicts)


def test_end_after_availability_window_is_conflict(session):
    make_availability(session, weekday=0, start=time(9, 0), end=time(17, 0))

    conflicts = check_all_conflicts(
        start_time=datetime(2026, 4, 20, 16, 0),
        end_time=datetime(2026, 4, 20, 18, 0),
        session=session,
    )

    assert any(c.reason_code == "OUTSIDE_AVAILABILITY" for c in conflicts)


def test_inactive_availability_is_ignored(session):
    """An inactive window for the weekday must not satisfy the availability rule."""
    make_availability(
        session, weekday=0, start=time(9, 0), end=time(17, 0), active=False
    )

    conflicts = check_all_conflicts(
        start_time=datetime(2026, 4, 20, 10, 0),
        end_time=datetime(2026, 4, 20, 11, 0),
        session=session,
    )

    assert any(c.reason_code == "OUTSIDE_AVAILABILITY" for c in conflicts)


def test_multiple_windows_any_container_is_ok(session):
    """With split AM/PM windows, a slot contained in either is allowed."""
    make_availability(session, weekday=0, start=time(9, 0), end=time(12, 0))
    make_availability(session, weekday=0, start=time(13, 0), end=time(17, 0))

    conflicts = check_all_conflicts(
        start_time=datetime(2026, 4, 20, 14, 0),
        end_time=datetime(2026, 4, 20, 15, 0),
        session=session,
    )

    assert conflicts == []


def test_straddles_gap_between_windows_is_conflict(session):
    """A slot that spans the 12:00–13:00 gap is not contained in any window."""
    make_availability(session, weekday=0, start=time(9, 0), end=time(12, 0))
    make_availability(session, weekday=0, start=time(13, 0), end=time(17, 0))

    conflicts = check_all_conflicts(
        start_time=datetime(2026, 4, 20, 11, 30),
        end_time=datetime(2026, 4, 20, 13, 30),
        session=session,
    )

    assert any(c.reason_code == "OUTSIDE_AVAILABILITY" for c in conflicts)
