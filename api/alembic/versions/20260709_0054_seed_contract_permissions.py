"""seed contract permissions

Revision ID: 20260709_0054
Revises: 20260709_0053
Create Date: 2026-07-09
"""

import sqlalchemy as sa

from alembic import op

revision = "20260709_0054"
down_revision = "20260709_0053"
branch_labels = None
depends_on = None

PERMISSIONS = [
    ("contract.view", "Ver contratos e fornecedores", "contract"),
    ("contract.create", "Criar contratos e fornecedores", "contract"),
    ("contract.edit", "Editar contratos e fornecedores", "contract"),
    ("contract.delete", "Excluir contratos e fornecedores", "contract"),
    ("contract.approve", "Aprovar/rejeitar contratos", "contract"),
]


def upgrade() -> None:
    conn = op.get_bind()
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
    for code, _, _ in PERMISSIONS:
        conn.execute(sa.text("DELETE FROM permissions WHERE code = :code"), {"code": code})
