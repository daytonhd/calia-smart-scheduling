"""Conflict-rule tests for the active conflict surface.

OUTSIDE_AVAILABILITY is no longer an active conflict — manual events are
allowed outside AvailabilityWindow rows and outside Daily Rhythm hours as
long as they have a valid range and do not overlap occupied time. These
tests pin that contract.
"""

from datetime import datetime, time

from app.services.conflict_detection import check_all_conflicts

from .factories import make_availability


def test_outside_availability_window_is_not_a_conflict(session):
    """A proposed time outside the only availability window must NOT produce
    OUTSIDE_AVAILABILITY (or any other conflict) when nothing else overlaps."""
    make_availability(session, weekday=0, start=time(9, 0), end=time(17, 0))

    conflicts = check_all_conflicts(
        start_time=datetime(2026, 4, 20, 22, 0),
        end_time=datetime(2026, 4, 20, 23, 0),
        session=session,
    )

    assert conflicts == []


def test_no_availability_for_weekday_is_not_a_conflict(session):
    """A weekday with no availability rows must NOT produce a conflict
    purely on that basis."""
    conflicts = check_all_conflicts(
        start_time=datetime(2026, 4, 21, 10, 0),
        end_time=datetime(2026, 4, 21, 11, 0),
        session=session,
    )

    assert conflicts == []


def test_inactive_availability_does_not_create_conflict(session):
    """Even when only an inactive availability window exists, no conflict
    is produced for a placement inside its hours — availability is no
    longer enforced."""
    make_availability(
        session, weekday=0, start=time(9, 0), end=time(17, 0), active=False
    )

    conflicts = check_all_conflicts(
        start_time=datetime(2026, 4, 20, 10, 0),
        end_time=datetime(2026, 4, 20, 11, 0),
        session=session,
    )

    assert conflicts == []


def test_no_outside_availability_reason_code_returned(session):
    """OUTSIDE_AVAILABILITY must never appear in the active conflict surface."""
    # Try a few placements that previously triggered OUTSIDE_AVAILABILITY:
    placements = [
        # Outside an existing 9-17 window.
        (datetime(2026, 4, 20, 8, 0), datetime(2026, 4, 20, 10, 0)),
        (datetime(2026, 4, 20, 16, 0), datetime(2026, 4, 20, 18, 0)),
        # Straddles a gap between two windows.
        (datetime(2026, 4, 20, 11, 30), datetime(2026, 4, 20, 13, 30)),
    ]
    make_availability(session, weekday=0, start=time(9, 0), end=time(12, 0))
    make_availability(session, weekday=0, start=time(13, 0), end=time(17, 0))

    for start, end in placements:
        conflicts = check_all_conflicts(start_time=start, end_time=end, session=session)
        codes = [c.reason_code for c in conflicts]
        assert "OUTSIDE_AVAILABILITY" not in codes


def test_fully_within_availability_still_clean(session):
    """A placement inside a window remains conflict-free (sanity check)."""
    make_availability(session, weekday=0, start=time(9, 0), end=time(17, 0))

    conflicts = check_all_conflicts(
        start_time=datetime(2026, 4, 20, 10, 0),
        end_time=datetime(2026, 4, 20, 11, 0),
        session=session,
    )

    assert conflicts == []
