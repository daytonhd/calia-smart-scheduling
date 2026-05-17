"""User model — email/password auth for the MVP."""

from datetime import datetime, timezone
from typing import Optional

from sqlmodel import Field, SQLModel


class User(SQLModel, table=True):
    __tablename__ = "users"

    id: Optional[int] = Field(default=None, primary_key=True)
    name: str = Field(nullable=False, max_length=120)
    email: str = Field(nullable=False, max_length=255, unique=True, index=True)
    hashed_password: str = Field(nullable=False, max_length=255)
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc), nullable=False
    )
