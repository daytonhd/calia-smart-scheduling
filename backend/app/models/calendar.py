"""Calendar model — a named container for events.

Each calendar belongs to exactly one user. Calendar names are unique per user
(two different users may both name a calendar "Main calendar"; one user may
not have two calendars with the same name).
"""

from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import UniqueConstraint
from sqlmodel import Field, SQLModel


class Calendar(SQLModel, table=True):
    __tablename__ = "calendars"
    __table_args__ = (
        UniqueConstraint("user_id", "name", name="uq_calendars_user_name"),
    )

    id: Optional[int] = Field(default=None, primary_key=True)
    user_id: int = Field(foreign_key="users.id", nullable=False, index=True)
    name: str = Field(max_length=120, nullable=False)
    color: Optional[str] = Field(default=None, max_length=7, description="Hex color, e.g. #3B82F6")
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc), nullable=False)
