"""Schemas for schedule-related endpoints."""

from datetime import date, datetime
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


class SuggestSlotsRequest(SQLModel):
    """Request body for POST /schedule/suggest-slots."""

    duration_minutes: int
    start_date: Optional[date] = None
    end_date: Optional[date] = None
    max_results: int = 10

    @model_validator(mode="after")
    def validate_fields(self):
        if self.duration_minutes < 1:
            raise ValueError("duration_minutes must be at least 1")
        if self.start_date and self.end_date and self.start_date > self.end_date:
            raise ValueError("start_date must not be after end_date")
        return self


class SlotSuggestion(SQLModel):
    """A single available time slot."""

    start_time: datetime
    end_time: datetime


class SuggestSlotsResponse(SQLModel):
    """Response for POST /schedule/suggest-slots."""

    slots: List[SlotSuggestion]
