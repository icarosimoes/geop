"""cost centers: cadastro próprio + FK em contracts (substitui campo texto)

Revision ID: 20260710_0055
Revises: 20260709_0054
Create Date: 2026-07-10
"""

import sqlalchemy as sa

from alembic import op

revision = "20260710_0055"
down_revision = "20260709_0054"
branch_labels = None
depends_on = None

RLS_TABLES = ["cost_centers"]


def upgrade() -> None:
    op.create_table(
        "cost_centers",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column(
            "company_id",
            sa.Integer,
            sa.ForeignKey("companies.id", ondelete="CASCADE"),
            nullable=False,
        ),  # noqa: E501
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("code", sa.String(40)),
        sa.Column(
            "parent_id", sa.Integer, sa.ForeignKey("cost_centers.id", ondelete="SET NULL")
        ),  # noqa: E501
        sa.Column("active", sa.Boolean, server_default=sa.true()),
        sa.Column("deleted_at", sa.DateTime),
        sa.Column("created_at", sa.DateTime, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime, server_default=sa.func.now(), onupdate=sa.func.now()),
    )
    op.create_index("ix_cost_centers_company_active", "cost_centers", ["company_id", "active"])

    for table in RLS_TABLES:
        op.execute(f"ALTER TABLE {table} ENABLE ROW LEVEL SECURITY")
        op.execute(
            f"CREATE POLICY tenant_isolation ON {table} "
            "USING (company_id = current_setting('app.current_company_id')::int)"
        )

    op.add_column(
        "contracts",
        sa.Column(
            "cost_center_id", sa.Integer, sa.ForeignKey("cost_centers.id", ondelete="SET NULL")
        ),
    )

    conn = op.get_bind()
    conn.execute(
        sa.text(
            "INSERT INTO cost_centers (company_id, name, active, created_at, updated_at) "
            "SELECT DISTINCT company_id, cost_center, true, now(), now() "
            "FROM contracts WHERE cost_center IS NOT NULL"
        )
    )
    conn.execute(
        sa.text(
            "UPDATE contracts c SET cost_center_id = cc.id "
            "FROM cost_centers cc "
            "WHERE cc.company_id = c.company_id AND cc.name = c.cost_center "
            "AND c.cost_center IS NOT NULL"
        )
    )
    op.drop_column("contracts", "cost_center")


def downgrade() -> None:
    op.add_column("contracts", sa.Column("cost_center", sa.String(120)))
    conn = op.get_bind()
    conn.execute(
        sa.text(
            "UPDATE contracts c SET cost_center = cc.name "
            "FROM cost_centers cc "
            "WHERE cc.id = c.cost_center_id"
        )
    )
    op.drop_column("contracts", "cost_center_id")

    for table in RLS_TABLES:
        op.execute(f"DROP POLICY IF EXISTS tenant_isolation ON {table}")
        op.execute(f"ALTER TABLE {table} DISABLE ROW LEVEL SECURITY")

    op.drop_index("ix_cost_centers_company_active", table_name="cost_centers")
    op.drop_table("cost_centers")
