"""Pydantic schemas for BlockedTime endpoints."""

from datetime import datetime
from typing import Optional

from pydantic import field_validator, model_validator
from sqlmodel import SQLModel

from app.services.time_contract import ensure_naive_datetime


class BlockedTimeCreate(SQLModel):
    """Request body for creating a blocked time."""

    title: str
    reason: Optional[str] = None
    notes: Optional[str] = None
    start_time: datetime
    end_time: datetime

    @field_validator("start_time", "end_time")
    @classmethod
    def _naive_only(cls, v: datetime) -> datetime:
        return ensure_naive_datetime(v, "start_time/end_time")

    @model_validator(mode="after")
    def validate_time_range(self):
        if self.start_time >= self.end_time:
            raise ValueError("start_time must be before end_time")
        return self


class BlockedTimeUpdate(SQLModel):
    """Request body for updating a blocked time. All fields optional."""

    title: Optional[str] = None
    reason: Optional[str] = None
    notes: Optional[str] = None
    start_time: Optional[datetime] = None
    end_time: Optional[datetime] = None

    @field_validator("start_time", "end_time")
    @classmethod
    def _naive_only(cls, v: Optional[datetime]) -> Optional[datetime]:
        return ensure_naive_datetime(v, "start_time/end_time")

    @model_validator(mode="after")
    def validate_time_range(self):
        if self.start_time is not None and self.end_time is not None:
            if self.start_time >= self.end_time:
                raise ValueError("start_time must be before end_time")
        return self


class BlockedTimeRead(SQLModel):
    """Response body for a blocked time."""

    id: int
    user_id: int
    title: str
    reason: Optional[str] = None
    notes: Optional[str] = None
    start_time: datetime
    end_time: datetime
    created_at: datetime
    updated_at: datetime
