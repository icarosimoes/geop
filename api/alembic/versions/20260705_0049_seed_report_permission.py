"""seed report.view permission

Revision ID: 20260705_0049
Revises: 20260705_0048
Create Date: 2026-07-05
"""

import sqlalchemy as sa

from alembic import op

revision = "20260705_0049"
down_revision = "20260705_0048"
branch_labels = None
depends_on = None

PERMISSIONS = [
    ("report.view", "Ver relatórios", "report"),
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
