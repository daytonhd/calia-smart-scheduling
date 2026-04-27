"""CRUD endpoints for blocked times."""

from datetime import datetime, timezone
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, status
from sqlmodel import Session, select

from app.database import get_session
from app.models.blocked_time import BlockedTime
from app.schemas.blocked_time import BlockedTimeCreate, BlockedTimeRead, BlockedTimeUpdate
from app.services.time_contract import ensure_naive_datetime

# Single MVP user — auth deferred
MVP_USER_ID = 1

router = APIRouter(prefix="/blocked-times", tags=["blocked-times"])


@router.post("/", response_model=BlockedTimeRead, status_code=status.HTTP_201_CREATED)
def create_blocked_time(body: BlockedTimeCreate, session: Session = Depends(get_session)):
    blocked = BlockedTime(user_id=MVP_USER_ID, **body.model_dump())
    session.add(blocked)
    session.commit()
    session.refresh(blocked)
    return blocked


@router.get("/", response_model=List[BlockedTimeRead])
def list_blocked_times(
    start_time: Optional[datetime] = None,
    end_time: Optional[datetime] = None,
    session: Session = Depends(get_session),
):
    try:
        start_time = ensure_naive_datetime(start_time, "start_time")
        end_time = ensure_naive_datetime(end_time, "end_time")
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))

    if start_time is not None and end_time is not None and start_time >= end_time:
        raise HTTPException(status_code=400, detail="start_time must be before end_time")

    query = select(BlockedTime).where(BlockedTime.user_id == MVP_USER_ID)

    if start_time is not None:
        query = query.where(BlockedTime.end_time > start_time)
    if end_time is not None:
        query = query.where(BlockedTime.start_time < end_time)

    query = query.order_by(BlockedTime.start_time)
    return session.exec(query).all()


@router.patch("/{blocked_id}", response_model=BlockedTimeRead)
def update_blocked_time(
    blocked_id: int,
    body: BlockedTimeUpdate,
    session: Session = Depends(get_session),
):
    blocked = session.get(BlockedTime, blocked_id)
    if not blocked or blocked.user_id != MVP_USER_ID:
        raise HTTPException(status_code=404, detail="Blocked time not found")

    updates = body.model_dump(exclude_unset=True)

    new_start = updates.get("start_time", blocked.start_time)
    new_end = updates.get("end_time", blocked.end_time)
    if new_start >= new_end:
        raise HTTPException(status_code=422, detail="start_time must be before end_time")

    for field, value in updates.items():
        setattr(blocked, field, value)

    blocked.updated_at = datetime.now(timezone.utc)
    session.add(blocked)
    session.commit()
    session.refresh(blocked)
    return blocked


@router.delete("/{blocked_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_blocked_time(blocked_id: int, session: Session = Depends(get_session)):
    blocked = session.get(BlockedTime, blocked_id)
    if not blocked or blocked.user_id != MVP_USER_ID:
        raise HTTPException(status_code=404, detail="Blocked time not found")

    session.delete(blocked)
    session.commit()
