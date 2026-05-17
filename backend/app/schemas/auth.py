"""Request and response schemas for the auth endpoints."""

from datetime import datetime

from pydantic import Field, field_validator
from sqlmodel import SQLModel


def _basic_email_check(value: str) -> str:
    """Lightweight email-shape check — full RFC validation is out of scope."""
    if not isinstance(value, str):
        raise ValueError("email must be a string")
    candidate = value.strip()
    if "@" not in candidate or "." not in candidate.split("@")[-1]:
        raise ValueError("invalid email address")
    if len(candidate) > 255:
        raise ValueError("email is too long")
    return candidate


class SignupRequest(SQLModel):
    """Request body for POST /auth/signup."""

    name: str = Field(min_length=1, max_length=120)
    email: str
    password: str = Field(min_length=8, max_length=128)

    @field_validator("name")
    @classmethod
    def _strip_name(cls, v: str) -> str:
        stripped = v.strip()
        if not stripped:
            raise ValueError("name must not be blank")
        return stripped

    @field_validator("email")
    @classmethod
    def _validate_email(cls, v: str) -> str:
        return _basic_email_check(v)


class LoginRequest(SQLModel):
    """Request body for POST /auth/login."""

    email: str
    password: str = Field(min_length=1, max_length=128)

    @field_validator("email")
    @classmethod
    def _validate_email(cls, v: str) -> str:
        return _basic_email_check(v)


class UserOut(SQLModel):
    """Public user shape — never includes the password hash."""

    id: int
    name: str
    email: str
    created_at: datetime


class AuthResponse(SQLModel):
    """Response body for POST /auth/signup and POST /auth/login."""

    access_token: str
    token_type: str = "bearer"
    user: UserOut
