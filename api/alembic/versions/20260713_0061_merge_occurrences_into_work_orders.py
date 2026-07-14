"""funde occurrences em work_orders: novos campos, work_order_participants, drop occurrences

Revision ID: 20260713_0061
Revises: 20260713_0060
Create Date: 2026-07-13
"""

import sqlalchemy as sa

from alembic import op

revision = "20260713_0061"
down_revision = "20260713_0060"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # 1. Novos campos em work_orders (portados de occurrences)
    op.add_column(
        "work_orders",
        sa.Column(
            "sector_id",
            sa.Integer(),
            sa.ForeignKey("sectors.id", ondelete="SET NULL"),
            nullable=True,
        ),
    )
    op.add_column("work_orders", sa.Column("unit", sa.String(255), nullable=True))
    op.add_column("work_orders", sa.Column("comments", sa.Text(), nullable=True))
    op.add_column("work_orders", sa.Column("deadline", sa.Date(), nullable=True))

    # 2. Remove occurrence_id de work_orders
    op.drop_constraint(
        "work_orders_occurrence_id_fkey", "work_orders", type_="foreignkey"
    )
    op.drop_column("work_orders", "occurrence_id")

    # 3. Remove occurrence_id de stock_movements
    op.drop_constraint(
        "stock_movements_occurrence_id_fkey", "stock_movements", type_="foreignkey"
    )
    op.drop_column("stock_movements", "occurrence_id")

    # 4. work_order_participants (substitui occurrence_participants)
    op.create_table(
        "work_order_participants",
        sa.Column(
            "work_order_id",
            sa.Integer,
            sa.ForeignKey("work_orders.id", ondelete="CASCADE"),
            primary_key=True,
        ),
        sa.Column(
            "user_id", sa.Integer, sa.ForeignKey("users.id", ondelete="CASCADE"), primary_key=True
        ),
        sa.Column("created_at", sa.DateTime, server_default=sa.func.now()),
    )

    # 5. Drop occurrence_participants e occurrences (RLS/índices somem junto)
    op.drop_table("occurrence_participants")
    op.drop_table("occurrences")

    # 6. Limpeza de permissões occurrence.*
    op.execute(
        "DELETE FROM role_permissions WHERE permission_id IN "
        "(SELECT id FROM permissions WHERE code LIKE 'occurrence.%')"
    )
    op.execute("DELETE FROM permissions WHERE code LIKE 'occurrence.%'")


def downgrade() -> None:
    # Recria permissões occurrence.*
    conn = op.get_bind()
    for code, name, module in [
        ("occurrence.view", "Ver ocorrências", "occurrence"),
        ("occurrence.create", "Criar ocorrências", "occurrence"),
        ("occurrence.edit", "Editar ocorrências", "occurrence"),
        ("occurrence.delete", "Excluir ocorrências", "occurrence"),
    ]:
        conn.execute(
            sa.text(
                "INSERT INTO permissions (code, name, module) VALUES (:code, :name, :module) "
                "ON CONFLICT (code) DO NOTHING"
            ),
            {"code": code, "name": name, "module": module},
        )

    # Recria occurrences (vazia, sem dados)
    op.create_table(
        "occurrences",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "company_id",
            sa.Integer(),
            sa.ForeignKey("companies.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("legacy_id", sa.Integer(), nullable=False),
        sa.Column("title", sa.String(255), nullable=False),
        sa.Column("description", sa.Text()),
        sa.Column("comments", sa.Text()),
        sa.Column("unit", sa.String(255)),
        sa.Column("deadline", sa.Date()),
        sa.Column("status", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("legacy_type_id", sa.Integer()),
        sa.Column("legacy_receiver_user_id", sa.Integer()),
        sa.Column("location_id", sa.Integer(), sa.ForeignKey("locations.id")),
        sa.Column("sector_id", sa.Integer(), sa.ForeignKey("sectors.id")),
        sa.Column("owner_user_id", sa.Integer(), sa.ForeignKey("users.id")),
        sa.Column("created_by_user_id", sa.Integer(), sa.ForeignKey("users.id")),
        sa.Column("updated_by_user_id", sa.Integer(), sa.ForeignKey("users.id")),
        sa.Column("file", sa.Text()),
        sa.Column("notify_user_ids", sa.JSON(), nullable=True),
        sa.Column("deleted_at", sa.DateTime()),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("company_id", "legacy_id", name="uq_occurrences_legacy"),
    )
    op.create_index("ix_occurrences_company_id", "occurrences", ["company_id"])
    op.create_index("ix_occurrences_status", "occurrences", ["status"])
    op.execute("ALTER TABLE occurrences ENABLE ROW LEVEL SECURITY")
    op.execute(
        "CREATE POLICY tenant_isolation ON occurrences "
        "USING (company_id = current_setting('app.current_company_id')::int)"
    )

    op.create_table(
        "occurrence_participants",
        sa.Column(
            "occurrence_id",
            sa.Integer,
            sa.ForeignKey("occurrences.id", ondelete="CASCADE"),
            primary_key=True,
        ),
        sa.Column(
            "user_id", sa.Integer, sa.ForeignKey("users.id", ondelete="CASCADE"), primary_key=True
        ),
        sa.Column("created_at", sa.DateTime, server_default=sa.func.now()),
    )

    op.drop_table("work_order_participants")

    op.add_column(
        "stock_movements",
        sa.Column(
            "occurrence_id", sa.Integer(), sa.ForeignKey("occurrences.id", ondelete="SET NULL")
        ),
    )

    op.add_column(
        "work_orders",
        sa.Column(
            "occurrence_id", sa.Integer(), sa.ForeignKey("occurrences.id", ondelete="SET NULL")
        ),
    )
    op.drop_column("work_orders", "deadline")
    op.drop_column("work_orders", "comments")
    op.drop_column("work_orders", "unit")
    op.drop_constraint("work_orders_sector_id_fkey", "work_orders", type_="foreignkey")
    op.drop_column("work_orders", "sector_id")
