"""companies: adiciona nome fantasia e endereço completo para consulta de CNPJ/CEP

Revision ID: 20260713_0060
Revises: 20260713_0059
Create Date: 2026-07-13
"""

import sqlalchemy as sa

from alembic import op

revision = "20260713_0060"
down_revision = "20260713_0059"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("companies", sa.Column("trade_name", sa.String(160)))
    op.add_column("companies", sa.Column("address_street", sa.String(255)))
    op.add_column("companies", sa.Column("address_number", sa.String(20)))
    op.add_column("companies", sa.Column("address_complement", sa.String(120)))
    op.add_column("companies", sa.Column("address_neighborhood", sa.String(120)))
    op.add_column("companies", sa.Column("address_city", sa.String(120)))
    op.add_column("companies", sa.Column("address_state", sa.String(2)))
    op.add_column("companies", sa.Column("address_zip", sa.String(10)))


def downgrade() -> None:
    op.drop_column("companies", "address_zip")
    op.drop_column("companies", "address_state")
    op.drop_column("companies", "address_city")
    op.drop_column("companies", "address_neighborhood")
    op.drop_column("companies", "address_complement")
    op.drop_column("companies", "address_number")
    op.drop_column("companies", "address_street")
    op.drop_column("companies", "trade_name")
