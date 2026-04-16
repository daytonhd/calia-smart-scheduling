"""CRUD endpoints for availability windows."""

from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, status
from sqlmodel import Session, select

from app.database import get_session
from app.models.availability_window import AvailabilityWindow
from app.schemas.availability import AvailabilityCreate, AvailabilityRead, AvailabilityUpdate

# Single MVP user — auth deferred
MVP_USER_ID = 1

router = APIRouter(prefix="/availability", tags=["availability"])


@router.post("/", response_model=AvailabilityRead, status_code=status.HTTP_201_CREATED)
def create_availability(body: AvailabilityCreate, session: Session = Depends(get_session)):
    window = AvailabilityWindow(user_id=MVP_USER_ID, **body.model_dump())
    session.add(window)
    session.commit()
    session.refresh(window)
    return window


@router.get("/", response_model=List[AvailabilityRead])
def list_availability(
    weekday: Optional[int] = None,
    active: Optional[bool] = None,
    session: Session = Depends(get_session),
):
    query = select(AvailabilityWindow).where(AvailabilityWindow.user_id == MVP_USER_ID)
    if weekday is not None:
        query = query.where(AvailabilityWindow.weekday == weekday)
    if active is not None:
        query = query.where(AvailabilityWindow.active == active)
    query = query.order_by(AvailabilityWindow.weekday, AvailabilityWindow.start_time)
    return session.exec(query).all()


@router.patch("/{window_id}", response_model=AvailabilityRead)
def update_availability(
    window_id: int,
    body: AvailabilityUpdate,
    session: Session = Depends(get_session),
):
    window = session.get(AvailabilityWindow, window_id)
    if not window or window.user_id != MVP_USER_ID:
        raise HTTPException(status_code=404, detail="Availability window not found")

    updates = body.model_dump(exclude_unset=True)

    new_start = updates.get("start_time", window.start_time)
    new_end = updates.get("end_time", window.end_time)
    if new_start >= new_end:
        raise HTTPException(status_code=422, detail="start_time must be before end_time")

    for field, value in updates.items():
        setattr(window, field, value)

    session.add(window)
    session.commit()
    session.refresh(window)
    return window


@router.delete("/{window_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_availability(window_id: int, session: Session = Depends(get_session)):
    window = session.get(AvailabilityWindow, window_id)
    if not window or window.user_id != MVP_USER_ID:
        raise HTTPException(status_code=404, detail="Availability window not found")

    session.delete(window)
    session.commit()
