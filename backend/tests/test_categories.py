"""Tests for the user-managed Category CRUD endpoints.

Categories are descriptive labels for events. These tests cover create,
list, get, update, delete, missing-category behavior, blank-name
rejection, and duplicate-name behavior per user.

All routes require an authenticated user; tests pass the `current_user`
fixture in lieu of the production HTTPBearer dependency.
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

from .factories import make_user


def test_create_category_returns_persisted_row(session, current_user):
    body = CategoryCreate(name="Study", color="#3B82F6")

    created = create_category(body, session, current_user)

    assert created.id is not None
    assert created.name == "Study"
    assert created.color == "#3B82F6"

    stored = session.exec(select(Category)).all()
    assert len(stored) == 1
    assert stored[0].user_id == current_user.id


def test_create_category_strips_whitespace_and_persists_trimmed_name(
    session, current_user
):
    body = CategoryCreate(name="  Gym  ")

    created = create_category(body, session, current_user)

    assert created.name == "Gym"


def test_create_category_rejects_blank_name():
    with pytest.raises(Exception):
        CategoryCreate(name="   ")


def test_create_category_rejects_duplicate_name(session, current_user):
    create_category(CategoryCreate(name="Class"), session, current_user)

    with pytest.raises(HTTPException) as excinfo:
        create_category(CategoryCreate(name="Class"), session, current_user)

    assert excinfo.value.status_code == 409


def test_list_categories_returns_only_current_user_rows(session, current_user):
    create_category(CategoryCreate(name="Personal"), session, current_user)
    create_category(CategoryCreate(name="Study"), session, current_user)

    # Insert a row for a different user — list must not include it.
    other_user = make_user(session, email="other@example.com")
    other = Category(user_id=other_user.id, name="Other-User Cat")
    session.add(other)
    session.commit()

    rows = list_categories(session, current_user)

    assert [r.name for r in rows] == ["Personal", "Study"]


def test_two_users_can_each_have_same_category_name(session, current_user):
    """Per-user uniqueness — Alice and Bob may both have a "Study" category."""
    create_category(CategoryCreate(name="Study"), session, current_user)

    other = make_user(session, email="other@example.com")
    other_cat = create_category(CategoryCreate(name="Study"), session, other)

    assert other_cat.user_id == other.id
    assert other_cat.user_id != current_user.id


def test_get_category_returns_row(session, current_user):
    created = create_category(CategoryCreate(name="Class"), session, current_user)

    fetched = get_category(created.id, session, current_user)

    assert fetched.id == created.id
    assert fetched.name == "Class"


def test_get_category_404_for_missing(session, current_user):
    with pytest.raises(HTTPException) as excinfo:
        get_category(9999, session, current_user)

    assert excinfo.value.status_code == 404


def test_get_category_404_for_other_user_row(session, current_user):
    other_user = make_user(session, email="other@example.com")
    other = Category(user_id=other_user.id, name="Other Cat")
    session.add(other)
    session.commit()
    session.refresh(other)

    with pytest.raises(HTTPException) as excinfo:
        get_category(other.id, session, current_user)

    assert excinfo.value.status_code == 404


def test_update_category_renames_and_updates_color(session, current_user):
    created = create_category(
        CategoryCreate(name="Study", color="#3B82F6"), session, current_user
    )

    updated = update_category(
        created.id,
        CategoryUpdate(name="Deep Work", color="#10B981"),
        session,
        current_user,
    )

    assert updated.id == created.id
    assert updated.name == "Deep Work"
    assert updated.color == "#10B981"


def test_update_category_404_for_missing(session, current_user):
    with pytest.raises(HTTPException) as excinfo:
        update_category(9999, CategoryUpdate(name="Whatever"), session, current_user)

    assert excinfo.value.status_code == 404


def test_update_category_rejects_duplicate_name(session, current_user):
    create_category(CategoryCreate(name="Class"), session, current_user)
    target = create_category(CategoryCreate(name="Study"), session, current_user)

    with pytest.raises(HTTPException) as excinfo:
        update_category(
            target.id, CategoryUpdate(name="Class"), session, current_user
        )

    assert excinfo.value.status_code == 409


def test_update_category_allows_keeping_same_name(session, current_user):
    target = create_category(CategoryCreate(name="Study"), session, current_user)

    updated = update_category(
        target.id,
        CategoryUpdate(name="Study", color="#FFFFFF"),
        session,
        current_user,
    )

    assert updated.name == "Study"
    assert updated.color == "#FFFFFF"


def test_update_category_rejects_blank_name():
    with pytest.raises(Exception):
        CategoryUpdate(name="   ")


def test_delete_category_removes_row(session, current_user):
    created = create_category(CategoryCreate(name="Class"), session, current_user)

    delete_category(created.id, session, current_user)

    assert session.get(Category, created.id) is None


def test_delete_category_404_for_missing(session, current_user):
    with pytest.raises(HTTPException) as excinfo:
        delete_category(9999, session, current_user)

    assert excinfo.value.status_code == 404


def test_delete_category_404_for_other_users_row(session, current_user):
    """User A may not delete user B's category."""
    other_user = make_user(session, email="other@example.com")
    other_cat = create_category(
        CategoryCreate(name="B's category"), session, other_user
    )

    with pytest.raises(HTTPException) as excinfo:
        delete_category(other_cat.id, session, current_user)

    assert excinfo.value.status_code == 404
    # And the row must still exist.
    assert session.get(Category, other_cat.id) is not None
