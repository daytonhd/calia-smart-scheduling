"""Conflict detection service — reusable logic for all scheduling conflict checks.

Three conflict types are checked:
  1. EVENT_OVERLAP         — proposed time overlaps an existing event
  2. BLOCKED_TIME_OVERLAP  — proposed time overlaps a blocked time entry
  3. OUTSIDE_AVAILABILITY  — proposed time is not fully contained within any active
                             availability window for that weekday

Touching boundaries (end_a == start_b) are NOT considered overlap.

Time contract: all datetime arguments must be naive (see
app.services.time_contract). Schemas reject tz-aware inputs at the API
boundary, so service-level code can safely compare naive values directly.
"""

from datetime import date, datetime, time, timedelta
from typing import List, NamedTuple, Optional, Tuple

from sqlmodel import Session, select

from app.models.availability_window import AvailabilityWindow
from app.models.blocked_time import BlockedTime
from app.models.event import Event
from app.schemas.schedule import ConflictDetail, SlotSuggestion


class FreeWindow(NamedTuple):
    """A maximal interval in which the user is free (inside availability, not
    overlapped by any event or blocked time)."""

    start_time: datetime
    end_time: datetime

# Single-user MVP — all blocked times and availability windows belong to this user.
MVP_USER_ID = 1

# Weekday names for human-readable messages.
_WEEKDAY_NAMES = [
    "Monday", "Tuesday", "Wednesday", "Thursday",
    "Friday", "Saturday", "Sunday",
]

# Slot suggestion explanation strings — kept here so the service is the single
# source of truth for deterministic backend-formatted text.
_SLOT_REASON_CODE = "EARLIEST_VALID_SLOT"
_SLOT_EXPLANATION = (
    "Selected because it fits inside an active availability window "
    "and avoids existing events and blocked times."
)


def _format_clock(dt: datetime) -> str:
    """Format a datetime as '1:00 PM' (no leading zero on hour)."""
    return dt.strftime("%I:%M %p").lstrip("0")


def _check_event_overlap(
    start_time: datetime,
    end_time: datetime,
    session: Session,
    exclude_event_id: Optional[int],
) -> List[ConflictDetail]:
    """Return one ConflictDetail per existing event that overlaps the proposed interval.

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

    details: List[ConflictDetail] = []
    for e in overlapping:
        details.append(ConflictDetail(
            reason_code="EVENT_OVERLAP",
            conflict_type="event",
            message=(
                f"This time overlaps an existing event from "
                f"{_format_clock(e.start_time)} to {_format_clock(e.end_time)}."
            ),
            start_time=e.start_time,
            end_time=e.end_time,
            related_event_id=e.id,
        ))
    return details


def _check_blocked_time_overlap(
    start_time: datetime,
    end_time: datetime,
    session: Session,
) -> List[ConflictDetail]:
    """Return one ConflictDetail per blocked-time row that overlaps the proposed interval.

    Overlap condition (touching boundaries excluded):
        blocked.start_time < end_time AND blocked.end_time > start_time
    """
    query = select(BlockedTime).where(
        BlockedTime.user_id == MVP_USER_ID,
        BlockedTime.start_time < end_time,
        BlockedTime.end_time > start_time,
    )
    overlapping = session.exec(query).all()

    details: List[ConflictDetail] = []
    for bt in overlapping:
        details.append(ConflictDetail(
            reason_code="BLOCKED_TIME_OVERLAP",
            conflict_type="blocked_time",
            message=(
                f"This time overlaps blocked time from "
                f"{_format_clock(bt.start_time)} to {_format_clock(bt.end_time)}."
            ),
            start_time=bt.start_time,
            end_time=bt.end_time,
            related_blocked_time_id=bt.id,
        ))
    return details


def _check_availability(
    start_time: datetime,
    end_time: datetime,
    session: Session,
) -> List[ConflictDetail]:
    """Return a conflict if the proposed time is not fully contained within any
    active availability window for the event's weekday.

    Availability windows store wall-clock time (no timezone). Both event and
    window comparisons happen in the same naive local-app-time frame per the
    MVP time contract.

    Weekday convention: 0=Monday, 6=Sunday (matches Python's datetime.weekday()).
    """
    weekday = start_time.weekday()
    weekday_name = _WEEKDAY_NAMES[weekday]
    event_start = start_time.time()
    event_end = end_time.time()

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
                conflict_type="availability",
                message=(
                    f"This time is outside your active availability window "
                    f"for {weekday_name}."
                ),
                start_time=start_time,
                end_time=end_time,
            )
        ]

    for window in windows:
        if window.start_time <= event_start and window.end_time >= event_end:
            return []  # Fully contained within this window — no conflict

    return [
        ConflictDetail(
            reason_code="OUTSIDE_AVAILABILITY",
            conflict_type="availability",
            message=(
                f"This time is outside your active availability window "
                f"for {weekday_name}."
            ),
            start_time=start_time,
            end_time=end_time,
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
        start_time:        Proposed event start (naive datetime).
        end_time:          Proposed event end (naive datetime).
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


def _subtract_intervals(
    start: datetime,
    end: datetime,
    occupied: List[Tuple[datetime, datetime]],
) -> List[Tuple[datetime, datetime]]:
    """Subtract occupied intervals from [start, end] and return maximal free gaps.

    Touching boundaries (gap end == next start) are preserved as a zero-length
    separator, not merged — but zero-length gaps are never emitted.
    """
    clipped: List[Tuple[datetime, datetime]] = []
    for o_start, o_end in occupied:
        s = max(o_start, start)
        e = min(o_end, end)
        if s < e:
            clipped.append((s, e))

    clipped.sort(key=lambda x: x[0])

    merged: List[Tuple[datetime, datetime]] = []
    for s, e in clipped:
        if merged and s <= merged[-1][1]:
            merged[-1] = (merged[-1][0], max(merged[-1][1], e))
        else:
            merged.append((s, e))

    result: List[Tuple[datetime, datetime]] = []
    cursor = start
    for s, e in merged:
        if cursor < s:
            result.append((cursor, s))
        cursor = max(cursor, e)
    if cursor < end:
        result.append((cursor, end))
    return result


def find_free_windows(
    start_date: date,
    end_date: date,
    session: Session,
) -> List[FreeWindow]:
    """Return maximal free intervals across [start_date, end_date].

    For each day:
      1. Collect active availability windows for that weekday.
      2. Collect events and blocked times that overlap the day.
      3. For each availability window, subtract the union of occupied intervals
         and emit the remaining free sub-intervals.

    This is a reusable lower-level helper — slot-fitting and triage logic layer
    on top by walking the returned windows. It does not enforce any slot
    duration or grid alignment; callers decide how to consume free intervals.

    Returns:
        Free windows ordered earliest-first. Empty list if no availability
        exists in the range.
    """
    results: List[FreeWindow] = []
    current_date = start_date

    while current_date <= end_date:
        weekday = current_date.weekday()

        windows = session.exec(
            select(AvailabilityWindow).where(
                AvailabilityWindow.user_id == MVP_USER_ID,
                AvailabilityWindow.weekday == weekday,
                AvailabilityWindow.active == True,  # noqa: E712
            )
        ).all()

        if not windows:
            current_date += timedelta(days=1)
            continue

        day_start = datetime.combine(current_date, time.min)
        day_end = datetime.combine(current_date + timedelta(days=1), time.min)

        events = session.exec(
            select(Event).where(
                Event.start_time < day_end,
                Event.end_time > day_start,
            )
        ).all()
        blocked = session.exec(
            select(BlockedTime).where(
                BlockedTime.user_id == MVP_USER_ID,
                BlockedTime.start_time < day_end,
                BlockedTime.end_time > day_start,
            )
        ).all()

        occupied: List[Tuple[datetime, datetime]] = [
            (e.start_time, e.end_time) for e in events
        ] + [(bt.start_time, bt.end_time) for bt in blocked]

        for window in windows:
            w_start = datetime.combine(current_date, window.start_time)
            w_end = datetime.combine(current_date, window.end_time)
            for s, e in _subtract_intervals(w_start, w_end, occupied):
                results.append(FreeWindow(start_time=s, end_time=e))

        current_date += timedelta(days=1)

    return results


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

    Each returned slot includes a deterministic reason_code (EARLIEST_VALID_SLOT)
    and an explanation string. Ranking is simple: earliest valid slots first.
    Rejected candidates are NOT returned in MVP.

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
                        reason_code=_SLOT_REASON_CODE,
                        explanation=_SLOT_EXPLANATION,
                    ))
                    if len(results) >= max_results:
                        break

                candidate_start += increment

        current_date += timedelta(days=1)

    return results
