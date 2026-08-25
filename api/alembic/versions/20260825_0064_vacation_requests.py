"""timeclock: tabela vacation_requests para requisição de férias pelo colaborador

Revision ID: 20260825_0064
Revises: 20260818_0063
Create Date: 2026-08-25
"""

from alembic import op
import sqlalchemy as sa

revision = "20260825_0064"
down_revision = "20260818_0063"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "vacation_requests",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("company_id", sa.Integer(), sa.ForeignKey("companies.id", ondelete="CASCADE"), nullable=False),
        sa.Column("employee_id", sa.Integer(), sa.ForeignKey("employees.id", ondelete="CASCADE"), nullable=False),
        sa.Column("start_date", sa.Date(), nullable=False),
        sa.Column("end_date", sa.Date(), nullable=False),
        sa.Column("days", sa.Integer(), nullable=False),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("status", sa.String(20), nullable=False, server_default="pending"),
        sa.Column("reviewed_by_user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("reviewed_at", sa.DateTime(), nullable=True),
        sa.Column("review_notes", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.func.now(), onupdate=sa.func.now(), nullable=False),
    )
    op.create_index("ix_vacation_requests_employee", "vacation_requests", ["company_id", "employee_id"])
    op.create_index("ix_vacation_requests_status", "vacation_requests", ["company_id", "status"])
    op.create_index("ix_vacation_requests_period", "vacation_requests", ["company_id", "start_date"])


def downgrade() -> None:
    op.drop_index("ix_vacation_requests_period", table_name="vacation_requests")
    op.drop_index("ix_vacation_requests_status", table_name="vacation_requests")
    op.drop_index("ix_vacation_requests_employee", table_name="vacation_requests")
    op.drop_table("vacation_requests")
