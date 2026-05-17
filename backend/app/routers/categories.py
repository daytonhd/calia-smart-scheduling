"""CRUD endpoints for user-managed categories.

Categories are descriptive labels for events. They do not affect conflict
detection, slot suggestions, replacement options, or any schedule metric —
this router only manages the set of labels a user can pick from. The
Event.category column stays an optional free-form string for MVP
compatibility and is not a foreign key into this table.
"""

from datetime import datetime, timezone
from typing import List

from fastapi import APIRouter, Depends, HTTPException, status
from sqlmodel import Session, select

from app.database import get_session
from app.models.category import Category
from app.schemas.category import CategoryCreate, CategoryRead, CategoryUpdate
from app.services.daily_rhythm import MVP_USER_ID

router = APIRouter(prefix="/categories", tags=["categories"])


def _find_duplicate(
    session: Session,
    user_id: int,
    name: str,
    exclude_id: int = None,
) -> Category:
    """Return an existing same-named category for this user, or None."""
    query = select(Category).where(
        Category.user_id == user_id,
        Category.name == name,
    )
    if exclude_id is not None:
        query = query.where(Category.id != exclude_id)
    return session.exec(query).first()


@router.post("/", response_model=CategoryRead, status_code=status.HTTP_201_CREATED)
def create_category(body: CategoryCreate, session: Session = Depends(get_session)):
    user_id = MVP_USER_ID
    name = body.name  # already stripped + non-blank by the schema validator

    clash = _find_duplicate(session, user_id, name)
    if clash is not None:
        raise HTTPException(
            status_code=409,
            detail=f"Category named {name!r} already exists",
        )

    category = Category(
        user_id=user_id,
        name=name,
        color=body.color,
    )
    session.add(category)
    session.commit()
    session.refresh(category)
    return category


@router.get("/", response_model=List[CategoryRead])
def list_categories(session: Session = Depends(get_session)):
    user_id = MVP_USER_ID
    return session.exec(
        select(Category)
        .where(Category.user_id == user_id)
        .order_by(Category.id)
    ).all()


@router.get("/{category_id}", response_model=CategoryRead)
def get_category(category_id: int, session: Session = Depends(get_session)):
    user_id = MVP_USER_ID
    category = session.get(Category, category_id)
    if not category or category.user_id != user_id:
        raise HTTPException(status_code=404, detail="Category not found")
    return category


@router.patch("/{category_id}", response_model=CategoryRead)
def update_category(
    category_id: int,
    body: CategoryUpdate,
    session: Session = Depends(get_session),
):
    user_id = MVP_USER_ID
    category = session.get(Category, category_id)
    if not category or category.user_id != user_id:
        raise HTTPException(status_code=404, detail="Category not found")

    updates = body.model_dump(exclude_unset=True)

    new_name = updates.get("name")
    if new_name is not None and new_name != category.name:
        clash = _find_duplicate(
            session, user_id, new_name, exclude_id=category_id
        )
        if clash is not None:
            raise HTTPException(
                status_code=409,
                detail=f"Category named {new_name!r} already exists",
            )

    for field, value in updates.items():
        setattr(category, field, value)

    category.updated_at = datetime.now(timezone.utc)
    session.add(category)
    session.commit()
    session.refresh(category)
    return category


@router.delete("/{category_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_category(category_id: int, session: Session = Depends(get_session)):
    user_id = MVP_USER_ID
    category = session.get(Category, category_id)
    if not category or category.user_id != user_id:
        raise HTTPException(status_code=404, detail="Category not found")

    session.delete(category)
    session.commit()
