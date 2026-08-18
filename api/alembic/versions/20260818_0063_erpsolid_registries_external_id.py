"""suppliers/cost_centers: adiciona import_source/external_id

Necessário para o sync erpsolid -> GEOP (Fornecedores/Centros de custo do erpsolid
alimentando o cadastro local do GEOP): mesmo padrão de dedup por
`(company_id, import_source, external_id)` já usado do lado erpsolid pra tudo que
chega do GEOP (Supplier/CostCenter/Employee lá) — replicado aqui pro sentido
contrário. Registro espelhado (import_source="erpsolid") nunca é editado
manualmente na tela do GEOP a não ser que perca o vínculo; registro criado
localmente no GEOP continua com import_source/external_id NULL, de fora do sync.

Revision ID: 20260818_0063
Revises: 20260817_0062
Create Date: 2026-08-18
"""

import sqlalchemy as sa

from alembic import op

revision = "20260818_0063"
down_revision = "20260817_0062"
branch_labels = None
depends_on = None

_TABLES = ("suppliers", "cost_centers")


def upgrade() -> None:
    for table in _TABLES:
        op.add_column(table, sa.Column("import_source", sa.String(length=30), nullable=True))
        op.add_column(table, sa.Column("external_id", sa.String(length=120), nullable=True))
        op.create_index(
            f"ix_{table}_external_id_unique",
            table,
            ["company_id", "import_source", "external_id"],
            unique=True,
            postgresql_where=sa.text("external_id IS NOT NULL"),
        )


def downgrade() -> None:
    for table in _TABLES:
        op.drop_index(f"ix_{table}_external_id_unique", table_name=table)
        op.drop_column(table, "external_id")
        op.drop_column(table, "import_source")
