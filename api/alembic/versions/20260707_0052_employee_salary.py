"""Add Employee.salary

Revision ID: 20260707_0052
Revises: 20260706_0051
Create Date: 2026-07-07

Salário mensal do funcionário, usado para calcular o valor em R$ da hora
extra no espelho de ponto (ver mirror.py) quando a config
`timeclock.overtime_paid_in_cash` estiver ligada.
"""

from alembic import op
import sqlalchemy as sa


revision = "20260707_0052"
down_revision = "20260706_0051"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("employees", sa.Column("salary", sa.Numeric(10, 2), nullable=True))


def downgrade() -> None:
    op.drop_column("employees", "salary")
