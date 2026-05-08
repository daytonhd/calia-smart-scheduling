"""drop availability_windows table

AvailabilityWindow has been fully removed from the active product. Daily
availability is now driven by Daily Rhythm suggestion hours, and occupied
time is represented as ordinary categorized Events. This migration drops
the ``availability_windows`` table.

Downgrade recreates the table with the same column shape it had under the
prior model definition (see revision ``52427ce9417d``).

Revision ID: c79d502acb1f
Revises: c4d5e6f7a8b9
Create Date: 2026-05-08 16:22:15.594506

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'c79d502acb1f'
down_revision: Union[str, Sequence[str], None] = 'c4d5e6f7a8b9'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema — drop the availability_windows table."""
    op.drop_table('availability_windows')


def downgrade() -> None:
    """Downgrade schema — recreate availability_windows with its prior shape."""
    op.create_table(
        'availability_windows',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('weekday', sa.Integer(), nullable=False),
        sa.Column('start_time', sa.Time(), nullable=False),
        sa.Column('end_time', sa.Time(), nullable=False),
        sa.Column('active', sa.Boolean(), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint('id'),
    )
