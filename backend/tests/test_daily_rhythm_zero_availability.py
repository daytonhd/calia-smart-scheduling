"""Daily Rhythm / zero-availability contract tests.

Pins the post-Batch 4 product contract:

  * AvailabilityWindow is no longer required for manual event creation.
  * AvailabilityWindow is no longer required for slot suggestions.
  * Manual events may be created outside Daily Rhythm awake hours
    (default 7:00 AM-11:00 PM) and outside Suggestion hours
    (default 8:00 AM-9:00 PM) when the range is valid and non-overlapping.
  * Slot suggestions and replacement options stay inside Suggestion hours.
  * Conflict checks never return OUTSIDE_AVAILABILITY.
  * Schedule Balance uses default Suggestion capacity (780 min/day) and
    subtracts events from it.
  * Default explanations never mention "availability" or "blocked time"
    (case-insensitive).

This file exists alongside the granular per-feature test files; it
exercises each acceptance criterion as one focused contract suite.
"""

from datetime import date, datetime, time

from app.routers.events import create_event
from app.routers.schedule import check_conflict
from app.schemas.event import EventCreate
from app.schemas.schedule import ConflictCheckRequest
from app.services.conflict_detection import find_available_slots
from app.services.daily_rhythm import (
    DEFAULT_AWAKE_END,
    DEFAULT_AWAKE_START,
    DEFAULT_SUGGESTIONS_END,
    DEFAULT_SUGGESTIONS_START,
)
from app.services.rescheduling import (
    find_replacement_slots,
    find_replacement_slots_for_proposed,
)
from app.services.triage import compute_weekly_triage

from .factories import make_calendar, make_event

MONDAY = date(2026, 4, 20)


# ---------------------------------------------------------------------------
# 1. Manual event creation succeeds with zero AvailabilityWindow rows
# ---------------------------------------------------------------------------


def test_event_creation_succeeds_with_zero_availability_rows(session):
    cal = make_calendar(session)
    body = EventCreate(
        calendar_id=cal.id,
        title="Inside suggestion hours",
        start_time=datetime(2026, 4, 20, 10, 0),
        end_time=datetime(2026, 4, 20, 11, 0),
    )

    event = create_event(body, session)

    assert event.id is not None
    assert event.start_time == datetime(2026, 4, 20, 10, 0)


# ---------------------------------------------------------------------------
# 2. Manual events succeed outside Suggestion hours and outside Awake hours
# ---------------------------------------------------------------------------


def test_event_creation_succeeds_outside_suggestion_hours_inside_awake(session):
    """22:00-23:00 falls outside Suggestion hours (8:00-21:00) but inside
    Awake hours (7:00-23:00) — should succeed."""
    cal = make_calendar(session)
    body = EventCreate(
        calendar_id=cal.id,
        title="Late evening",
        start_time=datetime(2026, 4, 20, 22, 0),
        end_time=datetime(2026, 4, 20, 23, 0),
    )

    event = create_event(body, session)
    assert event.id is not None


def test_event_creation_succeeds_outside_awake_hours(session):
    """5:00-6:00 is outside Awake hours (7:00-23:00) entirely — should
    still succeed, since Awake/Suggestion hours never gate manual events."""
    cal = make_calendar(session)
    body = EventCreate(
        calendar_id=cal.id,
        title="Pre-dawn",
        start_time=datetime(2026, 4, 20, 5, 0),
        end_time=datetime(2026, 4, 20, 6, 0),
    )

    event = create_event(body, session)
    assert event.id is not None


def test_event_creation_succeeds_late_night_after_awake_end(session):
    """23:30-23:59 is past Awake end (23:00) — manual event still allowed."""
    cal = make_calendar(session)
    body = EventCreate(
        calendar_id=cal.id,
        title="After awake",
        start_time=datetime(2026, 4, 20, 23, 30),
        end_time=datetime(2026, 4, 20, 23, 59),
    )

    event = create_event(body, session)
    assert event.id is not None


# ---------------------------------------------------------------------------
# 3. Slot suggestions work without AvailabilityWindow rows
# ---------------------------------------------------------------------------


def test_slot_suggestions_work_with_zero_availability_rows(session):
    slots = find_available_slots(
        duration_minutes=60,
        start_date=MONDAY,
        end_date=MONDAY,
        max_results=5,
        session=session,
    )

    assert len(slots) == 5
    assert slots[0].start_time == datetime.combine(MONDAY, DEFAULT_SUGGESTIONS_START)


# ---------------------------------------------------------------------------
# 4. Suggested slots respect Daily Rhythm boundaries (8 AM - 9 PM)
# ---------------------------------------------------------------------------


def test_suggested_slots_stay_inside_suggestion_hours(session):
    slots = find_available_slots(
        duration_minutes=60,
        start_date=MONDAY,
        end_date=MONDAY,
        max_results=100,
        session=session,
    )

    rhythm_start = datetime.combine(MONDAY, DEFAULT_SUGGESTIONS_START)
    rhythm_end = datetime.combine(MONDAY, DEFAULT_SUGGESTIONS_END)
    assert rhythm_start == datetime(2026, 4, 20, 8, 0)
    assert rhythm_end == datetime(2026, 4, 20, 21, 0)

    for s in slots:
        assert s.start_time >= rhythm_start
        assert s.end_time <= rhythm_end


# ---------------------------------------------------------------------------
# 5. Saved-event replacement with zero availability rows
# ---------------------------------------------------------------------------


def test_saved_event_replacement_works_with_zero_availability_rows(session):
    cal = make_calendar(session)
    ev = make_event(
        session, cal.id,
        start=datetime(2026, 4, 20, 10, 0),
        end=datetime(2026, 4, 20, 11, 0),
    )

    result = find_replacement_slots(
        event_id=ev.id,
        search_start=datetime(2026, 4, 20, 0, 0),
        search_end=datetime(2026, 4, 20, 23, 59),
        max_results=10,
        session=session,
    )

    assert result is not None
    assert len(result["options"]) >= 1
    for o in result["options"]:
        rhythm_start = datetime.combine(o["start_time"].date(), DEFAULT_SUGGESTIONS_START)
        rhythm_end = datetime.combine(o["start_time"].date(), DEFAULT_SUGGESTIONS_END)
        assert o["start_time"] >= rhythm_start
        assert o["end_time"] <= rhythm_end


# ---------------------------------------------------------------------------
# 6. Proposed-event replacement with zero availability rows
# ---------------------------------------------------------------------------


def test_proposed_event_replacement_works_with_zero_availability_rows(session):
    result = find_replacement_slots_for_proposed(
        title="Proposed",
        start_time=datetime(2026, 4, 20, 14, 0),
        end_time=datetime(2026, 4, 20, 15, 0),
        search_start=datetime(2026, 4, 20, 0, 0),
        search_end=datetime(2026, 4, 20, 23, 59),
        max_results=10,
        session=session,
    )

    assert len(result["options"]) >= 1
    for o in result["options"]:
        rhythm_start = datetime.combine(o["start_time"].date(), DEFAULT_SUGGESTIONS_START)
        rhythm_end = datetime.combine(o["start_time"].date(), DEFAULT_SUGGESTIONS_END)
        assert o["start_time"] >= rhythm_start
        assert o["end_time"] <= rhythm_end


# ---------------------------------------------------------------------------
# 7. Conflict checks never emit OUTSIDE_AVAILABILITY
# ---------------------------------------------------------------------------


def test_conflict_check_no_availability_rows_returns_clean(session):
    cal = make_calendar(session)
    body = ConflictCheckRequest(
        calendar_id=cal.id,
        start_time=datetime(2026, 4, 23, 10, 0),
        end_time=datetime(2026, 4, 23, 11, 0),
    )

    response = check_conflict(body, session)

    assert response.has_conflicts is False
    assert response.conflicts == []


def test_conflict_check_outside_suggestion_hours_returns_clean(session):
    """A non-overlapping placement outside Suggestion hours produces no
    active conflicts — including no OUTSIDE_AVAILABILITY."""
    cal = make_calendar(session)

    placements = [
        # Pre-dawn (outside Awake hours).
        (datetime(2026, 4, 20, 5, 0), datetime(2026, 4, 20, 6, 0)),
        # After Suggestion end, inside Awake.
        (datetime(2026, 4, 20, 21, 30), datetime(2026, 4, 20, 22, 30)),
        # After Awake end.
        (datetime(2026, 4, 20, 23, 30), datetime(2026, 4, 20, 23, 59)),
    ]

    for start, end in placements:
        body = ConflictCheckRequest(
            calendar_id=cal.id,
            start_time=start,
            end_time=end,
        )
        response = check_conflict(body, session)
        codes = [c.reason_code for c in response.conflicts]
        assert "OUTSIDE_AVAILABILITY" not in codes
        assert response.has_conflicts is False


# ---------------------------------------------------------------------------
# 8. Schedule Balance uses default Suggestion capacity
# ---------------------------------------------------------------------------


def test_schedule_balance_uses_default_suggestion_capacity(session):
    """With zero AvailabilityWindow rows and zero events, every day's free
    capacity equals the Suggestion-hour duration (8:00-21:00 = 780 min)."""
    triage = compute_weekly_triage(session, week_start=MONDAY)

    assert len(triage["days"]) == 7
    for day in triage["days"]:
        assert day["free_minutes"] == 780
        assert day["longest_free_window_minutes"] == 780


def test_schedule_balance_free_minutes_reflect_events(session):
    """A 60-min event inside the Suggestion window reduces free capacity
    by exactly 60 minutes — no AvailabilityWindow rows required."""
    cal = make_calendar(session)
    make_event(
        session, cal.id,
        start=datetime(2026, 4, 20, 10, 0),
        end=datetime(2026, 4, 20, 11, 0),
    )

    triage = compute_weekly_triage(session, week_start=MONDAY)
    monday = next(d for d in triage["days"] if d["date"] == MONDAY)

    assert monday["scheduled_minutes"] == 60
    assert monday["free_minutes"] == 720  # 780 - 60


# ---------------------------------------------------------------------------
# 9. Explanation regression — no "availability" or "blocked time"
# ---------------------------------------------------------------------------


_FORBIDDEN_PHRASES = ("availability", "blocked time")


def _assert_no_forbidden_phrases(text: str) -> None:
    lower = text.lower()
    for forbidden in _FORBIDDEN_PHRASES:
        assert forbidden not in lower, (
            f"explanation must not contain {forbidden!r} (case-insensitive); "
            f"got: {text!r}"
        )


def test_slot_explanation_omits_availability_and_blocked_time(session):
    slots = find_available_slots(
        duration_minutes=60,
        start_date=MONDAY,
        end_date=MONDAY,
        max_results=3,
        session=session,
    )
    assert slots, "expected at least one slot"
    for s in slots:
        _assert_no_forbidden_phrases(s.explanation)


def test_saved_replacement_explanation_omits_availability_and_blocked_time(
    session,
):
    cal = make_calendar(session)
    ev = make_event(
        session, cal.id,
        start=datetime(2026, 4, 20, 10, 0),
        end=datetime(2026, 4, 20, 11, 0),
    )

    result = find_replacement_slots(
        event_id=ev.id,
        search_start=datetime(2026, 4, 20, 0, 0),
        search_end=datetime(2026, 4, 20, 23, 59),
        max_results=3,
        session=session,
    )

    assert result["options"], "expected at least one option"
    for o in result["options"]:
        _assert_no_forbidden_phrases(o["explanation"])


def test_proposed_replacement_explanation_omits_availability_and_blocked_time(
    session,
):
    result = find_replacement_slots_for_proposed(
        title="Proposed",
        start_time=datetime(2026, 4, 20, 14, 0),
        end_time=datetime(2026, 4, 20, 15, 0),
        search_start=datetime(2026, 4, 20, 0, 0),
        search_end=datetime(2026, 4, 20, 23, 59),
        max_results=3,
        session=session,
    )

    assert result["options"], "expected at least one option"
    for o in result["options"]:
        _assert_no_forbidden_phrases(o["explanation"])


# ---------------------------------------------------------------------------
# Sanity — Daily Rhythm defaults match the product spec
# ---------------------------------------------------------------------------


def test_daily_rhythm_defaults_match_product_spec():
    assert DEFAULT_AWAKE_START == time(7, 0)
    assert DEFAULT_AWAKE_END == time(23, 0)
    assert DEFAULT_SUGGESTIONS_START == time(8, 0)
    assert DEFAULT_SUGGESTIONS_END == time(21, 0)
