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
