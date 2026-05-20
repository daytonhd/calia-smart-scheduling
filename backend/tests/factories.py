"""Tiny factories to keep scheduling tests terse and explicit.

All datetimes are naive. Tests anchor on Monday 2026-04-20 (weekday = 0)
unless stated otherwise.

User wiring: every calendar must belong to a user. `make_user` creates one
on demand; `make_calendar` auto-creates a default user (id = DEFAULT_USER_ID)
when one is not supplied, which keeps existing single-user tests terse.
Multi-user tests should call `make_user` for the second user explicitly.
"""

from datetime import datetime
from typing import Optional

from sqlmodel import Session

from app.models.calendar import Calendar
from app.models.event import Event
from app.models.user import User

DEFAULT_USER_ID = 1


def make_user(
    session: Session,
    name: str = "Test User",
    email: str = "test@example.com",
    user_id: Optional[int] = None,
) -> User:
    """Create and persist a User.

    `user_id` is optional; supply it to pin the primary key (needed when
    a test wants to reuse the DEFAULT_USER_ID sentinel). Otherwise the
    database assigns the next id.
    """
    user = User(
        name=name,
        email=email,
        hashed_password="!test",
    )
    if user_id is not None:
        user.id = user_id
    session.add(user)
    session.commit()
    session.refresh(user)
    return user


def ensure_default_user(session: Session) -> User:
    """Return the User with id = DEFAULT_USER_ID, creating it if missing."""
    user = session.get(User, DEFAULT_USER_ID)
    if user is None:
        user = make_user(session, user_id=DEFAULT_USER_ID)
    return user


def make_calendar(
    session: Session,
    name: str = "Default",
    user_id: Optional[int] = None,
) -> Calendar:
    """Create a calendar. Auto-creates a default user when user_id is None."""
    if user_id is None:
        user_id = ensure_default_user(session).id
    cal = Calendar(name=name, user_id=user_id)
    session.add(cal)
    session.commit()
    session.refresh(cal)
    return cal


def make_event(
    session: Session,
    calendar_id: int,
    start: datetime,
    end: datetime,
    title: str = "Event",
    category: Optional[str] = None,
) -> Event:
    ev = Event(
        calendar_id=calendar_id,
        title=title,
        start_time=start,
        end_time=end,
        category=category,
    )
    session.add(ev)
    session.commit()
    session.refresh(ev)
    return ev
