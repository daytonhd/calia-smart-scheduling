"""CRUD endpoints for blocked times.

DEPRECATED — TRANSITIONAL LEGACY SUPPORT
----------------------------------------
These endpoints (and the underlying ``BlockedTime`` rows) are retained for
backward compatibility during a transition period. They are no longer driven
by an active user-facing workflow:

* The user-facing blocked-time workflow is being replaced by categorized
  events / schedule items, where "blocked" is one category among many.
* Active scheduling logic should not depend on ``BlockedTime`` as the primary
  occupied-time model; event-based occupied time plus Daily Rhythm defaults
  are the authoritative signal.
* Existing clients can continue to call these routes without breaking, but
  new scheduling features should not depend on them.

These endpoints will be removed in a future cleanup pass once categorized
events fully replace the legacy blocked-time concept.
"""

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

# All routes in this router are flagged ``deprecated=True`` so they appear as
# struck-through in the generated OpenAPI / Swagger UI. Active scheduling logic
# does not depend on them.
router = APIRouter(prefix="/blocked-times", tags=["blocked-times"])

_DEPRECATION_NOTE = (
    "**Deprecated — transitional legacy support.** The user-facing blocked-time "
    "workflow is being replaced by categorized events / schedule items. Active "
    "scheduling logic does not depend on BlockedTime as the primary occupied-time "
    "model. This endpoint remains callable for backward compatibility during the "
    "transition and may be removed in a future release."
)


@router.post(
    "/",
    response_model=BlockedTimeRead,
    status_code=status.HTTP_201_CREATED,
    deprecated=True,
    description=_DEPRECATION_NOTE,
)
def create_blocked_time(body: BlockedTimeCreate, session: Session = Depends(get_session)):
    blocked = BlockedTime(user_id=MVP_USER_ID, **body.model_dump())
    session.add(blocked)
    session.commit()
    session.refresh(blocked)
    return blocked


@router.get(
    "/",
    response_model=List[BlockedTimeRead],
    deprecated=True,
    description=_DEPRECATION_NOTE,
)
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


@router.patch(
    "/{blocked_id}",
    response_model=BlockedTimeRead,
    deprecated=True,
    description=_DEPRECATION_NOTE,
)
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


@router.delete(
    "/{blocked_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    deprecated=True,
    description=_DEPRECATION_NOTE,
)
def delete_blocked_time(blocked_id: int, session: Session = Depends(get_session)):
    blocked = session.get(BlockedTime, blocked_id)
    if not blocked or blocked.user_id != MVP_USER_ID:
        raise HTTPException(status_code=404, detail="Blocked time not found")

    session.delete(blocked)
    session.commit()
