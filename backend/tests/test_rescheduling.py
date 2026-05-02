"""Tests for find_replacement_slots — adaptive rescheduling service.

Anchor week: Monday 2026-04-20 → Sunday 2026-04-26.
"""

from datetime import date, datetime, time

from app.services.rescheduling import find_replacement_slots

from .factories import (
    make_availability,
    make_blocked_time,
    make_calendar,
    make_event,
)

MONDAY = date(2026, 4, 20)
TUESDAY = date(2026, 4, 21)


def _weekday_availability(session, start=time(9, 0), end=time(17, 0)):
    """Mon–Fri availability."""
    for wd in range(5):
        make_availability(session, weekday=wd, start=start, end=end)


def test_returns_none_for_missing_event(session):
    _weekday_availability(session)
    result = find_replacement_slots(
        event_id=9999,
        search_start=datetime(2026, 4, 20, 9, 0),
        search_end=datetime(2026, 4, 20, 17, 0),
        max_results=5,
        session=session,
    )
    assert result is None


def test_ignores_self_during_overlap_check(session):
    """The selected event must not block its own time slot."""
    _weekday_availability(session)
    cal = make_calendar(session)
    ev = make_event(
        session, cal.id,
        start=datetime(2026, 4, 20, 10, 0),
        end=datetime(2026, 4, 20, 11, 0),
        title="Original",
    )

    result = find_replacement_slots(
        event_id=ev.id,
        search_start=datetime(2026, 4, 20, 9, 0),
        search_end=datetime(2026, 4, 20, 17, 0),
        max_results=20,
        session=session,
    )

    starts = [o["start_time"] for o in result["options"]]
    # The original 10:00 slot should be available because we excluded self.
    assert datetime(2026, 4, 20, 10, 0) in starts


def test_preserves_event_duration(session):
    _weekday_availability(session)
    cal = make_calendar(session)
    ev = make_event(
        session, cal.id,
        start=datetime(2026, 4, 20, 10, 0),
        end=datetime(2026, 4, 20, 11, 30),  # 90-minute event
    )

    result = find_replacement_slots(
        event_id=ev.id,
        search_start=datetime(2026, 4, 20, 9, 0),
        search_end=datetime(2026, 4, 20, 17, 0),
        max_results=5,
        session=session,
    )

    assert result["duration_minutes"] == 90
    for o in result["options"]:
        assert (o["end_time"] - o["start_time"]).total_seconds() == 90 * 60


def test_avoids_other_events(session):
    _weekday_availability(session)
    cal = make_calendar(session)
    ev = make_event(
        session, cal.id,
        start=datetime(2026, 4, 20, 10, 0),
        end=datetime(2026, 4, 20, 11, 0),
    )
    # Another event blocks 13:00-14:00.
    make_event(
        session, cal.id,
        start=datetime(2026, 4, 20, 13, 0),
        end=datetime(2026, 4, 20, 14, 0),
        title="Other",
    )

    result = find_replacement_slots(
        event_id=ev.id,
        search_start=datetime(2026, 4, 20, 9, 0),
        search_end=datetime(2026, 4, 20, 17, 0),
        max_results=20,
        session=session,
    )

    # No option should overlap [13:00, 14:00).
    for o in result["options"]:
        assert not (o["start_time"] < datetime(2026, 4, 20, 14, 0)
                    and o["end_time"] > datetime(2026, 4, 20, 13, 0))


def test_avoids_other_occupied_events(session):
    """Replacement options must avoid time blocked by another event.

    All occupied time is now represented as Events; a blocked-time-style
    use case is just an Event with an appropriate label.
    """
    _weekday_availability(session)
    cal = make_calendar(session)
    ev = make_event(
        session, cal.id,
        start=datetime(2026, 4, 20, 10, 0),
        end=datetime(2026, 4, 20, 11, 0),
    )
    # An event representing "lunch / occupied time" — what BlockedTime
    # used to model.
    make_event(
        session, cal.id,
        start=datetime(2026, 4, 20, 14, 0),
        end=datetime(2026, 4, 20, 15, 0),
        title="Lunch",
    )

    result = find_replacement_slots(
        event_id=ev.id,
        search_start=datetime(2026, 4, 20, 9, 0),
        search_end=datetime(2026, 4, 20, 17, 0),
        max_results=20,
        session=session,
    )

    for o in result["options"]:
        assert not (o["start_time"] < datetime(2026, 4, 20, 15, 0)
                    and o["end_time"] > datetime(2026, 4, 20, 14, 0))


def test_options_stay_within_daily_rhythm_hours(session):
    """Slots outside Daily Rhythm suggestion hours must not appear."""
    from app.services.daily_rhythm import (
        DEFAULT_SUGGESTIONS_END,
        DEFAULT_SUGGESTIONS_START,
    )
    cal = make_calendar(session)
    ev = make_event(
        session, cal.id,
        start=datetime(2026, 4, 20, 9, 0),
        end=datetime(2026, 4, 20, 10, 0),
    )

    result = find_replacement_slots(
        event_id=ev.id,
        search_start=datetime(2026, 4, 20, 0, 0),
        search_end=datetime(2026, 4, 22, 0, 0),
        max_results=20,
        session=session,
    )

    for o in result["options"]:
        rhythm_start = datetime.combine(
            o["start_time"].date(), DEFAULT_SUGGESTIONS_START
        )
        rhythm_end = datetime.combine(
            o["start_time"].date(), DEFAULT_SUGGESTIONS_END
        )
        assert o["start_time"] >= rhythm_start
        assert o["end_time"] <= rhythm_end


def test_same_day_options_rank_first(session):
    """Same-day candidates should appear before later-day candidates."""
    _weekday_availability(session)
    cal = make_calendar(session)
    ev = make_event(
        session, cal.id,
        start=datetime(2026, 4, 20, 10, 0),
        end=datetime(2026, 4, 20, 11, 0),
    )

    result = find_replacement_slots(
        event_id=ev.id,
        search_start=datetime(2026, 4, 20, 9, 0),
        search_end=datetime(2026, 4, 22, 0, 0),
        max_results=10,
        session=session,
    )

    # Find the index where the day flips from Monday to a later date.
    monday_seen = False
    later_seen = False
    for o in result["options"]:
        if o["start_time"].date() == MONDAY:
            assert not later_seen, "Monday options must come before later days"
            monday_seen = True
            assert o["reason_code"] == "SAME_DAY_REPLACEMENT"
        else:
            later_seen = True
    assert monday_seen, "expected at least one same-day option"


def test_returns_empty_when_no_valid_replacement(session):
    """Search range fully occupied by events → no options."""
    _weekday_availability(session)
    cal = make_calendar(session)
    ev = make_event(
        session, cal.id,
        start=datetime(2026, 4, 20, 10, 0),
        end=datetime(2026, 4, 20, 11, 0),
    )
    # Fill the rest of the Monday availability with events.
    make_event(
        session, cal.id,
        start=datetime(2026, 4, 20, 9, 0),
        end=datetime(2026, 4, 20, 10, 0),
        title="Block A",
    )
    make_event(
        session, cal.id,
        start=datetime(2026, 4, 20, 11, 0),
        end=datetime(2026, 4, 20, 17, 0),
        title="Block B",
    )

    result = find_replacement_slots(
        event_id=ev.id,
        search_start=datetime(2026, 4, 20, 9, 0),
        search_end=datetime(2026, 4, 20, 17, 0),
        max_results=10,
        session=session,
    )

    # Only the original slot itself remains valid (since we exclude self) —
    # so we DO get the 10:00 slot back. Replace this scenario by also
    # restricting search window to skip 10:00.
    starts = [o["start_time"] for o in result["options"]]
    assert datetime(2026, 4, 20, 10, 0) in starts

    result2 = find_replacement_slots(
        event_id=ev.id,
        search_start=datetime(2026, 4, 20, 11, 0),  # skip the original slot
        search_end=datetime(2026, 4, 20, 17, 0),
        max_results=10,
        session=session,
    )
    assert result2["options"] == []


def test_options_include_explainability_fields(session):
    _weekday_availability(session)
    cal = make_calendar(session)
    ev = make_event(
        session, cal.id,
        start=datetime(2026, 4, 20, 10, 0),
        end=datetime(2026, 4, 20, 11, 0),
        title="Original",
    )

    result = find_replacement_slots(
        event_id=ev.id,
        search_start=datetime(2026, 4, 20, 9, 0),
        search_end=datetime(2026, 4, 20, 17, 0),
        max_results=3,
        session=session,
    )

    assert result["event_id"] == ev.id
    assert result["event_title"] == "Original"
    assert result["duration_minutes"] == 60

    for idx, o in enumerate(result["options"], start=1):
        assert o["rank"] == idx
        assert "explanation" in o and o["explanation"]
        assert o["reason_code"] in {
            "SAME_DAY_REPLACEMENT",
            "EARLIEST_VALID_REPLACEMENT",
            "VALID_REPLACEMENT_SLOT",
        }
        # Minutes-from-original is signed and computed from the event start.
        expected = int(
            (o["start_time"] - datetime(2026, 4, 20, 10, 0)).total_seconds() // 60
        )
        assert o["minutes_from_original_start"] == expected


def test_max_results_respected(session):
    _weekday_availability(session)
    cal = make_calendar(session)
    ev = make_event(
        session, cal.id,
        start=datetime(2026, 4, 20, 10, 0),
        end=datetime(2026, 4, 20, 11, 0),
    )
    result = find_replacement_slots(
        event_id=ev.id,
        search_start=datetime(2026, 4, 20, 9, 0),
        search_end=datetime(2026, 4, 25, 0, 0),
        max_results=3,
        session=session,
    )
    assert len(result["options"]) <= 3
