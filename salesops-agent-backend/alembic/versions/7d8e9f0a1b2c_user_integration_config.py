"""user_integration_config — per-user third-party credentials (plan §41)

One generic table for ERPNext, Google Places and Google Calendar. The field
set for each provider is declared in core/integrations.py, so adding another
integration needs no further migration.

Secrets live in `secrets_encrypted` as a single AES-256-GCM blob containing a
JSON object of that provider's secret fields. Non-secret values (base URLs,
client IDs) stay in the plain `config` JSON so Settings can display them.

Revision ID: 7d8e9f0a1b2c
Revises: 6c7f6e87625b
Create Date: 2026-09-04

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "7d8e9f0a1b2c"
down_revision: Union[str, Sequence[str], None] = "6c7f6e87625b"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "user_integration_config",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("user_id", sa.String(), nullable=False),
        sa.Column("provider", sa.String(), nullable=False),
        sa.Column("enabled", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("config", sa.JSON(), nullable=False, server_default="{}"),
        sa.Column("secrets_encrypted", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("user_id", "provider", name="uq_user_integration_provider"),
    )
    op.create_index(
        op.f("ix_user_integration_config_user_id"),
        "user_integration_config",
        ["user_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_user_integration_config_provider"),
        "user_integration_config",
        ["provider"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(
        op.f("ix_user_integration_config_provider"),
        table_name="user_integration_config",
    )
    op.drop_index(
        op.f("ix_user_integration_config_user_id"),
        table_name="user_integration_config",
    )
    op.drop_table("user_integration_config")
