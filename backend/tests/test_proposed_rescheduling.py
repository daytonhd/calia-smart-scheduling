"""Tests for find_replacement_slots_for_proposed and the
POST /schedule/proposed-reschedule-options endpoint.

Anchor week: Monday 2026-04-20 → Sunday 2026-04-26.
"""

from datetime import date, datetime

import pytest
from fastapi import HTTPException
from pydantic import ValidationError

from app.routers.schedule import proposed_reschedule_options
from app.schemas.schedule import ProposedRescheduleOptionsRequest
from app.services.rescheduling import find_replacement_slots_for_proposed

from .factories import (
    make_calendar,
    make_event,
)

MONDAY = date(2026, 4, 20)


# ---------------------------------------------------------------------------
# Service-level tests
# ---------------------------------------------------------------------------


def test_returns_ranked_options_for_proposed_event(session):
    result = find_replacement_slots_for_proposed(
        title="Study block",
        start_time=datetime(2026, 4, 20, 14, 0),
        end_time=datetime(2026, 4, 20, 15, 30),  # 90 min
        search_start=datetime(2026, 4, 20, 9, 0),
        search_end=datetime(2026, 4, 20, 17, 0),
        max_results=5,
        session=session,
    )

    assert result["event_title"] == "Study block"
    assert result["duration_minutes"] == 90
    assert len(result["options"]) >= 1
    # Ranks are 1..N consecutively.
    assert [o["rank"] for o in result["options"]] == list(
        range(1, len(result["options"]) + 1)
    )
    # Each option carries explainability fields.
    for o in result["options"]:
        assert o["reason_code"] in {
            "SAME_DAY_REPLACEMENT",
            "EARLIEST_VALID_REPLACEMENT",
            "VALID_REPLACEMENT_SLOT",
        }
        assert o["explanation"]


def test_proposed_duration_is_preserved_in_every_option(session):
    result = find_replacement_slots_for_proposed(
        title="Long block",
        start_time=datetime(2026, 4, 20, 13, 0),
        end_time=datetime(2026, 4, 20, 14, 30),  # 90 min
        search_start=datetime(2026, 4, 20, 9, 0),
        search_end=datetime(2026, 4, 22, 0, 0),
        max_results=10,
        session=session,
    )

    assert result["duration_minutes"] == 90
    for o in result["options"]:
        assert (o["end_time"] - o["start_time"]).total_seconds() == 90 * 60


def test_excludes_existing_events_from_proposed_suggestions(session):
    cal = make_calendar(session)
    # Existing event blocks 13:00-14:00.
    make_event(
        session, cal.id,
        start=datetime(2026, 4, 20, 13, 0),
        end=datetime(2026, 4, 20, 14, 0),
        title="Existing",
    )

    result = find_replacement_slots_for_proposed(
        title="Proposed",
        start_time=datetime(2026, 4, 20, 13, 0),
        end_time=datetime(2026, 4, 20, 14, 0),
        search_start=datetime(2026, 4, 20, 9, 0),
        search_end=datetime(2026, 4, 20, 17, 0),
        max_results=20,
        session=session,
    )

    # No option should overlap [13:00, 14:00) — there's no event_id to
    # exclude, so the existing event is fully respected.
    for o in result["options"]:
        assert not (o["start_time"] < datetime(2026, 4, 20, 14, 0)
                    and o["end_time"] > datetime(2026, 4, 20, 13, 0))


def test_excludes_other_occupied_events_from_proposed_suggestions(session):
    """Proposed-event suggestions avoid time occupied by other events
    (categorized events are the sole occupied-time model)."""
    cal = make_calendar(session)
    make_event(
        session, cal.id,
        start=datetime(2026, 4, 20, 14, 0),
        end=datetime(2026, 4, 20, 15, 0),
        title="Lunch",
    )

    result = find_replacement_slots_for_proposed(
        title="Proposed",
        start_time=datetime(2026, 4, 20, 10, 0),
        end_time=datetime(2026, 4, 20, 11, 0),
        search_start=datetime(2026, 4, 20, 9, 0),
        search_end=datetime(2026, 4, 20, 17, 0),
        max_results=20,
        session=session,
    )

    for o in result["options"]:
        assert not (o["start_time"] < datetime(2026, 4, 20, 15, 0)
                    and o["end_time"] > datetime(2026, 4, 20, 14, 0))


def test_proposed_suggestions_stay_inside_daily_rhythm(session):
    """Proposed-event replacement slots must fall inside Daily Rhythm hours."""
    from app.services.daily_rhythm import (
        DEFAULT_SUGGESTIONS_END,
        DEFAULT_SUGGESTIONS_START,
    )

    result = find_replacement_slots_for_proposed(
        title="Proposed",
        start_time=datetime(2026, 4, 20, 23, 0),  # outside rhythm hours
        end_time=datetime(2026, 4, 21, 0, 0),
        search_start=datetime(2026, 4, 20, 0, 0),
        search_end=datetime(2026, 4, 22, 0, 0),
        max_results=20,
        session=session,
    )

    for o in result["options"]:
        rhythm_start = datetime.combine(
            o["start_time"].date(), DEFAULT_SUGGESTIONS_START
        )
        rhythm_end = datetime.combine(
            o["start_time"].date(), DEFAULT_SUGGESTIONS_END
        )
        assert o["start_time"] >= rhythm_start
        assert o["end_time"] <= rhythm_end


def test_max_results_respected_for_proposed(session):
    result = find_replacement_slots_for_proposed(
        title="Proposed",
        start_time=datetime(2026, 4, 20, 10, 0),
        end_time=datetime(2026, 4, 20, 11, 0),
        search_start=datetime(2026, 4, 20, 9, 0),
        search_end=datetime(2026, 4, 25, 0, 0),
        max_results=3,
        session=session,
    )

    assert len(result["options"]) <= 3


def test_proposed_same_day_options_rank_first(session):
    result = find_replacement_slots_for_proposed(
        title="Proposed",
        start_time=datetime(2026, 4, 20, 10, 0),
        end_time=datetime(2026, 4, 20, 11, 0),
        search_start=datetime(2026, 4, 20, 9, 0),
        search_end=datetime(2026, 4, 22, 0, 0),
        max_results=10,
        session=session,
    )

    later_seen = False
    for o in result["options"]:
        if o["start_time"].date() == MONDAY:
            assert not later_seen, "Monday options must come before later days"
            assert o["reason_code"] == "SAME_DAY_REPLACEMENT"
        else:
            later_seen = True


def test_proposed_minutes_from_original_start_is_signed(session):
    result = find_replacement_slots_for_proposed(
        title="Proposed",
        start_time=datetime(2026, 4, 20, 12, 0),
        end_time=datetime(2026, 4, 20, 13, 0),
        search_start=datetime(2026, 4, 20, 9, 0),
        search_end=datetime(2026, 4, 20, 17, 0),
        max_results=10,
        session=session,
    )

    for o in result["options"]:
        expected = int(
            (o["start_time"] - datetime(2026, 4, 20, 12, 0)).total_seconds() // 60
        )
        assert o["minutes_from_original_start"] == expected


# ---------------------------------------------------------------------------
# Schema validation tests
# ---------------------------------------------------------------------------


def test_schema_rejects_start_time_after_end_time():
    with pytest.raises(ValidationError) as exc:
        ProposedRescheduleOptionsRequest(
            calendar_id=1,
            title="X",
            start_time=datetime(2026, 4, 20, 11, 0),
            end_time=datetime(2026, 4, 20, 11, 0),  # equal — invalid
            search_start=datetime(2026, 4, 20, 9, 0),
            search_end=datetime(2026, 4, 20, 17, 0),
        )
    assert "start_time must be before end_time" in str(exc.value)


def test_schema_rejects_search_start_after_search_end():
    with pytest.raises(ValidationError) as exc:
        ProposedRescheduleOptionsRequest(
            calendar_id=1,
            title="X",
            start_time=datetime(2026, 4, 20, 10, 0),
            end_time=datetime(2026, 4, 20, 11, 0),
            search_start=datetime(2026, 4, 20, 17, 0),
            search_end=datetime(2026, 4, 20, 9, 0),  # before start — invalid
        )
    assert "search_start must be before search_end" in str(exc.value)


def test_schema_rejects_max_results_below_one():
    with pytest.raises(ValidationError):
        ProposedRescheduleOptionsRequest(
            calendar_id=1,
            title="X",
            start_time=datetime(2026, 4, 20, 10, 0),
            end_time=datetime(2026, 4, 20, 11, 0),
            search_start=datetime(2026, 4, 20, 9, 0),
            search_end=datetime(2026, 4, 20, 17, 0),
            max_results=0,
        )


# ---------------------------------------------------------------------------
# Route-handler tests (mirrors test_event_create_conflict_response.py style)
# ---------------------------------------------------------------------------


def test_route_returns_404_for_unknown_calendar(session):
    body = ProposedRescheduleOptionsRequest(
        calendar_id=9999,
        title="X",
        start_time=datetime(2026, 4, 20, 10, 0),
        end_time=datetime(2026, 4, 20, 11, 0),
        search_start=datetime(2026, 4, 20, 9, 0),
        search_end=datetime(2026, 4, 20, 17, 0),
        max_results=5,
    )

    with pytest.raises(HTTPException) as exc_info:
        proposed_reschedule_options(body, session)

    assert exc_info.value.status_code == 404
    assert exc_info.value.detail == "Calendar not found"


def test_route_returns_options_for_valid_calendar(session):
    cal = make_calendar(session)

    body = ProposedRescheduleOptionsRequest(
        calendar_id=cal.id,
        title="Study block",
        start_time=datetime(2026, 4, 20, 14, 0),
        end_time=datetime(2026, 4, 20, 15, 30),  # 90 min
        search_start=datetime(2026, 4, 20, 9, 0),
        search_end=datetime(2026, 4, 20, 17, 0),
        max_results=5,
    )

    result = proposed_reschedule_options(body, session)
    assert result["event_title"] == "Study block"
    assert result["duration_minutes"] == 90
    assert "event_id" not in result  # proposed events have no id
    assert len(result["options"]) >= 1
    assert len(result["options"]) <= 5
