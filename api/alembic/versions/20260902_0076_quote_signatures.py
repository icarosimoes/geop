"""assinatura eletrônica de orçamento: simples (OTP) e ICP-Brasil (provedor)

Revision ID: 20260902_0076
Revises: 20260831_0075
Create Date: 2026-09-02
"""

import sqlalchemy as sa

from alembic import op

revision = "20260902_0076"
down_revision = "20260831_0075"
branch_labels = None
depends_on = None

RLS_TABLES = ["quote_signatures"]


def upgrade() -> None:
    op.create_table(
        "quote_signatures",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column(
            "company_id",
            sa.Integer,
            sa.ForeignKey("companies.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "quote_id",
            sa.Integer,
            sa.ForeignKey("quotes.id", ondelete="CASCADE"),
            nullable=False,
            unique=True,
        ),
        sa.Column("method", sa.String(20), server_default="simples"),
        sa.Column("status", sa.String(20), server_default="pendente"),
        sa.Column("signer_name", sa.String(255)),
        sa.Column("signer_document", sa.String(20)),
        sa.Column("signer_email", sa.String(255)),
        sa.Column("ip_address", sa.String(45)),
        sa.Column("user_agent", sa.Text),
        sa.Column("document_hash", sa.String(64)),
        sa.Column("otp_code_hash", sa.String(100)),
        sa.Column("otp_sent_at", sa.DateTime),
        sa.Column("otp_verified_at", sa.DateTime),
        sa.Column("otp_attempts", sa.Integer, server_default="0"),
        sa.Column("provider", sa.String(30)),
        sa.Column("provider_envelope_id", sa.String(120)),
        sa.Column("provider_signer_id", sa.String(120)),
        sa.Column("certificate_info", sa.JSON),
        sa.Column(
            "signed_pdf_attachment_id",
            sa.Integer,
            sa.ForeignKey("attachments.id", ondelete="SET NULL"),
        ),
        sa.Column("signed_at", sa.DateTime),
        sa.Column("created_at", sa.DateTime, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime, server_default=sa.func.now(), onupdate=sa.func.now()),
    )
    op.create_index("ix_quote_signatures_status", "quote_signatures", ["status"])
    op.create_index(
        "ix_quote_signatures_provider_envelope", "quote_signatures", ["provider_envelope_id"]
    )

    for table in RLS_TABLES:
        op.execute(f"ALTER TABLE {table} ENABLE ROW LEVEL SECURITY")
        op.execute(f"ALTER TABLE {table} FORCE ROW LEVEL SECURITY")
        op.execute(
            f"CREATE POLICY tenant_isolation ON {table} "
            "USING (company_id = current_setting('app.current_company_id')::int)"
        )


def downgrade() -> None:
    for table in reversed(RLS_TABLES):
        op.execute(f"DROP POLICY IF EXISTS tenant_isolation ON {table}")
        op.execute(f"ALTER TABLE {table} DISABLE ROW LEVEL SECURITY")

    op.drop_table("quote_signatures")
