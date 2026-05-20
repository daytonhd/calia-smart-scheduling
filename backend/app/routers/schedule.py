"""Schedule endpoints — conflict checking and slot suggestions.

Every endpoint is scoped to the authenticated user. Conflict checks, slot
suggestions, replacement options, metrics, balance/triage, and saved weekly
summaries only ever consider the current user's calendars, events, daily
rhythm, and stored summaries.
"""

from datetime import date, timedelta
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlmodel import Session, select

from app.database import get_session
from app.models.calendar import Calendar
from app.models.schedule_summary import ScheduleSummary
from app.models.user import User
from app.routers.auth import get_current_user
from app.schemas.schedule import (
    ConflictCheckRequest,
    ConflictCheckResponse,
    ProposedRescheduleOptionsRequest,
    ProposedRescheduleOptionsResponse,
    RescheduleOptionsRequest,
    RescheduleOptionsResponse,
    ScheduleSummaryRead,
    SuggestSlotsRequest,
    SuggestSlotsResponse,
    TriageResponse,
    WeeklyMetricsResponse,
)
from app.services.conflict_detection import check_all_conflicts, find_available_slots
from app.services.metrics import compute_weekly_metrics, monday_of
from app.services.rescheduling import (
    find_replacement_slots,
    find_replacement_slots_for_proposed,
)
from app.services.triage import compute_weekly_triage

router = APIRouter(prefix="/schedule", tags=["schedule"])


@router.post("/check-conflict", response_model=ConflictCheckResponse)
def check_conflict(
    body: ConflictCheckRequest,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
):
    """Check whether a proposed event placement has any scheduling conflicts.

    Only the current user's events are consulted; cross-user collisions are
    never reported. Returns all detected conflicts. The active conflict type
    is event overlap. Placements outside Daily Rhythm hours are NOT flagged
    here. An empty conflicts list means the placement is clean.
    """
    conflicts = check_all_conflicts(
        start_time=body.start_time,
        end_time=body.end_time,
        session=session,
        user_id=current_user.id,
        exclude_event_id=body.exclude_event_id,
    )
    return ConflictCheckResponse(
        has_conflicts=len(conflicts) > 0,
        conflicts=conflicts,
    )


@router.post("/suggest-slots", response_model=SuggestSlotsResponse)
def suggest_slots(
    body: SuggestSlotsRequest,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
):
    """Return up to max_results conflict-free time slots of the requested duration.

    Scans the current user's Daily Rhythm suggestion hours in 30-minute
    increments over the given date range (defaults to the next 7 days).
    Returns earliest valid slots first. A slot is valid when it does not
    overlap an existing event on the user's own calendars.
    """
    today = date.today()
    start = body.start_date or today
    end = body.end_date or (start + timedelta(days=6))

    slots = find_available_slots(
        duration_minutes=body.duration_minutes,
        start_date=start,
        end_date=end,
        max_results=body.max_results,
        session=session,
        user_id=current_user.id,
    )
    return SuggestSlotsResponse(slots=slots)


@router.get("/metrics", response_model=WeeklyMetricsResponse)
def weekly_metrics(
    week_start: Optional[date] = Query(
        default=None,
        description=(
            "Any date inside the target week; snapped to that week's Monday. "
            "Defaults to the current week."
        ),
    ),
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
):
    """Return weekly scheduling metrics for the authenticated user.

    Counts and minutes are clipped to the target week [Mon 00:00, next Mon 00:00).
    """
    return compute_weekly_metrics(
        session=session, user_id=current_user.id, week_start=week_start
    )


@router.post("/reschedule-options", response_model=RescheduleOptionsResponse)
def reschedule_options(
    body: RescheduleOptionsRequest,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
):
    """Return ranked replacement slots for an existing event.

    The target event must belong to one of the current user's calendars;
    otherwise the endpoint returns 404. Candidate slots are scanned inside
    the user's Daily Rhythm suggestion hours, preserve the event's duration,
    and avoid existing events on the user's own calendars. The target event
    is excluded from event-overlap checks. Does NOT modify the event.
    """
    result = find_replacement_slots(
        event_id=body.event_id,
        search_start=body.search_start,
        search_end=body.search_end,
        max_results=body.max_results,
        session=session,
        user_id=current_user.id,
    )
    if result is None:
        raise HTTPException(status_code=404, detail="Event not found")
    return result


@router.post(
    "/proposed-reschedule-options",
    response_model=ProposedRescheduleOptionsResponse,
)
def proposed_reschedule_options(
    body: ProposedRescheduleOptionsRequest,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
):
    """Return ranked replacement slots for an unsaved proposed event.

    Mirrors POST /schedule/reschedule-options but for an event that has not
    been saved yet (typically because the initial create attempt produced a
    409 conflict). Candidate slots are scanned inside the user's Daily
    Rhythm suggestion hours, preserve the duration derived from the
    proposed start/end, and avoid existing events on the user's own
    calendars. The proposed event is NOT persisted — callers receive
    candidate options only and must still issue a POST /events/ to save.

    Returns 404 when calendar_id does not reference one of the user's
    calendars.
    """
    calendar = session.get(Calendar, body.calendar_id)
    if calendar is None or calendar.user_id != current_user.id:
        raise HTTPException(status_code=404, detail="Calendar not found")

    return find_replacement_slots_for_proposed(
        title=body.title,
        start_time=body.start_time,
        end_time=body.end_time,
        search_start=body.search_start,
        search_end=body.search_end,
        max_results=body.max_results,
        session=session,
        user_id=current_user.id,
    )


@router.get("/triage", response_model=TriageResponse)
def weekly_triage(
    week_start: Optional[date] = Query(
        default=None,
        description=(
            "Any date inside the target week; snapped to that week's Monday. "
            "Defaults to the current week."
        ),
    ),
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
):
    """Return per-day Schedule Balance diagnostics for a 7-day window
    starting Monday.

    Surfaces overloaded days, fragmented days, weak buffer capacity, and
    the longest free window per day for the authenticated user only.
    Free Capacity is bounded by Daily Rhythm suggestion hours and computed
    by subtracting the user's own events from each day's window.
    """
    anchor = week_start or date.today()
    ws = monday_of(anchor)
    return compute_weekly_triage(
        session=session, week_start=ws, user_id=current_user.id
    )


@router.get("/weekly-summary", response_model=ScheduleSummaryRead)
def get_weekly_summary(
    week_start: Optional[date] = Query(
        default=None,
        description=(
            "Any date inside the target week; snapped to that week's Monday. "
            "Defaults to the current week."
        ),
    ),
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
):
    """Return the stored weekly AI summary for the authenticated user.

    This is a read-only endpoint — no LLM is invoked. Returns 404 when no
    summary has been saved for the target week for this user.
    """
    anchor = week_start or date.today()
    ws = monday_of(anchor)

    summary = session.exec(
        select(ScheduleSummary)
        .where(ScheduleSummary.user_id == current_user.id)
        .where(ScheduleSummary.week_start == ws)
        .order_by(ScheduleSummary.created_at.desc())
    ).first()

    if summary is None:
        raise HTTPException(
            status_code=404,
            detail=f"No saved weekly summary for week starting {ws.isoformat()}",
        )
    return summary
