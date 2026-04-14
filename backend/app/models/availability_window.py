"""AvailabilityWindow model — recurring weekly time blocks when a user is available."""

from datetime import datetime, time, timezone
from typing import Optional

from sqlmodel import Field, SQLModel


class AvailabilityWindow(SQLModel, table=True):
    __tablename__ = "availability_windows"

    id: Optional[int] = Field(default=None, primary_key=True)
    user_id: int = Field(nullable=False)
    weekday: int = Field(nullable=False, description="0=Monday … 6=Sunday")
    start_time: time = Field(nullable=False)
    end_time: time = Field(nullable=False)
    active: bool = Field(default=True, nullable=False)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc), nullable=False)
