"""Schedule endpoints — conflict checking for proposed event placements."""

from fastapi import APIRouter, Depends
from sqlmodel import Session

from app.database import get_session
from app.schemas.schedule import ConflictCheckRequest, ConflictCheckResponse
from app.services.conflict_detection import check_all_conflicts

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
