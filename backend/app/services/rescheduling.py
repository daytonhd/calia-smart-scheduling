"""Adaptive rescheduling — find replacement slots for one selected event.

Replacement candidates are scanned inside Daily Rhythm suggestion hours
(8 AM–9 PM by default) via find_available_slots. They preserve the source
event's duration and avoid existing events and (transitionally) blocked
times. AvailabilityWindow rows are not consulted. The selected event is
excluded from the event-overlap check so its current placement does not
"conflict with itself".

Ranking is simple and deterministic:
  1. Same-day replacement slots (same calendar date as the event's original
     start) come before any other day.
  2. Within each group, earliest start time wins.

This service does NOT mutate the event — callers receive candidate options
only and decide whether to act on them.
"""

from datetime import datetime, timedelta
from typing import List, Optional

from sqlmodel import Session

from app.models.event import Event
from app.services.conflict_detection import find_available_slots

# Hard cap so callers cannot make us scan a runaway range. Tunable here.
MAX_RESULTS_HARD_CAP = 50

# Internal scan ceiling — find_available_slots returns ranked earliest-first
# candidates; we ask for a generous pool then re-rank/clip to satisfy the
# same-day-first ordering before slicing to the caller's max_results.
_INTERNAL_SCAN_LIMIT = 200


def _rank_replacement_options(
    *,
    duration_minutes: int,
    original_start: datetime,
    search_start: datetime,
    search_end: datetime,
    max_results: int,
    session: Session,
    exclude_event_id: Optional[int],
) -> List[dict]:
    """Shared core: scan candidate slots and rank them.

    Caller is responsible for any 404/validation concerns and for clamping
    max_results before invoking this helper.
    """
    original_date = original_start.date()
    scan_start_date = search_start.date()
    scan_end_date = search_end.date()

    raw = find_available_slots(
        duration_minutes=duration_minutes,
        start_date=scan_start_date,
        end_date=scan_end_date,
        max_results=_INTERNAL_SCAN_LIMIT,
        session=session,
        exclude_event_id=exclude_event_id,
    )

    # Filter to the requested datetime window. find_available_slots returns
    # whole days; clip to [search_start, search_end].
    in_window = [
        s for s in raw
        if s.start_time >= search_start and s.end_time <= search_end
    ]

    # Re-rank: same-day-first, then earliest start. Stable sort preserves the
    # earliest-first order within each group.
    in_window.sort(
        key=lambda s: (0 if s.start_time.date() == original_date else 1,
                       s.start_time)
    )

    options: List[dict] = []
    for idx, slot in enumerate(in_window[:max_results]):
        same_day = slot.start_time.date() == original_date
        delta_min = int(
            (slot.start_time - original_start).total_seconds() // 60
        )
        if same_day:
            reason_code = "SAME_DAY_REPLACEMENT"
        elif idx == 0:
            reason_code = "EARLIEST_VALID_REPLACEMENT"
        else:
            reason_code = "VALID_REPLACEMENT_SLOT"
        options.append({
            "rank": idx + 1,
            "start_time": slot.start_time,
            "end_time": slot.end_time,
            "reason_code": reason_code,
            "explanation": (
                "Selected because it preserves the event duration, fits "
                "your daily suggestion hours, and avoids existing events "
                "and blocked times."
            ),
            "minutes_from_original_start": delta_min,
        })

    return options


def find_replacement_slots(
    event_id: int,
    search_start: datetime,
    search_end: datetime,
    max_results: int,
    session: Session,
) -> Optional[dict]:
    """Return ranked replacement options for one event.

    Args:
        event_id:      Existing event id to reschedule.
        search_start:  Inclusive lower bound on candidate start time (naive).
        search_end:    Exclusive upper bound on candidate end time (naive).
        max_results:   Maximum number of options to return (clamped to
                       MAX_RESULTS_HARD_CAP, must be >= 1).
        session:       Active database session.

    Returns:
        dict matching RescheduleOptionsResponse, or None if the event does
        not exist (callers should translate None to a 404).
    """
    if max_results < 1:
        max_results = 1
    if max_results > MAX_RESULTS_HARD_CAP:
        max_results = MAX_RESULTS_HARD_CAP

    event = session.get(Event, event_id)
    if event is None:
        return None

    duration = event.end_time - event.start_time
    duration_minutes = int(duration.total_seconds() // 60)

    options = _rank_replacement_options(
        duration_minutes=duration_minutes,
        original_start=event.start_time,
        search_start=search_start,
        search_end=search_end,
        max_results=max_results,
        session=session,
        exclude_event_id=event_id,
    )

    return {
        "event_id": event.id,
        "event_title": event.title,
        "duration_minutes": duration_minutes,
        "options": options,
    }


def find_replacement_slots_for_proposed(
    title: str,
    start_time: datetime,
    end_time: datetime,
    search_start: datetime,
    search_end: datetime,
    max_results: int,
    session: Session,
) -> dict:
    """Return ranked replacement options for an unsaved proposed event.

    Mirrors find_replacement_slots but does not require an event_id — the
    proposed event is not stored, so there is nothing to exclude from the
    overlap check. Caller validates calendar_id and time-range invariants
    before calling.

    Args:
        title:         Proposed event title (echoed back in the response).
        start_time:    Original proposed start (naive).
        end_time:      Original proposed end (naive). Defines the duration
                       that every returned option preserves.
        search_start:  Inclusive lower bound on candidate start time (naive).
        search_end:    Exclusive upper bound on candidate end time (naive).
        max_results:   Maximum number of options to return (clamped to
                       MAX_RESULTS_HARD_CAP, must be >= 1).
        session:       Active database session.

    Returns:
        dict matching ProposedRescheduleOptionsResponse.
    """
    if max_results < 1:
        max_results = 1
    if max_results > MAX_RESULTS_HARD_CAP:
        max_results = MAX_RESULTS_HARD_CAP

    duration = end_time - start_time
    duration_minutes = int(duration.total_seconds() // 60)

    options = _rank_replacement_options(
        duration_minutes=duration_minutes,
        original_start=start_time,
        search_start=search_start,
        search_end=search_end,
        max_results=max_results,
        session=session,
        exclude_event_id=None,
    )

    return {
        "event_title": title,
        "duration_minutes": duration_minutes,
        "options": options,
    }
