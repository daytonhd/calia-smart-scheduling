"""add hashed_password and unique email to users

Adds the columns needed for email/password auth on the users table:
  - hashed_password (NOT NULL, varchar 255)
  - unique constraint on email

Existing rows (e.g. the seeded demo user from seed.py) are backfilled with
a placeholder hash that cannot match any real bcrypt verification, so those
accounts simply cannot log in until they re-register. The placeholder is
deliberately not a valid bcrypt digest.

Revision ID: e6f7a8b9c0d1
Revises: d5e6f7a8b9c0
Create Date: 2026-05-16

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
import sqlmodel


# revision identifiers, used by Alembic.
revision: str = 'e6f7a8b9c0d1'
down_revision: Union[str, Sequence[str], None] = 'd5e6f7a8b9c0'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema — add hashed_password column and unique email index."""
    # Add nullable first so existing rows survive, then backfill, then enforce NOT NULL.
    op.add_column(
        'users',
        sa.Column(
            'hashed_password',
            sqlmodel.sql.sqltypes.AutoString(length=255),
            nullable=True,
        ),
    )
    op.execute(
        "UPDATE users SET hashed_password = '!disabled' "
        "WHERE hashed_password IS NULL"
    )
    op.alter_column('users', 'hashed_password', nullable=False)

    op.create_index('ix_users_email', 'users', ['email'], unique=True)


def downgrade() -> None:
    """Downgrade schema — drop unique email index and hashed_password column."""
    op.drop_index('ix_users_email', table_name='users')
    op.drop_column('users', 'hashed_password')
