"""Tests for find_available_slots — the slot-suggestion engine.

Slot suggestions are now driven by Daily Rhythm suggestion hours
(8:00–21:00 by default). AvailabilityWindow rows are not consulted; slots
must avoid existing events.
"""

from datetime import date, datetime, time

from app.services.conflict_detection import find_available_slots
from app.services.daily_rhythm import (
    DEFAULT_SUGGESTIONS_END,
    DEFAULT_SUGGESTIONS_START,
)

from .factories import (
    make_availability,
    make_calendar,
    make_event,
)

MONDAY = date(2026, 4, 20)
TUESDAY = date(2026, 4, 21)
SUNDAY = date(2026, 4, 26)  # weekday = 6


def test_returns_slots_with_no_availability_window_rows(session):
    """Slot suggestions work even when there are zero AvailabilityWindow rows."""
    slots = find_available_slots(
        duration_minutes=60,
        start_date=MONDAY,
        end_date=MONDAY,
        max_results=5,
        session=session,
    )

    assert len(slots) == 5
    # First slot starts at the Daily Rhythm start.
    assert slots[0].start_time == datetime.combine(MONDAY, DEFAULT_SUGGESTIONS_START)


def test_slots_stay_within_daily_rhythm_hours(session):
    """All suggested slots fall inside [DEFAULT_SUGGESTIONS_START, DEFAULT_SUGGESTIONS_END]."""
    slots = find_available_slots(
        duration_minutes=60,
        start_date=MONDAY,
        end_date=TUESDAY,
        max_results=100,
        session=session,
    )

    assert slots, "expected slots to be generated"
    for s in slots:
        rhythm_start = datetime.combine(s.start_time.date(), DEFAULT_SUGGESTIONS_START)
        rhythm_end = datetime.combine(s.start_time.date(), DEFAULT_SUGGESTIONS_END)
        assert s.start_time >= rhythm_start
        assert s.end_time <= rhythm_end


def test_thirty_minute_grid_inside_rhythm_window(session):
    """Slots are scanned on a 30-minute grid starting at DEFAULT_SUGGESTIONS_START."""
    slots = find_available_slots(
        duration_minutes=60,
        start_date=MONDAY,
        end_date=MONDAY,
        max_results=4,
        session=session,
    )

    expected_starts = [
        datetime(2026, 4, 20, 8, 0),
        datetime(2026, 4, 20, 8, 30),
        datetime(2026, 4, 20, 9, 0),
        datetime(2026, 4, 20, 9, 30),
    ]
    assert [s.start_time for s in slots] == expected_starts


def test_max_results_is_honored(session):
    slots = find_available_slots(
        duration_minutes=30,
        start_date=MONDAY,
        end_date=MONDAY,
        max_results=3,
        session=session,
    )

    assert len(slots) == 3
    assert slots[0].start_time == datetime(2026, 4, 20, 8, 0)


def test_slot_touching_event_end_boundary_is_valid(session):
    """A slot that starts exactly when an event ends is not a conflict."""
    cal = make_calendar(session)
    # Event 8:00-9:00. A 9:00-10:00 slot touches its end — not overlap.
    make_event(
        session,
        cal.id,
        start=datetime(2026, 4, 20, 8, 0),
        end=datetime(2026, 4, 20, 9, 0),
    )

    slots = find_available_slots(
        duration_minutes=60,
        start_date=MONDAY,
        end_date=MONDAY,
        max_results=2,
        session=session,
    )

    # 8:00-9:00 grid candidate overlaps the event; 8:30-9:30 also overlaps.
    # Earliest valid is 9:00-10:00.
    assert slots[0].start_time == datetime(2026, 4, 20, 9, 0)
    assert slots[0].end_time == datetime(2026, 4, 20, 10, 0)


def test_slots_avoid_existing_events(session):
    """Slots that overlap an existing event must not be returned."""
    cal = make_calendar(session)
    make_event(
        session,
        cal.id,
        start=datetime(2026, 4, 20, 10, 0),
        end=datetime(2026, 4, 20, 11, 0),
    )

    slots = find_available_slots(
        duration_minutes=60,
        start_date=MONDAY,
        end_date=MONDAY,
        max_results=100,
        session=session,
    )

    for s in slots:
        # No slot should overlap [10:00, 11:00).
        assert not (
            s.start_time < datetime(2026, 4, 20, 11, 0)
            and s.end_time > datetime(2026, 4, 20, 10, 0)
        )


def test_slot_touching_event_boundary_is_valid(session):
    """A slot that ends exactly when an event starts is not a conflict."""
    cal = make_calendar(session)
    make_event(
        session,
        cal.id,
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

    # 9:00-10:00 ends at event start — not overlap → valid.
    starts = [s.start_time for s in slots]
    assert datetime(2026, 4, 20, 9, 0) in starts
    # 9:30-10:30 overlaps the event → must not appear.
    assert datetime(2026, 4, 20, 9, 30) not in starts


def test_empty_when_window_fully_occupied(session):
    """An event spanning the entire Daily Rhythm window leaves no fitting slots."""
    cal = make_calendar(session)
    make_event(
        session,
        cal.id,
        start=datetime.combine(MONDAY, DEFAULT_SUGGESTIONS_START),
        end=datetime.combine(MONDAY, DEFAULT_SUGGESTIONS_END),
    )

    slots = find_available_slots(
        duration_minutes=30,
        start_date=MONDAY,
        end_date=MONDAY,
        max_results=10,
        session=session,
    )
    assert slots == []


def test_duration_longer_than_rhythm_window_returns_empty(session):
    """Slot duration exceeds the Daily Rhythm window → no slot fits."""
    # 8:00-21:00 is 13h; require 14h.
    slots = find_available_slots(
        duration_minutes=14 * 60,
        start_date=MONDAY,
        end_date=MONDAY,
        max_results=10,
        session=session,
    )
    assert slots == []


def test_inactive_availability_window_does_not_suppress_slots(session):
    """AvailabilityWindow rows (active or inactive) do not affect slot output."""
    make_availability(
        session, weekday=0, start=time(9, 0), end=time(17, 0), active=False
    )

    slots = find_available_slots(
        duration_minutes=60,
        start_date=MONDAY,
        end_date=MONDAY,
        max_results=5,
        session=session,
    )

    # Daily Rhythm drives output even when avail rows exist or are inactive.
    assert len(slots) == 5
    assert slots[0].start_time == datetime(2026, 4, 20, 8, 0)


def test_scans_each_day_in_range(session):
    """Each day in the range contributes slots within its Daily Rhythm window."""
    slots = find_available_slots(
        duration_minutes=60,
        start_date=MONDAY,
        end_date=TUESDAY,
        max_results=100,
        session=session,
    )

    days_seen = {s.start_time.date() for s in slots}
    assert MONDAY in days_seen
    assert TUESDAY in days_seen
