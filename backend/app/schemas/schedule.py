"""Schemas for schedule-related endpoints."""

from datetime import datetime
from typing import List, Optional

from pydantic import model_validator
from sqlmodel import SQLModel


class ConflictCheckRequest(SQLModel):
    """Request body for checking scheduling conflicts for a proposed event placement."""

    calendar_id: int
    start_time: datetime
    end_time: datetime
    exclude_event_id: Optional[int] = None

    @model_validator(mode="after")
    def validate_time_range(self):
        if self.start_time >= self.end_time:
            raise ValueError("start_time must be before end_time")
        return self


class ConflictDetail(SQLModel):
    """A single detected conflict."""

    reason_code: str
    message: str


class ConflictCheckResponse(SQLModel):
    """Response for POST /schedule/check-conflict."""

    has_conflicts: bool
    conflicts: List[ConflictDetail]
