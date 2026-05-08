"""Conflict-rule tests for the active conflict surface.

OUTSIDE_AVAILABILITY is no longer an active conflict — manual events are
allowed outside Daily Rhythm hours as long as they have a valid range and
do not overlap occupied time. These tests pin that contract.
"""

from datetime import datetime

from app.services.conflict_detection import check_all_conflicts


def test_outside_daily_rhythm_is_not_a_conflict(session):
    """A proposed time outside Daily Rhythm hours must NOT produce
    OUTSIDE_AVAILABILITY (or any other conflict) when nothing else overlaps."""
    conflicts = check_all_conflicts(
        start_time=datetime(2026, 4, 20, 22, 0),
        end_time=datetime(2026, 4, 20, 23, 0),
        session=session,
    )

    assert conflicts == []


def test_weekday_with_no_setup_is_not_a_conflict(session):
    """A weekday with no setup must NOT produce a conflict
    purely on that basis."""
    conflicts = check_all_conflicts(
        start_time=datetime(2026, 4, 21, 10, 0),
        end_time=datetime(2026, 4, 21, 11, 0),
        session=session,
    )

    assert conflicts == []


def test_no_outside_availability_reason_code_returned(session):
    """OUTSIDE_AVAILABILITY must never appear in the active conflict surface."""
    # Try a few placements that previously triggered OUTSIDE_AVAILABILITY:
    placements = [
        # Outside what was previously a 9-17 window.
        (datetime(2026, 4, 20, 8, 0), datetime(2026, 4, 20, 10, 0)),
        (datetime(2026, 4, 20, 16, 0), datetime(2026, 4, 20, 18, 0)),
        # Straddles a gap between two windows.
        (datetime(2026, 4, 20, 11, 30), datetime(2026, 4, 20, 13, 30)),
    ]

    for start, end in placements:
        conflicts = check_all_conflicts(start_time=start, end_time=end, session=session)
        codes = [c.reason_code for c in conflicts]
        assert "OUTSIDE_AVAILABILITY" not in codes


def test_clean_placement_inside_daily_rhythm(session):
    """A placement inside Daily Rhythm hours remains conflict-free (sanity check)."""
    conflicts = check_all_conflicts(
        start_time=datetime(2026, 4, 20, 10, 0),
        end_time=datetime(2026, 4, 20, 11, 0),
        session=session,
    )

    assert conflicts == []
