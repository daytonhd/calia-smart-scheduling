"""CRUD endpoints for calendars."""

from typing import List

from fastapi import APIRouter, Depends, HTTPException, status
from sqlmodel import Session, select

from app.database import get_session
from app.models.calendar import Calendar
from app.schemas.calendar import CalendarCreate, CalendarRead, CalendarUpdate

router = APIRouter(prefix="/calendars", tags=["calendars"])


@router.post("/", response_model=CalendarRead, status_code=status.HTTP_201_CREATED)
def create_calendar(body: CalendarCreate, session: Session = Depends(get_session)):
    # Calendar names are treated as unique in the single-user MVP — the seed
    # script relies on the same invariant (idempotent-by-name).
    existing = session.exec(select(Calendar).where(Calendar.name == body.name)).first()
    if existing:
        raise HTTPException(
            status_code=409,
            detail=f"Calendar named {body.name!r} already exists",
        )
    calendar = Calendar(**body.model_dump())
    session.add(calendar)
    session.commit()
    session.refresh(calendar)
    return calendar


@router.get("/", response_model=List[CalendarRead])
def list_calendars(session: Session = Depends(get_session)):
    return session.exec(select(Calendar).order_by(Calendar.id)).all()


@router.get("/{calendar_id}", response_model=CalendarRead)
def get_calendar(calendar_id: int, session: Session = Depends(get_session)):
    calendar = session.get(Calendar, calendar_id)
    if not calendar:
        raise HTTPException(status_code=404, detail="Calendar not found")
    return calendar


@router.patch("/{calendar_id}", response_model=CalendarRead)
def update_calendar(
    calendar_id: int,
    body: CalendarUpdate,
    session: Session = Depends(get_session),
):
    calendar = session.get(Calendar, calendar_id)
    if not calendar:
        raise HTTPException(status_code=404, detail="Calendar not found")

    updates = body.model_dump(exclude_unset=True)

    # If the name is being changed, keep the unique-by-name invariant.
    new_name = updates.get("name")
    if new_name is not None and new_name != calendar.name:
        clash = session.exec(
            select(Calendar).where(Calendar.name == new_name)
        ).first()
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
def delete_calendar(calendar_id: int, session: Session = Depends(get_session)):
    calendar = session.get(Calendar, calendar_id)
    if not calendar:
        raise HTTPException(status_code=404, detail="Calendar not found")

    session.delete(calendar)
    session.commit()
