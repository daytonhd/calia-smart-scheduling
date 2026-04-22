"""CRUD endpoints for events."""

from datetime import datetime, timezone
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlmodel import Session, select

from app.database import get_session
from app.models.calendar import Calendar
from app.models.event import Event
from app.schemas.event import EventCreate, EventRead, EventUpdate
from app.services.conflict_detection import check_all_conflicts

router = APIRouter(prefix="/events", tags=["events"])


def _ensure_calendar_exists(calendar_id: int, session: Session) -> None:
    """Raise 404 if the referenced calendar does not exist."""
    if not session.get(Calendar, calendar_id):
        raise HTTPException(status_code=404, detail="Calendar not found")


@router.post("/", response_model=EventRead, status_code=status.HTTP_201_CREATED)
def create_event(body: EventCreate, session: Session = Depends(get_session)):
    _ensure_calendar_exists(body.calendar_id, session)

    conflicts = check_all_conflicts(body.start_time, body.end_time, session)
    if conflicts:
        raise HTTPException(
            status_code=409,
            detail={"conflicts": [c.model_dump() for c in conflicts]},
        )

    event = Event(**body.model_dump())
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
):
    if start_time is not None and end_time is not None and start_time >= end_time:
        raise HTTPException(status_code=400, detail="start_time must be before end_time")

    query = select(Event)
    if calendar_id is not None:
        query = query.where(Event.calendar_id == calendar_id)
    # Half-open overlap window: event.end > start AND event.start < end.
    if start_time is not None:
        query = query.where(Event.end_time > start_time)
    if end_time is not None:
        query = query.where(Event.start_time < end_time)

    query = query.order_by(Event.start_time)
    return session.exec(query).all()


@router.get("/{event_id}", response_model=EventRead)
def get_event(event_id: int, session: Session = Depends(get_session)):
    event = session.get(Event, event_id)
    if not event:
        raise HTTPException(status_code=404, detail="Event not found")
    return event


@router.patch("/{event_id}", response_model=EventRead)
def update_event(
    event_id: int,
    body: EventUpdate,
    session: Session = Depends(get_session),
):
    event = session.get(Event, event_id)
    if not event:
        raise HTTPException(status_code=404, detail="Event not found")

    updates = body.model_dump(exclude_unset=True)

    # If updating calendar_id, verify the new calendar exists
    if "calendar_id" in updates:
        _ensure_calendar_exists(updates["calendar_id"], session)

    # If only one of start/end is being updated, cross-validate against the
    # existing value so we never end up with start >= end.
    new_start = updates.get("start_time", event.start_time)
    new_end = updates.get("end_time", event.end_time)
    if new_start >= new_end:
        raise HTTPException(
            status_code=422,
            detail="start_time must be before end_time",
        )

    conflicts = check_all_conflicts(new_start, new_end, session, exclude_event_id=event_id)
    if conflicts:
        raise HTTPException(
            status_code=409,
            detail={"conflicts": [c.model_dump() for c in conflicts]},
        )

    for field, value in updates.items():
        setattr(event, field, value)

    event.updated_at = datetime.now(timezone.utc)
    session.add(event)
    session.commit()
    session.refresh(event)
    return event


@router.delete("/{event_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_event(event_id: int, session: Session = Depends(get_session)):
    event = session.get(Event, event_id)
    if not event:
        raise HTTPException(status_code=404, detail="Event not found")

    session.delete(event)
    session.commit()
