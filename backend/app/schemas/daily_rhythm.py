"""Schemas for Daily Rhythm endpoints.

Daily Rhythm describes the shape of the user's day: the awake-hours window
and the narrower suggestion-hours window used by scheduling. It is not
"availability" — manual events are never rejected for falling outside it.

Times cross the API as "HH:MM" 24-hour strings (e.g. "07:00"). The stored
model uses datetime.time columns; the router converts at the boundary.
"""

from datetime import datetime, time

from pydantic import field_validator, model_validator
from sqlmodel import SQLModel

_TIME_FIELDS = (
    "awake_start_time",
    "awake_end_time",
    "suggestions_start_time",
    "suggestions_end_time",
)


def parse_hhmm(value: str) -> time:
    """Parse an "HH:MM" (or "HH:MM:SS") 24-hour string into a time.

    Raises ValueError on anything that is not a valid 24-hour clock value.
    """
    if not isinstance(value, str):
        raise ValueError("time must be a string in HH:MM 24-hour format")
    raw = value.strip()
    for fmt in ("%H:%M", "%H:%M:%S"):
        try:
            return datetime.strptime(raw, fmt).time()
        except ValueError:
            continue
    raise ValueError(f"invalid time {value!r}; expected HH:MM (24-hour)")


def format_hhmm(value: time) -> str:
    """Format a time as a canonical "HH:MM" 24-hour string."""
    return value.strftime("%H:%M")


class DailyRhythmRead(SQLModel):
    """Response body for Daily Rhythm — times as "HH:MM" strings."""

    awake_start_time: str
    awake_end_time: str
    suggestions_start_time: str
    suggestions_end_time: str


class DailyRhythmUpdate(SQLModel):
    """Request body for PATCH /daily-rhythm. All four fields are required.

    Validation:
      - awake_start_time   < awake_end_time
      - suggestions_start_time < suggestions_end_time
      - suggestion hours fit inside awake hours:
          awake_start_time <= suggestions_start_time
          suggestions_end_time <= awake_end_time
    """

    awake_start_time: str
    awake_end_time: str
    suggestions_start_time: str
    suggestions_end_time: str

    @field_validator(*_TIME_FIELDS)
    @classmethod
    def _normalize_hhmm(cls, v: str) -> str:
        # Reject malformed values, then store the canonical HH:MM form.
        return format_hhmm(parse_hhmm(v))

    @model_validator(mode="after")
    def _validate_ranges(self):
        awake_start = parse_hhmm(self.awake_start_time)
        awake_end = parse_hhmm(self.awake_end_time)
        sugg_start = parse_hhmm(self.suggestions_start_time)
        sugg_end = parse_hhmm(self.suggestions_end_time)

        if awake_start >= awake_end:
            raise ValueError("awake_start_time must be before awake_end_time")
        if sugg_start >= sugg_end:
            raise ValueError(
                "suggestions_start_time must be before suggestions_end_time"
            )
        if sugg_start < awake_start:
            raise ValueError(
                "suggestions_start_time must be at or after awake_start_time"
            )
        if sugg_end > awake_end:
            raise ValueError(
                "suggestions_end_time must be at or before awake_end_time"
            )
        return self
