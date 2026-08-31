"""email_account_oauth

Revision ID: 20260831_0068
Revises: 20260830_0067
Create Date: 2026-08-31

Adiciona autenticação OAuth2 (Google) às contas de e-mail: auth_type e os
campos de token, e torna password_enc opcional (contas OAuth não têm senha).
"""

import sqlalchemy as sa

from alembic import op

revision = "20260831_0068"
down_revision = "20260830_0067"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "email_accounts",
        sa.Column("auth_type", sa.String(10), nullable=False, server_default="password"),
    )
    op.add_column("email_accounts", sa.Column("oauth_access_token_enc", sa.Text(), nullable=True))
    op.add_column("email_accounts", sa.Column("oauth_refresh_token_enc", sa.Text(), nullable=True))
    op.add_column(
        "email_accounts", sa.Column("oauth_token_expires_at", sa.DateTime(), nullable=True)
    )
    op.alter_column("email_accounts", "password_enc", existing_type=sa.Text(), nullable=True)


def downgrade() -> None:
    op.alter_column("email_accounts", "password_enc", existing_type=sa.Text(), nullable=False)
    op.drop_column("email_accounts", "oauth_token_expires_at")
    op.drop_column("email_accounts", "oauth_refresh_token_enc")
    op.drop_column("email_accounts", "oauth_access_token_enc")
    op.drop_column("email_accounts", "auth_type")
