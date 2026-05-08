"""Tests for the free-window scanning helper.

Free-window output is now driven by Daily Rhythm suggestion hours
(8:00–21:00 by default). Each day in the requested range emits one
suggestion window minus any overlapping events.
"""

from datetime import date, datetime

from app.services.conflict_detection import find_free_windows
from app.services.daily_rhythm import (
    DEFAULT_SUGGESTIONS_END,
    DEFAULT_SUGGESTIONS_START,
)

from .factories import (
    make_calendar,
    make_event,
)

MONDAY = date(2026, 4, 20)
TUESDAY = date(2026, 4, 21)


def _rhythm_start(d: date) -> datetime:
    return datetime.combine(d, DEFAULT_SUGGESTIONS_START)


def _rhythm_end(d: date) -> datetime:
    return datetime.combine(d, DEFAULT_SUGGESTIONS_END)


def test_no_data_returns_full_daily_rhythm_window(session):
    """With no events, the full Daily Rhythm window for each day is free."""
    windows = find_free_windows(MONDAY, MONDAY, session)

    assert len(windows) == 1
    assert windows[0].start_time == _rhythm_start(MONDAY)
    assert windows[0].end_time == _rhythm_end(MONDAY)


def test_event_splits_daily_rhythm_window(session):
    cal = make_calendar(session)
    make_event(
        session,
        cal.id,
        start=datetime(2026, 4, 20, 12, 0),
        end=datetime(2026, 4, 20, 13, 0),
    )

    windows = find_free_windows(MONDAY, MONDAY, session)

    assert [(w.start_time, w.end_time) for w in windows] == [
        (_rhythm_start(MONDAY), datetime(2026, 4, 20, 12, 0)),
        (datetime(2026, 4, 20, 13, 0), _rhythm_end(MONDAY)),
    ]


def test_event_touching_window_edge_does_not_shrink_available(session):
    """An event ending exactly at suggestion start is not overlap — window is full."""
    cal = make_calendar(session)
    make_event(
        session,
        cal.id,
        start=datetime(2026, 4, 20, 7, 0),
        end=datetime(2026, 4, 20, 8, 0),  # touches DEFAULT_SUGGESTIONS_START
    )

    windows = find_free_windows(MONDAY, MONDAY, session)

    assert len(windows) == 1
    assert windows[0].start_time == _rhythm_start(MONDAY)
    assert windows[0].end_time == _rhythm_end(MONDAY)


def test_overlapping_occupancies_merge(session):
    """Two overlapping events should be merged before subtraction."""
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
        (_rhythm_start(MONDAY), datetime(2026, 4, 20, 10, 0)),
        (datetime(2026, 4, 20, 13, 0), _rhythm_end(MONDAY)),
    ]


def test_multi_day_range_emits_one_window_per_day(session):
    """Every day in the range gets its Daily Rhythm window — no day is skipped."""
    windows = find_free_windows(MONDAY, TUESDAY, session)

    assert [(w.start_time, w.end_time) for w in windows] == [
        (_rhythm_start(MONDAY), _rhythm_end(MONDAY)),
        (_rhythm_start(TUESDAY), _rhythm_end(TUESDAY)),
    ]


def test_event_filling_entire_window_yields_no_free_time(session):
    cal = make_calendar(session)
    make_event(
        session,
        cal.id,
        start=_rhythm_start(MONDAY),
        end=_rhythm_end(MONDAY),
    )

    assert find_free_windows(MONDAY, MONDAY, session) == []


def test_events_outside_rhythm_window_are_ignored(session):
    """Events outside the Daily Rhythm window must not affect free intervals."""
    cal = make_calendar(session)
    # Pre-rhythm and post-rhythm events.
    make_event(
        session,
        cal.id,
        start=datetime(2026, 4, 20, 6, 0),
        end=datetime(2026, 4, 20, 7, 30),
    )
    make_event(
        session,
        cal.id,
        start=datetime(2026, 4, 20, 22, 0),
        end=datetime(2026, 4, 20, 23, 0),
    )

    windows = find_free_windows(MONDAY, MONDAY, session)

    assert len(windows) == 1
    assert windows[0].start_time == _rhythm_start(MONDAY)
    assert windows[0].end_time == _rhythm_end(MONDAY)
