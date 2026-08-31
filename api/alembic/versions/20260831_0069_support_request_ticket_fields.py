"""central de suporte: assunto, prioridade e resposta em support_requests

Revision ID: 20260831_0069
Revises: 20260831_0068
Create Date: 2026-08-31

Fecha o ciclo do pedido de suporte: hoje o tenant manda nome/whatsapp/mensagem
livre e nunca vê a resposta do time. Adiciona `subject`/`priority` ao pedido e
`response_message`/`responded_by` para a resposta do admin da plataforma
chegar de volta ao tenant (ver docs/oportunidades-legado-operacao.md#6).
"""

import sqlalchemy as sa

from alembic import op

revision = "20260831_0069"
down_revision = "20260831_0068"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "support_requests", sa.Column("subject", sa.String(length=160), nullable=True)
    )
    op.add_column(
        "support_requests",
        sa.Column("priority", sa.String(length=10), server_default="MEDIA", nullable=False),
    )
    op.add_column(
        "support_requests",
        sa.Column("response_message", sa.String(length=2000), nullable=True),
    )
    op.add_column(
        "support_requests", sa.Column("responded_by", sa.Integer(), nullable=True)
    )
    op.create_foreign_key(
        "fk_support_requests_responded_by",
        "support_requests",
        "platform_users",
        ["responded_by"],
        ["id"],
        ondelete="SET NULL",
    )


def downgrade() -> None:
    op.drop_constraint(
        "fk_support_requests_responded_by", "support_requests", type_="foreignkey"
    )
    op.drop_column("support_requests", "responded_by")
    op.drop_column("support_requests", "response_message")
    op.drop_column("support_requests", "priority")
    op.drop_column("support_requests", "subject")
