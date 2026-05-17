"""Tests for the user-managed Category CRUD endpoints.

Categories are descriptive labels for events. These tests cover create,
list, get, update, delete, missing-category behavior, blank-name
rejection, and duplicate-name behavior per user.
"""

import pytest
from fastapi import HTTPException
from sqlmodel import select

from app.models.category import Category
from app.routers.categories import (
    create_category,
    delete_category,
    get_category,
    list_categories,
    update_category,
)
from app.schemas.category import CategoryCreate, CategoryUpdate
from app.services.daily_rhythm import MVP_USER_ID


def test_create_category_returns_persisted_row(session):
    body = CategoryCreate(name="Study", color="#3B82F6")

    created = create_category(body, session)

    assert created.id is not None
    assert created.name == "Study"
    assert created.color == "#3B82F6"

    stored = session.exec(select(Category)).all()
    assert len(stored) == 1
    assert stored[0].user_id == MVP_USER_ID


def test_create_category_strips_whitespace_and_persists_trimmed_name(session):
    body = CategoryCreate(name="  Gym  ")

    created = create_category(body, session)

    assert created.name == "Gym"


def test_create_category_rejects_blank_name():
    with pytest.raises(Exception):
        CategoryCreate(name="   ")


def test_create_category_rejects_duplicate_name(session):
    create_category(CategoryCreate(name="Class"), session)

    with pytest.raises(HTTPException) as excinfo:
        create_category(CategoryCreate(name="Class"), session)

    assert excinfo.value.status_code == 409


def test_list_categories_returns_only_current_user_rows(session):
    create_category(CategoryCreate(name="Personal"), session)
    create_category(CategoryCreate(name="Study"), session)

    # Insert a row for a different user — list must not include it.
    other = Category(user_id=MVP_USER_ID + 1, name="Other-User Cat")
    session.add(other)
    session.commit()

    rows = list_categories(session)

    assert [r.name for r in rows] == ["Personal", "Study"]


def test_get_category_returns_row(session):
    created = create_category(CategoryCreate(name="Class"), session)

    fetched = get_category(created.id, session)

    assert fetched.id == created.id
    assert fetched.name == "Class"


def test_get_category_404_for_missing(session):
    with pytest.raises(HTTPException) as excinfo:
        get_category(9999, session)

    assert excinfo.value.status_code == 404


def test_get_category_404_for_other_user_row(session):
    other = Category(user_id=MVP_USER_ID + 1, name="Other Cat")
    session.add(other)
    session.commit()
    session.refresh(other)

    with pytest.raises(HTTPException) as excinfo:
        get_category(other.id, session)

    assert excinfo.value.status_code == 404


def test_update_category_renames_and_updates_color(session):
    created = create_category(
        CategoryCreate(name="Study", color="#3B82F6"), session
    )

    updated = update_category(
        created.id,
        CategoryUpdate(name="Deep Work", color="#10B981"),
        session,
    )

    assert updated.id == created.id
    assert updated.name == "Deep Work"
    assert updated.color == "#10B981"


def test_update_category_404_for_missing(session):
    with pytest.raises(HTTPException) as excinfo:
        update_category(9999, CategoryUpdate(name="Whatever"), session)

    assert excinfo.value.status_code == 404


def test_update_category_rejects_duplicate_name(session):
    create_category(CategoryCreate(name="Class"), session)
    target = create_category(CategoryCreate(name="Study"), session)

    with pytest.raises(HTTPException) as excinfo:
        update_category(target.id, CategoryUpdate(name="Class"), session)

    assert excinfo.value.status_code == 409


def test_update_category_allows_keeping_same_name(session):
    target = create_category(CategoryCreate(name="Study"), session)

    updated = update_category(
        target.id, CategoryUpdate(name="Study", color="#FFFFFF"), session
    )

    assert updated.name == "Study"
    assert updated.color == "#FFFFFF"


def test_update_category_rejects_blank_name():
    with pytest.raises(Exception):
        CategoryUpdate(name="   ")


def test_delete_category_removes_row(session):
    created = create_category(CategoryCreate(name="Class"), session)

    delete_category(created.id, session)

    assert session.get(Category, created.id) is None


def test_delete_category_404_for_missing(session):
    with pytest.raises(HTTPException) as excinfo:
        delete_category(9999, session)

    assert excinfo.value.status_code == 404
