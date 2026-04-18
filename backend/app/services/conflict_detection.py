"""Conflict detection service — reusable logic for all scheduling conflict checks.

Three conflict types are checked:
  1. EVENT_OVERLAP         — proposed time overlaps an existing event
  2. BLOCKED_TIME_OVERLAP  — proposed time overlaps a blocked time entry
  3. OUTSIDE_AVAILABILITY  — proposed time is not fully contained within any active
                             availability window for that weekday

Touching boundaries (end_a == start_b) are NOT considered overlap.
"""

from datetime import date, datetime, timedelta
from typing import List, Optional

from sqlmodel import Session, select

from app.models.availability_window import AvailabilityWindow
from app.models.blocked_time import BlockedTime
from app.models.event import Event
from app.schemas.schedule import ConflictDetail, SlotSuggestion

# Single-user MVP — all blocked times and availability windows belong to this user.
MVP_USER_ID = 1


def _check_event_overlap(
    start_time: datetime,
    end_time: datetime,
    session: Session,
    exclude_event_id: Optional[int],
) -> List[ConflictDetail]:
    """Return conflicts for each existing event that overlaps the proposed interval.

    Overlap condition (touching boundaries excluded):
        existing.start_time < end_time AND existing.end_time > start_time
    """
    query = select(Event).where(
        Event.start_time < end_time,
        Event.end_time > start_time,
    )
    if exclude_event_id is not None:
        query = query.where(Event.id != exclude_event_id)

    overlapping = session.exec(query).all()

    return [
        ConflictDetail(
            reason_code="EVENT_OVERLAP",
            message=(
                f"Conflicts with existing event '{e.title}' (id={e.id}) "
                f"from {e.start_time.isoformat()} to {e.end_time.isoformat()}"
            ),
        )
        for e in overlapping
    ]


def _check_blocked_time_overlap(
    start_time: datetime,
    end_time: datetime,
    session: Session,
) -> List[ConflictDetail]:
    """Return conflicts for each blocked time entry that overlaps the proposed interval.

    Overlap condition (touching boundaries excluded):
        blocked.start_time < end_time AND blocked.end_time > start_time
    """
    query = select(BlockedTime).where(
        BlockedTime.user_id == MVP_USER_ID,
        BlockedTime.start_time < end_time,
        BlockedTime.end_time > start_time,
    )
    overlapping = session.exec(query).all()

    return [
        ConflictDetail(
            reason_code="BLOCKED_TIME_OVERLAP",
            message=(
                f"Conflicts with blocked time '{bt.title}' (id={bt.id}) "
                f"from {bt.start_time.isoformat()} to {bt.end_time.isoformat()}"
            ),
        )
        for bt in overlapping
    ]


def _check_availability(
    start_time: datetime,
    end_time: datetime,
    session: Session,
) -> List[ConflictDetail]:
    """Return a conflict if the proposed time is not fully contained within any
    active availability window for the event's weekday.

    Availability windows store wall-clock time (no timezone). The comparison uses
    .time() on the event datetimes, which drops timezone info. For MVP, datetimes
    are expected to be in a consistent timezone context (e.g., all naive or all UTC).

    Weekday convention: 0=Monday, 6=Sunday (matches Python's datetime.weekday()).
    """
    weekday = start_time.weekday()
    event_start = start_time.time().replace(tzinfo=None)
    event_end = end_time.time().replace(tzinfo=None)

    windows = session.exec(
        select(AvailabilityWindow).where(
            AvailabilityWindow.user_id == MVP_USER_ID,
            AvailabilityWindow.weekday == weekday,
            AvailabilityWindow.active == True,  # noqa: E712
        )
    ).all()

    if not windows:
        return [
            ConflictDetail(
                reason_code="OUTSIDE_AVAILABILITY",
                message=(
                    f"No active availability window exists for weekday {weekday} "
                    f"(0=Monday, 6=Sunday)"
                ),
            )
        ]

    for window in windows:
        if window.start_time <= event_start and window.end_time >= event_end:
            return []  # Fully contained within this window — no conflict

    return [
        ConflictDetail(
            reason_code="OUTSIDE_AVAILABILITY",
            message=(
                f"Proposed event ({event_start.isoformat()}–{event_end.isoformat()}) "
                f"is not fully contained within any active availability window "
                f"for weekday {weekday} (0=Monday, 6=Sunday)"
            ),
        )
    ]


def check_all_conflicts(
    start_time: datetime,
    end_time: datetime,
    session: Session,
    exclude_event_id: Optional[int] = None,
) -> List[ConflictDetail]:
    """Run all three conflict checks and return every detected conflict.

    Args:
        start_time:        Proposed event start.
        end_time:          Proposed event end.
        session:           Active database session.
        exclude_event_id:  Event id to skip during overlap check (used on update
                           so the event does not conflict with itself).

    Returns:
        List of ConflictDetail — empty means no conflicts.
    """
    conflicts: List[ConflictDetail] = []
    conflicts.extend(_check_event_overlap(start_time, end_time, session, exclude_event_id))
    conflicts.extend(_check_blocked_time_overlap(start_time, end_time, session))
    conflicts.extend(_check_availability(start_time, end_time, session))
    return conflicts


def find_available_slots(
    duration_minutes: int,
    start_date: date,
    end_date: date,
    max_results: int,
    session: Session,
) -> List[SlotSuggestion]:
    """Return up to max_results conflict-free slots of the requested duration.

    Scans each day in [start_date, end_date] in order. For each day, iterates
    through active availability windows for that weekday in 30-minute increments.
    A candidate slot is valid when check_all_conflicts returns empty.

    Args:
        duration_minutes:  Required slot length in minutes (>= 1).
        start_date:        First day to scan (inclusive).
        end_date:          Last day to scan (inclusive).
        max_results:       Maximum number of slots to return.
        session:           Active database session.

    Returns:
        List of SlotSuggestion ordered earliest first. Empty if none found.
    """
    slot_duration = timedelta(minutes=duration_minutes)
    increment = timedelta(minutes=30)
    results: List[SlotSuggestion] = []

    current_date = start_date
    while current_date <= end_date and len(results) < max_results:
        weekday = current_date.weekday()

        windows = session.exec(
            select(AvailabilityWindow).where(
                AvailabilityWindow.user_id == MVP_USER_ID,
                AvailabilityWindow.weekday == weekday,
                AvailabilityWindow.active == True,  # noqa: E712
            )
        ).all()

        for window in windows:
            if len(results) >= max_results:
                break

            window_start = datetime.combine(current_date, window.start_time)
            window_end = datetime.combine(current_date, window.end_time)
            candidate_start = window_start

            while candidate_start + slot_duration <= window_end:
                candidate_end = candidate_start + slot_duration

                if not check_all_conflicts(candidate_start, candidate_end, session):
                    results.append(SlotSuggestion(
                        start_time=candidate_start,
                        end_time=candidate_end,
                    ))
                    if len(results) >= max_results:
                        break

                candidate_start += increment

        current_date += timedelta(days=1)

    return results
