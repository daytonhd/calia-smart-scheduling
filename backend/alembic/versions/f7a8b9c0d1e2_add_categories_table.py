"""add categories table

Creates the user-managed Category table. Categories are descriptive labels
users attach to events; they never affect conflict detection, slot
suggestions, replacement options, or any schedule metric. Event.category
remains a plain optional string for MVP compatibility and is not a foreign
key into this table.

Revision ID: f7a8b9c0d1e2
Revises: e6f7a8b9c0d1
Create Date: 2026-05-17

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
import sqlmodel


# revision identifiers, used by Alembic.
revision: str = 'f7a8b9c0d1e2'
down_revision: Union[str, Sequence[str], None] = 'e6f7a8b9c0d1'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema — create the categories table."""
    op.create_table(
        'categories',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column(
            'name',
            sqlmodel.sql.sqltypes.AutoString(length=120),
            nullable=False,
        ),
        sa.Column(
            'color',
            sqlmodel.sql.sqltypes.AutoString(length=7),
            nullable=True,
        ),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(
        'ix_categories_user_id',
        'categories',
        ['user_id'],
        unique=False,
    )


def downgrade() -> None:
    """Downgrade schema — drop the categories table."""
    op.drop_index('ix_categories_user_id', table_name='categories')
    op.drop_table('categories')
