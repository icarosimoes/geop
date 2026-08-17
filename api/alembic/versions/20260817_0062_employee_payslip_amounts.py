"""employee_payslips: adiciona campos de valor (bruto/líquido/INSS/IRRF/FGTS)

Necessário para o sync GEOP -> ERP Solid (reflexão financeira de folha): sem
esses campos, o contracheque no GEOP é só um anexo PDF, sem dado estruturado
para alimentar Payable no módulo de Folha do ERP. Nullable porque upload
manual de PDF antigo continua podendo existir sem valor estruturado.

Revision ID: 20260817_0062
Revises: 20260713_0061
Create Date: 2026-08-17
"""

import sqlalchemy as sa

from alembic import op

revision = "20260817_0062"
down_revision = "20260713_0061"
branch_labels = None
depends_on = None


def upgrade() -> None:
    for column in ("gross_amount", "net_amount", "inss_amount", "irrf_amount", "fgts_amount"):
        op.add_column(
            "employee_payslips",
            sa.Column(column, sa.Numeric(15, 2), nullable=True),
        )


def downgrade() -> None:
    for column in ("fgts_amount", "irrf_amount", "inss_amount", "net_amount", "gross_amount"):
        op.drop_column("employee_payslips", column)
