from datetime import date, datetime
from decimal import Decimal

from pydantic import BaseModel, Field

# ---------------------------------------------------------------------------
# Customer
# ---------------------------------------------------------------------------


class CustomerOut(BaseModel):
    id: int
    name: str
    document: str | None
    document_type: str | None
    email: str | None
    phone: str | None
    whatsapp: str | None
    address_street: str | None
    address_number: str | None
    address_complement: str | None
    address_neighborhood: str | None
    address_city: str | None
    address_state: str | None
    address_zip: str | None
    active: bool
    notes: str | None
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class CustomerSummary(BaseModel):
    id: int
    name: str
    document: str | None
    email: str | None
    phone: str | None
    active: bool
    quote_count: int
    updated_at: datetime


class CustomerListResponse(BaseModel):
    items: list[CustomerSummary]
    total: int
    page: int
    page_size: int


class CustomerCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)
    document: str | None = None
    document_type: str | None = None
    email: str | None = None
    phone: str | None = None
    whatsapp: str | None = None
    address_street: str | None = None
    address_number: str | None = None
    address_complement: str | None = None
    address_neighborhood: str | None = None
    address_city: str | None = None
    address_state: str | None = None
    address_zip: str | None = None
    notes: str | None = None


class CustomerUpdate(BaseModel):
    name: str | None = None
    document: str | None = None
    document_type: str | None = None
    email: str | None = None
    phone: str | None = None
    whatsapp: str | None = None
    address_street: str | None = None
    address_number: str | None = None
    address_complement: str | None = None
    address_neighborhood: str | None = None
    address_city: str | None = None
    address_state: str | None = None
    address_zip: str | None = None
    active: bool | None = None
    notes: str | None = None


class CustomerOption(BaseModel):
    id: int
    name: str
    document: str | None


# ---------------------------------------------------------------------------
# Quote
# ---------------------------------------------------------------------------


class QuoteItemIn(BaseModel):
    item_type: str = Field("produto", pattern="^(produto|servico)$")
    stock_item_id: int | None = None
    description: str = Field(..., min_length=1, max_length=255)
    unit: str = "un"
    quantity: Decimal = Decimal(1)
    unit_price: Decimal = Decimal(0)
    discount_percent: Decimal | None = None


class QuoteItemOut(BaseModel):
    id: int
    item_type: str
    stock_item_id: int | None
    description: str
    unit: str
    quantity: Decimal
    unit_price: Decimal
    discount_percent: Decimal | None
    line_total: Decimal
    sort_order: int


class QuoteOut(BaseModel):
    id: int
    number: str | None
    customer_id: int
    customer_name: str | None
    title: str
    status: str
    responsible_user_id: int | None
    responsible_name: str | None
    created_by_user_id: int | None
    description: str | None
    conditions: str | None
    notes: str | None
    issued_at: date | None
    valid_until: date | None
    discount_amount: Decimal
    subtotal: Decimal
    total: Decimal
    decided_at: datetime | None
    decision_note: str | None
    items: list[QuoteItemOut] = []
    acceptance_url: str | None = None
    created_at: datetime
    updated_at: datetime


class QuoteSummary(BaseModel):
    id: int
    number: str | None
    customer_id: int
    customer_name: str | None
    title: str
    status: str
    total: Decimal
    valid_until: date | None
    updated_at: datetime


class QuoteListResponse(BaseModel):
    items: list[QuoteSummary]
    total: int
    page: int
    page_size: int


class QuoteCreate(BaseModel):
    customer_id: int
    title: str = Field(..., min_length=1, max_length=255)
    responsible_user_id: int | None = None
    description: str | None = None
    conditions: str | None = None
    notes: str | None = None
    valid_until: date | None = None
    discount_amount: Decimal = Decimal(0)
    items: list[QuoteItemIn] = []


class QuoteUpdate(BaseModel):
    customer_id: int | None = None
    title: str | None = None
    responsible_user_id: int | None = None
    description: str | None = None
    conditions: str | None = None
    notes: str | None = None
    valid_until: date | None = None
    discount_amount: Decimal | None = None
    items: list[QuoteItemIn] | None = None


class QuoteSendResponse(BaseModel):
    quote: QuoteOut
    acceptance_url: str


# ---------------------------------------------------------------------------
# Public (aceite do cliente, sem login)
# ---------------------------------------------------------------------------


class PublicQuoteOut(BaseModel):
    number: str | None
    title: str
    status: str
    customer_name: str
    company_name: str
    description: str | None
    conditions: str | None
    notes: str | None
    issued_at: date | None
    valid_until: date | None
    expired: bool
    discount_amount: Decimal
    subtotal: Decimal
    total: Decimal
    decided_at: datetime | None
    items: list[QuoteItemOut]


class PublicQuoteDecision(BaseModel):
    decision_note: str | None = None


# ---------------------------------------------------------------------------
# Sales Invoice / Payment (definidos antes de Sale — SaleOut embute a lista de
# faturas, igual QuoteOut embute os itens)
# ---------------------------------------------------------------------------


class SalesPaymentOut(BaseModel):
    id: int
    invoice_id: int
    amount: Decimal
    method: str | None
    paid_at: date
    reference: str | None
    notes: str | None
    created_at: datetime


class SalesInvoiceOut(BaseModel):
    id: int
    sale_id: int
    number: str | None
    nf_number: str | None
    status: str
    amount: Decimal
    issued_at: date | None
    due_date: date | None
    notes: str | None
    paid_total: Decimal
    payments: list[SalesPaymentOut] = []
    created_at: datetime
    updated_at: datetime


class SalesInvoiceCreate(BaseModel):
    amount: Decimal = Field(..., gt=0)
    issued_at: date | None = None
    due_date: date | None = None
    nf_number: str | None = None
    notes: str | None = None


class SalesInvoiceUpdate(BaseModel):
    status: str | None = Field(None, pattern="^(pendente|faturada|paga|atrasada|cancelada)$")
    amount: Decimal | None = None
    issued_at: date | None = None
    due_date: date | None = None
    nf_number: str | None = None
    notes: str | None = None


class SalesPaymentCreate(BaseModel):
    amount: Decimal = Field(..., gt=0)
    paid_at: date
    method: str | None = Field(None, pattern="^(pix|boleto|cartao|transferencia|dinheiro|outro)$")
    reference: str | None = None
    notes: str | None = None


# ---------------------------------------------------------------------------
# Sale
# ---------------------------------------------------------------------------


class SaleOut(BaseModel):
    id: int
    number: str | None
    quote_id: int
    customer_id: int
    customer_name: str | None
    status: str
    total_value: Decimal
    responsible_user_id: int | None
    responsible_name: str | None
    delivered_at: date | None
    installation_status: str
    installation_scheduled_at: date | None
    installation_completed_at: date | None
    installation_notes: str | None
    notes: str | None
    invoiced_total: Decimal
    received_total: Decimal
    invoices: list[SalesInvoiceOut] = []
    created_at: datetime
    updated_at: datetime


class SaleSummary(BaseModel):
    id: int
    number: str | None
    customer_id: int
    customer_name: str | None
    status: str
    total_value: Decimal
    installation_status: str
    delivered_at: date | None
    invoiced_total: Decimal
    received_total: Decimal
    updated_at: datetime


class SaleListResponse(BaseModel):
    items: list[SaleSummary]
    total: int
    page: int
    page_size: int


class SaleUpdate(BaseModel):
    status: str | None = Field(None, pattern="^(confirmada|entregue|concluida|cancelada)$")
    delivered_at: date | None = None
    installation_status: str | None = Field(
        None, pattern="^(pendente|agendada|em_andamento|concluida|cancelada)$"
    )
    installation_scheduled_at: date | None = None
    installation_completed_at: date | None = None
    installation_notes: str | None = None
    notes: str | None = None


# ---------------------------------------------------------------------------
# Funil (dashboard)
# ---------------------------------------------------------------------------


class CommercialFunnel(BaseModel):
    quoted_count: int
    quoted_total: Decimal
    approved_count: int
    approved_total: Decimal
    delivered_count: int
    invoiced_total: Decimal
    received_total: Decimal
