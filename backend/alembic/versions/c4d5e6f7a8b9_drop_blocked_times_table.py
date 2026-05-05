"""drop blocked_times table

BlockedTime has been fully removed from the active product. Day-to-day
unavailable periods, commutes, classes, focus blocks, and appointments are
represented as ordinary categorized Events. This migration drops the
``blocked_times`` table.

Downgrade recreates the table with the same column shape it had under the
prior model definition.

Revision ID: c4d5e6f7a8b9
Revises: b3c4d5e6f7a8
Create Date: 2026-05-05 00:00:00.000000
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
import sqlmodel


# revision identifiers, used by Alembic.
revision: str = 'c4d5e6f7a8b9'
down_revision: Union[str, Sequence[str], None] = 'b3c4d5e6f7a8'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema — drop the blocked_times table."""
    op.drop_table('blocked_times')


def downgrade() -> None:
    """Downgrade schema — recreate blocked_times with its prior shape."""
    op.create_table(
        'blocked_times',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('title', sqlmodel.sql.sqltypes.AutoString(length=255), nullable=False),
        sa.Column('reason', sqlmodel.sql.sqltypes.AutoString(length=255), nullable=True),
        sa.Column('start_time', sa.DateTime(), nullable=False),
        sa.Column('end_time', sa.DateTime(), nullable=False),
        sa.Column('notes', sqlmodel.sql.sqltypes.AutoString(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint('id'),
    )
