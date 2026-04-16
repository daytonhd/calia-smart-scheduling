"""Pydantic schemas for AvailabilityWindow endpoints."""

from datetime import datetime, time
from typing import Optional

from pydantic import model_validator
from sqlmodel import SQLModel


class AvailabilityCreate(SQLModel):
    """Request body for creating an availability window.

    weekday: 0=Monday, 1=Tuesday, ..., 6=Sunday
    start_time / end_time: wall-clock time in HH:MM or HH:MM:SS format
    active: defaults to True; set False to disable without deleting
    """

    weekday: int
    start_time: time
    end_time: time
    active: Optional[bool] = True

    @model_validator(mode="after")
    def validate_window(self):
        if self.weekday < 0 or self.weekday > 6:
            raise ValueError("weekday must be between 0 (Monday) and 6 (Sunday)")
        if self.start_time >= self.end_time:
            raise ValueError("start_time must be before end_time")
        return self


class AvailabilityUpdate(SQLModel):
    """Request body for updating an availability window. All fields optional."""

    weekday: Optional[int] = None
    start_time: Optional[time] = None
    end_time: Optional[time] = None
    active: Optional[bool] = None

    @model_validator(mode="after")
    def validate_window(self):
        if self.weekday is not None and (self.weekday < 0 or self.weekday > 6):
            raise ValueError("weekday must be between 0 (Monday) and 6 (Sunday)")
        if self.start_time is not None and self.end_time is not None:
            if self.start_time >= self.end_time:
                raise ValueError("start_time must be before end_time")
        return self


class AvailabilityRead(SQLModel):
    """Response body for an availability window."""

    id: int
    user_id: int
    weekday: int
    start_time: time
    end_time: time
    active: bool
    created_at: datetime
