"""add daily_rhythm table

Persists the single-user MVP Daily Rhythm: awake hours and suggestion hours.
When no row exists, the API and scheduling logic fall back to system
defaults — see app.services.daily_rhythm. Daily Rhythm is not "availability";
manual event create/update is never gated on it.

Revision ID: d5e6f7a8b9c0
Revises: c79d502acb1f
Create Date: 2026-05-14

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'd5e6f7a8b9c0'
down_revision: Union[str, Sequence[str], None] = 'c79d502acb1f'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema — create the daily_rhythm table."""
    op.create_table(
        'daily_rhythm',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('awake_start_time', sa.Time(), nullable=False),
        sa.Column('awake_end_time', sa.Time(), nullable=False),
        sa.Column('suggestions_start_time', sa.Time(), nullable=False),
        sa.Column('suggestions_end_time', sa.Time(), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint('id'),
    )


def downgrade() -> None:
    """Downgrade schema — drop the daily_rhythm table."""
    op.drop_table('daily_rhythm')
