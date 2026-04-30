"""Tests for explainable ConflictDetail responses.

Verifies that every conflict path populates structured fields (reason_code,
conflict_type, start_time, end_time, related_*_id) and that multiple
conflicts of different kinds are returned together.
"""

from datetime import datetime, time

from app.services.conflict_detection import check_all_conflicts

from .factories import (
    make_availability,
    make_blocked_time,
    make_calendar,
    make_event,
)


def _monday_availability(session):
    make_availability(session, weekday=0, start=time(9, 0), end=time(17, 0))


def test_event_overlap_detail_has_event_id_and_human_message(session):
    _monday_availability(session)
    cal = make_calendar(session)
    ev = make_event(
        session,
        cal.id,
        start=datetime(2026, 4, 20, 13, 0),
        end=datetime(2026, 4, 20, 14, 0),
    )

    conflicts = check_all_conflicts(
        start_time=datetime(2026, 4, 20, 13, 30),
        end_time=datetime(2026, 4, 20, 14, 30),
        session=session,
    )

    overlap = next(c for c in conflicts if c.reason_code == "EVENT_OVERLAP")
    assert overlap.conflict_type == "event"
    assert overlap.related_event_id == ev.id
    assert overlap.related_blocked_time_id is None
    assert overlap.start_time == datetime(2026, 4, 20, 13, 0)
    assert overlap.end_time == datetime(2026, 4, 20, 14, 0)
    assert "1:00 PM" in overlap.message
    assert "2:00 PM" in overlap.message
    assert "overlaps" in overlap.message.lower()


def test_blocked_time_detail_has_blocked_id_and_human_message(session):
    _monday_availability(session)
    bt = make_blocked_time(
        session,
        start=datetime(2026, 4, 20, 14, 0),
        end=datetime(2026, 4, 20, 15, 0),
    )

    conflicts = check_all_conflicts(
        start_time=datetime(2026, 4, 20, 14, 30),
        end_time=datetime(2026, 4, 20, 15, 30),
        session=session,
    )

    blocked_conflict = next(
        c for c in conflicts if c.reason_code == "BLOCKED_TIME_OVERLAP"
    )
    assert blocked_conflict.conflict_type == "blocked_time"
    assert blocked_conflict.related_blocked_time_id == bt.id
    assert blocked_conflict.related_event_id is None
    assert blocked_conflict.start_time == datetime(2026, 4, 20, 14, 0)
    assert blocked_conflict.end_time == datetime(2026, 4, 20, 15, 0)
    assert "2:00 PM" in blocked_conflict.message
    assert "3:00 PM" in blocked_conflict.message


def test_outside_availability_is_no_longer_returned(session):
    """OUTSIDE_AVAILABILITY must not appear for a placement on a weekday
    that has no availability row — that scenario is now allowed."""
    conflicts = check_all_conflicts(
        start_time=datetime(2026, 4, 23, 10, 0),
        end_time=datetime(2026, 4, 23, 11, 0),
        session=session,
    )

    assert conflicts == []


def test_returns_all_active_conflicts_not_just_first(session):
    """A single proposed time can trigger event + blocked overlaps together.

    OUTSIDE_AVAILABILITY is no longer an active conflict, so the active
    surface is event + blocked-time overlap only.
    """
    cal = make_calendar(session)
    ev = make_event(
        session,
        cal.id,
        start=datetime(2026, 4, 20, 9, 30),
        end=datetime(2026, 4, 20, 10, 30),
    )
    bt = make_blocked_time(
        session,
        start=datetime(2026, 4, 20, 10, 15),
        end=datetime(2026, 4, 20, 11, 0),
    )

    conflicts = check_all_conflicts(
        start_time=datetime(2026, 4, 20, 10, 0),
        end_time=datetime(2026, 4, 20, 10, 45),
        session=session,
    )

    codes = sorted({c.reason_code for c in conflicts})
    assert codes == ["BLOCKED_TIME_OVERLAP", "EVENT_OVERLAP"]
    assert "OUTSIDE_AVAILABILITY" not in codes
    event_conflict = next(c for c in conflicts if c.reason_code == "EVENT_OVERLAP")
    blocked_conflict = next(
        c for c in conflicts if c.reason_code == "BLOCKED_TIME_OVERLAP"
    )
    assert event_conflict.related_event_id == ev.id
    assert blocked_conflict.related_blocked_time_id == bt.id


def test_messages_are_deterministic(session):
    """Identical inputs produce identical messages — no nondeterministic content."""
    _monday_availability(session)
    cal = make_calendar(session)
    make_event(
        session,
        cal.id,
        start=datetime(2026, 4, 20, 13, 0),
        end=datetime(2026, 4, 20, 14, 0),
    )

    a = check_all_conflicts(
        datetime(2026, 4, 20, 13, 30),
        datetime(2026, 4, 20, 14, 30),
        session,
    )
    b = check_all_conflicts(
        datetime(2026, 4, 20, 13, 30),
        datetime(2026, 4, 20, 14, 30),
        session,
    )
    assert [c.message for c in a] == [c.message for c in b]
