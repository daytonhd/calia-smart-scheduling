"""Tests for Daily Rhythm persistence — the GET/PATCH endpoint handlers and
the effect of persisted suggestion hours on scheduling.

These tests invoke the route handlers directly (no TestClient/httpx
dependency), matching the rest of the suite. Schema-level validation is
exercised by constructing DailyRhythmUpdate — exactly what FastAPI does
before a request ever reaches the handler.
"""

from datetime import date, datetime, time

import pytest
from pydantic import ValidationError
from sqlmodel import select

from app.models.daily_rhythm import DailyRhythm
from app.routers.daily_rhythm import get_daily_rhythm, update_daily_rhythm
from app.schemas.daily_rhythm import DailyRhythmUpdate
from app.services.conflict_detection import find_available_slots

MONDAY = date(2026, 4, 20)


def test_get_returns_defaults_when_no_row(session):
    """GET with no persisted row returns the system defaults, unpersisted."""
    result = get_daily_rhythm(session)

    assert result.awake_start_time == "07:00"
    assert result.awake_end_time == "23:00"
    assert result.suggestions_start_time == "08:00"
    assert result.suggestions_end_time == "21:00"

    # Defaults must not have been written to the table.
    assert session.exec(select(DailyRhythm)).all() == []


def test_patch_saves_valid_values(session):
    body = DailyRhythmUpdate(
        awake_start_time="06:30",
        awake_end_time="22:30",
        suggestions_start_time="09:00",
        suggestions_end_time="20:00",
    )

    result = update_daily_rhythm(body, session)

    assert result.awake_start_time == "06:30"
    assert result.awake_end_time == "22:30"
    assert result.suggestions_start_time == "09:00"
    assert result.suggestions_end_time == "20:00"


def test_get_returns_saved_values(session):
    update_daily_rhythm(
        DailyRhythmUpdate(
            awake_start_time="05:00",
            awake_end_time="21:00",
            suggestions_start_time="07:30",
            suggestions_end_time="19:30",
        ),
        session,
    )

    result = get_daily_rhythm(session)

    assert result.awake_start_time == "05:00"
    assert result.awake_end_time == "21:00"
    assert result.suggestions_start_time == "07:30"
    assert result.suggestions_end_time == "19:30"


def test_patch_updates_single_row_does_not_duplicate(session):
    """The MVP keeps one active row — a second PATCH updates, not inserts."""
    update_daily_rhythm(
        DailyRhythmUpdate(
            awake_start_time="07:00",
            awake_end_time="23:00",
            suggestions_start_time="08:00",
            suggestions_end_time="21:00",
        ),
        session,
    )
    update_daily_rhythm(
        DailyRhythmUpdate(
            awake_start_time="08:00",
            awake_end_time="22:00",
            suggestions_start_time="09:00",
            suggestions_end_time="18:00",
        ),
        session,
    )

    rows = session.exec(select(DailyRhythm)).all()
    assert len(rows) == 1
    assert get_daily_rhythm(session).suggestions_end_time == "18:00"


def test_patch_rejects_invalid_awake_range():
    """awake_start_time must be before awake_end_time."""
    with pytest.raises(ValidationError):
        DailyRhythmUpdate(
            awake_start_time="22:00",
            awake_end_time="07:00",
            suggestions_start_time="08:00",
            suggestions_end_time="21:00",
        )


def test_patch_rejects_invalid_suggestions_range():
    """suggestions_start_time must be before suggestions_end_time."""
    with pytest.raises(ValidationError):
        DailyRhythmUpdate(
            awake_start_time="07:00",
            awake_end_time="23:00",
            suggestions_start_time="20:00",
            suggestions_end_time="09:00",
        )


def test_patch_rejects_suggestions_outside_awake_hours():
    """Suggestion hours must fit inside awake hours on both ends."""
    # Suggestions start before awake start.
    with pytest.raises(ValidationError):
        DailyRhythmUpdate(
            awake_start_time="08:00",
            awake_end_time="22:00",
            suggestions_start_time="07:00",
            suggestions_end_time="21:00",
        )
    # Suggestions end after awake end.
    with pytest.raises(ValidationError):
        DailyRhythmUpdate(
            awake_start_time="08:00",
            awake_end_time="22:00",
            suggestions_start_time="09:00",
            suggestions_end_time="23:00",
        )


def test_scheduling_works_with_no_rhythm_row(session):
    """With no persisted row, scheduling falls back to the default
    08:00–21:00 suggestion window and still produces slots."""
    slots = find_available_slots(
        duration_minutes=60,
        start_date=MONDAY,
        end_date=MONDAY,
        max_results=50,
        session=session,
    )

    assert slots, "expected slots in the default suggestion window"
    assert slots[0].start_time == datetime.combine(MONDAY, time(8, 0))
    for s in slots:
        assert s.start_time >= datetime.combine(MONDAY, time(8, 0))
        assert s.end_time <= datetime.combine(MONDAY, time(21, 0))


def test_scheduling_uses_saved_suggestion_hours(session):
    """After saving a narrower suggestion window, slot suggestions are
    bounded by the saved hours, not the defaults."""
    update_daily_rhythm(
        DailyRhythmUpdate(
            awake_start_time="07:00",
            awake_end_time="23:00",
            suggestions_start_time="10:00",
            suggestions_end_time="14:00",
        ),
        session,
    )

    slots = find_available_slots(
        duration_minutes=60,
        start_date=MONDAY,
        end_date=MONDAY,
        max_results=50,
        session=session,
    )

    assert slots, "expected slots in the saved suggestion window"
    assert slots[0].start_time == datetime.combine(MONDAY, time(10, 0))
    for s in slots:
        assert s.start_time >= datetime.combine(MONDAY, time(10, 0))
        assert s.end_time <= datetime.combine(MONDAY, time(14, 0))
