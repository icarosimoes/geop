"""suppliers: adiciona bairro (address_neighborhood) para paridade com o lookup de CEP

Revision ID: 20260713_0059
Revises: 20260711_0058
Create Date: 2026-07-13
"""

import sqlalchemy as sa

from alembic import op

revision = "20260713_0059"
down_revision = "20260711_0058"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("suppliers", sa.Column("address_neighborhood", sa.String(120)))


def downgrade() -> None:
    op.drop_column("suppliers", "address_neighborhood")
