"""POST and GET endpoints for availability windows."""

from typing import List, Optional

from fastapi import APIRouter, Depends, status
from sqlmodel import Session, select

from app.database import get_session
from app.models.availability_window import AvailabilityWindow
from app.schemas.availability import AvailabilityCreate, AvailabilityRead

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
