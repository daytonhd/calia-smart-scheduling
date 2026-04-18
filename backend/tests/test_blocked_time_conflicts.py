"""Blocked-time overlap conflict tests."""

from datetime import datetime, time

from app.services.conflict_detection import check_all_conflicts

from .factories import make_availability, make_blocked_time


def _monday_availability(session):
    make_availability(session, weekday=0, start=time(9, 0), end=time(17, 0))


def test_blocked_time_overlap_detected(session):
    _monday_availability(session)
    make_blocked_time(
        session,
        start=datetime(2026, 4, 20, 10, 0),
        end=datetime(2026, 4, 20, 12, 0),
        title="Lunch",
    )

    conflicts = check_all_conflicts(
        start_time=datetime(2026, 4, 20, 11, 0),
        end_time=datetime(2026, 4, 20, 11, 30),
        session=session,
    )

    assert any(c.reason_code == "BLOCKED_TIME_OVERLAP" for c in conflicts)


def test_blocked_time_touching_boundary_is_not_overlap(session):
    """A proposed slot starting exactly when a blocked time ends is allowed."""
    _monday_availability(session)
    make_blocked_time(
        session,
        start=datetime(2026, 4, 20, 10, 0),
        end=datetime(2026, 4, 20, 11, 0),
    )

    conflicts = check_all_conflicts(
        start_time=datetime(2026, 4, 20, 11, 0),
        end_time=datetime(2026, 4, 20, 12, 0),
        session=session,
    )

    assert not any(c.reason_code == "BLOCKED_TIME_OVERLAP" for c in conflicts)


def test_blocked_time_no_conflict_when_separate(session):
    _monday_availability(session)
    make_blocked_time(
        session,
        start=datetime(2026, 4, 20, 9, 0),
        end=datetime(2026, 4, 20, 10, 0),
    )

    conflicts = check_all_conflicts(
        start_time=datetime(2026, 4, 20, 13, 0),
        end_time=datetime(2026, 4, 20, 14, 0),
        session=session,
    )

    assert conflicts == []


def test_blocked_time_fully_contains_proposed(session):
    _monday_availability(session)
    make_blocked_time(
        session,
        start=datetime(2026, 4, 20, 9, 0),
        end=datetime(2026, 4, 20, 17, 0),
    )

    conflicts = check_all_conflicts(
        start_time=datetime(2026, 4, 20, 10, 0),
        end_time=datetime(2026, 4, 20, 11, 0),
        session=session,
    )

    assert any(c.reason_code == "BLOCKED_TIME_OVERLAP" for c in conflicts)
