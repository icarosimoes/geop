from datetime import date, datetime
from typing import Any

from pydantic import BaseModel, Field, field_validator


class PlatformLoginRequest(BaseModel):
    email: str = Field(min_length=3, max_length=255)
    password: str = Field(min_length=1, max_length=72)

    @field_validator("email")
    @classmethod
    def normalize_email(cls, value: str) -> str:
        return value.strip().lower()


class PlatformTokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int
    name: str
    role: str


class ImpersonationLinkResponse(BaseModel):
    web_url: str


class PlatformMetricsResponse(BaseModel):
    tenants_total: int
    tenants_active: int
    tenants_trial: int
    tenants_past_due: int
    mrr_cents: int


class TenantSummary(BaseModel):
    id: int
    name: str
    slug: str
    email: str | None = None
    document: str | None = None
    trade_name: str | None = None
    address_street: str | None = None
    address_number: str | None = None
    address_complement: str | None = None
    address_neighborhood: str | None = None
    address_city: str | None = None
    address_state: str | None = None
    address_zip: str | None = None
    timezone: str = "America/Sao_Paulo"
    status: str
    users_count: int
    subscription_status: str | None
    plan_name: str | None
    trial_ends_at: datetime | None


class PlanResponse(BaseModel):
    id: int
    code: str
    name: str
    price_cents: int
    currency: str
    billing_period: str
    features: dict[str, Any]
    limits: dict[str, Any]
    active: bool
    public: bool


# ---------------------------------------------------------------------------
# Tenant CRUD
# ---------------------------------------------------------------------------


class TenantCreate(BaseModel):
    name: str = Field(min_length=1, max_length=160)
    slug: str = Field(min_length=1, max_length=100)
    email: str | None = Field(None, max_length=255)
    document: str | None = Field(None, max_length=20)
    trade_name: str | None = Field(None, max_length=160)
    address_street: str | None = Field(None, max_length=255)
    address_number: str | None = Field(None, max_length=20)
    address_complement: str | None = Field(None, max_length=120)
    address_neighborhood: str | None = Field(None, max_length=120)
    address_city: str | None = Field(None, max_length=120)
    address_state: str | None = Field(None, max_length=2)
    address_zip: str | None = Field(None, max_length=10)
    timezone: str = "America/Sao_Paulo"
    plan_id: int
    trial_days: int = 14

    @field_validator("slug")
    @classmethod
    def normalize_slug(cls, value: str) -> str:
        return value.strip().lower()


class TenantUpdate(BaseModel):
    name: str | None = Field(None, max_length=160)
    email: str | None = Field(None, max_length=255)
    document: str | None = Field(None, max_length=20)
    trade_name: str | None = Field(None, max_length=160)
    address_street: str | None = Field(None, max_length=255)
    address_number: str | None = Field(None, max_length=20)
    address_complement: str | None = Field(None, max_length=120)
    address_neighborhood: str | None = Field(None, max_length=120)
    address_city: str | None = Field(None, max_length=120)
    address_state: str | None = Field(None, max_length=2)
    address_zip: str | None = Field(None, max_length=10)
    status: str | None = Field(None, max_length=20)
    timezone: str | None = Field(None, max_length=60)


class InvoiceSummary(BaseModel):
    id: int
    value_cents: int
    status: str
    due_date: date
    payment_date: date | None
    external_payment_id: str | None


class SubscriptionDetail(BaseModel):
    id: int
    plan_id: int
    plan_name: str
    plan_code: str
    status: str
    trial_ends_at: datetime | None
    current_period_start: datetime | None
    current_period_end: datetime | None
    past_due_since: datetime | None
    suspended_at: datetime | None
    invoices: list[InvoiceSummary] = []


class TenantDetail(BaseModel):
    id: int
    name: str
    slug: str
    email: str | None
    document: str | None
    trade_name: str | None = None
    address_street: str | None = None
    address_number: str | None = None
    address_complement: str | None = None
    address_neighborhood: str | None = None
    address_city: str | None = None
    address_state: str | None = None
    address_zip: str | None = None
    status: str
    timezone: str
    users_count: int
    created_at: datetime
    subscription: SubscriptionDetail | None


# ---------------------------------------------------------------------------
# Plan CRUD
# ---------------------------------------------------------------------------


class PlanCreate(BaseModel):
    code: str = Field(min_length=1, max_length=60)
    name: str = Field(min_length=1, max_length=120)
    price_cents: int = 0
    currency: str = "BRL"
    billing_period: str = "monthly"
    features: dict[str, Any] = {}
    limits: dict[str, Any] = {}
    active: bool = True
    public: bool = True


class PlanUpdate(BaseModel):
    name: str | None = None
    price_cents: int | None = None
    features: dict[str, Any] | None = None
    limits: dict[str, Any] | None = None
    active: bool | None = None
    public: bool | None = None


# ---------------------------------------------------------------------------
# Subscription
# ---------------------------------------------------------------------------


class SubscriptionUpdate(BaseModel):
    plan_id: int | None = None
    status: str | None = None


class SubscriptionWithInvoices(BaseModel):
    subscription: SubscriptionDetail
    invoices: list[InvoiceSummary]


# ---------------------------------------------------------------------------
# Billing lifecycle
# ---------------------------------------------------------------------------


class LifecycleProcessed(BaseModel):
    company_id: int
    company_name: str
    action: str


class LifecycleResponse(BaseModel):
    processed: list[LifecycleProcessed]


# ---------------------------------------------------------------------------
# Platform users (equipe interna)
# ---------------------------------------------------------------------------


class PlatformUserCreate(BaseModel):
    name: str = Field(min_length=1, max_length=160)
    email: str = Field(min_length=3, max_length=255)
    role: str = "read_only"
    password: str = Field(min_length=8, max_length=72)

    @field_validator("email")
    @classmethod
    def normalize_email(cls, value: str) -> str:
        return value.strip().lower()


class PlatformUserUpdate(BaseModel):
    name: str | None = Field(None, max_length=160)
    email: str | None = Field(None, max_length=255)
    role: str | None = None
    password: str | None = Field(None, min_length=8, max_length=72)
    active: bool | None = None


class PlatformUserResponse(BaseModel):
    id: int
    name: str
    email: str
    role: str
    active: bool
    last_login_at: datetime | None
    created_at: datetime


# ---------------------------------------------------------------------------
# Support requests
# ---------------------------------------------------------------------------


class SupportRequestUpdate(BaseModel):
    status: str = Field(min_length=1, max_length=20)


class SupportRequestResponse(BaseModel):
    id: int
    company_id: int
    company_name: str | None
    contact_name: str
    contact_whatsapp: str
    message: str | None
    status: str
    created_at: datetime


# ---------------------------------------------------------------------------
# Usage
# ---------------------------------------------------------------------------


class UsageRecordResponse(BaseModel):
    id: int
    company_id: int
    company_name: str | None
    metric: str
    value: int
    period_start: date
    period_end: date
    created_at: datetime


# ---------------------------------------------------------------------------
# Configurações — e-mail transacional (Brevo)
# ---------------------------------------------------------------------------


class PlatformEmailConfig(BaseModel):
    brevo_api_key: str | None = Field(None, max_length=255)
    email_from_address: str | None = Field(None, max_length=255)
    email_from_name: str | None = Field(None, max_length=160)


class PlatformEmailRead(BaseModel):
    brevo_configured: bool
    email_from_address: str | None
    email_from_name: str | None
