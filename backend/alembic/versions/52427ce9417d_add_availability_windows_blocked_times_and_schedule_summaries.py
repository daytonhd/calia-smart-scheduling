"""add availability_windows, blocked_times, and schedule_summaries tables

Revision ID: 52427ce9417d
Revises: aafcb58ffae4
Create Date: 2026-04-13 00:00:00.000000

Note: This migration file was reconstructed to match tables already present in the
database from a prior session whose migration file was lost.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
import sqlmodel


# revision identifiers, used by Alembic.
revision: str = '52427ce9417d'
down_revision: Union[str, Sequence[str], None] = 'aafcb58ffae4'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table('availability_windows',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('user_id', sa.Integer(), nullable=False),
    sa.Column('weekday', sa.Integer(), nullable=False),
    sa.Column('start_time', sa.Time(), nullable=False),
    sa.Column('end_time', sa.Time(), nullable=False),
    sa.Column('active', sa.Boolean(), nullable=False),
    sa.Column('created_at', sa.DateTime(), nullable=False),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_table('blocked_times',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('user_id', sa.Integer(), nullable=False),
    sa.Column('title', sqlmodel.sql.sqltypes.AutoString(length=255), nullable=False),
    sa.Column('reason', sqlmodel.sql.sqltypes.AutoString(length=255), nullable=True),
    sa.Column('start_time', sa.DateTime(), nullable=False),
    sa.Column('end_time', sa.DateTime(), nullable=False),
    sa.Column('notes', sqlmodel.sql.sqltypes.AutoString(), nullable=True),
    sa.Column('created_at', sa.DateTime(), nullable=False),
    sa.Column('updated_at', sa.DateTime(), nullable=False),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_table('schedule_summaries',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('user_id', sa.Integer(), nullable=False),
    sa.Column('week_start', sa.Date(), nullable=False),
    sa.Column('generated_text', sqlmodel.sql.sqltypes.AutoString(), nullable=False),
    sa.Column('created_at', sa.DateTime(), nullable=False),
    sa.PrimaryKeyConstraint('id')
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_table('schedule_summaries')
    op.drop_table('blocked_times')
    op.drop_table('availability_windows')
