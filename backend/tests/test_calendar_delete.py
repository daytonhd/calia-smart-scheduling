"""Tests for DELETE /calendars/{id} guarding against orphaned events."""

from datetime import datetime

import pytest
from fastapi import HTTPException
from sqlmodel import select

from app.models.calendar import Calendar
from app.routers.calendars import delete_calendar

from .factories import make_calendar, make_event


def test_delete_missing_calendar_returns_404(session):
    with pytest.raises(HTTPException) as exc:
        delete_calendar(calendar_id=999, session=session)

    assert exc.value.status_code == 404
    assert exc.value.detail == "Calendar not found"


def test_delete_calendar_with_no_events_succeeds(session):
    cal = make_calendar(session)

    delete_calendar(calendar_id=cal.id, session=session)

    assert session.get(Calendar, cal.id) is None


def test_delete_calendar_with_events_returns_409_and_preserves_calendar(session):
    cal = make_calendar(session)
    make_event(
        session,
        cal.id,
        start=datetime(2026, 4, 20, 10, 0),
        end=datetime(2026, 4, 20, 11, 0),
    )

    with pytest.raises(HTTPException) as exc:
        delete_calendar(calendar_id=cal.id, session=session)

    assert exc.value.status_code == 409
    assert exc.value.detail == (
        "Cannot delete calendar because it has existing events. "
        "Delete or move those events first."
    )
    # Calendar must still exist after the rejected delete.
    assert session.get(Calendar, cal.id) is not None
