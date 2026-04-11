"""Pydantic schemas for Event endpoints."""

from datetime import datetime
from typing import Optional

from pydantic import model_validator
from sqlmodel import SQLModel


class EventCreate(SQLModel):
    """Request body for creating an event."""

    calendar_id: int
    title: str
    description: Optional[str] = None
    category: Optional[str] = None
    priority: Optional[str] = None
    location: Optional[str] = None
    start_time: datetime
    end_time: datetime

    @model_validator(mode="after")
    def validate_time_range(self):
        if self.start_time >= self.end_time:
            raise ValueError("start_time must be before end_time")
        return self


class EventUpdate(SQLModel):
    """Request body for updating an event. All fields optional."""

    calendar_id: Optional[int] = None
    title: Optional[str] = None
    description: Optional[str] = None
    category: Optional[str] = None
    priority: Optional[str] = None
    location: Optional[str] = None
    start_time: Optional[datetime] = None
    end_time: Optional[datetime] = None

    @model_validator(mode="after")
    def validate_time_range(self):
        # Only validate if both times are provided in the update
        if self.start_time is not None and self.end_time is not None:
            if self.start_time >= self.end_time:
                raise ValueError("start_time must be before end_time")
        return self


class EventRead(SQLModel):
    """Response body for an event."""

    id: int
    calendar_id: int
    title: str
    description: Optional[str] = None
    category: Optional[str] = None
    priority: Optional[str] = None
    location: Optional[str] = None
    start_time: datetime
    end_time: datetime
    created_at: datetime
    updated_at: datetime
