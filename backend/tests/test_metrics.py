"""Tests for compute_weekly_metrics."""

from datetime import date, datetime

from app.services.metrics import compute_weekly_metrics, monday_of

from .factories import make_blocked_time, make_calendar, make_event

# Week of Monday 2026-04-20 → Sunday 2026-04-26.
MONDAY = date(2026, 4, 20)
SUNDAY = date(2026, 4, 26)


def test_empty_week_returns_zero_metrics(session):
    m = compute_weekly_metrics(session, week_start=MONDAY)
    assert m["week_start"] == MONDAY
    assert m["week_end"] == SUNDAY
    assert m["total_events"] == 0
    assert m["total_blocked_times"] == 0
    assert m["total_scheduled_minutes"] == 0
    assert m["total_blocked_minutes"] == 0
    assert m["busiest_day"] is None
    assert m["busiest_day_minutes"] == 0


def test_week_start_snaps_to_monday(session):
    # Passing a Wednesday should snap to that week's Monday.
    m = compute_weekly_metrics(session, week_start=date(2026, 4, 22))
    assert m["week_start"] == MONDAY
    assert m["week_end"] == SUNDAY


def test_counts_events_and_minutes(session):
    cal = make_calendar(session)
    # Monday: 60 minutes
    make_event(
        session, cal.id,
        start=datetime(2026, 4, 20, 9, 0),
        end=datetime(2026, 4, 20, 10, 0),
    )
    # Wednesday: 90 minutes (busiest)
    make_event(
        session, cal.id,
        start=datetime(2026, 4, 22, 14, 0),
        end=datetime(2026, 4, 22, 15, 30),
    )

    m = compute_weekly_metrics(session, week_start=MONDAY)

    assert m["total_events"] == 2
    assert m["total_scheduled_minutes"] == 150
    assert m["busiest_day"] == date(2026, 4, 22)
    assert m["busiest_day_minutes"] == 90


def test_blocked_minutes_counted_separately(session):
    make_blocked_time(
        session,
        start=datetime(2026, 4, 21, 9, 0),
        end=datetime(2026, 4, 21, 11, 0),
    )

    m = compute_weekly_metrics(session, week_start=MONDAY)

    assert m["total_blocked_times"] == 1
    assert m["total_blocked_minutes"] == 120
    assert m["total_scheduled_minutes"] == 0
    # Blocked time must not drive busiest_day (events only).
    assert m["busiest_day"] is None


def test_intervals_outside_week_are_ignored(session):
    cal = make_calendar(session)
    # Prior week's Sunday — must not be counted.
    make_event(
        session, cal.id,
        start=datetime(2026, 4, 19, 10, 0),
        end=datetime(2026, 4, 19, 11, 0),
    )
    # Next week's Monday — must not be counted.
    make_event(
        session, cal.id,
        start=datetime(2026, 4, 27, 10, 0),
        end=datetime(2026, 4, 27, 11, 0),
    )

    m = compute_weekly_metrics(session, week_start=MONDAY)
    assert m["total_events"] == 0
    assert m["total_scheduled_minutes"] == 0


def test_interval_is_clipped_to_week_boundary(session):
    cal = make_calendar(session)
    # Straddles Sunday 23:00 → next Monday 01:00 (2 hours total;
    # only the first 60 minutes fall inside the target week).
    make_event(
        session, cal.id,
        start=datetime(2026, 4, 26, 23, 0),
        end=datetime(2026, 4, 27, 1, 0),
    )

    m = compute_weekly_metrics(session, week_start=MONDAY)

    assert m["total_events"] == 1
    assert m["total_scheduled_minutes"] == 60
    assert m["busiest_day"] == date(2026, 4, 26)
    assert m["busiest_day_minutes"] == 60


def test_monday_of_helper():
    assert monday_of(date(2026, 4, 20)) == date(2026, 4, 20)  # Monday
    assert monday_of(date(2026, 4, 22)) == date(2026, 4, 20)  # Wednesday
    assert monday_of(date(2026, 4, 26)) == date(2026, 4, 20)  # Sunday
