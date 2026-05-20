"""CRUD endpoints for calendars.

All routes are scoped to the authenticated user: a user only ever sees and
modifies their own calendars. Calendar names are unique per user — two
users may both have a calendar named "Main calendar".
"""

from typing import List

from fastapi import APIRouter, Depends, HTTPException, status
from sqlmodel import Session, select

from app.database import get_session
from app.models.calendar import Calendar
from app.models.event import Event
from app.models.user import User
from app.routers.auth import get_current_user
from app.schemas.calendar import CalendarCreate, CalendarRead, CalendarUpdate

router = APIRouter(prefix="/calendars", tags=["calendars"])


def _find_user_calendar_by_name(
    session: Session, user_id: int, name: str
) -> Calendar:
    return session.exec(
        select(Calendar).where(
            Calendar.user_id == user_id,
            Calendar.name == name,
        )
    ).first()


@router.post("/", response_model=CalendarRead, status_code=status.HTTP_201_CREATED)
def create_calendar(
    body: CalendarCreate,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
):
    # Calendar names are unique per user. Two users may both have "Main calendar".
    existing = _find_user_calendar_by_name(session, current_user.id, body.name)
    if existing:
        raise HTTPException(
            status_code=409,
            detail=f"Calendar named {body.name!r} already exists",
        )
    calendar = Calendar(**body.model_dump(), user_id=current_user.id)
    session.add(calendar)
    session.commit()
    session.refresh(calendar)
    return calendar


@router.get("/", response_model=List[CalendarRead])
def list_calendars(
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
):
    return session.exec(
        select(Calendar)
        .where(Calendar.user_id == current_user.id)
        .order_by(Calendar.id)
    ).all()


@router.get("/{calendar_id}", response_model=CalendarRead)
def get_calendar(
    calendar_id: int,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
):
    calendar = session.get(Calendar, calendar_id)
    # Cross-user reads return 404, not 403 — never leak existence.
    if not calendar or calendar.user_id != current_user.id:
        raise HTTPException(status_code=404, detail="Calendar not found")
    return calendar


@router.patch("/{calendar_id}", response_model=CalendarRead)
def update_calendar(
    calendar_id: int,
    body: CalendarUpdate,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
):
    calendar = session.get(Calendar, calendar_id)
    if not calendar or calendar.user_id != current_user.id:
        raise HTTPException(status_code=404, detail="Calendar not found")

    updates = body.model_dump(exclude_unset=True)

    # If the name is being changed, keep the per-user unique-by-name invariant.
    new_name = updates.get("name")
    if new_name is not None and new_name != calendar.name:
        clash = _find_user_calendar_by_name(session, current_user.id, new_name)
        if clash:
            raise HTTPException(
                status_code=409,
                detail=f"Calendar named {new_name!r} already exists",
            )

    for field, value in updates.items():
        setattr(calendar, field, value)

    session.add(calendar)
    session.commit()
    session.refresh(calendar)
    return calendar


@router.delete("/{calendar_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_calendar(
    calendar_id: int,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
):
    calendar = session.get(Calendar, calendar_id)
    if not calendar or calendar.user_id != current_user.id:
        raise HTTPException(status_code=404, detail="Calendar not found")

    # Block deletion when events still reference this calendar — otherwise
    # Postgres raises a ForeignKeyViolation and the request 500s.
    referenced = session.exec(
        select(Event.id).where(Event.calendar_id == calendar_id).limit(1)
    ).first()
    if referenced is not None:
        raise HTTPException(
            status_code=409,
            detail=(
                "Cannot delete calendar because it has existing events. "
                "Delete or move those events first."
            ),
        )

    session.delete(calendar)
    session.commit()
