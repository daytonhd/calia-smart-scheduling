"""Overlap override — explicit allow_conflicts bypass for event create/update.

By default POST/PATCH /events reject overlapping events with a 409. A client
may opt into saving an overlapping event by sending allow_conflicts=True. The
override only bypasses EVENT_OVERLAP conflicts — invalid time ranges still
fail, and allow_conflicts is never persisted on the Event or in EventRead.

These tests invoke the route handlers directly (matching
test_event_create_conflict_response.py) — no TestClient dependency.

Anchor date: Monday 2026-04-20 (weekday = 0).
"""

from datetime import datetime

import pytest
from fastapi import HTTPException
from pydantic import ValidationError

from app.routers.events import create_event, update_event
from app.schemas.event import EventCreate, EventRead, EventUpdate

from .factories import make_calendar, make_event


def _overlapping_create_body(
    calendar_id: int, allow_conflicts: bool = False
) -> EventCreate:
    """An EventCreate that overlaps the 10:00-11:00 event the tests set up."""
    return EventCreate(
        calendar_id=calendar_id,
        title="Overlapping",
        start_time=datetime(2026, 4, 20, 10, 30),
        end_time=datetime(2026, 4, 20, 11, 30),
        allow_conflicts=allow_conflicts,
    )


def test_create_overlap_rejected_by_default(session):
    """POST /events rejects an overlapping event with 409 when allow_conflicts is omitted."""
    cal = make_calendar(session)
    make_event(
        session,
        cal.id,
        start=datetime(2026, 4, 20, 10, 0),
        end=datetime(2026, 4, 20, 11, 0),
        title="Existing",
    )

    body = _overlapping_create_body(cal.id)  # allow_conflicts defaults to False

    with pytest.raises(HTTPException) as exc_info:
        create_event(body, session)
    assert exc_info.value.status_code == 409


def test_create_overlap_allowed_with_allow_conflicts(session):
    """POST /events saves an overlapping event when allow_conflicts is True."""
    cal = make_calendar(session)
    existing = make_event(
        session,
        cal.id,
        start=datetime(2026, 4, 20, 10, 0),
        end=datetime(2026, 4, 20, 11, 0),
        title="Existing",
    )

    body = _overlapping_create_body(cal.id, allow_conflicts=True)
    event = create_event(body, session)

    assert event.id is not None
    assert event.id != existing.id
    assert event.start_time == datetime(2026, 4, 20, 10, 30)
    assert event.end_time == datetime(2026, 4, 20, 11, 30)


def test_patch_overlap_rejected_by_default(session):
    """PATCH /events rejects moving an event onto another with 409 by default."""
    cal = make_calendar(session)
    make_event(
        session,
        cal.id,
        start=datetime(2026, 4, 20, 14, 0),
        end=datetime(2026, 4, 20, 15, 0),
        title="Blocker",
    )
    moveable = make_event(
        session,
        cal.id,
        start=datetime(2026, 4, 20, 10, 0),
        end=datetime(2026, 4, 20, 11, 0),
        title="Moveable",
    )

    body = EventUpdate(
        start_time=datetime(2026, 4, 20, 14, 30),
        end_time=datetime(2026, 4, 20, 15, 30),
    )

    with pytest.raises(HTTPException) as exc_info:
        update_event(moveable.id, body, session)
    assert exc_info.value.status_code == 409


def test_patch_overlap_allowed_with_allow_conflicts(session):
    """PATCH /events moves an event onto another when allow_conflicts is True."""
    cal = make_calendar(session)
    make_event(
        session,
        cal.id,
        start=datetime(2026, 4, 20, 14, 0),
        end=datetime(2026, 4, 20, 15, 0),
        title="Blocker",
    )
    moveable = make_event(
        session,
        cal.id,
        start=datetime(2026, 4, 20, 10, 0),
        end=datetime(2026, 4, 20, 11, 0),
        title="Moveable",
    )

    body = EventUpdate(
        start_time=datetime(2026, 4, 20, 14, 30),
        end_time=datetime(2026, 4, 20, 15, 30),
        allow_conflicts=True,
    )

    event = update_event(moveable.id, body, session)

    assert event.id == moveable.id
    assert event.start_time == datetime(2026, 4, 20, 14, 30)
    assert event.end_time == datetime(2026, 4, 20, 15, 30)


def test_invalid_time_range_still_fails_with_allow_conflicts(session):
    """allow_conflicts never bypasses an invalid time range — the schema rejects it."""
    cal = make_calendar(session)

    with pytest.raises(ValidationError):
        EventCreate(
            calendar_id=cal.id,
            title="Backwards",
            start_time=datetime(2026, 4, 20, 12, 0),
            end_time=datetime(2026, 4, 20, 11, 0),
            allow_conflicts=True,
        )


def test_allow_conflicts_is_not_persisted(session):
    """allow_conflicts is request-only — never stored on the Event or in EventRead."""
    cal = make_calendar(session)
    make_event(
        session,
        cal.id,
        start=datetime(2026, 4, 20, 10, 0),
        end=datetime(2026, 4, 20, 11, 0),
        title="Existing",
    )

    body = _overlapping_create_body(cal.id, allow_conflicts=True)
    event = create_event(body, session)

    # Not an attribute on the saved ORM object...
    assert not hasattr(event, "allow_conflicts")
    # ...and not a field in the response schema.
    assert "allow_conflicts" not in EventRead.model_fields
