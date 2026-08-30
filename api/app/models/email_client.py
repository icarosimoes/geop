"""Modelos para o cliente de e-mail e alertas WhatsApp."""

from datetime import datetime

import sqlalchemy as sa
from sqlalchemy import (
    JSON,
    Boolean,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TenantMixin, TimestampMixin


class EmailAccount(Base, TenantMixin, TimestampMixin):
    """Conta de e-mail IMAP configurada por tenant."""

    __tablename__ = "email_accounts"
    __table_args__ = (Index("ix_email_accounts_company", "company_id"),)

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(120))
    provider: Mapped[str] = mapped_column(String(40), default="imap")
    # gmail | microsoft | imap
    imap_host: Mapped[str] = mapped_column(String(255))
    imap_port: Mapped[int] = mapped_column(Integer, default=993)
    imap_ssl: Mapped[bool] = mapped_column(Boolean, default=True)
    username: Mapped[str] = mapped_column(String(255))
    password_enc: Mapped[str] = mapped_column(Text)  # criptografado na camada de serviço
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    last_synced_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)


class EmailMessage(Base, TenantMixin, TimestampMixin):
    """E-mail cacheado localmente após sincronização IMAP."""

    __tablename__ = "email_messages"
    __table_args__ = (
        Index("ix_email_messages_company_account", "company_id", "account_id"),
        Index("ix_email_messages_uid", "account_id", "uid"),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    account_id: Mapped[int] = mapped_column(
        ForeignKey("email_accounts.id", ondelete="CASCADE"), index=True
    )
    uid: Mapped[str] = mapped_column(String(80))  # IMAP UID
    folder: Mapped[str] = mapped_column(String(120), default="INBOX")
    from_addr: Mapped[str] = mapped_column(String(500))
    from_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    to_addr: Mapped[str | None] = mapped_column(String(1000), nullable=True)
    subject: Mapped[str | None] = mapped_column(String(1000), nullable=True)
    body_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    body_html: Mapped[str | None] = mapped_column(Text, nullable=True)
    received_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    is_read: Mapped[bool] = mapped_column(Boolean, default=False)
    is_flagged: Mapped[bool] = mapped_column(Boolean, default=False)
    # IDs das regras que já dispararam alerta para esta mensagem (evita duplicatas)
    alerted_rule_ids: Mapped[list] = mapped_column(JSON, default=list)


class EmailAlertRule(Base, TenantMixin, TimestampMixin):
    """Regra de alerta: quando um e-mail corresponder ao filtro, envia para WhatsApp."""

    __tablename__ = "email_alert_rules"
    __table_args__ = (Index("ix_email_alert_rules_company", "company_id"),)

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(120))
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    # Tipo de filtro: subject | domain | sender
    filter_type: Mapped[str] = mapped_column(String(20))
    # Valor a comparar (case-insensitive contains para subject/sender, exact match para domain)
    filter_value: Mapped[str] = mapped_column(String(500))
    # Lista de destinos WhatsApp: [{"number": "5511999...", "label": "Grupo Financeiro"}]
    whatsapp_targets: Mapped[list] = mapped_column(JSON, default=list)
    # Quais contas monitorar ([] = todas as contas ativas do tenant)
    account_ids: Mapped[list] = mapped_column(JSON, default=list)
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
