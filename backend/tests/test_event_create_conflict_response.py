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
from datetime import datetime, time

import pytest
from fastapi import HTTPException

from app.routers.events import create_event, update_event
from app.schemas.event import EventCreate, EventUpdate

from .factories import make_availability, make_calendar, make_event


def test_create_event_outside_availability_returns_serializable_409(session):
    """Conflicting create raises 409 whose detail is JSON-serializable."""
    cal = make_calendar(session)
    # Monday 9:00-17:00 availability so a 22:00 slot falls outside it.
    make_availability(session, weekday=0, start=time(9, 0), end=time(17, 0))

    body = EventCreate(
        calendar_id=cal.id,
        title="Late night",
        start_time=datetime(2026, 4, 20, 22, 0),
        end_time=datetime(2026, 4, 20, 23, 0),
    )

    with pytest.raises(HTTPException) as exc_info:
        create_event(body, session)

    assert exc_info.value.status_code == 409

    # The bug surfaced as TypeError when FastAPI tried to json.dumps the
    # detail. Reproduce that here — it must not raise.
    rendered = json.dumps(exc_info.value.detail)
    payload = json.loads(rendered)

    conflicts = payload["conflicts"]
    assert len(conflicts) >= 1

    availability = next(
        c for c in conflicts if c["reason_code"] == "OUTSIDE_AVAILABILITY"
    )
    assert isinstance(availability["start_time"], str)
    assert isinstance(availability["end_time"], str)
    assert availability["start_time"] == "2026-04-20T22:00:00"
    assert availability["end_time"] == "2026-04-20T23:00:00"
    assert availability["conflict_type"] == "availability"


def test_create_event_overlap_returns_serializable_409(session):
    cal = make_calendar(session)
    make_availability(session, weekday=0, start=time(9, 0), end=time(17, 0))
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
    make_availability(session, weekday=0, start=time(9, 0), end=time(17, 0))
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
