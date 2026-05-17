"""Pydantic schemas for Category endpoints.

Categories are user-managed labels for events. They do not affect
scheduling logic; these schemas only describe the CRUD shape.
"""

from datetime import datetime
from typing import Optional

from pydantic import field_validator
from sqlmodel import SQLModel


def _validate_name(value: str) -> str:
    """Strip and reject blank names."""
    stripped = value.strip()
    if not stripped:
        raise ValueError("name must not be blank")
    if len(stripped) > 120:
        raise ValueError("name is too long")
    return stripped


class CategoryCreate(SQLModel):
    """Request body for creating a category."""

    name: str
    color: Optional[str] = None

    @field_validator("name")
    @classmethod
    def _strip_name(cls, v: str) -> str:
        return _validate_name(v)


class CategoryUpdate(SQLModel):
    """Request body for updating a category. All fields optional."""

    name: Optional[str] = None
    color: Optional[str] = None

    @field_validator("name")
    @classmethod
    def _strip_name(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return v
        return _validate_name(v)


class CategoryRead(SQLModel):
    """Response body for a category."""

    id: int
    name: str
    color: Optional[str] = None
    created_at: datetime
    updated_at: datetime
