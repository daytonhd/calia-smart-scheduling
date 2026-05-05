"""CRUD endpoints for availability windows.

DEPRECATED — TRANSITIONAL LEGACY SUPPORT
----------------------------------------
These endpoints (and the underlying ``AvailabilityWindow`` rows) are retained
for backward compatibility during a transition period. They are no longer used
by active scheduling logic:

* Active scheduling uses the user's Daily Rhythm defaults plus event-based
  occupied time as the authoritative occupied/free signal.
* Slot suggestions and replacement options no longer require any
  ``AvailabilityWindow`` rows to exist; placements outside such rows are not
  flagged as conflicts.
* Existing clients can continue to call these routes without breaking, but new
  scheduling features should not depend on them.

These endpoints will be removed in a future cleanup pass once all clients have
migrated.
"""

from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, status
from sqlmodel import Session, select

from app.database import get_session
from app.models.availability_window import AvailabilityWindow
from app.schemas.availability import AvailabilityCreate, AvailabilityRead, AvailabilityUpdate

# Single MVP user — auth deferred
MVP_USER_ID = 1

# All routes in this router are flagged ``deprecated=True`` so they appear as
# struck-through in the generated OpenAPI / Swagger UI. Active scheduling logic
# (Daily Rhythm + event-based occupied time) does not depend on them.
router = APIRouter(prefix="/availability", tags=["availability"])

_DEPRECATION_NOTE = (
    "**Deprecated — transitional legacy support.** Active scheduling logic uses "
    "Daily Rhythm defaults and event-based occupied time. Slot suggestions and "
    "replacement options do not require AvailabilityWindow rows. This endpoint "
    "remains callable for backward compatibility during the transition and may "
    "be removed in a future release."
)


@router.post(
    "/",
    response_model=AvailabilityRead,
    status_code=status.HTTP_201_CREATED,
    deprecated=True,
    description=_DEPRECATION_NOTE,
)
def create_availability(body: AvailabilityCreate, session: Session = Depends(get_session)):
    window = AvailabilityWindow(user_id=MVP_USER_ID, **body.model_dump())
    session.add(window)
    session.commit()
    session.refresh(window)
    return window


@router.get(
    "/",
    response_model=List[AvailabilityRead],
    deprecated=True,
    description=_DEPRECATION_NOTE,
)
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


@router.patch(
    "/{window_id}",
    response_model=AvailabilityRead,
    deprecated=True,
    description=_DEPRECATION_NOTE,
)
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


@router.delete(
    "/{window_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    deprecated=True,
    description=_DEPRECATION_NOTE,
)
def delete_availability(window_id: int, session: Session = Depends(get_session)):
    window = session.get(AvailabilityWindow, window_id)
    if not window or window.user_id != MVP_USER_ID:
        raise HTTPException(status_code=404, detail="Availability window not found")

    session.delete(window)
    session.commit()
