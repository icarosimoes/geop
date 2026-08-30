"""email_client: contas IMAP, cache de mensagens e regras de alerta WhatsApp

Revision ID: 20260830_0065
Revises: 20260825_0064
Create Date: 2026-08-30
"""

import sqlalchemy as sa

from alembic import op

revision = "20260830_0065"
down_revision = "20260825_0064"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Contas de e-mail IMAP por tenant
    op.create_table(
        "email_accounts",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column(
            "company_id",
            sa.Integer(),
            sa.ForeignKey("companies.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("name", sa.String(120), nullable=False),
        sa.Column("provider", sa.String(40), nullable=False, server_default="imap"),
        sa.Column("imap_host", sa.String(255), nullable=False),
        sa.Column("imap_port", sa.Integer(), nullable=False, server_default="993"),
        sa.Column("imap_ssl", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column("username", sa.String(255), nullable=False),
        sa.Column("password_enc", sa.Text(), nullable=False),
        sa.Column("active", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column("last_synced_at", sa.DateTime(), nullable=True),
        sa.Column("deleted_at", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_email_accounts_company", "email_accounts", ["company_id"])

    # Cache de mensagens recebidas
    op.create_table(
        "email_messages",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column(
            "company_id",
            sa.Integer(),
            sa.ForeignKey("companies.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "account_id",
            sa.Integer(),
            sa.ForeignKey("email_accounts.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("uid", sa.String(80), nullable=False),
        sa.Column("folder", sa.String(120), nullable=False, server_default="INBOX"),
        sa.Column("from_addr", sa.String(500), nullable=False),
        sa.Column("from_name", sa.String(255), nullable=True),
        sa.Column("to_addr", sa.String(1000), nullable=True),
        sa.Column("subject", sa.String(1000), nullable=True),
        sa.Column("body_text", sa.Text(), nullable=True),
        sa.Column("body_html", sa.Text(), nullable=True),
        sa.Column("received_at", sa.DateTime(), nullable=True),
        sa.Column("is_read", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("is_flagged", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("alerted_rule_ids", sa.JSON(), nullable=False, server_default="[]"),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
    )
    op.create_index(
        "ix_email_messages_company_account", "email_messages", ["company_id", "account_id"]
    )
    op.create_index("ix_email_messages_uid", "email_messages", ["account_id", "uid"])
    op.create_index("ix_email_messages_account_id", "email_messages", ["account_id"])

    # Regras de alerta → WhatsApp
    op.create_table(
        "email_alert_rules",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column(
            "company_id",
            sa.Integer(),
            sa.ForeignKey("companies.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("name", sa.String(120), nullable=False),
        sa.Column("active", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column("filter_type", sa.String(20), nullable=False),
        sa.Column("filter_value", sa.String(500), nullable=False),
        sa.Column("whatsapp_targets", sa.JSON(), nullable=False, server_default="[]"),
        sa.Column("account_ids", sa.JSON(), nullable=False, server_default="[]"),
        sa.Column("deleted_at", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_email_alert_rules_company", "email_alert_rules", ["company_id"])


def downgrade() -> None:
    op.drop_table("email_alert_rules")
    op.drop_table("email_messages")
    op.drop_table("email_accounts")
