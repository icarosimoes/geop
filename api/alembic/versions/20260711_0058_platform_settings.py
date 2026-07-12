"""platform_settings: configurações globais da plataforma (ex.: e-mail)

Revision ID: 20260711_0058
Revises: 20260711_0057
Create Date: 2026-07-11
"""

import sqlalchemy as sa

from alembic import op

revision = "20260711_0058"
down_revision = "20260711_0057"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "platform_settings",
        sa.Column("key", sa.String(120), primary_key=True),
        sa.Column("value", sa.JSON, server_default="{}", nullable=False),
        sa.Column("created_at", sa.DateTime, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime, server_default=sa.func.now(), onupdate=sa.func.now()),
    )


def downgrade() -> None:
    op.drop_table("platform_settings")
