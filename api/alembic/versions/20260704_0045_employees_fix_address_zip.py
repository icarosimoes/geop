"""Fix address_zip column size for Brazilian CEP format (XXXXX-XXX)

Revision ID: 20260704_0045
Revises: 20260703_0044
Create Date: 2026-07-04

Brazilian CEP format is XXXXX-XXX (9 chars), not 8.
"""

from alembic import op
import sqlalchemy as sa


revision = "20260704_0045"
down_revision = "20260703_0044"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.alter_column("employees", "address_zip", type_=sa.String(10))


def downgrade() -> None:
    op.alter_column("employees", "address_zip", type_=sa.String(8))
