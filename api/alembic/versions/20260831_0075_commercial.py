"""pipeline comercial: clientes, orçamentos, vendas, faturamento, cobrança

Revision ID: 20260831_0075
Revises: 20260831_0074
Create Date: 2026-08-31
"""

import sqlalchemy as sa

from alembic import op

revision = "20260831_0075"
down_revision = "20260831_0074"
branch_labels = None
depends_on = None

RLS_TABLES = [
    "customers",
    "quotes",
    "quote_items",
    "sales",
    "sales_invoices",
    "sales_payments",
]

PERMISSIONS = [
    ("commercial.view", "Ver clientes, orçamentos, vendas e faturamento", "commercial"),
    ("commercial.create", "Criar clientes e orçamentos", "commercial"),
    ("commercial.edit", "Editar orçamentos/vendas/faturas e registrar recebimentos", "commercial"),
    ("commercial.delete", "Excluir clientes e orçamentos", "commercial"),
]


def upgrade() -> None:
    op.create_table(
        "customers",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column(
            "company_id",
            sa.Integer,
            sa.ForeignKey("companies.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("document", sa.String(20)),
        sa.Column("document_type", sa.String(10)),
        sa.Column("email", sa.String(255)),
        sa.Column("phone", sa.String(30)),
        sa.Column("whatsapp", sa.String(30)),
        sa.Column("address_street", sa.String(255)),
        sa.Column("address_number", sa.String(20)),
        sa.Column("address_complement", sa.String(120)),
        sa.Column("address_neighborhood", sa.String(120)),
        sa.Column("address_city", sa.String(120)),
        sa.Column("address_state", sa.String(2)),
        sa.Column("address_zip", sa.String(10)),
        sa.Column("active", sa.Boolean, server_default=sa.true()),
        sa.Column("notes", sa.Text),
        sa.Column("deleted_at", sa.DateTime),
        sa.Column("created_at", sa.DateTime, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime, server_default=sa.func.now(), onupdate=sa.func.now()),
    )
    op.create_index("ix_customers_company_active", "customers", ["company_id", "active"])

    op.create_table(
        "quotes",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column(
            "company_id",
            sa.Integer,
            sa.ForeignKey("companies.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("number", sa.String(80)),
        sa.Column(
            "customer_id",
            sa.Integer,
            sa.ForeignKey("customers.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("title", sa.String(255), nullable=False),
        sa.Column("status", sa.String(20), server_default="rascunho"),
        sa.Column(
            "responsible_user_id", sa.Integer, sa.ForeignKey("users.id", ondelete="SET NULL")
        ),  # noqa: E501
        sa.Column("created_by_user_id", sa.Integer, sa.ForeignKey("users.id", ondelete="SET NULL")),
        sa.Column("description", sa.Text),
        sa.Column("conditions", sa.Text),
        sa.Column("notes", sa.Text),
        sa.Column("issued_at", sa.Date),
        sa.Column("valid_until", sa.Date),
        sa.Column("discount_amount", sa.Numeric(14, 2), server_default="0"),
        sa.Column("subtotal", sa.Numeric(14, 2), server_default="0"),
        sa.Column("total", sa.Numeric(14, 2), server_default="0"),
        sa.Column("decided_at", sa.DateTime),
        sa.Column("decision_note", sa.Text),
        sa.Column("deleted_at", sa.DateTime),
        sa.Column("created_at", sa.DateTime, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime, server_default=sa.func.now(), onupdate=sa.func.now()),
    )
    op.create_index("ix_quotes_company_status", "quotes", ["company_id", "status"])
    op.create_index("ix_quotes_company_customer", "quotes", ["company_id", "customer_id"])

    op.create_table(
        "quote_items",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column(
            "company_id",
            sa.Integer,
            sa.ForeignKey("companies.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "quote_id", sa.Integer, sa.ForeignKey("quotes.id", ondelete="CASCADE"), nullable=False
        ),  # noqa: E501
        sa.Column("item_type", sa.String(20), server_default="produto"),
        sa.Column(
            "stock_item_id", sa.Integer, sa.ForeignKey("stock_items.id", ondelete="SET NULL")
        ),  # noqa: E501
        sa.Column("description", sa.String(255), nullable=False),
        sa.Column("unit", sa.String(20), server_default="un"),
        sa.Column("quantity", sa.Numeric(12, 3), server_default="1"),
        sa.Column("unit_price", sa.Numeric(14, 2), server_default="0"),
        sa.Column("discount_percent", sa.Numeric(5, 2)),
        sa.Column("line_total", sa.Numeric(14, 2), server_default="0"),
        sa.Column("sort_order", sa.Integer, server_default="0"),
        sa.Column("created_at", sa.DateTime, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime, server_default=sa.func.now(), onupdate=sa.func.now()),
    )
    op.create_index("ix_quote_items_quote", "quote_items", ["quote_id"])

    op.create_table(
        "sales",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column(
            "company_id",
            sa.Integer,
            sa.ForeignKey("companies.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("number", sa.String(80)),
        sa.Column(
            "quote_id",
            sa.Integer,
            sa.ForeignKey("quotes.id", ondelete="RESTRICT"),
            nullable=False,
            unique=True,
        ),
        sa.Column(
            "customer_id",
            sa.Integer,
            sa.ForeignKey("customers.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("status", sa.String(20), server_default="confirmada"),
        sa.Column("total_value", sa.Numeric(14, 2), server_default="0"),
        sa.Column(
            "responsible_user_id", sa.Integer, sa.ForeignKey("users.id", ondelete="SET NULL")
        ),  # noqa: E501
        sa.Column("created_by_user_id", sa.Integer, sa.ForeignKey("users.id", ondelete="SET NULL")),
        sa.Column("delivered_at", sa.Date),
        sa.Column("installation_status", sa.String(20), server_default="pendente"),
        sa.Column("installation_scheduled_at", sa.Date),
        sa.Column("installation_completed_at", sa.Date),
        sa.Column("installation_notes", sa.Text),
        sa.Column("notes", sa.Text),
        sa.Column("erpsolid_external_id", sa.String(60)),
        sa.Column("deleted_at", sa.DateTime),
        sa.Column("created_at", sa.DateTime, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime, server_default=sa.func.now(), onupdate=sa.func.now()),
    )
    op.create_index("ix_sales_company_status", "sales", ["company_id", "status"])

    op.create_table(
        "sales_invoices",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column(
            "company_id",
            sa.Integer,
            sa.ForeignKey("companies.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "sale_id", sa.Integer, sa.ForeignKey("sales.id", ondelete="CASCADE"), nullable=False
        ),  # noqa: E501
        sa.Column("number", sa.String(80)),
        sa.Column("nf_number", sa.String(40)),
        sa.Column("status", sa.String(20), server_default="pendente"),
        sa.Column("amount", sa.Numeric(14, 2), server_default="0"),
        sa.Column("issued_at", sa.Date),
        sa.Column("due_date", sa.Date),
        sa.Column("notes", sa.Text),
        sa.Column("erpsolid_external_id", sa.String(60)),
        sa.Column("deleted_at", sa.DateTime),
        sa.Column("created_at", sa.DateTime, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime, server_default=sa.func.now(), onupdate=sa.func.now()),
    )
    op.create_index("ix_sales_invoices_company_status", "sales_invoices", ["company_id", "status"])

    op.create_table(
        "sales_payments",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column(
            "company_id",
            sa.Integer,
            sa.ForeignKey("companies.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "invoice_id",
            sa.Integer,
            sa.ForeignKey("sales_invoices.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("amount", sa.Numeric(14, 2), nullable=False),
        sa.Column("method", sa.String(20)),
        sa.Column("paid_at", sa.Date, nullable=False),
        sa.Column("reference", sa.String(120)),
        sa.Column("notes", sa.Text),
        sa.Column("created_by_user_id", sa.Integer, sa.ForeignKey("users.id", ondelete="SET NULL")),
        sa.Column("erpsolid_external_id", sa.String(60)),
        sa.Column("created_at", sa.DateTime, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime, server_default=sa.func.now(), onupdate=sa.func.now()),
    )
    op.create_index("ix_sales_payments_invoice", "sales_payments", ["invoice_id"])

    for table in RLS_TABLES:
        op.execute(f"ALTER TABLE {table} ENABLE ROW LEVEL SECURITY")
        op.execute(f"ALTER TABLE {table} FORCE ROW LEVEL SECURITY")
        op.execute(
            f"CREATE POLICY tenant_isolation ON {table} "
            "USING (company_id = current_setting('app.current_company_id')::int)"
        )

    conn = op.get_bind()
    for code, name, module in PERMISSIONS:
        conn.execute(
            sa.text(
                "INSERT INTO permissions (code, name, module, created_at, updated_at) "
                "VALUES (:code, :name, :module, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP) "
                "ON CONFLICT (code) DO UPDATE SET name = EXCLUDED.name, module = EXCLUDED.module"
            ),
            {"code": code, "name": name, "module": module},
        )


def downgrade() -> None:
    conn = op.get_bind()
    for code, _, _ in PERMISSIONS:
        conn.execute(sa.text("DELETE FROM permissions WHERE code = :code"), {"code": code})

    for table in reversed(RLS_TABLES):
        op.execute(f"DROP POLICY IF EXISTS tenant_isolation ON {table}")
        op.execute(f"ALTER TABLE {table} DISABLE ROW LEVEL SECURITY")

    op.drop_table("sales_payments")
    op.drop_table("sales_invoices")
    op.drop_table("sales")
    op.drop_table("quote_items")
    op.drop_table("quotes")
    op.drop_table("customers")
