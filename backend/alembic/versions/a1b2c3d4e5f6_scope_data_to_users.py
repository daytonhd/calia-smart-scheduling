"""scope calendars/categories/rhythm/summaries to users

Adds the missing user ownership wiring to bring stored data in line with the
authenticated multi-user contract:

  - calendars: add user_id column + FK + per-user (user_id, name) uniqueness.
    Backfills existing calendars to the lowest existing user id; if no users
    exist but calendars do, those orphan calendars and their events are
    deleted (otherwise the NOT NULL + FK would fail).

  - categories: column already exists but had no FK or per-user uniqueness;
    this migration adds the FK to users.id and the (user_id, name) unique
    constraint.

  - daily_rhythm: FK on user_id -> users.id (column already exists).

  - schedule_summaries: FK on user_id -> users.id (column already exists).

Revision ID: a1b2c3d4e5f6
Revises: f7a8b9c0d1e2
Create Date: 2026-05-19

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "a1b2c3d4e5f6"
down_revision: Union[str, Sequence[str], None] = "f7a8b9c0d1e2"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema — wire user ownership across scheduling tables."""
    bind = op.get_bind()

    # ---------- calendars: add user_id + FK + per-user uniqueness ----------
    op.add_column(
        "calendars",
        sa.Column("user_id", sa.Integer(), nullable=True),
    )

    # Backfill: assign all existing calendars to the lowest existing user id.
    # If there are no users, drop orphan calendars (and the events that point
    # at them) so the NOT NULL + FK constraints below can be applied cleanly.
    user_id_row = bind.execute(sa.text("SELECT MIN(id) FROM users")).scalar()
    if user_id_row is not None:
        op.execute(
            sa.text("UPDATE calendars SET user_id = :uid WHERE user_id IS NULL").bindparams(
                uid=user_id_row
            )
        )
    else:
        # No users to attribute the rows to — wipe orphan calendars and their
        # events. This only triggers in fresh environments that pre-date auth.
        op.execute(
            sa.text(
                "DELETE FROM events WHERE calendar_id IN "
                "(SELECT id FROM calendars WHERE user_id IS NULL)"
            )
        )
        op.execute(sa.text("DELETE FROM calendars WHERE user_id IS NULL"))

    op.alter_column("calendars", "user_id", nullable=False)
    op.create_index(
        "ix_calendars_user_id", "calendars", ["user_id"], unique=False
    )
    op.create_foreign_key(
        "fk_calendars_user_id_users",
        "calendars",
        "users",
        ["user_id"],
        ["id"],
    )
    op.create_unique_constraint(
        "uq_calendars_user_name", "calendars", ["user_id", "name"]
    )

    # ---------- categories: add FK + per-user uniqueness ----------
    # Backfill: any pre-auth categories were attributed to the default
    # user_id=1 sentinel. If that user no longer exists, redirect them to
    # the lowest existing user id, otherwise the FK below would fail.
    if user_id_row is not None and user_id_row != 1:
        op.execute(
            sa.text(
                "UPDATE categories SET user_id = :uid "
                "WHERE user_id NOT IN (SELECT id FROM users)"
            ).bindparams(uid=user_id_row)
        )
    elif user_id_row is None:
        op.execute(sa.text("DELETE FROM categories"))

    op.create_foreign_key(
        "fk_categories_user_id_users",
        "categories",
        "users",
        ["user_id"],
        ["id"],
    )
    op.create_unique_constraint(
        "uq_categories_user_name", "categories", ["user_id", "name"]
    )

    # ---------- daily_rhythm: add FK ----------
    # Backfill: a pre-auth row at user_id=1 may not match an existing user.
    if user_id_row is not None and user_id_row != 1:
        op.execute(
            sa.text(
                "UPDATE daily_rhythm SET user_id = :uid "
                "WHERE user_id NOT IN (SELECT id FROM users)"
            ).bindparams(uid=user_id_row)
        )
    elif user_id_row is None:
        op.execute(sa.text("DELETE FROM daily_rhythm"))

    op.create_index(
        "ix_daily_rhythm_user_id", "daily_rhythm", ["user_id"], unique=False
    )
    op.create_foreign_key(
        "fk_daily_rhythm_user_id_users",
        "daily_rhythm",
        "users",
        ["user_id"],
        ["id"],
    )

    # ---------- schedule_summaries: add FK ----------
    if user_id_row is not None:
        op.execute(
            sa.text(
                "DELETE FROM schedule_summaries "
                "WHERE user_id NOT IN (SELECT id FROM users)"
            )
        )
    else:
        op.execute(sa.text("DELETE FROM schedule_summaries"))

    op.create_index(
        "ix_schedule_summaries_user_id",
        "schedule_summaries",
        ["user_id"],
        unique=False,
    )
    op.create_foreign_key(
        "fk_schedule_summaries_user_id_users",
        "schedule_summaries",
        "users",
        ["user_id"],
        ["id"],
    )


def downgrade() -> None:
    """Downgrade schema — drop user ownership wiring."""
    op.drop_constraint(
        "fk_schedule_summaries_user_id_users",
        "schedule_summaries",
        type_="foreignkey",
    )
    op.drop_index(
        "ix_schedule_summaries_user_id", table_name="schedule_summaries"
    )

    op.drop_constraint(
        "fk_daily_rhythm_user_id_users", "daily_rhythm", type_="foreignkey"
    )
    op.drop_index("ix_daily_rhythm_user_id", table_name="daily_rhythm")

    op.drop_constraint(
        "uq_categories_user_name", "categories", type_="unique"
    )
    op.drop_constraint(
        "fk_categories_user_id_users", "categories", type_="foreignkey"
    )

    op.drop_constraint(
        "uq_calendars_user_name", "calendars", type_="unique"
    )
    op.drop_constraint(
        "fk_calendars_user_id_users", "calendars", type_="foreignkey"
    )
    op.drop_index("ix_calendars_user_id", table_name="calendars")
    op.drop_column("calendars", "user_id")
