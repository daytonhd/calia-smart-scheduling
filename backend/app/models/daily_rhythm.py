"""DailyRhythm model — persisted awake hours and suggestion hours per user.

Each user has at most one active DailyRhythm row. When no row exists for the
current user, callers fall back to the system defaults in
app.services.daily_rhythm. Daily Rhythm is not "availability" — it describes
the shape of the user's day and bounds where suggestions land.
"""

from datetime import datetime, time, timezone
from typing import Optional

from sqlmodel import Field, SQLModel


class DailyRhythm(SQLModel, table=True):
    __tablename__ = "daily_rhythm"

    id: Optional[int] = Field(default=None, primary_key=True)
    user_id: int = Field(foreign_key="users.id", nullable=False, index=True)
    awake_start_time: time = Field(nullable=False)
    awake_end_time: time = Field(nullable=False)
    suggestions_start_time: time = Field(nullable=False)
    suggestions_end_time: time = Field(nullable=False)
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc), nullable=False
    )
    updated_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc), nullable=False
    )
