"""remove solicitações fiscais (recurso descontinuado)

Revision ID: 20260831_0074
Revises: 20260831_0073
Create Date: 2026-08-31

Feature removida do produto (menu, domínio de API, dashboard, relatórios,
timeline, anexos e notificações) — dropa a tabela `fiscal_requests` (criada em
20260620_0003 e evoluída em várias migrations desde então) e as 4 permissões
`fiscal_request.*`. downgrade() recria a tabela no formato atual (colunas +
índices + RLS + permissões), mas sem os dados nem os artefatos legados do
MySQL (constraints `*_ibfk_*` duplicadas).
"""

import sqlalchemy as sa

from alembic import op

revision = "20260831_0074"
down_revision = "20260831_0073"
branch_labels = None
depends_on = None

PERMISSIONS = (
    ("fiscal_request.view", "Ver solicitações fiscais", "fiscal_request"),
    ("fiscal_request.create", "Criar solicitações fiscais", "fiscal_request"),
    ("fiscal_request.edit", "Editar solicitações fiscais", "fiscal_request"),
    ("fiscal_request.delete", "Excluir solicitações fiscais", "fiscal_request"),
)


def upgrade() -> None:
    conn = op.get_bind()
    conn.execute(sa.text("DROP POLICY IF EXISTS tenant_isolation ON fiscal_requests"))
    for code, _, _ in PERMISSIONS:
        conn.execute(sa.text("DELETE FROM permissions WHERE code = :code"), {"code": code})
    op.drop_table("fiscal_requests")


def downgrade() -> None:
    op.create_table(
        "fiscal_requests",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("company_id", sa.Integer(), nullable=False),
        sa.Column("protocol", sa.String(length=40), nullable=False),
        sa.Column("request_type", sa.String(length=120), nullable=False),
        sa.Column("title", sa.String(length=255), nullable=True),
        sa.Column("apartment", sa.String(length=40), nullable=True),
        sa.Column("requester", sa.String(length=160), nullable=False),
        sa.Column("requester_email", sa.String(length=255), nullable=True),
        sa.Column("requester_user_id", sa.Integer(), nullable=True),
        sa.Column("responsible_user_id", sa.Integer(), nullable=True),
        sa.Column("chess_user_id", sa.String(length=80), nullable=True),
        sa.Column("reservation_number", sa.String(length=80), nullable=True),
        sa.Column("sla_deadline", sa.DateTime(), nullable=True),
        sa.Column("sla_paused_at", sa.DateTime(), nullable=True),
        sa.Column("sla_paused_seconds", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("origin", sa.String(length=80), nullable=False, server_default="registro"),
        sa.Column("status", sa.String(length=40), nullable=False, server_default="Em andamento"),
        sa.Column("payload", sa.JSON(), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False
        ),
        sa.ForeignKeyConstraint(["company_id"], ["companies.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["requester_user_id"], ["users.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["responsible_user_id"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("protocol"),
    )
    op.create_index("ix_fiscal_requests_company_id", "fiscal_requests", ["company_id"])
    op.create_index(
        "ix_fiscal_requests_company_status", "fiscal_requests", ["company_id", "status"]
    )
    op.create_index("ix_fiscal_requests_request_type", "fiscal_requests", ["request_type"])
    op.create_index("ix_fiscal_requests_requester_email", "fiscal_requests", ["requester_email"])
    op.create_index(
        "ix_fiscal_requests_requester_user_id", "fiscal_requests", ["requester_user_id"]
    )
    op.create_index(
        "ix_fiscal_requests_responsible_user_id", "fiscal_requests", ["responsible_user_id"]
    )
    op.create_index("ix_fiscal_requests_status", "fiscal_requests", ["status"])

    conn = op.get_bind()
    conn.execute(sa.text("ALTER TABLE fiscal_requests ENABLE ROW LEVEL SECURITY"))
    conn.execute(sa.text("ALTER TABLE fiscal_requests FORCE ROW LEVEL SECURITY"))
    conn.execute(
        sa.text(
            "CREATE POLICY tenant_isolation ON fiscal_requests "
            "USING (company_id = current_setting('app.current_company_id')::int)"
        )
    )
    for code, name, module in PERMISSIONS:
        conn.execute(
            sa.text(
                "INSERT INTO permissions (code, name, module, created_at, updated_at) "
                "VALUES (:code, :name, :module, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP) "
                "ON CONFLICT (code) DO UPDATE SET name = EXCLUDED.name, module = EXCLUDED.module"
            ),
            {"code": code, "name": name, "module": module},
        )
