"""Event-overlap conflict tests.

Anchor date: Monday 2026-04-20 (weekday = 0).
"""

from datetime import datetime

from app.services.conflict_detection import check_all_conflicts

from .factories import make_calendar, make_event


MONDAY = datetime(2026, 4, 20).date()


def test_event_overlap_conflict_detected(session):
    cal = make_calendar(session)
    make_event(
        session,
        cal.id,
        start=datetime(2026, 4, 20, 10, 0),
        end=datetime(2026, 4, 20, 11, 0),
        title="Existing",
    )

    conflicts = check_all_conflicts(
        start_time=datetime(2026, 4, 20, 10, 30),
        end_time=datetime(2026, 4, 20, 11, 30),
        session=session,
    )

    codes = [c.reason_code for c in conflicts]
    assert "EVENT_OVERLAP" in codes
    assert len([c for c in conflicts if c.reason_code == "EVENT_OVERLAP"]) == 1


def test_event_fully_contained_overlap_detected(session):
    cal = make_calendar(session)
    make_event(
        session,
        cal.id,
        start=datetime(2026, 4, 20, 10, 0),
        end=datetime(2026, 4, 20, 12, 0),
    )

    conflicts = check_all_conflicts(
        start_time=datetime(2026, 4, 20, 10, 30),
        end_time=datetime(2026, 4, 20, 11, 0),
        session=session,
    )

    assert any(c.reason_code == "EVENT_OVERLAP" for c in conflicts)


def test_event_touching_boundary_is_not_overlap(session):
    """end_a == start_b must NOT count as an event overlap."""
    cal = make_calendar(session)
    make_event(
        session,
        cal.id,
        start=datetime(2026, 4, 20, 10, 0),
        end=datetime(2026, 4, 20, 11, 0),
    )

    conflicts = check_all_conflicts(
        start_time=datetime(2026, 4, 20, 11, 0),
        end_time=datetime(2026, 4, 20, 12, 0),
        session=session,
    )

    assert not any(c.reason_code == "EVENT_OVERLAP" for c in conflicts)


def test_event_fully_separate_no_conflict(session):
    cal = make_calendar(session)
    make_event(
        session,
        cal.id,
        start=datetime(2026, 4, 20, 9, 0),
        end=datetime(2026, 4, 20, 10, 0),
    )

    conflicts = check_all_conflicts(
        start_time=datetime(2026, 4, 20, 14, 0),
        end_time=datetime(2026, 4, 20, 15, 0),
        session=session,
    )

    assert conflicts == []


def test_exclude_event_id_skips_self_overlap(session):
    """When updating an event, excluding its own id must suppress self-overlap."""
    cal = make_calendar(session)
    ev = make_event(
        session,
        cal.id,
        start=datetime(2026, 4, 20, 10, 0),
        end=datetime(2026, 4, 20, 11, 0),
    )

    conflicts = check_all_conflicts(
        start_time=datetime(2026, 4, 20, 10, 0),
        end_time=datetime(2026, 4, 20, 11, 0),
        session=session,
        exclude_event_id=ev.id,
    )

    assert not any(c.reason_code == "EVENT_OVERLAP" for c in conflicts)
