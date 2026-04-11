"""Pydantic schemas for Calendar endpoints."""

from datetime import datetime
from typing import Optional

from sqlmodel import SQLModel


class CalendarCreate(SQLModel):
    """Request body for creating a calendar."""

    name: str
    color: Optional[str] = None


class CalendarUpdate(SQLModel):
    """Request body for updating a calendar. All fields optional."""

    name: Optional[str] = None
    color: Optional[str] = None


class CalendarRead(SQLModel):
    """Response body for a calendar."""

    id: int
    name: str
    color: Optional[str] = None
    created_at: datetime
