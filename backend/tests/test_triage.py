"""Tests for compute_weekly_triage.

Anchor week: Monday 2026-04-20 → Sunday 2026-04-26.
"""

from datetime import date, datetime, time

from app.services.triage import (
    FRAGMENTED_DAY_FREE_WINDOW_MAX,
    OVERLOADED_DAY_BUSY_MINUTES,
    WEAK_BUFFER_FREE_MINUTES,
    compute_weekly_triage,
)

from .factories import (
    make_availability,
    make_blocked_time,
    make_calendar,
    make_event,
)

MONDAY = date(2026, 4, 20)
SUNDAY = date(2026, 4, 26)


def _full_week_availability(session, start=time(9, 0), end=time(17, 0)):
    """9-5 every weekday (Mon-Fri)."""
    for wd in range(5):
        make_availability(session, weekday=wd, start=start, end=end)


def _day(triage, d: date):
    return next(x for x in triage["days"] if x["date"] == d)


def test_empty_low_data_week_is_clean(session):
    """No events / no blocked times → each day is fully free inside the
    Daily Rhythm window (8:00–21:00 = 780 min) and there are no warnings."""
    triage = compute_weekly_triage(session, week_start=MONDAY)

    assert triage["week_start"] == MONDAY
    assert triage["week_end"] == SUNDAY
    assert len(triage["days"]) == 7
    for d in triage["days"]:
        assert d["scheduled_minutes"] == 0
        assert d["blocked_minutes"] == 0
        assert d["total_busy_minutes"] == 0
        # 8:00–21:00 = 13h = 780 min of free time per day.
        assert d["free_minutes"] == 780
        assert d["longest_free_window_minutes"] == 780
        assert d["is_overloaded"] is False
        assert d["is_fragmented"] is False
        assert d["has_weak_buffer"] is False
        assert d["warnings"] == []
    # 7 * 780 = 5460 min of weekly free time — well above the weak-buffer
    # threshold, so no week-level warnings.
    assert triage["week_warnings"] == []


def test_overloaded_day_detection(session):
    """6h+ scheduled+blocked on Monday → OVERLOADED_DAY warning."""
    _full_week_availability(session)
    cal = make_calendar(session)
    # 6 hours of scheduled events on Monday: 9-12 and 13-16 (6h total)
    make_event(session, cal.id,
               start=datetime(2026, 4, 20, 9, 0),
               end=datetime(2026, 4, 20, 12, 0))
    make_event(session, cal.id,
               start=datetime(2026, 4, 20, 13, 0),
               end=datetime(2026, 4, 20, 16, 0))

    triage = compute_weekly_triage(session, week_start=MONDAY)
    monday = _day(triage, MONDAY)

    assert monday["scheduled_minutes"] == 360
    assert monday["total_busy_minutes"] >= OVERLOADED_DAY_BUSY_MINUTES
    assert monday["is_overloaded"] is True
    assert any(w["reason_code"] == "OVERLOADED_DAY" for w in monday["warnings"])


def test_overloaded_uses_events_only(session):
    """Multiple events hitting the threshold trigger overload — blocked
    time rows do not contribute and blocked_minutes is always 0."""
    _full_week_availability(session)
    cal = make_calendar(session)
    make_event(session, cal.id,
               start=datetime(2026, 4, 20, 9, 0),
               end=datetime(2026, 4, 20, 12, 0))   # 3h
    make_event(session, cal.id,
               start=datetime(2026, 4, 20, 13, 0),
               end=datetime(2026, 4, 20, 16, 0))   # 3h
    # A blocked-time row that should NOT contribute to busy time.
    make_blocked_time(session,
                      start=datetime(2026, 4, 20, 16, 0),
                      end=datetime(2026, 4, 20, 18, 0))

    triage = compute_weekly_triage(session, week_start=MONDAY)
    monday = _day(triage, MONDAY)

    assert monday["scheduled_minutes"] == 360
    assert monday["blocked_minutes"] == 0
    assert monday["total_busy_minutes"] == 360
    assert monday["is_overloaded"] is True


def test_fragmented_day_detection(session):
    """3+ free windows shorter than the small-window threshold → FRAGMENTED_DAY."""
    _full_week_availability(session)
    cal = make_calendar(session)
    # In a 9-5 (480 min) window, place events to leave 4 small free gaps:
    # free: 9:00-9:30 (30), 10:00-10:30 (30), 11:00-11:30 (30), 12:00-12:30 (30),
    #       13:00-17:00 (240)
    make_event(session, cal.id,
               start=datetime(2026, 4, 20, 9, 30),
               end=datetime(2026, 4, 20, 10, 0))
    make_event(session, cal.id,
               start=datetime(2026, 4, 20, 10, 30),
               end=datetime(2026, 4, 20, 11, 0))
    make_event(session, cal.id,
               start=datetime(2026, 4, 20, 11, 30),
               end=datetime(2026, 4, 20, 12, 0))
    make_event(session, cal.id,
               start=datetime(2026, 4, 20, 12, 30),
               end=datetime(2026, 4, 20, 13, 0))

    triage = compute_weekly_triage(session, week_start=MONDAY)
    monday = _day(triage, MONDAY)

    small_count = sum(
        1 for d in [30, 30, 30, 30] if d < FRAGMENTED_DAY_FREE_WINDOW_MAX
    )
    assert small_count >= 3
    assert monday["is_fragmented"] is True
    assert any(w["reason_code"] == "FRAGMENTED_DAY" for w in monday["warnings"])


def test_weak_buffer_detection(session):
    """Day where events/blocked times consume nearly the whole Daily Rhythm
    window leaves <90 min free → WEAK_BUFFER."""
    # Daily Rhythm is 8:00-21:00 (780 min). Block 8:00-20:00 (720 min) so
    # only the 20:00-21:00 hour (60 min) remains free — below threshold.
    cal = make_calendar(session)
    make_event(session, cal.id,
               start=datetime(2026, 4, 21, 8, 0),
               end=datetime(2026, 4, 21, 20, 0))

    triage = compute_weekly_triage(session, week_start=MONDAY)
    tuesday = _day(triage, date(2026, 4, 21))

    assert tuesday["free_minutes"] < WEAK_BUFFER_FREE_MINUTES
    assert tuesday["has_weak_buffer"] is True
    assert any(w["reason_code"] == "WEAK_BUFFER" for w in tuesday["warnings"])


def test_longest_free_window_calculation(session):
    """longest_free_window_minutes = max of per-day free window durations."""
    cal = make_calendar(session)
    # Daily Rhythm 8:00-21:00 split by a 12:00-12:30 lunch event.
    # Free windows: 8:00-12:00 (240) and 12:30-21:00 (510). Longest = 510.
    make_event(session, cal.id,
               start=datetime(2026, 4, 20, 12, 0),
               end=datetime(2026, 4, 20, 12, 30))

    triage = compute_weekly_triage(session, week_start=MONDAY)
    monday = _day(triage, MONDAY)

    assert monday["longest_free_window_minutes"] == 510


def test_unscheduled_day_not_flagged_weak_buffer(session):
    """A day with zero events/blocked times has the full Daily Rhythm
    window free (780 min) — well above the weak-buffer threshold."""
    triage = compute_weekly_triage(session, week_start=MONDAY)
    monday = _day(triage, MONDAY)

    # 13h * 60 = 780 min free (the full 8:00-21:00 window).
    assert monday["free_minutes"] == 780
    assert monday["has_weak_buffer"] is False


def test_busy_minutes_clipped_to_day_boundary(session):
    """Cross-midnight events should attribute minutes to each day."""
    _full_week_availability(session)
    cal = make_calendar(session)
    # Mon 23:00 → Tue 02:00 (3h total: 60 min Monday, 120 min Tuesday)
    make_event(session, cal.id,
               start=datetime(2026, 4, 20, 23, 0),
               end=datetime(2026, 4, 21, 2, 0))

    triage = compute_weekly_triage(session, week_start=MONDAY)
    monday = _day(triage, MONDAY)
    tuesday = _day(triage, date(2026, 4, 21))

    assert monday["scheduled_minutes"] == 60
    assert tuesday["scheduled_minutes"] == 120
