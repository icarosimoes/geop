"""email_account_pop3_protocol

Revision ID: 20260830_0066
Revises: 20260830_0065
Create Date: 2026-08-30

Adiciona coluna `protocol` (imap|pop3) à tabela email_accounts.
"""

from alembic import op
import sqlalchemy as sa

revision = "20260830_0066"
down_revision = "20260830_0065"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "email_accounts",
        sa.Column("protocol", sa.String(10), nullable=False, server_default="imap"),
    )


def downgrade() -> None:
    op.drop_column("email_accounts", "protocol")
