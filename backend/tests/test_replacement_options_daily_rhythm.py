"""Batch 3 contract tests: replacement options use Daily Rhythm hours and
do not depend on AvailabilityWindow rows.

Covers both the saved-event endpoint (find_replacement_slots) and the
proposed-event endpoint (find_replacement_slots_for_proposed). Each pin:

  - works with zero AvailabilityWindow rows
  - stays within 8:00 AM-9:00 PM
  - preserves the source duration
  - avoids existing events
  - explanation does not mention "availability windows"
"""

from datetime import date, datetime
from typing import Optional

from app.services.daily_rhythm import (
    DEFAULT_SUGGESTIONS_END,
    DEFAULT_SUGGESTIONS_START,
)
from app.services.rescheduling import (
    find_replacement_slots,
    find_replacement_slots_for_proposed,
)

from .factories import make_calendar, make_event

MONDAY = date(2026, 4, 20)


def assert_no_legacy_scheduling_language(text: Optional[str]) -> None:
    """Assert an explanation string does not leak deprecated wording.

    User-facing scheduling explanations must use the current product
    language (Daily Rhythm, suggestion hours, occupied time, replacement
    options, Schedule Balance) and never mention legacy "availability"
    concepts.
    """
    if text is None:
        return
    value = text.lower()
    assert "availability" not in value, text


def _within_rhythm(o):
    rhythm_start = datetime.combine(o["start_time"].date(), DEFAULT_SUGGESTIONS_START)
    rhythm_end = datetime.combine(o["start_time"].date(), DEFAULT_SUGGESTIONS_END)
    return o["start_time"] >= rhythm_start and o["end_time"] <= rhythm_end


# ---------------------------------------------------------------------------
# Saved-event replacement (POST /schedule/reschedule-options)
# ---------------------------------------------------------------------------


def test_saved_replacement_works_with_zero_availability_rows(session):
    """No AvailabilityWindow rows → saved-event replacements are still returned."""
    cal = make_calendar(session)
    ev = make_event(
        session, cal.id,
        start=datetime(2026, 4, 20, 10, 0),
        end=datetime(2026, 4, 20, 11, 0),
    )

    result = find_replacement_slots(
        event_id=ev.id,
        search_start=datetime(2026, 4, 20, 0, 0),
        search_end=datetime(2026, 4, 20, 23, 59),
        max_results=10,
        session=session,
    )

    assert result is not None
    assert len(result["options"]) >= 1


def test_saved_replacement_stays_within_daily_rhythm(session):
    cal = make_calendar(session)
    ev = make_event(
        session, cal.id,
        start=datetime(2026, 4, 20, 10, 0),
        end=datetime(2026, 4, 20, 11, 0),
    )

    result = find_replacement_slots(
        event_id=ev.id,
        search_start=datetime(2026, 4, 20, 0, 0),
        search_end=datetime(2026, 4, 22, 23, 59),
        max_results=50,
        session=session,
    )

    assert result["options"], "expected at least one option"
    for o in result["options"]:
        assert _within_rhythm(o)


def test_saved_replacement_preserves_duration(session):
    cal = make_calendar(session)
    ev = make_event(
        session, cal.id,
        start=datetime(2026, 4, 20, 10, 0),
        end=datetime(2026, 4, 20, 11, 30),  # 90 minutes
    )

    result = find_replacement_slots(
        event_id=ev.id,
        search_start=datetime(2026, 4, 20, 0, 0),
        search_end=datetime(2026, 4, 20, 23, 59),
        max_results=10,
        session=session,
    )

    assert result["duration_minutes"] == 90
    for o in result["options"]:
        assert (o["end_time"] - o["start_time"]).total_seconds() == 90 * 60


def test_saved_replacement_avoids_existing_events(session):
    cal = make_calendar(session)
    ev = make_event(
        session, cal.id,
        start=datetime(2026, 4, 20, 10, 0),
        end=datetime(2026, 4, 20, 11, 0),
    )
    # Other events that must not be overlapped.
    make_event(
        session, cal.id,
        start=datetime(2026, 4, 20, 13, 0),
        end=datetime(2026, 4, 20, 14, 0),
        title="Other A",
    )
    make_event(
        session, cal.id,
        start=datetime(2026, 4, 20, 16, 0),
        end=datetime(2026, 4, 20, 17, 0),
        title="Other B",
    )

    result = find_replacement_slots(
        event_id=ev.id,
        search_start=datetime(2026, 4, 20, 0, 0),
        search_end=datetime(2026, 4, 20, 23, 59),
        max_results=50,
        session=session,
    )

    for o in result["options"]:
        assert not (
            o["start_time"] < datetime(2026, 4, 20, 14, 0)
            and o["end_time"] > datetime(2026, 4, 20, 13, 0)
        )
        assert not (
            o["start_time"] < datetime(2026, 4, 20, 17, 0)
            and o["end_time"] > datetime(2026, 4, 20, 16, 0)
        )


def test_saved_replacement_explanation_mentions_no_availability_windows(session):
    cal = make_calendar(session)
    ev = make_event(
        session, cal.id,
        start=datetime(2026, 4, 20, 10, 0),
        end=datetime(2026, 4, 20, 11, 0),
    )

    result = find_replacement_slots(
        event_id=ev.id,
        search_start=datetime(2026, 4, 20, 0, 0),
        search_end=datetime(2026, 4, 20, 23, 59),
        max_results=3,
        session=session,
    )

    assert result["options"], "expected at least one option"
    for o in result["options"]:
        assert_no_legacy_scheduling_language(o["explanation"])


def test_saved_replacement_explanations_avoid_legacy_language(session):
    """Regression: every saved-event replacement option's explanation must
    avoid the legacy "availability" wording."""
    cal = make_calendar(session)
    ev = make_event(
        session, cal.id,
        start=datetime(2026, 4, 20, 10, 0),
        end=datetime(2026, 4, 20, 11, 0),
    )

    result = find_replacement_slots(
        event_id=ev.id,
        search_start=datetime(2026, 4, 20, 0, 0),
        search_end=datetime(2026, 4, 22, 23, 59),
        max_results=10,
        session=session,
    )

    assert result is not None
    options = result["options"]
    assert len(options) >= 2, "need multiple options so the assertion is meaningful"
    for o in options:
        assert_no_legacy_scheduling_language(o.get("explanation"))


# ---------------------------------------------------------------------------
# Proposed-event replacement (POST /schedule/proposed-reschedule-options)
# ---------------------------------------------------------------------------


def test_proposed_replacement_works_with_zero_availability_rows(session):
    """No AvailabilityWindow rows → proposed-event replacements still returned."""
    result = find_replacement_slots_for_proposed(
        title="Proposed",
        start_time=datetime(2026, 4, 20, 14, 0),
        end_time=datetime(2026, 4, 20, 15, 0),
        search_start=datetime(2026, 4, 20, 0, 0),
        search_end=datetime(2026, 4, 20, 23, 59),
        max_results=10,
        session=session,
    )

    assert len(result["options"]) >= 1


def test_proposed_replacement_stays_within_daily_rhythm(session):
    result = find_replacement_slots_for_proposed(
        title="Proposed",
        start_time=datetime(2026, 4, 20, 14, 0),
        end_time=datetime(2026, 4, 20, 15, 0),
        search_start=datetime(2026, 4, 20, 0, 0),
        search_end=datetime(2026, 4, 22, 23, 59),
        max_results=50,
        session=session,
    )

    assert result["options"], "expected at least one option"
    for o in result["options"]:
        assert _within_rhythm(o)


def test_proposed_replacement_preserves_duration_from_proposed_range(session):
    """Duration is computed from the proposed start/end and preserved."""
    result = find_replacement_slots_for_proposed(
        title="Proposed",
        start_time=datetime(2026, 4, 20, 14, 0),
        end_time=datetime(2026, 4, 20, 15, 45),  # 105 minutes
        search_start=datetime(2026, 4, 20, 0, 0),
        search_end=datetime(2026, 4, 20, 23, 59),
        max_results=10,
        session=session,
    )

    assert result["duration_minutes"] == 105
    for o in result["options"]:
        assert (o["end_time"] - o["start_time"]).total_seconds() == 105 * 60


def test_proposed_replacement_avoids_existing_events(session):
    cal = make_calendar(session)
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
        search_start=datetime(2026, 4, 20, 0, 0),
        search_end=datetime(2026, 4, 20, 23, 59),
        max_results=50,
        session=session,
    )

    for o in result["options"]:
        assert not (
            o["start_time"] < datetime(2026, 4, 20, 14, 0)
            and o["end_time"] > datetime(2026, 4, 20, 13, 0)
        )


def test_proposed_replacement_explanation_mentions_no_availability_windows(session):
    result = find_replacement_slots_for_proposed(
        title="Proposed",
        start_time=datetime(2026, 4, 20, 14, 0),
        end_time=datetime(2026, 4, 20, 15, 0),
        search_start=datetime(2026, 4, 20, 0, 0),
        search_end=datetime(2026, 4, 20, 23, 59),
        max_results=3,
        session=session,
    )

    assert result["options"], "expected at least one option"
    for o in result["options"]:
        assert_no_legacy_scheduling_language(o["explanation"])


def test_proposed_replacement_explanations_avoid_legacy_language(session):
    """Regression: every proposed-event replacement option's explanation
    must avoid the legacy "availability" wording."""
    result = find_replacement_slots_for_proposed(
        title="Proposed",
        start_time=datetime(2026, 4, 20, 14, 0),
        end_time=datetime(2026, 4, 20, 15, 0),
        search_start=datetime(2026, 4, 20, 0, 0),
        search_end=datetime(2026, 4, 22, 23, 59),
        max_results=10,
        session=session,
    )

    options = result["options"]
    assert len(options) >= 2, "need multiple options so the assertion is meaningful"
    for o in options:
        assert_no_legacy_scheduling_language(o.get("explanation"))
