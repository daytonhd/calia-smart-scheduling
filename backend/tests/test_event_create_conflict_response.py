"""Regression tests proving event create/update produce a JSON-serializable
409 conflict payload (not a 500 from a non-serializable datetime).

Background: ConflictDetail.model_dump() previously returned dicts containing
raw datetime objects inside HTTPException.detail. FastAPI routes detail
through json.dumps(), which cannot serialize datetime, so the actual HTTP
response was 500 with a TypeError instead of the intended 409 conflict
payload. The fix is model_dump(mode="json") which produces ISO strings.

These tests invoke the route handlers directly (no TestClient/httpx
dependency) and verify two things:
  1. HTTPException(status_code=409, ...) is raised — not a 500 due to
     serialization failure.
  2. json.dumps(exc.detail) succeeds and produces ISO-string datetimes —
     reproducing exactly what FastAPI's response renderer does.
"""

import json
from datetime import datetime

import pytest
from fastapi import HTTPException

from app.routers.events import create_event, update_event
from app.schemas.event import EventCreate, EventUpdate

from .factories import make_calendar, make_event


def test_create_event_outside_daily_rhythm_now_succeeds(session):
    """Events outside Daily Rhythm hours are no longer rejected — a
    valid late-night create with no overlap should succeed."""
    cal = make_calendar(session)

    body = EventCreate(
        calendar_id=cal.id,
        title="Late night",
        start_time=datetime(2026, 4, 20, 22, 0),
        end_time=datetime(2026, 4, 20, 23, 0),
    )

    event = create_event(body, session)

    assert event.id is not None
    assert event.start_time == datetime(2026, 4, 20, 22, 0)
    assert event.end_time == datetime(2026, 4, 20, 23, 0)


def test_create_event_overlap_returns_serializable_409(session):
    cal = make_calendar(session)
    existing = make_event(
        session,
        cal.id,
        start=datetime(2026, 4, 20, 10, 0),
        end=datetime(2026, 4, 20, 11, 0),
        title="Existing",
    )

    body = EventCreate(
        calendar_id=cal.id,
        title="Overlap",
        start_time=datetime(2026, 4, 20, 10, 30),
        end_time=datetime(2026, 4, 20, 11, 30),
    )

    with pytest.raises(HTTPException) as exc_info:
        create_event(body, session)

    assert exc_info.value.status_code == 409
    rendered = json.dumps(exc_info.value.detail)
    payload = json.loads(rendered)

    overlap = next(
        c for c in payload["conflicts"] if c["reason_code"] == "EVENT_OVERLAP"
    )
    assert isinstance(overlap["start_time"], str)
    assert isinstance(overlap["end_time"], str)
    assert overlap["start_time"] == "2026-04-20T10:00:00"
    assert overlap["end_time"] == "2026-04-20T11:00:00"
    assert overlap["related_event_id"] == existing.id


def test_update_event_into_conflict_returns_serializable_409(session):
    cal = make_calendar(session)
    blocker = make_event(
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

    # Try to move "Moveable" on top of "Blocker".
    body = EventUpdate(
        start_time=datetime(2026, 4, 20, 14, 30),
        end_time=datetime(2026, 4, 20, 15, 30),
    )

    with pytest.raises(HTTPException) as exc_info:
        update_event(moveable.id, body, session)

    assert exc_info.value.status_code == 409
    rendered = json.dumps(exc_info.value.detail)
    payload = json.loads(rendered)

    overlap = next(
        c for c in payload["conflicts"] if c["reason_code"] == "EVENT_OVERLAP"
    )
    assert overlap["related_event_id"] == blocker.id
    assert isinstance(overlap["start_time"], str)
    assert isinstance(overlap["end_time"], str)
    assert overlap["start_time"] == "2026-04-20T14:00:00"
    assert overlap["end_time"] == "2026-04-20T15:00:00"
