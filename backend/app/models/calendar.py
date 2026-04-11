"""Calendar model — a named container for events."""

from datetime import datetime, timezone
from typing import Optional

from sqlmodel import Field, SQLModel


class Calendar(SQLModel, table=True):
    __tablename__ = "calendars"

    id: Optional[int] = Field(default=None, primary_key=True)
    name: str = Field(max_length=120, nullable=False)
    color: Optional[str] = Field(default=None, max_length=7, description="Hex color, e.g. #3B82F6")
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc), nullable=False)
