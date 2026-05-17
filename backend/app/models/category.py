"""Category model — a user-managed label for events.

Categories are descriptive labels users attach to events (e.g. Class, Gym,
Study, Personal). They never affect conflict detection, slot suggestions,
replacement options, blocking, or any schedule metric — every event is
treated as occupied time regardless of category. The Event.category column
remains a plain optional string for MVP compatibility; this table only
manages the set of labels a user can pick from.
"""

from datetime import datetime, timezone
from typing import Optional

from sqlmodel import Field, SQLModel


class Category(SQLModel, table=True):
    __tablename__ = "categories"

    id: Optional[int] = Field(default=None, primary_key=True)
    # Single-user MVP — auth deferred. Defaults to the seeded MVP user id,
    # matching the convention used by DailyRhythm.
    user_id: int = Field(default=1, nullable=False, index=True)
    name: str = Field(max_length=120, nullable=False)
    color: Optional[str] = Field(
        default=None,
        max_length=7,
        description="Hex color, e.g. #3B82F6",
    )
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc), nullable=False
    )
    updated_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc), nullable=False
    )
