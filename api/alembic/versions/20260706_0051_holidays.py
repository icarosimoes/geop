"""Feriados (calendário por tenant, usado no cálculo de HE 100% do espelho).

Revision ID: 20260706_0051
Revises: 20260705_0050
Create Date: 2026-07-06

- holidays: feriado nacional/estadual/municipal cadastrado manualmente pelo
  tenant, usado por mirror.py para qualificar um dia como dia de descanso
  (HE 100%) além de domingo e folga agendada.
"""

import sqlalchemy as sa

from alembic import op

revision = "20260706_0051"
down_revision = "20260705_0050"
branch_labels = None
depends_on = None

RLS_TABLES = ["holidays"]

PERMISSIONS = [
    ("holiday.view", "Ver feriados", "timeclock"),
    ("holiday.manage", "Gerenciar feriados", "timeclock"),
]


def upgrade() -> None:
    op.create_table(
        "holidays",
        sa.Column("id", sa.Integer(), nullable=False, autoincrement=True),
        sa.Column("company_id", sa.Integer(), nullable=False),
        sa.Column("date", sa.Date(), nullable=False),
        sa.Column("name", sa.String(length=120), nullable=False),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.Column(
            "updated_at",
            sa.DateTime(),
            server_default=sa.func.now(),
            onupdate=sa.func.now(),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["company_id"], ["companies.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("company_id", "date", name="uq_holidays_company_date"),
    )
    op.create_index("ix_holidays_date", "holidays", ["company_id", "date"])

    for table in RLS_TABLES:
        op.execute(f"ALTER TABLE {table} ENABLE ROW LEVEL SECURITY")
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

    for table in RLS_TABLES:
        op.execute(f"DROP POLICY IF EXISTS tenant_isolation ON {table}")
        op.execute(f"ALTER TABLE {table} DISABLE ROW LEVEL SECURITY")

    op.drop_index("ix_holidays_date", table_name="holidays")
    op.drop_table("holidays")
