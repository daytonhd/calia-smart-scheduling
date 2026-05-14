"""Regression: event `category` is optional on create.

Category is descriptive only — a user must be able to create a normal event
without assigning one. These tests pin that the create flow accepts a
missing category, an explicit null category (as the API would receive it
from a JSON body), and still stores a provided category unchanged.

Tests invoke the route handler directly (matching
test_event_create_conflict_response.py) — no TestClient dependency.

Anchor date: Monday 2026-04-20 (weekday = 0).
"""

from datetime import datetime

from app.routers.events import create_event
from app.schemas.event import EventCreate

from .factories import make_calendar

START = datetime(2026, 4, 20, 10, 0)
END = datetime(2026, 4, 20, 11, 0)


def test_create_event_succeeds_with_category_omitted(session):
    """Omitting category entirely is allowed — the event is created with category None."""
    cal = make_calendar(session)

    body = EventCreate(
        calendar_id=cal.id,
        title="No category",
        start_time=START,
        end_time=END,
    )

    event = create_event(body, session)

    assert event.id is not None
    assert event.category is None


def test_create_event_succeeds_with_category_null(session):
    """An explicit null category (as FastAPI parses from a JSON body) is allowed."""
    cal = make_calendar(session)

    # model_validate on a dict reproduces what the API does with a JSON body
    # that contains "category": null.
    body = EventCreate.model_validate({
        "calendar_id": cal.id,
        "title": "Null category",
        "category": None,
        "start_time": START.isoformat(),
        "end_time": END.isoformat(),
    })

    event = create_event(body, session)

    assert event.id is not None
    assert event.category is None


def test_create_event_still_stores_provided_category(session):
    """When a category is provided, it is stored unchanged (existing behavior)."""
    cal = make_calendar(session)

    body = EventCreate(
        calendar_id=cal.id,
        title="With category",
        category="Study",
        start_time=START,
        end_time=END,
    )

    event = create_event(body, session)

    assert event.id is not None
    assert event.category == "Study"
