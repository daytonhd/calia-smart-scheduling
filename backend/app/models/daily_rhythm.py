"""DailyRhythm model — persisted awake hours and suggestion hours.

Single-user MVP: there is one active Daily Rhythm row (user_id = 1). When no
row exists, callers fall back to the system defaults in
app.services.daily_rhythm. Daily Rhythm is not "availability" — it describes
the shape of the user's day and bounds where suggestions land.
"""

from datetime import datetime, time, timezone
from typing import Optional

from sqlmodel import Field, SQLModel


class DailyRhythm(SQLModel, table=True):
    __tablename__ = "daily_rhythm"

    id: Optional[int] = Field(default=None, primary_key=True)
    # Single-user MVP — auth deferred. Defaults to the seeded MVP user id.
    user_id: int = Field(default=1, nullable=False)
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
