"""remove feature flags (decisão: não seguir com essa funcionalidade)

Revision ID: 20260711_0057
Revises: 20260710_0056
Create Date: 2026-07-11
"""

import sqlalchemy as sa

from alembic import op

revision = "20260711_0057"
down_revision = "20260710_0056"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.drop_table("feature_flags")


def downgrade() -> None:
    op.create_table(
        "feature_flags",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("key", sa.String(120), nullable=False, unique=True),
        sa.Column("description", sa.String(500)),
        sa.Column("enabled_default", sa.Boolean, server_default=sa.false(), nullable=False),
        sa.Column("targeting_rules", sa.JSON, server_default="{}", nullable=False),
        sa.Column("deleted_at", sa.DateTime),
        sa.Column("created_at", sa.DateTime, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime, server_default=sa.func.now(), onupdate=sa.func.now()),
    )
