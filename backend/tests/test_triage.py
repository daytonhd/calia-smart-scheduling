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
    """No events, no blocked times, no availability → all days zeroed, no warnings."""
    triage = compute_weekly_triage(session, week_start=MONDAY)

    assert triage["week_start"] == MONDAY
    assert triage["week_end"] == SUNDAY
    assert len(triage["days"]) == 7
    for d in triage["days"]:
        assert d["scheduled_minutes"] == 0
        assert d["blocked_minutes"] == 0
        assert d["total_busy_minutes"] == 0
        assert d["free_minutes"] == 0
        assert d["longest_free_window_minutes"] == 0
        assert d["is_overloaded"] is False
        assert d["is_fragmented"] is False
        assert d["has_weak_buffer"] is False
        assert d["warnings"] == []
    # No availability all week → no free time → weak weekly buffer fires.
    assert any(w["reason_code"] == "WEAK_WEEKLY_BUFFER" for w in triage["week_warnings"])


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


def test_overloaded_uses_blocked_time_too(session):
    """Mix of events + blocked time hitting threshold also triggers."""
    _full_week_availability(session)
    cal = make_calendar(session)
    make_event(session, cal.id,
               start=datetime(2026, 4, 20, 9, 0),
               end=datetime(2026, 4, 20, 12, 0))   # 3h
    make_blocked_time(session,
                      start=datetime(2026, 4, 20, 13, 0),
                      end=datetime(2026, 4, 20, 16, 0))  # 3h

    triage = compute_weekly_triage(session, week_start=MONDAY)
    monday = _day(triage, MONDAY)

    assert monday["scheduled_minutes"] == 180
    assert monday["blocked_minutes"] == 180
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
    """Day with limited availability and most of it occupied → WEAK_BUFFER."""
    # Tuesday only — 1 hour availability, 30 minutes free → < 90 minute threshold.
    make_availability(session, weekday=1, start=time(9, 0), end=time(10, 0))
    cal = make_calendar(session)
    make_event(session, cal.id,
               start=datetime(2026, 4, 21, 9, 0),
               end=datetime(2026, 4, 21, 9, 30))

    triage = compute_weekly_triage(session, week_start=MONDAY)
    tuesday = _day(triage, date(2026, 4, 21))

    assert tuesday["free_minutes"] < WEAK_BUFFER_FREE_MINUTES
    assert tuesday["has_weak_buffer"] is True
    assert any(w["reason_code"] == "WEAK_BUFFER" for w in tuesday["warnings"])


def test_longest_free_window_calculation(session):
    """longest_free_window_minutes = max of per-day free window durations."""
    _full_week_availability(session)
    cal = make_calendar(session)
    # On Monday: split 9-17 (480 min) by 12:00-12:30 lunch.
    # Free windows: 9:00-12:00 (180) and 12:30-17:00 (270). Longest = 270.
    make_event(session, cal.id,
               start=datetime(2026, 4, 20, 12, 0),
               end=datetime(2026, 4, 20, 12, 30))

    triage = compute_weekly_triage(session, week_start=MONDAY)
    monday = _day(triage, MONDAY)

    assert monday["longest_free_window_minutes"] == 270


def test_day_without_availability_not_flagged_weak_buffer(session):
    """Days with zero availability and zero events are not flagged as weak."""
    # Only Tuesday gets availability; rest of week is intentionally off.
    make_availability(session, weekday=1, start=time(9, 0), end=time(17, 0))

    triage = compute_weekly_triage(session, week_start=MONDAY)
    monday = _day(triage, MONDAY)

    assert monday["free_minutes"] == 0
    # Monday has no availability and no events → not weak-buffer flagged.
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
