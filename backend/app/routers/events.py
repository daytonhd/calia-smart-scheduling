"""CRUD endpoints for events.

Events are owned through their calendar: a user may only create, read,
update, or delete an event when the parent calendar belongs to them. All
queries are scoped to the authenticated user, and overlap/conflict checks
only consider the user's own events.
"""

from datetime import datetime, timezone
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlmodel import Session, select

from app.database import get_session
from app.models.calendar import Calendar
from app.models.event import Event
from app.models.user import User
from app.routers.auth import get_current_user
from app.schemas.event import EventCreate, EventRead, EventUpdate
from app.services.conflict_detection import check_all_conflicts
from app.services.time_contract import ensure_naive_datetime

router = APIRouter(prefix="/events", tags=["events"])


def _ensure_user_owns_calendar(
    calendar_id: int, user_id: int, session: Session
) -> None:
    """Raise 404 unless the calendar exists AND belongs to user_id."""
    calendar = session.get(Calendar, calendar_id)
    if not calendar or calendar.user_id != user_id:
        raise HTTPException(status_code=404, detail="Calendar not found")


def _get_user_event(event_id: int, user_id: int, session: Session) -> Event:
    """Return the event if it belongs to a calendar owned by user_id; else 404."""
    event = session.get(Event, event_id)
    if event is None:
        raise HTTPException(status_code=404, detail="Event not found")
    calendar = session.get(Calendar, event.calendar_id)
    if calendar is None or calendar.user_id != user_id:
        # Cross-user lookup must look like the event does not exist.
        raise HTTPException(status_code=404, detail="Event not found")
    return event


@router.post("/", response_model=EventRead, status_code=status.HTTP_201_CREATED)
def create_event(
    body: EventCreate,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
):
    _ensure_user_owns_calendar(body.calendar_id, current_user.id, session)

    conflicts = check_all_conflicts(
        body.start_time, body.end_time, session, user_id=current_user.id
    )
    if conflicts and not body.allow_conflicts:
        raise HTTPException(
            status_code=409,
            detail={"conflicts": [c.model_dump(mode="json") for c in conflicts]},
        )

    # allow_conflicts is a request-only override flag — exclude it before
    # constructing the Event, which has no such column.
    event = Event(**body.model_dump(exclude={"allow_conflicts"}))
    session.add(event)
    session.commit()
    session.refresh(event)
    return event


@router.get("/", response_model=List[EventRead])
def list_events(
    calendar_id: Optional[int] = Query(default=None, description="Filter by calendar"),
    start_time: Optional[datetime] = Query(
        default=None,
        description="Return events that overlap [start_time, end_time). Both required together.",
    ),
    end_time: Optional[datetime] = Query(default=None),
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
):
    try:
        start_time = ensure_naive_datetime(start_time, "start_time")
        end_time = ensure_naive_datetime(end_time, "end_time")
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))

    if start_time is not None and end_time is not None and start_time >= end_time:
        raise HTTPException(status_code=400, detail="start_time must be before end_time")

    # Always join through Calendar so cross-user events are never returned.
    query = (
        select(Event)
        .join(Calendar, Event.calendar_id == Calendar.id)
        .where(Calendar.user_id == current_user.id)
    )
    if calendar_id is not None:
        # When a calendar filter is supplied, also ensure it belongs to the
        # user — otherwise an unauthorized id would silently produce empty
        # results, which can mask bugs.
        _ensure_user_owns_calendar(calendar_id, current_user.id, session)
        query = query.where(Event.calendar_id == calendar_id)
    # Half-open overlap window: event.end > start AND event.start < end.
    if start_time is not None:
        query = query.where(Event.end_time > start_time)
    if end_time is not None:
        query = query.where(Event.start_time < end_time)

    query = query.order_by(Event.start_time)
    return session.exec(query).all()


@router.get("/{event_id}", response_model=EventRead)
def get_event(
    event_id: int,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
):
    return _get_user_event(event_id, current_user.id, session)


@router.patch("/{event_id}", response_model=EventRead)
def update_event(
    event_id: int,
    body: EventUpdate,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
):
    event = _get_user_event(event_id, current_user.id, session)

    # allow_conflicts is a request-only override flag — exclude it from the
    # fields applied to the Event, which has no such column.
    updates = body.model_dump(exclude_unset=True, exclude={"allow_conflicts"})

    # If updating calendar_id, verify the destination calendar belongs to
    # the same user — never let a user move an event onto another user's
    # calendar.
    if "calendar_id" in updates:
        _ensure_user_owns_calendar(updates["calendar_id"], current_user.id, session)

    # If only one of start/end is being updated, cross-validate against the
    # existing value so we never end up with start >= end.
    new_start = updates.get("start_time", event.start_time)
    new_end = updates.get("end_time", event.end_time)
    if new_start >= new_end:
        raise HTTPException(
            status_code=422,
            detail="start_time must be before end_time",
        )

    conflicts = check_all_conflicts(
        new_start,
        new_end,
        session,
        user_id=current_user.id,
        exclude_event_id=event_id,
    )
    if conflicts and not body.allow_conflicts:
        raise HTTPException(
            status_code=409,
            detail={"conflicts": [c.model_dump(mode="json") for c in conflicts]},
        )

    for field, value in updates.items():
        setattr(event, field, value)

    event.updated_at = datetime.now(timezone.utc)
    session.add(event)
    session.commit()
    session.refresh(event)
    return event


@router.delete("/{event_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_event(
    event_id: int,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
):
    event = _get_user_event(event_id, current_user.id, session)
    session.delete(event)
    session.commit()
