"""Conflict detection service — reusable logic for all scheduling conflict checks.

Active conflict types:
  1. EVENT_OVERLAP — proposed time overlaps an existing event

All saved Events count as occupied time. Categorized Events (e.g.
Unavailable, Commute, Class, Focus block) are the sole occupied-time
model.

Legacy availability-window checks have been removed. Manual event create /
update is allowed outside Daily Rhythm hours as long as the range is valid
and does not overlap an existing event.
Touching boundaries (end_a == start_b) are NOT considered overlap.

Time contract: all datetime arguments must be naive (see
app.services.time_contract). Schemas reject tz-aware inputs at the API
boundary, so service-level code can safely compare naive values directly.

Free-window scans and slot suggestions are driven by Daily Rhythm
suggestion hours (see app.services.daily_rhythm).
"""

from datetime import date, datetime, timedelta
from typing import List, NamedTuple, Optional, Tuple

from sqlmodel import Session, select

from app.models.event import Event
from app.schemas.schedule import ConflictDetail, SlotSuggestion
from app.services.daily_rhythm import get_suggestion_windows_for_range


class FreeWindow(NamedTuple):
    """A maximal interval in which the user is free (inside the daily
    suggestion window and not overlapped by any event)."""

    start_time: datetime
    end_time: datetime

# Single-user MVP user id.
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
    "Selected because it fits inside your daily suggestion hours "
    "and avoids existing events and other occupied schedule items."
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

def check_all_conflicts(
    start_time: datetime,
    end_time: datetime,
    session: Session,
    exclude_event_id: Optional[int] = None,
) -> List[ConflictDetail]:
    """Return every detected conflict for a proposed event placement.

    Active checks:
      1. EVENT_OVERLAP — proposed time overlaps an existing event

    Legacy availability-window checks have been removed. Manual events
    outside Daily Rhythm hours are allowed as long as they have a valid
    range and do not overlap an existing event.

    Args:
        start_time:        Proposed event start (naive datetime).
        end_time:          Proposed event end (naive datetime).
        session:           Active database session.
        exclude_event_id:  Event id to skip during overlap check (used on
                           update so the event does not conflict with itself).

    Returns:
        List of ConflictDetail — empty means no conflicts.
    """
    return _check_event_overlap(start_time, end_time, session, exclude_event_id)


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

    Driven by Daily Rhythm suggestion hours. For each day in the range,
    the service builds the daily suggestion window, collects overlapping
    events, subtracts occupied intervals, and returns the remaining free
    intervals.

    This is a reusable lower-level helper — slot-fitting and triage logic
    layer on top by walking the returned windows. It does not enforce any
    slot duration or grid alignment; callers decide how to consume the
    returned intervals.

    Returns:
        Free windows ordered earliest-first.
    """
    results: List[FreeWindow] = []

    for w_start, w_end in get_suggestion_windows_for_range(start_date, end_date):
        events = session.exec(
            select(Event).where(
                Event.start_time < w_end,
                Event.end_time > w_start,
            )
        ).all()

        occupied: List[Tuple[datetime, datetime]] = [
            (e.start_time, e.end_time) for e in events
        ]

        for s, e in _subtract_intervals(w_start, w_end, occupied):
            results.append(FreeWindow(start_time=s, end_time=e))

    return results


def find_available_slots(
    duration_minutes: int,
    start_date: date,
    end_date: date,
    max_results: int,
    session: Session,
    exclude_event_id: Optional[int] = None,
) -> List[SlotSuggestion]:
    """Return up to max_results conflict-free slots of the requested duration.
    
    Scans each day's Daily Rhythm suggestion window in 30-minute increments.
    The Daily Rhythm window is the single source of truth for which hours we
    suggest in. A candidate slot is valid when it does not overlap any
    existing event.

    Each returned slot includes a deterministic reason_code (EARLIEST_VALID_SLOT)
    and an explanation string. Ranking is simple: earliest valid slots first.
    Rejected candidates are NOT returned in MVP.

    Args:
        duration_minutes:  Required slot length in minutes (>= 1).
        start_date:        First day to scan (inclusive).
        end_date:          Last day to scan (inclusive).
        max_results:       Maximum number of slots to return.
        session:           Active database session.
        exclude_event_id:  Event id to skip during overlap check (used by
                           rescheduling so the target event does not block
                           its own time).

    Returns:
        List of SlotSuggestion ordered earliest first. Empty if none found.
    """
    slot_duration = timedelta(minutes=duration_minutes)
    increment = timedelta(minutes=30)
    results: List[SlotSuggestion] = []

    for window_start, window_end in get_suggestion_windows_for_range(
        start_date, end_date
    ):
        if len(results) >= max_results:
            break

        candidate_start = window_start
        while candidate_start + slot_duration <= window_end:
            candidate_end = candidate_start + slot_duration

            if not _check_event_overlap(
                candidate_start,
                candidate_end,
                session,
                exclude_event_id,
            ):
                results.append(SlotSuggestion(
                    start_time=candidate_start,
                    end_time=candidate_end,
                    reason_code=_SLOT_REASON_CODE,
                    explanation=_SLOT_EXPLANATION,
                ))
                if len(results) >= max_results:
                    break

            candidate_start += increment

    return results
