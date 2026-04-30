"""Batch 2 contract tests: events outside AvailabilityWindow rows or
outside Daily Rhythm hours are allowed if the range is valid and there
is no overlap. POST /schedule/check-conflict no longer returns
OUTSIDE_AVAILABILITY.

These tests pin the new conflict semantics introduced in Batch 2 so future
changes can't silently regress.
"""

from datetime import datetime, time

import pytest
from fastapi import HTTPException
from pydantic import ValidationError

from app.routers.events import create_event, update_event
from app.routers.schedule import check_conflict
from app.schemas.event import EventCreate, EventUpdate
from app.schemas.schedule import ConflictCheckRequest

from .factories import make_availability, make_calendar, make_event


# ---------------------------------------------------------------------------
# POST /events outside availability is allowed
# ---------------------------------------------------------------------------


def test_post_events_allows_outside_availability_window_rows(session):
    """An event placed outside the only AvailabilityWindow row succeeds."""
    cal = make_calendar(session)
    make_availability(session, weekday=0, start=time(9, 0), end=time(17, 0))

    body = EventCreate(
        calendar_id=cal.id,
        title="After hours",
        start_time=datetime(2026, 4, 20, 22, 0),
        end_time=datetime(2026, 4, 20, 23, 0),
    )

    event = create_event(body, session)

    assert event.id is not None
    assert event.start_time == datetime(2026, 4, 20, 22, 0)
    assert event.end_time == datetime(2026, 4, 20, 23, 0)


def test_post_events_allows_when_no_availability_rows_exist(session):
    """No AvailabilityWindow rows at all → event create still succeeds."""
    cal = make_calendar(session)

    body = EventCreate(
        calendar_id=cal.id,
        title="Anywhere",
        start_time=datetime(2026, 4, 20, 6, 0),  # outside Daily Rhythm too
        end_time=datetime(2026, 4, 20, 7, 0),
    )

    event = create_event(body, session)
    assert event.id is not None


# ---------------------------------------------------------------------------
# PATCH /events outside availability is allowed
# ---------------------------------------------------------------------------


def test_patch_events_allows_move_outside_availability_window_rows(session):
    """Moving an event outside availability rows is allowed when no overlap."""
    cal = make_calendar(session)
    make_availability(session, weekday=0, start=time(9, 0), end=time(17, 0))
    ev = make_event(
        session, cal.id,
        start=datetime(2026, 4, 20, 10, 0),
        end=datetime(2026, 4, 20, 11, 0),
    )

    body = EventUpdate(
        start_time=datetime(2026, 4, 20, 22, 0),
        end_time=datetime(2026, 4, 20, 23, 0),
    )

    updated = update_event(ev.id, body, session)
    assert updated.start_time == datetime(2026, 4, 20, 22, 0)
    assert updated.end_time == datetime(2026, 4, 20, 23, 0)


# ---------------------------------------------------------------------------
# POST /schedule/check-conflict — OUTSIDE_AVAILABILITY is not returned
# ---------------------------------------------------------------------------


def test_check_conflict_does_not_return_outside_availability(session):
    """Outside-availability placements produce no conflicts at the router."""
    cal = make_calendar(session)
    make_availability(session, weekday=0, start=time(9, 0), end=time(17, 0))

    body = ConflictCheckRequest(
        calendar_id=cal.id,
        start_time=datetime(2026, 4, 20, 22, 0),
        end_time=datetime(2026, 4, 20, 23, 0),
    )

    response = check_conflict(body, session)

    assert response.has_conflicts is False
    assert response.conflicts == []
    codes = [c.reason_code for c in response.conflicts]
    assert "OUTSIDE_AVAILABILITY" not in codes


def test_check_conflict_no_availability_rows_returns_clean(session):
    """With no AvailabilityWindow rows at all, the placement is clean."""
    cal = make_calendar(session)

    body = ConflictCheckRequest(
        calendar_id=cal.id,
        start_time=datetime(2026, 4, 23, 10, 0),
        end_time=datetime(2026, 4, 23, 11, 0),
    )

    response = check_conflict(body, session)
    assert response.has_conflicts is False
    assert response.conflicts == []


# ---------------------------------------------------------------------------
# Active conflicts and validation still fire
# ---------------------------------------------------------------------------


def test_invalid_time_range_still_fails_at_schema():
    """start_time >= end_time is still rejected at the schema layer."""
    with pytest.raises(ValidationError):
        EventCreate(
            calendar_id=1,
            title="Bad",
            start_time=datetime(2026, 4, 20, 11, 0),
            end_time=datetime(2026, 4, 20, 11, 0),  # equal — invalid
        )


def test_event_overlap_still_returns_409_on_create(session):
    """Creating an event that overlaps an existing one still returns 409."""
    cal = make_calendar(session)
    make_event(
        session, cal.id,
        start=datetime(2026, 4, 20, 10, 0),
        end=datetime(2026, 4, 20, 11, 0),
    )

    body = EventCreate(
        calendar_id=cal.id,
        title="Overlap",
        start_time=datetime(2026, 4, 20, 10, 30),
        end_time=datetime(2026, 4, 20, 11, 30),
    )

    with pytest.raises(HTTPException) as exc:
        create_event(body, session)
    assert exc.value.status_code == 409
    codes = [c["reason_code"] for c in exc.value.detail["conflicts"]]
    assert "EVENT_OVERLAP" in codes


def test_touching_event_boundary_is_allowed_on_create(session):
    """A new event whose start equals an existing event's end is allowed."""
    cal = make_calendar(session)
    make_event(
        session, cal.id,
        start=datetime(2026, 4, 20, 10, 0),
        end=datetime(2026, 4, 20, 11, 0),
    )

    body = EventCreate(
        calendar_id=cal.id,
        title="Touching",
        start_time=datetime(2026, 4, 20, 11, 0),
        end_time=datetime(2026, 4, 20, 12, 0),
    )

    event = create_event(body, session)
    assert event.id is not None
