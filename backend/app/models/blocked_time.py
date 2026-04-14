"""BlockedTime model — a specific datetime range when a user is unavailable."""

from datetime import datetime, timezone
from typing import Optional

from sqlmodel import Field, SQLModel


class BlockedTime(SQLModel, table=True):
    __tablename__ = "blocked_times"

    id: Optional[int] = Field(default=None, primary_key=True)
    user_id: int = Field(nullable=False)
    title: str = Field(max_length=255, nullable=False)
    reason: Optional[str] = Field(default=None, max_length=255)
    notes: Optional[str] = Field(default=None)
    start_time: datetime = Field(nullable=False)
    end_time: datetime = Field(nullable=False)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc), nullable=False)
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc), nullable=False)
