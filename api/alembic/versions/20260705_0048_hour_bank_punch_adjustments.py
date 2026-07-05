"""Banco de horas e ajuste de ponto com aprovação.

Revision ID: 20260705_0048
Revises: 20260704_0047
Create Date: 2026-07-05

- hour_bank_entries: lançamentos diários calculados (escala x pontos) e saldo
  inicial migrado de outro sistema.
- punch_adjustment_requests: solicitação do funcionário (Portal do Colaborador)
  para corrigir uma batida existente ou registrar uma batida esquecida, sujeita
  à aprovação do RH.
"""

import sqlalchemy as sa

from alembic import op

revision = "20260705_0048"
down_revision = "20260704_0047"
branch_labels = None
depends_on = None

NEW_PERMISSIONS = [
    ("hour_bank.view", "Ver banco de horas", "hour_bank"),
    ("hour_bank.manage", "Gerenciar banco de horas", "hour_bank"),
    ("punch_adjustment.view", "Ver solicitações de ajuste de ponto", "punch_adjustment"),
    ("punch_adjustment.manage", "Aprovar/rejeitar ajustes de ponto", "punch_adjustment"),
]

RLS_TABLES = ["hour_bank_entries", "punch_adjustment_requests"]


def upgrade() -> None:
    op.create_table(
        "hour_bank_entries",
        sa.Column("id", sa.Integer(), nullable=False, autoincrement=True),
        sa.Column("company_id", sa.Integer(), nullable=False),
        sa.Column("employee_id", sa.Integer(), nullable=False),
        sa.Column("reference_date", sa.Date(), nullable=False),
        sa.Column("expected_minutes", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("worked_minutes", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("balance_minutes", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("source", sa.String(20), nullable=False, server_default="calculated"),
        sa.Column("notes", sa.Text(), nullable=True),
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
        sa.UniqueConstraint(
            "company_id",
            "employee_id",
            "reference_date",
            "source",
            name="uq_hour_bank_entries_employee_date_source",
        ),
    )
    op.create_index(
        "ix_hour_bank_entries_employee", "hour_bank_entries", ["company_id", "employee_id"]
    )

    op.create_table(
        "punch_adjustment_requests",
        sa.Column("id", sa.Integer(), nullable=False, autoincrement=True),
        sa.Column("company_id", sa.Integer(), nullable=False),
        sa.Column("employee_id", sa.Integer(), nullable=False),
        sa.Column("punch_id", sa.Integer(), nullable=True),
        sa.Column("requested_punched_at", sa.DateTime(), nullable=False),
        sa.Column("requested_punch_type", sa.String(10), nullable=True),
        sa.Column("reason", sa.Text(), nullable=False),
        sa.Column("status", sa.String(20), nullable=False, server_default="pending"),
        sa.Column("reviewed_by_user_id", sa.Integer(), nullable=True),
        sa.Column("reviewed_at", sa.DateTime(), nullable=True),
        sa.Column("review_notes", sa.Text(), nullable=True),
        sa.Column("resulting_punch_id", sa.Integer(), nullable=True),
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
        sa.ForeignKeyConstraint(["punch_id"], ["time_punches.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["reviewed_by_user_id"], ["users.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["resulting_punch_id"], ["time_punches.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_punch_adjustment_requests_employee",
        "punch_adjustment_requests",
        ["company_id", "employee_id"],
    )
    op.create_index(
        "ix_punch_adjustment_requests_status",
        "punch_adjustment_requests",
        ["company_id", "status"],
    )

    for table in RLS_TABLES:
        op.execute(f"ALTER TABLE {table} ENABLE ROW LEVEL SECURITY")
        op.execute(
            f"CREATE POLICY tenant_isolation ON {table} "
            "USING (company_id = current_setting('app.current_company_id')::int)"
        )

    conn = op.get_bind()
    for code, name, module in NEW_PERMISSIONS:
        conn.execute(
            sa.text(
                "INSERT INTO permissions (code, name, module) VALUES (:code, :name, :module) "
                "ON CONFLICT (code) DO NOTHING"
            ),
            {"code": code, "name": name, "module": module},
        )
    conn.execute(
        sa.text(
            """
            INSERT INTO role_permissions (role_id, permission_id)
            SELECT r.id, p.id
            FROM roles r
            CROSS JOIN permissions p
            WHERE r.code = 'admin'
              AND p.code IN (
                'hour_bank.view', 'hour_bank.manage',
                'punch_adjustment.view', 'punch_adjustment.manage'
              )
            ON CONFLICT DO NOTHING
            """
        )
    )


def downgrade() -> None:
    for table in RLS_TABLES:
        op.execute(f"DROP POLICY IF EXISTS tenant_isolation ON {table}")
        op.execute(f"ALTER TABLE {table} DISABLE ROW LEVEL SECURITY")

    op.drop_index("ix_punch_adjustment_requests_status", table_name="punch_adjustment_requests")
    op.drop_index("ix_punch_adjustment_requests_employee", table_name="punch_adjustment_requests")
    op.drop_table("punch_adjustment_requests")

    op.drop_index("ix_hour_bank_entries_employee", table_name="hour_bank_entries")
    op.drop_table("hour_bank_entries")

    conn = op.get_bind()
    for code, _, _ in NEW_PERMISSIONS:
        conn.execute(sa.text("DELETE FROM permissions WHERE code = :code"), {"code": code})
