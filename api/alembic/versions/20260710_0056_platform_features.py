"""feature flags, pedidos de suporte e registros de uso da plataforma

Revision ID: 20260710_0056
Revises: 20260710_0055
Create Date: 2026-07-10
"""

import sqlalchemy as sa

from alembic import op

revision = "20260710_0056"
down_revision = "20260710_0055"
branch_labels = None
depends_on = None


def upgrade() -> None:
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

    op.create_table(
        "support_requests",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column(
            "company_id",
            sa.Integer,
            sa.ForeignKey("companies.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("user_id", sa.Integer, sa.ForeignKey("users.id", ondelete="SET NULL")),
        sa.Column("contact_name", sa.String(160), nullable=False),
        sa.Column("contact_whatsapp", sa.String(30), nullable=False),
        sa.Column("message", sa.String(2000)),
        sa.Column("status", sa.String(20), server_default="pending", nullable=False),
        sa.Column("created_at", sa.DateTime, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime, server_default=sa.func.now(), onupdate=sa.func.now()),
    )
    op.create_index("ix_support_requests_company_id", "support_requests", ["company_id"])
    op.create_index("ix_support_requests_status", "support_requests", ["status"])

    op.create_table(
        "usage_records",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column(
            "company_id",
            sa.Integer,
            sa.ForeignKey("companies.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("metric", sa.String(60), nullable=False),
        sa.Column("value", sa.Integer, nullable=False),
        sa.Column("period_start", sa.Date, nullable=False),
        sa.Column("period_end", sa.Date, nullable=False),
        sa.Column("created_at", sa.DateTime, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime, server_default=sa.func.now(), onupdate=sa.func.now()),
    )
    op.create_index("ix_usage_records_company_id", "usage_records", ["company_id"])
    op.create_index("ix_usage_records_metric", "usage_records", ["metric"])


def downgrade() -> None:
    op.drop_index("ix_usage_records_metric", table_name="usage_records")
    op.drop_index("ix_usage_records_company_id", table_name="usage_records")
    op.drop_table("usage_records")

    op.drop_index("ix_support_requests_status", table_name="support_requests")
    op.drop_index("ix_support_requests_company_id", table_name="support_requests")
    op.drop_table("support_requests")

    op.drop_table("feature_flags")
