"""Tests for the explanation surface of compute_weekly_triage.

Verifies that warning codes are stable, messages are deterministic and
human-readable, and longest_free_window values stay deterministic across
repeated calls with the same data.
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


def _full_week_availability(session, start=time(9, 0), end=time(17, 0)):
    for wd in range(5):
        make_availability(session, weekday=wd, start=start, end=end)


def _day(triage, d: date):
    return next(x for x in triage["days"] if x["date"] == d)


def test_overloaded_day_warning_code_and_message(session):
    _full_week_availability(session)
    cal = make_calendar(session)
    make_event(session, cal.id,
               start=datetime(2026, 4, 20, 9, 0),
               end=datetime(2026, 4, 20, 12, 0))   # 3h
    make_event(session, cal.id,
               start=datetime(2026, 4, 20, 13, 0),
               end=datetime(2026, 4, 20, 16, 0))   # 3h

    triage = compute_weekly_triage(session, week_start=MONDAY)
    monday = _day(triage, MONDAY)

    warnings = [w for w in monday["warnings"] if w["reason_code"] == "OVERLOADED_DAY"]
    assert len(warnings) == 1
    assert "6 hours" in warnings[0]["message"]
    assert monday["total_busy_minutes"] >= OVERLOADED_DAY_BUSY_MINUTES


def test_fragmented_day_warning_code_and_message(session):
    _full_week_availability(session)
    cal = make_calendar(session)
    # Same setup as test_triage.py — produces 4 small free windows.
    for hh in (9, 10, 11, 12):
        make_event(session, cal.id,
                   start=datetime(2026, 4, 20, hh, 30),
                   end=datetime(2026, 4, 20, hh + 1, 0))

    triage = compute_weekly_triage(session, week_start=MONDAY)
    monday = _day(triage, MONDAY)

    warnings = [w for w in monday["warnings"] if w["reason_code"] == "FRAGMENTED_DAY"]
    assert len(warnings) == 1
    assert str(FRAGMENTED_DAY_FREE_WINDOW_MAX) in warnings[0]["message"]
    assert monday["is_fragmented"] is True


def test_weak_buffer_warning_code_and_message(session):
    # Block 8:00-20:00 of Tuesday (12h) so only the 20:00-21:00 hour remains
    # free inside the Daily Rhythm window — below the weak-buffer threshold.
    cal = make_calendar(session)
    make_event(session, cal.id,
               start=datetime(2026, 4, 21, 8, 0),
               end=datetime(2026, 4, 21, 20, 0))

    triage = compute_weekly_triage(session, week_start=MONDAY)
    tuesday = _day(triage, date(2026, 4, 21))

    warnings = [w for w in tuesday["warnings"] if w["reason_code"] == "WEAK_BUFFER"]
    assert len(warnings) == 1
    assert "minutes" in warnings[0]["message"].lower()
    assert tuesday["free_minutes"] < WEAK_BUFFER_FREE_MINUTES


def test_longest_free_window_is_deterministic(session):
    """Same inputs → same longest_free_window_minutes across repeated calls."""
    _full_week_availability(session)
    cal = make_calendar(session)
    make_event(session, cal.id,
               start=datetime(2026, 4, 20, 12, 0),
               end=datetime(2026, 4, 20, 12, 30))

    a = compute_weekly_triage(session, week_start=MONDAY)
    b = compute_weekly_triage(session, week_start=MONDAY)

    a_lf = [d["longest_free_window_minutes"] for d in a["days"]]
    b_lf = [d["longest_free_window_minutes"] for d in b["days"]]
    assert a_lf == b_lf

    monday_a = _day(a, MONDAY)
    # Daily Rhythm 8:00-21:00 minus 12:00-12:30 → free windows of 240 and
    # 510 minutes → longest 510.
    assert monday_a["longest_free_window_minutes"] == 510


def test_warning_messages_are_deterministic(session):
    """Identical inputs produce identical warning messages."""
    _full_week_availability(session)
    cal = make_calendar(session)
    make_event(session, cal.id,
               start=datetime(2026, 4, 20, 9, 0),
               end=datetime(2026, 4, 20, 15, 0))   # 6h overload

    a = compute_weekly_triage(session, week_start=MONDAY)
    b = compute_weekly_triage(session, week_start=MONDAY)

    assert _day(a, MONDAY)["warnings"] == _day(b, MONDAY)["warnings"]


def test_blocked_time_contributes_to_overload_warning(session):
    """Overloaded warning fires from event+blocked mix, not just events."""
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

    codes = [w["reason_code"] for w in monday["warnings"]]
    assert "OVERLOADED_DAY" in codes
