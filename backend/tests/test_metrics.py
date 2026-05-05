"""Tests for compute_weekly_metrics."""

from datetime import date, datetime, time

from app.services.metrics import compute_weekly_metrics, monday_of

from .factories import make_availability, make_calendar, make_event

# Week of Monday 2026-04-20 → Sunday 2026-04-26.
MONDAY = date(2026, 4, 20)
SUNDAY = date(2026, 4, 26)


def test_empty_week_returns_zero_metrics(session):
    m = compute_weekly_metrics(session, week_start=MONDAY)
    assert m["week_start"] == MONDAY
    assert m["week_end"] == SUNDAY
    assert m["total_events"] == 0
    assert m["total_scheduled_minutes"] == 0
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


def test_metrics_do_not_require_availability_window_rows(session):
    """Metrics must compute correctly with zero AvailabilityWindow rows
    (the post-Daily-Rhythm baseline) — counts are derived from events alone."""
    cal = make_calendar(session)
    make_event(
        session, cal.id,
        start=datetime(2026, 4, 20, 9, 0),
        end=datetime(2026, 4, 20, 10, 0),
    )

    m = compute_weekly_metrics(session, week_start=MONDAY)

    assert m["total_events"] == 1
    assert m["total_scheduled_minutes"] == 60
    assert m["busiest_day"] == date(2026, 4, 20)
    assert m["busiest_day_minutes"] == 60


def test_metrics_ignore_availability_window_rows(session):
    """AvailabilityWindow rows are legacy and must not influence metrics —
    adding or removing them does not change totals or busiest day."""
    cal = make_calendar(session)
    # Add an AvailabilityWindow row that does NOT cover the event time.
    # If metrics depended on AvailabilityWindow, the event would be excluded.
    make_availability(
        session,
        weekday=0,  # Monday
        start=time(13, 0),
        end=time(17, 0),
    )
    # Event at 09:00–10:00 Monday — outside the AvailabilityWindow above.
    make_event(
        session, cal.id,
        start=datetime(2026, 4, 20, 9, 0),
        end=datetime(2026, 4, 20, 10, 0),
    )

    m = compute_weekly_metrics(session, week_start=MONDAY)

    assert m["total_events"] == 1
    assert m["total_scheduled_minutes"] == 60
    assert m["busiest_day"] == date(2026, 4, 20)
    assert m["busiest_day_minutes"] == 60


def test_metrics_include_events_outside_daily_rhythm_suggestion_hours(session):
    """Manual events placed outside Daily Rhythm suggestion hours
    (default 08:00–21:00) must still count toward total_events and
    total_scheduled_minutes — metrics describe what is scheduled, not what
    suggestion logic would have proposed."""
    cal = make_calendar(session)
    # 06:00–07:00 Monday — before suggestion-hours start.
    make_event(
        session, cal.id,
        start=datetime(2026, 4, 20, 6, 0),
        end=datetime(2026, 4, 20, 7, 0),
    )
    # 22:00–23:00 Tuesday — after suggestion-hours end.
    make_event(
        session, cal.id,
        start=datetime(2026, 4, 21, 22, 0),
        end=datetime(2026, 4, 21, 23, 0),
    )

    m = compute_weekly_metrics(session, week_start=MONDAY)

    assert m["total_events"] == 2
    assert m["total_scheduled_minutes"] == 120
    # Tie on minutes (60 each) — earliest day wins per the service contract.
    assert m["busiest_day"] == date(2026, 4, 20)
    assert m["busiest_day_minutes"] == 60


def test_monday_of_helper():
    assert monday_of(date(2026, 4, 20)) == date(2026, 4, 20)  # Monday
    assert monday_of(date(2026, 4, 22)) == date(2026, 4, 20)  # Wednesday
    assert monday_of(date(2026, 4, 26)) == date(2026, 4, 20)  # Sunday
