"""Tests for find_available_slots — the slot-suggestion engine.

Exercises boundary, empty-result, valid-result, and availability-filtering
behavior directly against the service to keep tests fast and deterministic.
"""

from datetime import date, datetime, time

from app.services.conflict_detection import find_available_slots

from .factories import (
    make_availability,
    make_blocked_time,
    make_calendar,
    make_event,
)

MONDAY = date(2026, 4, 20)
TUESDAY = date(2026, 4, 21)
SUNDAY = date(2026, 4, 26)  # weekday = 6


def test_empty_when_no_availability(session):
    """No availability windows defined → no slots, regardless of range."""
    slots = find_available_slots(
        duration_minutes=60,
        start_date=MONDAY,
        end_date=TUESDAY,
        max_results=10,
        session=session,
    )
    assert slots == []


def test_valid_result_returns_slots_in_order(session):
    """Open day with no conflicts → 30-min grid over the availability window."""
    make_availability(session, weekday=0, start=time(9, 0), end=time(11, 0))

    slots = find_available_slots(
        duration_minutes=60,
        start_date=MONDAY,
        end_date=MONDAY,
        max_results=10,
        session=session,
    )

    # 60-min slots on a 30-min grid inside [9,11) → 9:00, 9:30, 10:00.
    assert [(s.start_time, s.end_time) for s in slots] == [
        (datetime(2026, 4, 20, 9, 0), datetime(2026, 4, 20, 10, 0)),
        (datetime(2026, 4, 20, 9, 30), datetime(2026, 4, 20, 10, 30)),
        (datetime(2026, 4, 20, 10, 0), datetime(2026, 4, 20, 11, 0)),
    ]


def test_max_results_is_honored(session):
    make_availability(session, weekday=0, start=time(9, 0), end=time(17, 0))

    slots = find_available_slots(
        duration_minutes=30,
        start_date=MONDAY,
        end_date=MONDAY,
        max_results=3,
        session=session,
    )

    assert len(slots) == 3
    assert slots[0].start_time == datetime(2026, 4, 20, 9, 0)


def test_slot_touching_event_end_boundary_is_valid(session):
    """A slot that starts exactly when an event ends is not a conflict."""
    make_availability(session, weekday=0, start=time(9, 0), end=time(11, 0))
    cal = make_calendar(session)
    # Event occupies 9:00–10:00. A 10:00–11:00 slot touches its end — not overlap.
    make_event(
        session,
        cal.id,
        start=datetime(2026, 4, 20, 9, 0),
        end=datetime(2026, 4, 20, 10, 0),
    )

    slots = find_available_slots(
        duration_minutes=60,
        start_date=MONDAY,
        end_date=MONDAY,
        max_results=10,
        session=session,
    )

    assert [(s.start_time, s.end_time) for s in slots] == [
        (datetime(2026, 4, 20, 10, 0), datetime(2026, 4, 20, 11, 0)),
    ]


def test_slot_touching_blocked_time_boundary_is_valid(session):
    """A slot that ends exactly when a blocked time starts is not a conflict."""
    make_availability(session, weekday=0, start=time(9, 0), end=time(11, 0))
    make_blocked_time(
        session,
        start=datetime(2026, 4, 20, 10, 0),
        end=datetime(2026, 4, 20, 11, 0),
    )

    slots = find_available_slots(
        duration_minutes=60,
        start_date=MONDAY,
        end_date=MONDAY,
        max_results=10,
        session=session,
    )

    # Only 9:00–10:00 fits. 9:30–10:30 overlaps blocked time.
    assert [(s.start_time, s.end_time) for s in slots] == [
        (datetime(2026, 4, 20, 9, 0), datetime(2026, 4, 20, 10, 0)),
    ]


def test_empty_when_window_fully_occupied(session):
    """Availability exists but a blocking event covers the entire window."""
    make_availability(session, weekday=0, start=time(9, 0), end=time(10, 0))
    cal = make_calendar(session)
    make_event(
        session,
        cal.id,
        start=datetime(2026, 4, 20, 9, 0),
        end=datetime(2026, 4, 20, 10, 0),
    )

    slots = find_available_slots(
        duration_minutes=30,
        start_date=MONDAY,
        end_date=MONDAY,
        max_results=10,
        session=session,
    )
    assert slots == []


def test_duration_longer_than_window_returns_empty(session):
    """Slot duration exceeds the only availability window → no slot fits."""
    make_availability(session, weekday=0, start=time(9, 0), end=time(9, 45))

    slots = find_available_slots(
        duration_minutes=60,
        start_date=MONDAY,
        end_date=MONDAY,
        max_results=10,
        session=session,
    )
    assert slots == []


def test_filters_by_availability_weekday(session):
    """Only weekdays with active availability produce slots — others are skipped."""
    # Monday (weekday=0) is open; Tuesday (weekday=1) has no availability.
    make_availability(session, weekday=0, start=time(9, 0), end=time(10, 0))

    slots = find_available_slots(
        duration_minutes=60,
        start_date=MONDAY,
        end_date=TUESDAY,
        max_results=10,
        session=session,
    )

    assert [(s.start_time, s.end_time) for s in slots] == [
        (datetime(2026, 4, 20, 9, 0), datetime(2026, 4, 20, 10, 0)),
    ]


def test_inactive_availability_window_is_ignored(session):
    """Availability rows with active=False must not produce slots."""
    make_availability(
        session, weekday=0, start=time(9, 0), end=time(17, 0), active=False
    )

    slots = find_available_slots(
        duration_minutes=60,
        start_date=MONDAY,
        end_date=MONDAY,
        max_results=10,
        session=session,
    )
    assert slots == []


def test_spans_multiple_availability_windows_same_day(session):
    """Two windows on the same weekday → both produce slots, in window order."""
    make_availability(session, weekday=0, start=time(9, 0), end=time(10, 0))
    make_availability(session, weekday=0, start=time(14, 0), end=time(15, 0))

    slots = find_available_slots(
        duration_minutes=60,
        start_date=MONDAY,
        end_date=MONDAY,
        max_results=10,
        session=session,
    )

    starts = [s.start_time for s in slots]
    assert datetime(2026, 4, 20, 9, 0) in starts
    assert datetime(2026, 4, 20, 14, 0) in starts
