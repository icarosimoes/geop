from datetime import datetime
from typing import Any, Self

from pydantic import BaseModel, Field, model_validator

from app.core.validators import validate_cpf_cnpj, validate_email_basic


def _validate_payload(payload: dict[str, Any]) -> dict[str, Any]:
    if (doc := payload.get("taxpayerDoc")) and isinstance(doc, str) and doc.strip():
        payload["taxpayerDoc"] = validate_cpf_cnpj(doc)
    if (email := payload.get("taxpayerEmail")) and isinstance(email, str) and email.strip():
        payload["taxpayerEmail"] = validate_email_basic(email)
    return payload


class FiscalRequestUserCreate(BaseModel):
    request_type: str
    title: str
    apartment: str | None = None
    requester: str
    description: str | None = None
    status: str = "Em andamento"
    payload: dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="after")
    def normalize_payload(self) -> Self:
        if self.payload:
            self.payload = _validate_payload(self.payload)
        return self


class FiscalRequestUpdate(BaseModel):
    request_type: str | None = None
    title: str | None = None
    apartment: str | None = None
    requester: str | None = None
    description: str | None = None
    status: str | None = None
    payload: dict[str, Any] | None = None

    @model_validator(mode="after")
    def normalize_payload(self) -> Self:
        if self.payload:
            self.payload = _validate_payload(self.payload)
        return self


class FiscalRequestSummary(BaseModel):
    id: int
    protocol: str
    request_type: str
    title: str | None = None
    apartment: str | None
    requester: str
    description: str | None = None
    reservation_number: str | None = None
    sla_deadline: datetime | None = None
    sla_status: str | None = None
    status: str
    payload: dict[str, Any]
    created_at: datetime
    updated_at: datetime


class FiscalRequestListResponse(BaseModel):
    items: list[FiscalRequestSummary]
    total: int
    page: int
    page_size: int
