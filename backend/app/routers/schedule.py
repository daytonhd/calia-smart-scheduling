"""Schedule endpoints — conflict checking and slot suggestions."""

from datetime import date, timedelta
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlmodel import Session, select

from app.database import get_session
from app.models.schedule_summary import ScheduleSummary
from app.schemas.schedule import (
    ConflictCheckRequest,
    ConflictCheckResponse,
    ScheduleSummaryRead,
    SuggestSlotsRequest,
    SuggestSlotsResponse,
    WeeklyMetricsResponse,
)
from app.services.conflict_detection import MVP_USER_ID, check_all_conflicts, find_available_slots
from app.services.metrics import compute_weekly_metrics, monday_of

router = APIRouter(prefix="/schedule", tags=["schedule"])


@router.post("/check-conflict", response_model=ConflictCheckResponse)
def check_conflict(
    body: ConflictCheckRequest,
    session: Session = Depends(get_session),
):
    """Check whether a proposed event placement has any scheduling conflicts.

    Returns all detected conflicts (event overlap, blocked time overlap, outside
    availability). An empty conflicts list means the placement is clean.
    """
    conflicts = check_all_conflicts(
        start_time=body.start_time,
        end_time=body.end_time,
        session=session,
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
):
    """Return up to max_results conflict-free time slots of the requested duration.

    Scans availability windows in 30-minute increments over the given date range
    (defaults to the next 7 days). Returns earliest valid slots first.
    A slot is valid when it has no event overlap, no blocked-time overlap, and is
    fully contained within an active availability window.
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
):
    """Return weekly scheduling metrics for the single MVP user.

    Counts and minutes are clipped to the target week [Mon 00:00, next Mon 00:00).
    """
    return compute_weekly_metrics(session=session, week_start=week_start)


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
):
    """Return the stored weekly AI summary for the given week.

    This is a read-only endpoint — no LLM is invoked. Returns 404 when no
    summary has been saved for the target week.
    """
    anchor = week_start or date.today()
    ws = monday_of(anchor)

    summary = session.exec(
        select(ScheduleSummary)
        .where(ScheduleSummary.user_id == MVP_USER_ID)
        .where(ScheduleSummary.week_start == ws)
        .order_by(ScheduleSummary.created_at.desc())
    ).first()

    if summary is None:
        raise HTTPException(
            status_code=404,
            detail=f"No saved weekly summary for week starting {ws.isoformat()}",
        )
    return summary
