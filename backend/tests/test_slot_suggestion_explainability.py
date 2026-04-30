"""Tests for explainable SlotSuggestion responses."""

from datetime import date, time

from app.services.conflict_detection import find_available_slots

from .factories import make_availability

MONDAY = date(2026, 4, 20)


def test_each_slot_has_reason_and_explanation(session):
    slots = find_available_slots(
        duration_minutes=60,
        start_date=MONDAY,
        end_date=MONDAY,
        max_results=3,
        session=session,
    )

    assert slots, "expected at least one slot"
    for s in slots:
        assert s.reason_code == "EARLIEST_VALID_SLOT"
        assert s.explanation
        # Explanation no longer mentions "availability windows" — it
        # references daily suggestion hours and the things slots avoid.
        assert "suggestion" in s.explanation.lower()
        assert "events" in s.explanation.lower()
        assert "availability window" not in s.explanation.lower()


def test_explanation_is_deterministic(session):
    make_availability(session, weekday=0, start=time(9, 0), end=time(10, 0))

    a = find_available_slots(
        duration_minutes=60,
        start_date=MONDAY,
        end_date=MONDAY,
        max_results=10,
        session=session,
    )
    b = find_available_slots(
        duration_minutes=60,
        start_date=MONDAY,
        end_date=MONDAY,
        max_results=10,
        session=session,
    )
    assert [(s.start_time, s.end_time, s.reason_code, s.explanation) for s in a] == \
           [(s.start_time, s.end_time, s.reason_code, s.explanation) for s in b]
