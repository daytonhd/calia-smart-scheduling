"""Tiny factories to keep scheduling tests terse and explicit.

All datetimes are naive. Availability windows belong to MVP_USER_ID (= 1).
Tests anchor on Monday 2026-04-20 (weekday = 0) unless stated otherwise.
"""

from datetime import datetime, time

from sqlmodel import Session

from app.models.calendar import Calendar
from app.models.event import Event
from app.services.conflict_detection import MVP_USER_ID


def make_calendar(session: Session, name: str = "Default") -> Calendar:
    cal = Calendar(name=name)
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
) -> Event:
    ev = Event(calendar_id=calendar_id, title=title, start_time=start, end_time=end)
    session.add(ev)
    session.commit()
    session.refresh(ev)
    return ev
