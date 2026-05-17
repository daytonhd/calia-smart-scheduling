"""Tests for the email/password auth MVP — signup, login, /me.

These tests invoke the route handlers directly, matching the rest of the
suite (no TestClient / httpx). Handlers that depend on the bearer header
are exercised by constructing the HTTPAuthorizationCredentials object the
HTTPBearer security scheme would normally produce.
"""

import pytest
from fastapi import HTTPException
from fastapi.security import HTTPAuthorizationCredentials
from sqlmodel import select

from app.models.calendar import Calendar
from app.models.category import Category
from app.models.daily_rhythm import DailyRhythm
from app.models.user import User
from app.routers.auth import (
    get_current_user,
    login,
    read_current_user,
    signup,
)
from app.schemas.auth import LoginRequest, SignupRequest


def _bearer(token: str) -> HTTPAuthorizationCredentials:
    return HTTPAuthorizationCredentials(scheme="Bearer", credentials=token)


def _signup_body(**overrides) -> SignupRequest:
    defaults = {
        "name": "Alice Example",
        "email": "alice@example.com",
        "password": "correct-horse",
    }
    defaults.update(overrides)
    return SignupRequest(**defaults)


def test_signup_creates_user_and_returns_token(session):
    response = signup(_signup_body(), session)

    assert response.access_token
    assert response.token_type == "bearer"
    assert response.user.id is not None
    assert response.user.name == "Alice Example"
    assert response.user.email == "alice@example.com"

    stored = session.exec(select(User)).all()
    assert len(stored) == 1


def test_signup_normalizes_email_to_lowercase_and_trimmed(session):
    response = signup(
        _signup_body(email="  Alice@Example.COM  "),
        session,
    )

    assert response.user.email == "alice@example.com"


def test_signup_rejects_duplicate_email(session):
    signup(_signup_body(), session)

    with pytest.raises(HTTPException) as excinfo:
        signup(
            _signup_body(name="Other", email="ALICE@example.com"),
            session,
        )

    assert excinfo.value.status_code == 409


def test_signup_hashes_password_not_plaintext(session):
    signup(_signup_body(password="super-secret-1"), session)

    stored = session.exec(select(User)).first()
    assert stored.hashed_password
    assert stored.hashed_password != "super-secret-1"
    # bcrypt hashes start with a $2 prefix; the placeholder marker doesn't.
    assert stored.hashed_password.startswith("$2")


def test_signup_does_not_create_calendars(session):
    signup(_signup_body(), session)
    assert session.exec(select(Calendar)).all() == []


def test_signup_does_not_create_categories(session):
    signup(_signup_body(), session)
    assert session.exec(select(Category)).all() == []


def test_signup_creates_daily_rhythm_defaults_for_new_user(session):
    response = signup(_signup_body(), session)

    rows = session.exec(
        select(DailyRhythm).where(DailyRhythm.user_id == response.user.id)
    ).all()
    assert len(rows) == 1
    row = rows[0]
    # Stored as datetime.time objects.
    assert row.awake_start_time.strftime("%H:%M") == "07:00"
    assert row.awake_end_time.strftime("%H:%M") == "23:00"
    assert row.suggestions_start_time.strftime("%H:%M") == "08:00"
    assert row.suggestions_end_time.strftime("%H:%M") == "21:00"


def test_login_succeeds_with_correct_password(session):
    signup(_signup_body(password="correct-horse"), session)

    response = login(
        LoginRequest(email="alice@example.com", password="correct-horse"),
        session,
    )

    assert response.access_token
    assert response.user.email == "alice@example.com"


def test_login_normalizes_email_before_lookup(session):
    signup(_signup_body(password="correct-horse"), session)

    response = login(
        LoginRequest(email="ALICE@Example.com", password="correct-horse"),
        session,
    )

    assert response.user.email == "alice@example.com"


def test_login_rejects_wrong_password(session):
    signup(_signup_body(password="correct-horse"), session)

    with pytest.raises(HTTPException) as excinfo:
        login(
            LoginRequest(email="alice@example.com", password="wrong-pass"),
            session,
        )

    assert excinfo.value.status_code == 401


def test_login_rejects_unknown_email(session):
    with pytest.raises(HTTPException) as excinfo:
        login(
            LoginRequest(email="ghost@example.com", password="whatever-1"),
            session,
        )

    assert excinfo.value.status_code == 401


def test_me_returns_current_user_with_valid_token(session):
    response = signup(_signup_body(), session)

    user = get_current_user(_bearer(response.access_token), session)
    me = read_current_user(user)

    assert me.id == response.user.id
    assert me.email == "alice@example.com"


def test_me_rejects_missing_token(session):
    with pytest.raises(HTTPException) as excinfo:
        get_current_user(None, session)

    assert excinfo.value.status_code == 401


def test_me_rejects_invalid_token(session):
    with pytest.raises(HTTPException) as excinfo:
        get_current_user(_bearer("not-a-real-jwt"), session)

    assert excinfo.value.status_code == 401


def test_me_rejects_token_for_deleted_user(session):
    response = signup(_signup_body(), session)
    user = session.get(User, response.user.id)
    session.delete(user)
    session.commit()

    with pytest.raises(HTTPException) as excinfo:
        get_current_user(_bearer(response.access_token), session)

    assert excinfo.value.status_code == 401


def test_signup_rejects_short_password():
    with pytest.raises(Exception):
        SignupRequest(name="A", email="a@b.com", password="short")
