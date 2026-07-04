"""Add HR fields to Employee: job_title, hire_date, termination_date, registration_number, sector_id

Revision ID: 20260704_0046
Revises: 20260704_0045
Create Date: 2026-07-04

E10 (cargo/admissão/matrícula) e E11 (setor/departamento) do backlog do
cadastro de funcionários.
"""

from alembic import op
import sqlalchemy as sa


revision = "20260704_0046"
down_revision = "20260704_0045"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("employees", sa.Column("job_title", sa.String(120), nullable=True))
    op.add_column("employees", sa.Column("hire_date", sa.String(10), nullable=True))
    op.add_column("employees", sa.Column("termination_date", sa.String(10), nullable=True))
    op.add_column("employees", sa.Column("registration_number", sa.String(40), nullable=True))
    op.add_column("employees", sa.Column("sector_id", sa.Integer(), nullable=True))
    op.create_index("ix_employees_sector_id", "employees", ["sector_id"])
    op.create_foreign_key(
        "fk_employees_sector_id",
        "employees",
        "sectors",
        ["sector_id"],
        ["id"],
        ondelete="SET NULL",
    )


def downgrade() -> None:
    op.drop_constraint("fk_employees_sector_id", "employees", type_="foreignkey")
    op.drop_index("ix_employees_sector_id", table_name="employees")
    op.drop_column("employees", "sector_id")
    op.drop_column("employees", "registration_number")
    op.drop_column("employees", "termination_date")
    op.drop_column("employees", "hire_date")
    op.drop_column("employees", "job_title")
