"""Schemas for schedule-related endpoints.

All scheduling datetime fields follow the MVP time contract: naive datetimes
representing local app time. Timezone-aware values are rejected at the API
boundary by ensure_naive_datetime so downstream comparisons are consistent.
"""

from datetime import date, datetime
from typing import List, Optional

from pydantic import field_validator, model_validator
from sqlmodel import SQLModel

from app.services.time_contract import ensure_naive_datetime


class ConflictCheckRequest(SQLModel):
    """Request body for checking scheduling conflicts for a proposed event placement."""

    calendar_id: int
    start_time: datetime
    end_time: datetime
    exclude_event_id: Optional[int] = None

    @field_validator("start_time", "end_time")
    @classmethod
    def _naive_only(cls, v: datetime) -> datetime:
        return ensure_naive_datetime(v, "start_time/end_time")

    @model_validator(mode="after")
    def validate_time_range(self):
        if self.start_time >= self.end_time:
            raise ValueError("start_time must be before end_time")
        return self


class ConflictDetail(SQLModel):
    """A single detected conflict.

    reason_code is a stable machine identifier. Active codes are
    EVENT_OVERLAP; INVALID_TIME_RANGE may be surfaced from input
    validation.
    message is a deterministic backend-formatted human-readable string
    that references existing events / occupied schedule items.
    conflict_type is the high-level category ("event", "input") — these
    strings are stable identifiers used by clients.
    start_time / end_time identify the offending interval when applicable
    (the related event interval, or the proposed interval for input
    issues). related_event_id links the conflict back to a specific
    stored row when applicable.
    """

    reason_code: str
    message: str
    conflict_type: Optional[str] = None
    start_time: Optional[datetime] = None
    end_time: Optional[datetime] = None
    related_event_id: Optional[int] = None


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
    """A single available time slot.

    reason_code is a stable identifier (EARLIEST_VALID_SLOT). explanation
    is a deterministic human-readable string describing why this slot was
    selected.
    """

    start_time: datetime
    end_time: datetime
    reason_code: str = "EARLIEST_VALID_SLOT"
    explanation: str = (
        "Selected because it fits inside your daily suggestion hours "
        "and avoids existing events and other occupied schedule items."
    )


class SuggestSlotsResponse(SQLModel):
    """Response for POST /schedule/suggest-slots."""

    slots: List[SlotSuggestion]


class WeeklyMetricsResponse(SQLModel):
    """Response for GET /schedule/metrics — weekly scheduling facts."""

    week_start: date
    week_end: date
    total_events: int
    total_scheduled_minutes: int
    busiest_day: Optional[date] = None
    busiest_day_minutes: int


class ScheduleSummaryRead(SQLModel):
    """Response for GET /schedule/weekly-summary — a stored AI summary."""

    id: int
    user_id: int
    week_start: date
    generated_text: str
    created_at: datetime


# ---------------------------------------------------------------------------
# Triage schemas (GET /schedule/triage)
# ---------------------------------------------------------------------------


class TriageWarning(SQLModel):
    """A single triage warning attached to a day or week."""

    reason_code: str
    message: str


class TriageDay(SQLModel):
    """Per-day triage summary."""

    date: date
    scheduled_minutes: int
    total_busy_minutes: int
    free_minutes: int
    longest_free_window_minutes: int
    is_overloaded: bool
    is_fragmented: bool
    has_weak_buffer: bool
    warnings: List[TriageWarning]


class TriageResponse(SQLModel):
    """Response for GET /schedule/triage."""

    week_start: date
    week_end: date
    days: List[TriageDay]
    week_warnings: List[TriageWarning]


# ---------------------------------------------------------------------------
# Adaptive rescheduling schemas (POST /schedule/reschedule-options)
# ---------------------------------------------------------------------------


class RescheduleOptionsRequest(SQLModel):
    """Request body for POST /schedule/reschedule-options."""

    event_id: int
    search_start: datetime
    search_end: datetime
    max_results: int = 5

    @field_validator("search_start", "search_end")
    @classmethod
    def _naive_only(cls, v: datetime) -> datetime:
        return ensure_naive_datetime(v, "search_start/search_end")

    @model_validator(mode="after")
    def validate_fields(self):
        if self.search_start >= self.search_end:
            raise ValueError("search_start must be before search_end")
        if self.max_results < 1:
            raise ValueError("max_results must be at least 1")
        return self


class RescheduleOption(SQLModel):
    """A single ranked replacement option."""

    rank: int
    start_time: datetime
    end_time: datetime
    reason_code: str
    explanation: str
    minutes_from_original_start: int


class RescheduleOptionsResponse(SQLModel):
    """Response for POST /schedule/reschedule-options."""

    event_id: int
    event_title: str
    duration_minutes: int
    options: List[RescheduleOption]


class ProposedRescheduleOptionsRequest(SQLModel):
    """Request body for POST /schedule/proposed-reschedule-options.

    Used when the user is composing an event that has not been saved yet —
    typically because the initial create attempt produced a 409 conflict.
    Unlike RescheduleOptionsRequest, no event_id is required since there is
    no stored row to exclude from the overlap check.
    """

    calendar_id: int
    title: str
    start_time: datetime
    end_time: datetime
    search_start: datetime
    search_end: datetime
    max_results: int = 5

    @field_validator("start_time", "end_time", "search_start", "search_end")
    @classmethod
    def _naive_only(cls, v: datetime) -> datetime:
        return ensure_naive_datetime(
            v, "start_time/end_time/search_start/search_end"
        )

    @model_validator(mode="after")
    def validate_fields(self):
        if self.start_time >= self.end_time:
            raise ValueError("start_time must be before end_time")
        if self.search_start >= self.search_end:
            raise ValueError("search_start must be before search_end")
        if self.max_results < 1:
            raise ValueError("max_results must be at least 1")
        return self


class ProposedRescheduleOptionsResponse(SQLModel):
    """Response for POST /schedule/proposed-reschedule-options.

    Note: there is no event_id field — the proposed event has not been saved.
    Each option reuses the existing RescheduleOption shape so frontend code
    can render saved and proposed reschedule options with the same component.
    """

    event_title: str
    duration_minutes: int
    options: List[RescheduleOption]
