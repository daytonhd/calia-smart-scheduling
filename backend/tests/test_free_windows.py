"""Tests for the free-window scanning helper (open-slot engine part 1)."""

from datetime import date, datetime, time

from app.services.conflict_detection import find_free_windows

from .factories import (
    make_availability,
    make_blocked_time,
    make_calendar,
    make_event,
)

MONDAY = date(2026, 4, 20)
TUESDAY = date(2026, 4, 21)


def test_no_availability_returns_empty(session):
    assert find_free_windows(MONDAY, MONDAY, session) == []


def test_single_availability_no_occupancy_returns_full_window(session):
    make_availability(session, weekday=0, start=time(9, 0), end=time(17, 0))

    windows = find_free_windows(MONDAY, MONDAY, session)

    assert len(windows) == 1
    assert windows[0].start_time == datetime(2026, 4, 20, 9, 0)
    assert windows[0].end_time == datetime(2026, 4, 20, 17, 0)


def test_event_splits_availability_window(session):
    make_availability(session, weekday=0, start=time(9, 0), end=time(17, 0))
    cal = make_calendar(session)
    make_event(
        session,
        cal.id,
        start=datetime(2026, 4, 20, 12, 0),
        end=datetime(2026, 4, 20, 13, 0),
    )

    windows = find_free_windows(MONDAY, MONDAY, session)

    assert [(w.start_time, w.end_time) for w in windows] == [
        (datetime(2026, 4, 20, 9, 0), datetime(2026, 4, 20, 12, 0)),
        (datetime(2026, 4, 20, 13, 0), datetime(2026, 4, 20, 17, 0)),
    ]


def test_blocked_time_is_excluded(session):
    make_availability(session, weekday=0, start=time(9, 0), end=time(17, 0))
    make_blocked_time(
        session,
        start=datetime(2026, 4, 20, 10, 0),
        end=datetime(2026, 4, 20, 11, 0),
    )

    windows = find_free_windows(MONDAY, MONDAY, session)

    assert [(w.start_time, w.end_time) for w in windows] == [
        (datetime(2026, 4, 20, 9, 0), datetime(2026, 4, 20, 10, 0)),
        (datetime(2026, 4, 20, 11, 0), datetime(2026, 4, 20, 17, 0)),
    ]


def test_event_touching_window_edge_does_not_shrink_available(session):
    """An event ending exactly at window start is not overlap — window is full."""
    make_availability(session, weekday=0, start=time(9, 0), end=time(17, 0))
    cal = make_calendar(session)
    make_event(
        session,
        cal.id,
        start=datetime(2026, 4, 20, 8, 0),
        end=datetime(2026, 4, 20, 9, 0),
    )

    windows = find_free_windows(MONDAY, MONDAY, session)

    assert len(windows) == 1
    assert windows[0].start_time == datetime(2026, 4, 20, 9, 0)
    assert windows[0].end_time == datetime(2026, 4, 20, 17, 0)


def test_overlapping_occupancies_merge(session):
    """Two overlapping events should be merged before subtraction."""
    make_availability(session, weekday=0, start=time(9, 0), end=time(17, 0))
    cal = make_calendar(session)
    make_event(
        session,
        cal.id,
        start=datetime(2026, 4, 20, 10, 0),
        end=datetime(2026, 4, 20, 12, 0),
    )
    make_event(
        session,
        cal.id,
        start=datetime(2026, 4, 20, 11, 0),
        end=datetime(2026, 4, 20, 13, 0),
    )

    windows = find_free_windows(MONDAY, MONDAY, session)

    assert [(w.start_time, w.end_time) for w in windows] == [
        (datetime(2026, 4, 20, 9, 0), datetime(2026, 4, 20, 10, 0)),
        (datetime(2026, 4, 20, 13, 0), datetime(2026, 4, 20, 17, 0)),
    ]


def test_multi_day_range_skips_days_without_availability(session):
    """Monday has availability; Tuesday has none → only Monday windows emitted."""
    make_availability(session, weekday=0, start=time(9, 0), end=time(12, 0))

    windows = find_free_windows(MONDAY, TUESDAY, session)

    assert len(windows) == 1
    assert windows[0].start_time == datetime(2026, 4, 20, 9, 0)
    assert windows[0].end_time == datetime(2026, 4, 20, 12, 0)


def test_inactive_availability_is_ignored(session):
    make_availability(
        session, weekday=0, start=time(9, 0), end=time(17, 0), active=False
    )

    assert find_free_windows(MONDAY, MONDAY, session) == []


def test_event_filling_entire_window_yields_no_free_time(session):
    make_availability(session, weekday=0, start=time(9, 0), end=time(12, 0))
    cal = make_calendar(session)
    make_event(
        session,
        cal.id,
        start=datetime(2026, 4, 20, 9, 0),
        end=datetime(2026, 4, 20, 12, 0),
    )

    assert find_free_windows(MONDAY, MONDAY, session) == []
