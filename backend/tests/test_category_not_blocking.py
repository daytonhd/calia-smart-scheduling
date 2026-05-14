"""Category is descriptive only — it must never affect scheduling behavior.

Event categories (Study, Gym, Personal, Focus block, Appointment, Class,
Commute, Unavailable, ...) are labels for display, filtering, and analytics.
They do NOT control whether a time slot is treated as free or occupied.
Every saved Event blocks slot suggestions, replacement options, and conflict
checks regardless of its category value.

Anchor date: Monday 2026-04-20 (weekday = 0).
"""

from datetime import date, datetime

from app.models.event import Event
from app.services.conflict_detection import (
    check_all_conflicts,
    find_available_slots,
)
from app.services.rescheduling import find_replacement_slots

from .factories import make_calendar, make_event

MONDAY = date(2026, 4, 20)


def test_study_event_blocks_slot_suggestions(session):
    """An event categorized 'Study' occupies its time like any other event."""
    cal = make_calendar(session)
    make_event(
        session,
        cal.id,
        start=datetime(2026, 4, 20, 10, 0),
        end=datetime(2026, 4, 20, 11, 0),
        category="Study",
    )

    slots = find_available_slots(
        duration_minutes=60,
        start_date=MONDAY,
        end_date=MONDAY,
        max_results=100,
        session=session,
    )

    assert slots, "expected slot suggestions to be generated"
    for s in slots:
        assert not (
            s.start_time < datetime(2026, 4, 20, 11, 0)
            and s.end_time > datetime(2026, 4, 20, 10, 0)
        ), "a 'Study' event must block overlapping slot suggestions"


def test_gym_event_blocks_slot_suggestions(session):
    """An event categorized 'Gym' occupies its time like any other event."""
    cal = make_calendar(session)
    make_event(
        session,
        cal.id,
        start=datetime(2026, 4, 20, 14, 0),
        end=datetime(2026, 4, 20, 15, 0),
        category="Gym",
    )

    slots = find_available_slots(
        duration_minutes=60,
        start_date=MONDAY,
        end_date=MONDAY,
        max_results=100,
        session=session,
    )

    assert slots, "expected slot suggestions to be generated"
    for s in slots:
        assert not (
            s.start_time < datetime(2026, 4, 20, 15, 0)
            and s.end_time > datetime(2026, 4, 20, 14, 0)
        ), "a 'Gym' event must block overlapping slot suggestions"


def test_personal_event_blocks_replacement_options(session):
    """A 'Personal' event is avoided when ranking replacement options."""
    cal = make_calendar(session)
    # The event we want replacement options for.
    target = make_event(
        session,
        cal.id,
        start=datetime(2026, 4, 20, 9, 0),
        end=datetime(2026, 4, 20, 10, 0),
        title="Target",
    )
    # A 'Personal' event occupying 11:00-12:00 — replacement options must avoid it.
    make_event(
        session,
        cal.id,
        start=datetime(2026, 4, 20, 11, 0),
        end=datetime(2026, 4, 20, 12, 0),
        title="Personal block",
        category="Personal",
    )

    result = find_replacement_slots(
        event_id=target.id,
        search_start=datetime(2026, 4, 20, 8, 0),
        search_end=datetime(2026, 4, 20, 21, 0),
        max_results=50,
        session=session,
    )

    options = result["options"]
    assert options, "expected at least one replacement option"
    for opt in options:
        assert not (
            opt["start_time"] < datetime(2026, 4, 20, 12, 0)
            and opt["end_time"] > datetime(2026, 4, 20, 11, 0)
        ), "a 'Personal' event must block overlapping replacement options"


def test_conflict_detection_does_not_depend_on_category(session):
    """Overlap is flagged identically no matter the existing event's category."""
    cal = make_calendar(session)
    placement = dict(
        start=datetime(2026, 4, 20, 13, 0),
        end=datetime(2026, 4, 20, 14, 0),
    )
    probe = dict(
        start_time=datetime(2026, 4, 20, 13, 30),
        end_time=datetime(2026, 4, 20, 14, 30),
    )

    # "Unavailable" sounds the most blocking, but category carries no weight.
    categorized = make_event(
        session, cal.id, title="Unavailable block",
        category="Unavailable", **placement,
    )
    with_category = check_all_conflicts(session=session, **probe)

    session.delete(categorized)
    session.commit()

    # Same placement, no category at all → must behave identically.
    make_event(session, cal.id, title="Plain event", category=None, **placement)
    without_category = check_all_conflicts(session=session, **probe)

    assert [c.reason_code for c in with_category] == ["EVENT_OVERLAP"]
    assert [c.reason_code for c in without_category] == ["EVENT_OVERLAP"]


def test_category_is_stored_and_returned(session):
    """Category is persisted and round-trips unchanged — it stays a normal field."""
    cal = make_calendar(session)
    ev = make_event(
        session,
        cal.id,
        start=datetime(2026, 4, 20, 16, 0),
        end=datetime(2026, 4, 20, 17, 0),
        category="Focus block",
    )

    fetched = session.get(Event, ev.id)
    assert fetched is not None
    assert fetched.category == "Focus block"
