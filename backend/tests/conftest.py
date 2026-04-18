"""Shared pytest fixtures.

Uses an in-memory SQLite database per test so scheduling logic can be exercised
without a live Postgres. All models are imported via `app.models` so that
SQLModel.metadata is populated before create_all runs.
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
