"""contract management: suppliers, contracts, amendments, approvals

Revision ID: 20260709_0053
Revises: 20260707_0052
Create Date: 2026-07-09
"""

import sqlalchemy as sa

from alembic import op

revision = "20260709_0053"
down_revision = "20260707_0052"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "suppliers",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("company_id", sa.Integer, sa.ForeignKey("companies.id", ondelete="CASCADE"), nullable=False),  # noqa: E501
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("document", sa.String(20)),
        sa.Column("document_type", sa.String(10)),
        sa.Column("category", sa.String(120)),
        sa.Column("email", sa.String(255)),
        sa.Column("phone", sa.String(30)),
        sa.Column("website", sa.String(255)),
        sa.Column("address_street", sa.String(255)),
        sa.Column("address_number", sa.String(20)),
        sa.Column("address_complement", sa.String(120)),
        sa.Column("address_city", sa.String(120)),
        sa.Column("address_state", sa.String(2)),
        sa.Column("address_zip", sa.String(10)),
        sa.Column("active", sa.Boolean, server_default=sa.true()),
        sa.Column("notes", sa.Text),
        sa.Column("deleted_at", sa.DateTime),
        sa.Column("created_at", sa.DateTime, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime, server_default=sa.func.now(), onupdate=sa.func.now()),
    )
    op.create_index("ix_suppliers_company_active", "suppliers", ["company_id", "active"])

    op.create_table(
        "supplier_contacts",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("company_id", sa.Integer, sa.ForeignKey("companies.id", ondelete="CASCADE"), nullable=False),  # noqa: E501
        sa.Column("supplier_id", sa.Integer, sa.ForeignKey("suppliers.id", ondelete="CASCADE"), nullable=False),  # noqa: E501
        sa.Column("name", sa.String(160), nullable=False),
        sa.Column("role", sa.String(120)),
        sa.Column("email", sa.String(255)),
        sa.Column("phone", sa.String(30)),
        sa.Column("whatsapp", sa.String(30)),
        sa.Column("is_primary", sa.Boolean, server_default=sa.false()),
        sa.Column("notes", sa.Text),
        sa.Column("deleted_at", sa.DateTime),
        sa.Column("created_at", sa.DateTime, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime, server_default=sa.func.now(), onupdate=sa.func.now()),
    )
    op.create_index("ix_supplier_contacts_supplier", "supplier_contacts", ["supplier_id"])

    op.create_table(
        "contracts",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("company_id", sa.Integer, sa.ForeignKey("companies.id", ondelete="CASCADE"), nullable=False),  # noqa: E501
        sa.Column("number", sa.String(80)),
        sa.Column("title", sa.String(255), nullable=False),
        sa.Column("contract_type", sa.String(40), server_default="servico"),
        sa.Column("supplier_id", sa.Integer, sa.ForeignKey("suppliers.id", ondelete="SET NULL")),
        sa.Column("responsible_user_id", sa.Integer, sa.ForeignKey("users.id", ondelete="SET NULL")),  # noqa: E501
        sa.Column("created_by_user_id", sa.Integer, sa.ForeignKey("users.id", ondelete="SET NULL")),
        sa.Column("status", sa.String(40), server_default="rascunho"),
        sa.Column("description", sa.Text),
        sa.Column("conditions", sa.Text),
        sa.Column("notes", sa.Text),
        sa.Column("signed_at", sa.Date),
        sa.Column("start_date", sa.Date),
        sa.Column("end_date", sa.Date),
        sa.Column("alert_days", sa.Integer, server_default="60"),
        sa.Column("auto_renew", sa.Boolean, server_default=sa.false()),
        sa.Column("indexer", sa.String(20)),
        sa.Column("total_value", sa.Numeric(14, 2)),
        sa.Column("monthly_value", sa.Numeric(14, 2)),
        sa.Column("currency", sa.String(3), server_default="BRL"),
        sa.Column("payment_frequency", sa.String(20)),
        sa.Column("payment_day", sa.Integer),
        sa.Column("cost_center", sa.String(120)),
        sa.Column("budget_category", sa.String(120)),
        sa.Column("deleted_at", sa.DateTime),
        sa.Column("created_at", sa.DateTime, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime, server_default=sa.func.now(), onupdate=sa.func.now()),
    )
    op.create_index("ix_contracts_company_status", "contracts", ["company_id", "status"])
    op.create_index("ix_contracts_company_end_date", "contracts", ["company_id", "end_date"])

    op.create_table(
        "contract_amendments",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("company_id", sa.Integer, sa.ForeignKey("companies.id", ondelete="CASCADE"), nullable=False),  # noqa: E501
        sa.Column("contract_id", sa.Integer, sa.ForeignKey("contracts.id", ondelete="CASCADE"), nullable=False),  # noqa: E501
        sa.Column("amendment_type", sa.String(40), nullable=False),
        sa.Column("description", sa.Text, nullable=False),
        sa.Column("new_end_date", sa.Date),
        sa.Column("new_value", sa.Numeric(14, 2)),
        sa.Column("signed_at", sa.Date),
        sa.Column("created_by_user_id", sa.Integer, sa.ForeignKey("users.id", ondelete="SET NULL")),
        sa.Column("created_at", sa.DateTime, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime, server_default=sa.func.now(), onupdate=sa.func.now()),
    )
    op.create_index("ix_contract_amendments_contract", "contract_amendments", ["contract_id"])

    op.create_table(
        "contract_approval_steps",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("company_id", sa.Integer, sa.ForeignKey("companies.id", ondelete="CASCADE"), nullable=False),  # noqa: E501
        sa.Column("contract_id", sa.Integer, sa.ForeignKey("contracts.id", ondelete="CASCADE"), nullable=False),  # noqa: E501
        sa.Column("step_order", sa.Integer, server_default="1"),
        sa.Column("approver_user_id", sa.Integer, sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),  # noqa: E501
        sa.Column("status", sa.String(20), server_default="pendente"),
        sa.Column("comment", sa.Text),
        sa.Column("decided_at", sa.DateTime),
        sa.Column("created_at", sa.DateTime, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime, server_default=sa.func.now(), onupdate=sa.func.now()),
    )
    op.create_index("ix_contract_approval_steps_contract", "contract_approval_steps", ["contract_id"])  # noqa: E501


def downgrade() -> None:
    op.drop_table("contract_approval_steps")
    op.drop_table("contract_amendments")
    op.drop_table("contracts")
    op.drop_table("supplier_contacts")
    op.drop_table("suppliers")
