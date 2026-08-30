"""Schemas Pydantic para o domínio email_client."""

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field, field_validator


# ── Contas de e-mail ──


class WhatsAppTarget(BaseModel):
    number: str = Field(..., description="Número ou JID do grupo WhatsApp")
    label: str | None = None


class EmailAccountCreate(BaseModel):
    name: str = Field(..., max_length=120)
    provider: Literal["gmail", "microsoft", "imap"] = "imap"
    protocol: Literal["imap", "pop3"] = "imap"
    imap_host: str = Field(..., max_length=255)
    imap_port: int = Field(993, ge=1, le=65535)
    imap_ssl: bool = True
    username: str = Field(..., max_length=255)
    password: str = Field(..., min_length=1)

    @field_validator("imap_host")
    @classmethod
    def normalizar_host(cls, v: str) -> str:
        return v.strip().lower()


class EmailAccountUpdate(BaseModel):
    name: str | None = Field(None, max_length=120)
    protocol: Literal["imap", "pop3"] | None = None
    imap_host: str | None = Field(None, max_length=255)
    imap_port: int | None = Field(None, ge=1, le=65535)
    imap_ssl: bool | None = None
    username: str | None = Field(None, max_length=255)
    password: str | None = None
    active: bool | None = None


class EmailAccountRead(BaseModel):
    id: int
    name: str
    provider: str
    protocol: str
    imap_host: str
    imap_port: int
    imap_ssl: bool
    username: str
    active: bool
    last_synced_at: datetime | None
    created_at: datetime

    model_config = {"from_attributes": True}


# ── Mensagens ──


class EmailMessageRead(BaseModel):
    id: int
    account_id: int
    uid: str
    folder: str
    from_addr: str
    from_name: str | None
    to_addr: str | None
    subject: str | None
    body_text: str | None
    received_at: datetime | None
    is_read: bool
    is_flagged: bool
    created_at: datetime

    model_config = {"from_attributes": True}


class EmailMessageList(BaseModel):
    id: int
    account_id: int
    uid: str
    from_addr: str
    from_name: str | None
    subject: str | None
    received_at: datetime | None
    is_read: bool
    is_flagged: bool

    model_config = {"from_attributes": True}


class MessagePage(BaseModel):
    items: list[EmailMessageList]
    total: int
    page: int
    page_size: int


# ── Regras de alerta ──


class EmailAlertRuleCreate(BaseModel):
    name: str = Field(..., max_length=120)
    filter_type: Literal["subject", "domain", "sender"]
    filter_value: str = Field(..., max_length=500)
    whatsapp_targets: list[WhatsAppTarget] = Field(default_factory=list)
    account_ids: list[int] = Field(default_factory=list)


class EmailAlertRuleUpdate(BaseModel):
    name: str | None = Field(None, max_length=120)
    active: bool | None = None
    filter_type: Literal["subject", "domain", "sender"] | None = None
    filter_value: str | None = Field(None, max_length=500)
    whatsapp_targets: list[WhatsAppTarget] | None = None
    account_ids: list[int] | None = None


class EmailAlertRuleRead(BaseModel):
    id: int
    name: str
    active: bool
    filter_type: str
    filter_value: str
    whatsapp_targets: list[WhatsAppTarget]
    account_ids: list[int]
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


# ── Sincronização manual ──


class SyncResult(BaseModel):
    account_id: int
    new_messages: int
    alerts_sent: int
    error: str | None = None
