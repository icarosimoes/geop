"""add operational discrepancy reports

Revision ID: 20260828_0064
Revises: 20260818_0063
Create Date: 2026-08-28
"""

import sqlalchemy as sa

from alembic import op

revision = "20260828_0064"
down_revision = "20260818_0063"
branch_labels = None
depends_on = None

PERMISSIONS = (
    ("discrepancy_report.view", "Ver conferências de discrepâncias", "discrepancy_report"),
    ("discrepancy_report.create", "Criar conferências de discrepâncias", "discrepancy_report"),
    ("discrepancy_report.edit", "Editar conferências de discrepâncias", "discrepancy_report"),
    ("discrepancy_report.delete", "Excluir conferências de discrepâncias", "discrepancy_report"),
)


def upgrade() -> None:
    op.create_table(
        "discrepancy_reports",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("company_id", sa.Integer(), nullable=False),
        sa.Column("report_date", sa.Date(), nullable=False),
        sa.Column("prepared_by_user_id", sa.Integer(), nullable=True),
        sa.Column("checked_by_user_id", sa.Integer(), nullable=True),
        sa.Column("received_by_user_id", sa.Integer(), nullable=True),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("observations", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.Column("deleted_at", sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(["company_id"], ["companies.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["prepared_by_user_id"], ["users.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["checked_by_user_id"], ["users.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["received_by_user_id"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_discrepancy_reports_company_date",
        "discrepancy_reports",
        ["company_id", "report_date"],
    )
    op.create_table(
        "discrepancy_report_entries",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("report_id", sa.Integer(), nullable=False),
        sa.Column("location_id", sa.Integer(), nullable=False),
        sa.Column("first_code", sa.String(length=40), nullable=True),
        sa.Column("second_code", sa.String(length=40), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.ForeignKeyConstraint(["report_id"], ["discrepancy_reports.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["location_id"], ["locations.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("report_id", "location_id", name="uq_discrepancy_entries_location"),
    )
    op.create_index(
        "ix_discrepancy_entries_report",
        "discrepancy_report_entries",
        ["report_id"],
    )

    conn = op.get_bind()
    conn.execute(
        sa.text(
            "ALTER TABLE discrepancy_reports ENABLE ROW LEVEL SECURITY"
        )
    )
    conn.execute(sa.text("ALTER TABLE discrepancy_reports FORCE ROW LEVEL SECURITY"))
    conn.execute(
        sa.text(
            "CREATE POLICY tenant_isolation ON discrepancy_reports "
            "USING (company_id = current_setting('app.current_company_id')::int)"
        )
    )
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
    conn.execute(sa.text("DROP POLICY IF EXISTS tenant_isolation ON discrepancy_reports"))
    conn.execute(sa.text("ALTER TABLE discrepancy_reports DISABLE ROW LEVEL SECURITY"))
    for code, _, _ in PERMISSIONS:
        conn.execute(sa.text("DELETE FROM permissions WHERE code = :code"), {"code": code})
    op.drop_index("ix_discrepancy_entries_report", table_name="discrepancy_report_entries")
    op.drop_table("discrepancy_report_entries")
    op.drop_index("ix_discrepancy_reports_company_date", table_name="discrepancy_reports")
    op.drop_table("discrepancy_reports")
