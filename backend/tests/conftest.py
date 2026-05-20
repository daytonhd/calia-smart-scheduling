"""Shared pytest fixtures.

Uses an in-memory SQLite database per test so scheduling logic can be exercised
without a live Postgres. All models are imported via `app.models` so that
SQLModel.metadata is populated before create_all runs.

A `current_user` fixture is also provided. Tests that invoke route handlers
directly pass this user into the `current_user` parameter (the production
HTTPBearer dependency is bypassed in unit tests).
"""

import pytest
from sqlalchemy.pool import StaticPool
from sqlmodel import Session, SQLModel, create_engine

import app.models  # noqa: F401  — populate SQLModel.metadata


@pytest.fixture
def session():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    SQLModel.metadata.create_all(engine)
    with Session(engine) as s:
        yield s


@pytest.fixture
def current_user(session):
    """A persisted User with id = factories.DEFAULT_USER_ID.

    Created lazily so the same id is reused by make_calendar()'s auto-create
    path — tests can mix `current_user` and `make_calendar(session)` freely.
    """
    from tests.factories import ensure_default_user

    return ensure_default_user(session)
