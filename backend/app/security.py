"""Password hashing and JWT helpers for the auth MVP.

Kept deliberately small: bcrypt for password storage, HS256 JWTs for access
tokens. The JWT secret comes from app.config (env-driven; the local default
is insecure and only acceptable for development).
"""

from datetime import datetime, timedelta, timezone
from typing import Optional

from jose import JWTError, jwt
from passlib.context import CryptContext

from app.config import (
    JWT_ACCESS_TOKEN_EXPIRE_MINUTES,
    JWT_ALGORITHM,
    JWT_SECRET_KEY,
)

_pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def hash_password(password: str) -> str:
    """Return a bcrypt hash for the given plaintext password."""
    return _pwd_context.hash(password)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Return True iff plain_password matches the stored bcrypt hash.

    Returns False (never raises) when the stored hash is malformed — e.g. the
    `!disabled` placeholder used for pre-auth seeded users.
    """
    try:
        return _pwd_context.verify(plain_password, hashed_password)
    except (ValueError, TypeError):
        return False


def normalize_email(email: str) -> str:
    """Canonicalize an email for storage and lookup: trim + lowercase."""
    return email.strip().lower()


def create_access_token(
    subject: str,
    expires_minutes: Optional[int] = None,
) -> str:
    """Issue a signed JWT access token with `sub` set to subject.

    subject is the stringified user id. Use decode_access_token to read it back.
    """
    minutes = (
        expires_minutes
        if expires_minutes is not None
        else JWT_ACCESS_TOKEN_EXPIRE_MINUTES
    )
    now = datetime.now(timezone.utc)
    payload = {
        "sub": str(subject),
        "iat": int(now.timestamp()),
        "exp": int((now + timedelta(minutes=minutes)).timestamp()),
    }
    return jwt.encode(payload, JWT_SECRET_KEY, algorithm=JWT_ALGORITHM)


def decode_access_token(token: str) -> Optional[int]:
    """Return the user id encoded in token, or None if invalid/expired."""
    try:
        payload = jwt.decode(token, JWT_SECRET_KEY, algorithms=[JWT_ALGORITHM])
    except JWTError:
        return None
    sub = payload.get("sub")
    if sub is None:
        return None
    try:
        return int(sub)
    except (TypeError, ValueError):
        return None
