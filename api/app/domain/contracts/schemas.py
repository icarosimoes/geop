from datetime import date, datetime
from decimal import Decimal

from pydantic import BaseModel, Field, model_validator  # noqa: F401

# ---------------------------------------------------------------------------
# Supplier
# ---------------------------------------------------------------------------


class SupplierContactOut(BaseModel):
    id: int
    supplier_id: int
    name: str
    role: str | None
    email: str | None
    phone: str | None
    whatsapp: str | None
    is_primary: bool
    notes: str | None
    created_at: datetime

    class Config:
        from_attributes = True


class SupplierOut(BaseModel):
    id: int
    name: str
    document: str | None
    document_type: str | None
    category: str | None
    email: str | None
    phone: str | None
    website: str | None
    address_street: str | None
    address_number: str | None
    address_complement: str | None
    address_city: str | None
    address_state: str | None
    address_zip: str | None
    active: bool
    notes: str | None
    contacts: list[SupplierContactOut] = []
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class SupplierSummary(BaseModel):
    id: int
    name: str
    document: str | None
    category: str | None
    email: str | None
    phone: str | None
    active: bool
    contact_count: int
    contract_count: int
    updated_at: datetime


class SupplierListResponse(BaseModel):
    items: list[SupplierSummary]
    total: int
    page: int
    page_size: int


class SupplierCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)
    document: str | None = None
    document_type: str | None = None
    category: str | None = None
    email: str | None = None
    phone: str | None = None
    website: str | None = None
    address_street: str | None = None
    address_number: str | None = None
    address_complement: str | None = None
    address_city: str | None = None
    address_state: str | None = None
    address_zip: str | None = None
    notes: str | None = None


class SupplierUpdate(BaseModel):
    name: str | None = None
    document: str | None = None
    document_type: str | None = None
    category: str | None = None
    email: str | None = None
    phone: str | None = None
    website: str | None = None
    address_street: str | None = None
    address_number: str | None = None
    address_complement: str | None = None
    address_city: str | None = None
    address_state: str | None = None
    address_zip: str | None = None
    active: bool | None = None
    notes: str | None = None


class SupplierContactCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=160)
    role: str | None = None
    email: str | None = None
    phone: str | None = None
    whatsapp: str | None = None
    is_primary: bool = False
    notes: str | None = None


class SupplierContactUpdate(BaseModel):
    name: str | None = None
    role: str | None = None
    email: str | None = None
    phone: str | None = None
    whatsapp: str | None = None
    is_primary: bool | None = None
    notes: str | None = None


# ---------------------------------------------------------------------------
# Contract
# ---------------------------------------------------------------------------


class ContractAmendmentOut(BaseModel):
    id: int
    contract_id: int
    amendment_type: str
    description: str
    new_end_date: date | None
    new_value: Decimal | None
    signed_at: date | None
    created_by_user_id: int | None
    created_by_name: str | None
    created_at: datetime


class ContractApprovalStepOut(BaseModel):
    id: int
    step_order: int
    approver_user_id: int
    approver_name: str | None
    status: str
    comment: str | None
    decided_at: datetime | None


class ContractOut(BaseModel):
    id: int
    number: str | None
    title: str
    contract_type: str
    supplier_id: int | None
    supplier_name: str | None
    responsible_user_id: int | None
    responsible_name: str | None
    created_by_user_id: int | None
    status: str
    description: str | None
    conditions: str | None
    notes: str | None
    signed_at: date | None
    start_date: date | None
    end_date: date | None
    alert_days: int
    auto_renew: bool
    indexer: str | None
    total_value: Decimal | None
    monthly_value: Decimal | None
    currency: str
    payment_frequency: str | None
    payment_day: int | None
    cost_center: str | None
    budget_category: str | None
    amendments: list[ContractAmendmentOut] = []
    approval_steps: list[ContractApprovalStepOut] = []
    created_at: datetime
    updated_at: datetime


class ContractSummary(BaseModel):
    id: int
    number: str | None
    title: str
    contract_type: str
    supplier_name: str | None
    responsible_name: str | None
    status: str
    start_date: date | None
    end_date: date | None
    total_value: Decimal | None
    monthly_value: Decimal | None
    alert_days: int
    days_until_expiry: int | None
    expiry_alert: bool
    updated_at: datetime


class ContractListResponse(BaseModel):
    items: list[ContractSummary]
    total: int
    page: int
    page_size: int


class ContractCreate(BaseModel):
    number: str | None = None
    title: str = Field(..., min_length=1, max_length=255)
    contract_type: str = "servico"
    supplier_id: int | None = None
    responsible_user_id: int | None = None
    description: str | None = None
    conditions: str | None = None
    notes: str | None = None
    signed_at: date | None = None
    start_date: date | None = None
    end_date: date | None = None
    alert_days: int = 60
    auto_renew: bool = False
    indexer: str | None = None
    total_value: Decimal | None = None
    monthly_value: Decimal | None = None
    currency: str = "BRL"
    payment_frequency: str | None = None
    payment_day: int | None = None
    cost_center: str | None = None
    budget_category: str | None = None
    approver_user_ids: list[int] = []

    @model_validator(mode="after")
    def validate_dates(self) -> "ContractCreate":
        if self.start_date and self.end_date and self.start_date > self.end_date:
            raise ValueError("start_date não pode ser posterior a end_date")
        if self.signed_at and self.start_date and self.signed_at > self.start_date:
            raise ValueError("signed_at não pode ser posterior a start_date")
        return self


class ContractUpdate(BaseModel):
    number: str | None = None
    title: str | None = None
    contract_type: str | None = None
    supplier_id: int | None = None
    responsible_user_id: int | None = None
    description: str | None = None
    conditions: str | None = None
    notes: str | None = None
    signed_at: date | None = None
    start_date: date | None = None
    end_date: date | None = None
    alert_days: int | None = None
    auto_renew: bool | None = None
    indexer: str | None = None
    total_value: Decimal | None = None
    monthly_value: Decimal | None = None
    currency: str | None = None
    payment_frequency: str | None = None
    payment_day: int | None = None
    cost_center: str | None = None
    budget_category: str | None = None
    approver_user_ids: list[int] | None = None

    @model_validator(mode="after")
    def validate_dates(self) -> "ContractUpdate":
        if self.start_date and self.end_date and self.start_date > self.end_date:
            raise ValueError("start_date não pode ser posterior a end_date")
        if self.signed_at and self.start_date and self.signed_at > self.start_date:
            raise ValueError("signed_at não pode ser posterior a start_date")
        return self


class ContractStatusUpdate(BaseModel):
    status: str = Field(
        ...,
        pattern="^(rascunho|aguardando_aprovacao|ativo|em_renovacao|suspenso|encerrado|cancelado)$",
    )
    comment: str | None = None


class ContractSubmit(BaseModel):
    """Envia contrato para aprovação, opcionalmente redefinindo os aprovadores."""
    approver_user_ids: list[int] | None = None


class ContractAmendmentCreate(BaseModel):
    amendment_type: str = Field(..., pattern="^(prazo|valor|objeto|outros)$")
    description: str = Field(..., min_length=1)
    new_end_date: date | None = None
    new_value: Decimal | None = None
    signed_at: date | None = None


class ApprovalDecision(BaseModel):
    approved: bool
    comment: str | None = None


class SupplierOption(BaseModel):
    id: int
    name: str
    document: str | None


# ---------------------------------------------------------------------------
# History
# ---------------------------------------------------------------------------


class ContractHistoryItem(BaseModel):
    id: int
    event_type: str
    diff: dict | None
    user_id: int
    user_name: str | None
    created_at: datetime


class ContractHistoryResponse(BaseModel):
    items: list[ContractHistoryItem]
    total: int
