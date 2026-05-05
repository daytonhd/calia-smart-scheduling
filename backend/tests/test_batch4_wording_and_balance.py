"""Batch 4 contract tests: user-facing wording and Schedule Balance bounds.

Pins:
  1. Slot suggestion explanations reference daily suggestion hours / existing
     events / occupied schedule items, and never mention "availability".
  2. Replacement option explanations (saved + proposed) reference daily
     suggestion hours / existing events / occupied schedule items, and never
     mention "availability".
  3. Weekly Schedule Balance (compute_weekly_triage) bounds free capacity by
     Daily Rhythm suggestion hours (8:00-21:00 = 780 min/day), works with
     zero AvailabilityWindow rows, and subtracts events from that capacity.
"""

from datetime import date, datetime, time

from app.services.conflict_detection import find_available_slots
from app.services.daily_rhythm import (
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

# Allowed user-facing phrases we expect explanations to lean on.
_ALLOWED_TOKENS = (
    "daily suggestion",
    "suggestion hours",
    "existing events",
    "occupied schedule",
)

# Phrases we must NOT find in user-facing explanation strings.
_FORBIDDEN_TOKENS = (
    "availability",
    "availability window",
)


def _assert_clean_wording(text: str) -> None:
    lower = text.lower()
    for forbidden in _FORBIDDEN_TOKENS:
        assert forbidden not in lower, (
            f"explanation should not mention {forbidden!r}, got: {text!r}"
        )
    assert any(token in lower for token in _ALLOWED_TOKENS), (
        f"explanation should reference daily suggestion hours / existing "
        f"events / occupied schedule items, got: {text!r}"
    )


# ---------------------------------------------------------------------------
# 1. Slot suggestion explanations
# ---------------------------------------------------------------------------


def test_slot_suggestion_explanation_uses_clean_wording(session):
    slots = find_available_slots(
        duration_minutes=60,
        start_date=MONDAY,
        end_date=MONDAY,
        max_results=3,
        session=session,
    )
    assert slots, "expected at least one slot"
    for s in slots:
        _assert_clean_wording(s.explanation)


# ---------------------------------------------------------------------------
# 2. Replacement option explanations (saved + proposed)
# ---------------------------------------------------------------------------


def test_saved_replacement_explanation_uses_clean_wording(session):
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
        _assert_clean_wording(o["explanation"])


def test_proposed_replacement_explanation_uses_clean_wording(session):
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
        _assert_clean_wording(o["explanation"])


# ---------------------------------------------------------------------------
# 3. Schedule Balance / free-capacity bounds use Daily Rhythm hours
# ---------------------------------------------------------------------------


def test_balance_free_minutes_match_daily_rhythm_with_no_availability_rows(
    session,
):
    """With zero AvailabilityWindow rows and zero events, every day's free
    capacity equals the Daily Rhythm suggestion-hour duration."""
    rhythm_minutes = (
        datetime.combine(MONDAY, DEFAULT_SUGGESTIONS_END)
        - datetime.combine(MONDAY, DEFAULT_SUGGESTIONS_START)
    ).total_seconds() // 60
    rhythm_minutes = int(rhythm_minutes)
    assert rhythm_minutes == 780  # sanity check: 8:00-21:00

    triage = compute_weekly_triage(session, week_start=MONDAY)

    assert len(triage["days"]) == 7
    for day in triage["days"]:
        assert day["free_minutes"] == rhythm_minutes
        assert day["longest_free_window_minutes"] == rhythm_minutes


def test_balance_subtracts_events_from_daily_rhythm_capacity(session):
    """A single 60-min event inside the Daily Rhythm window reduces free
    capacity by exactly 60 minutes (no AvailabilityWindow rows present)."""
    cal = make_calendar(session)
    make_event(
        session, cal.id,
        start=datetime(2026, 4, 20, 10, 0),
        end=datetime(2026, 4, 20, 11, 0),
    )

    triage = compute_weekly_triage(session, week_start=MONDAY)
    monday = next(d for d in triage["days"] if d["date"] == MONDAY)

    # 780 (rhythm) − 60 (event) = 720 free.
    assert monday["scheduled_minutes"] == 60
    assert monday["free_minutes"] == 720


def test_balance_event_outside_rhythm_does_not_change_free_capacity(session):
    """Events placed outside Daily Rhythm hours (e.g. 22:00-23:00) do not
    consume free capacity — Free Capacity is bounded by Daily Rhythm only."""
    cal = make_calendar(session)
    # 22:00-23:00 is outside the 8:00-21:00 suggestion window.
    make_event(
        session, cal.id,
        start=datetime(2026, 4, 20, 22, 0),
        end=datetime(2026, 4, 20, 23, 0),
    )

    triage = compute_weekly_triage(session, week_start=MONDAY)
    monday = next(d for d in triage["days"] if d["date"] == MONDAY)

    # Event minutes still attributed to the day total (busy), but free
    # capacity inside the Daily Rhythm window is untouched.
    assert monday["scheduled_minutes"] == 60
    assert monday["free_minutes"] == 780
    assert monday["longest_free_window_minutes"] == 780


def test_balance_overload_message_uses_neutral_wording(session):
    """Overloaded-day warnings should report busy hours."""
    cal = make_calendar(session)
    make_event(
        session, cal.id,
        start=datetime(2026, 4, 20, 9, 0),
        end=datetime(2026, 4, 20, 15, 0),  # 6h scheduled → overload
    )

    triage = compute_weekly_triage(session, week_start=MONDAY)
    monday = next(d for d in triage["days"] if d["date"] == MONDAY)

    overloaded = [w for w in monday["warnings"] if w["reason_code"] == "OVERLOADED_DAY"]
    assert len(overloaded) == 1
    # Must still report the busy hour count.
    assert "6 hours" in overloaded[0]["message"]
