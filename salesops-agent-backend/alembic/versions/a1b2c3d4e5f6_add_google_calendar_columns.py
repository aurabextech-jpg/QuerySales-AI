"""add_google_calendar_columns

Revision ID: a1b2c3d4e5f6
Revises: 544a285687fd
Create Date: 2026-05-17 12:28:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'a1b2c3d4e5f6'
down_revision: Union[str, Sequence[str], None] = '544a285687fd'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add Google Calendar integration columns to users table."""
    op.add_column(
        'users',
        sa.Column('google_refresh_token', sa.String(), nullable=True),
    )
    op.add_column(
        'users',
        sa.Column(
            'google_calendar_connected',
            sa.Boolean(),
            server_default=sa.text('false'),
            nullable=True,
        ),
    )


def downgrade() -> None:
    """Remove Google Calendar integration columns from users table."""
    op.drop_column('users', 'google_calendar_connected')
    op.drop_column('users', 'google_refresh_token')
