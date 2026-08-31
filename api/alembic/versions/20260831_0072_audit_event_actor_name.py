"""audit_events: user_id opcional + actor_name (atores sem linha em users)

Revision ID: 20260831_0072
Revises: 20260831_0071
Create Date: 2026-08-31

Chamados de suporte agora geram timeline (`app/domain/timeline`): cada resposta
do admin da plataforma vira um `AuditEvent`. O admin é um `PlatformUser`, não um
`User` do tenant — não tem `id` compatível com a FK `users.id`. `user_id` vira
opcional e `actor_name` guarda o nome do ator pra exibição quando não há User
correspondente. Eventos existentes (todos com `user_id` de um User real) não são
afetados.
"""

import sqlalchemy as sa

from alembic import op

revision = "20260831_0072"
down_revision = "20260831_0071"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.alter_column("audit_events", "user_id", existing_type=sa.Integer(), nullable=True)
    op.add_column("audit_events", sa.Column("actor_name", sa.String(length=160), nullable=True))


def downgrade() -> None:
    op.drop_column("audit_events", "actor_name")
    op.alter_column("audit_events", "user_id", existing_type=sa.Integer(), nullable=False)
