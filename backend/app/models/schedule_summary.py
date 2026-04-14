"""ScheduleSummary model — AI-generated weekly availability summary for a user."""

from datetime import date, datetime, timezone
from typing import Optional

from sqlmodel import Field, SQLModel


class ScheduleSummary(SQLModel, table=True):
    __tablename__ = "schedule_summaries"

    id: Optional[int] = Field(default=None, primary_key=True)
    user_id: int = Field(nullable=False)
    week_start: date = Field(nullable=False)
    generated_text: str = Field(nullable=False)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc), nullable=False)
