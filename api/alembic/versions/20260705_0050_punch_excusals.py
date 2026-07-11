"""Abono de ponto (registro de auditoria + neutralização no banco de horas).

Revision ID: 20260705_0050
Revises: 20260705_0049
Create Date: 2026-07-05

- punch_excusals: abono concedido diretamente pelo RH (sem fluxo de aprovação,
  quem cria já é o aprovador), justificando um dia ou uma quantidade de minutos
  sem impactar o banco de horas do funcionário.
"""

import sqlalchemy as sa

from alembic import op

revision = "20260705_0050"
down_revision = "20260705_0049"
branch_labels = None
depends_on = None

RLS_TABLES = ["punch_excusals"]


def upgrade() -> None:
    op.create_table(
        "punch_excusals",
        sa.Column("id", sa.Integer(), nullable=False, autoincrement=True),
        sa.Column("company_id", sa.Integer(), nullable=False),
        sa.Column("employee_id", sa.Integer(), nullable=False),
        sa.Column("reference_date", sa.Date(), nullable=False),
        sa.Column("minutes", sa.Integer(), nullable=True),
        sa.Column("reason", sa.Text(), nullable=False),
        sa.Column("created_by_user_id", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.Column(
            "updated_at",
            sa.DateTime(),
            server_default=sa.func.now(),
            onupdate=sa.func.now(),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["company_id"], ["companies.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["employee_id"], ["employees.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["created_by_user_id"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_punch_excusals_employee", "punch_excusals", ["company_id", "employee_id"])
    op.create_index("ix_punch_excusals_date", "punch_excusals", ["company_id", "reference_date"])

    for table in RLS_TABLES:
        op.execute(f"ALTER TABLE {table} ENABLE ROW LEVEL SECURITY")
        op.execute(
            f"CREATE POLICY tenant_isolation ON {table} "
            "USING (company_id = current_setting('app.current_company_id')::int)"
        )


def downgrade() -> None:
    for table in RLS_TABLES:
        op.execute(f"DROP POLICY IF EXISTS tenant_isolation ON {table}")
        op.execute(f"ALTER TABLE {table} DISABLE ROW LEVEL SECURITY")

    op.drop_index("ix_punch_excusals_date", table_name="punch_excusals")
    op.drop_index("ix_punch_excusals_employee", table_name="punch_excusals")
    op.drop_table("punch_excusals")
