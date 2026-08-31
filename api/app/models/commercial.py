"""Pipeline comercial: Cliente -> Orçamento -> Aceite -> Venda -> Instalação ->
Faturamento -> Cobrança. Domínio separado de `contracts` (que cobre o lado de
compra/fornecedor) — este cobre o lado de venda pro cliente do tenant. Ver
app/domain/commercial/.

`SalesInvoice`/`SalesPayment` (não `Invoice`/`Payment`) pra não colidir com
`app.models.platform.Invoice` (fatura de assinatura SaaS do tenant, outro
domínio inteiramente)."""

from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import Boolean, Date, DateTime, ForeignKey, Index, Integer, Numeric, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TenantMixin, TimestampMixin

QUOTE_STATUSES = ("rascunho", "enviado", "aceito", "recusado", "expirado", "cancelado")
SALE_STATUSES = ("confirmada", "entregue", "concluida", "cancelada")
INSTALLATION_STATUSES = ("pendente", "agendada", "em_andamento", "concluida", "cancelada")
INVOICE_STATUSES = ("pendente", "faturada", "paga", "atrasada", "cancelada")


class Customer(Base, TenantMixin, TimestampMixin):
    __tablename__ = "customers"
    __table_args__ = (Index("ix_customers_company_active", "company_id", "active"),)

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(255))
    document: Mapped[str | None] = mapped_column(String(20))
    document_type: Mapped[str | None] = mapped_column(String(10))  # cpf|cnpj
    email: Mapped[str | None] = mapped_column(String(255))
    phone: Mapped[str | None] = mapped_column(String(30))
    whatsapp: Mapped[str | None] = mapped_column(String(30))
    address_street: Mapped[str | None] = mapped_column(String(255))
    address_number: Mapped[str | None] = mapped_column(String(20))
    address_complement: Mapped[str | None] = mapped_column(String(120))
    address_neighborhood: Mapped[str | None] = mapped_column(String(120))
    address_city: Mapped[str | None] = mapped_column(String(120))
    address_state: Mapped[str | None] = mapped_column(String(2))
    address_zip: Mapped[str | None] = mapped_column(String(10))
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    notes: Mapped[str | None] = mapped_column(Text)
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime)


class Quote(Base, TenantMixin, TimestampMixin):
    """Orçamento. `subtotal`/`total` são recalculados a partir dos `QuoteItem`
    toda vez que a lista de itens muda (ver commercial/service.py::_recalculate_quote)
    — denormalizado pra listar/filtrar sem agregação a cada request, igual
    `Contract.total_value`."""

    __tablename__ = "quotes"
    __table_args__ = (
        Index("ix_quotes_company_status", "company_id", "status"),
        Index("ix_quotes_company_customer", "company_id", "customer_id"),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    number: Mapped[str | None] = mapped_column(String(80))
    customer_id: Mapped[int] = mapped_column(ForeignKey("customers.id", ondelete="RESTRICT"))
    title: Mapped[str] = mapped_column(String(255))
    status: Mapped[str] = mapped_column(String(20), default="rascunho", index=True)
    responsible_user_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL")
    )
    created_by_user_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL")
    )
    description: Mapped[str | None] = mapped_column(Text)
    conditions: Mapped[str | None] = mapped_column(Text)  # condições de pagamento/prazo/garantia
    notes: Mapped[str | None] = mapped_column(Text)
    issued_at: Mapped[date | None] = mapped_column(Date)
    valid_until: Mapped[date | None] = mapped_column(Date)
    discount_amount: Mapped[Decimal] = mapped_column(Numeric(14, 2), default=0)
    subtotal: Mapped[Decimal] = mapped_column(Numeric(14, 2), default=0)
    total: Mapped[Decimal] = mapped_column(Numeric(14, 2), default=0)
    decided_at: Mapped[datetime | None] = mapped_column(DateTime)
    decision_note: Mapped[str | None] = mapped_column(Text)
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime)


class QuoteItem(Base, TenantMixin, TimestampMixin):
    __tablename__ = "quote_items"
    __table_args__ = (Index("ix_quote_items_quote", "quote_id"),)

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    quote_id: Mapped[int] = mapped_column(ForeignKey("quotes.id", ondelete="CASCADE"))
    item_type: Mapped[str] = mapped_column(String(20), default="produto")  # produto|servico
    stock_item_id: Mapped[int | None] = mapped_column(
        ForeignKey("stock_items.id", ondelete="SET NULL")
    )
    description: Mapped[str] = mapped_column(String(255))
    unit: Mapped[str] = mapped_column(String(20), default="un")
    quantity: Mapped[Decimal] = mapped_column(Numeric(12, 3), default=1)
    unit_price: Mapped[Decimal] = mapped_column(Numeric(14, 2), default=0)
    discount_percent: Mapped[Decimal | None] = mapped_column(Numeric(5, 2))
    line_total: Mapped[Decimal] = mapped_column(Numeric(14, 2), default=0)
    sort_order: Mapped[int] = mapped_column(Integer, default=0)


class Sale(Base, TenantMixin, TimestampMixin):
    """Venda — criada automaticamente quando o cliente aceita o orçamento (ver
    commercial/service.py::decide_quote). `installation_*` cobre a instalação no
    cliente como um estágio da venda, não como domínio próprio: escopo suficiente
    pra rastrear status/data sem duplicar o que `work_orders` já resolve pra
    trabalho interno."""

    __tablename__ = "sales"
    __table_args__ = (Index("ix_sales_company_status", "company_id", "status"),)

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    number: Mapped[str | None] = mapped_column(String(80))
    quote_id: Mapped[int] = mapped_column(ForeignKey("quotes.id", ondelete="RESTRICT"), unique=True)
    customer_id: Mapped[int] = mapped_column(ForeignKey("customers.id", ondelete="RESTRICT"))
    status: Mapped[str] = mapped_column(String(20), default="confirmada", index=True)
    total_value: Mapped[Decimal] = mapped_column(Numeric(14, 2), default=0)
    responsible_user_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL")
    )
    created_by_user_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL")
    )
    delivered_at: Mapped[date | None] = mapped_column(Date)
    installation_status: Mapped[str] = mapped_column(String(20), default="pendente")
    installation_scheduled_at: Mapped[date | None] = mapped_column(Date)
    installation_completed_at: Mapped[date | None] = mapped_column(Date)
    installation_notes: Mapped[str | None] = mapped_column(Text)
    notes: Mapped[str | None] = mapped_column(Text)
    # Campo de preparação pro push futuro pro erpsolid (ver
    # app/domain/integrations_erpsolid/) — não lido/escrito por nada ainda.
    erpsolid_external_id: Mapped[str | None] = mapped_column(String(60))
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime)


class SalesInvoice(Base, TenantMixin, TimestampMixin):
    """Fatura da venda pro cliente (faturamento). Uma venda pode ter mais de uma
    (ex.: entrada + saldo) — por isso `sale_id` não é único."""

    __tablename__ = "sales_invoices"
    __table_args__ = (Index("ix_sales_invoices_company_status", "company_id", "status"),)

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    sale_id: Mapped[int] = mapped_column(ForeignKey("sales.id", ondelete="CASCADE"))
    number: Mapped[str | None] = mapped_column(String(80))
    nf_number: Mapped[str | None] = mapped_column(String(40))
    status: Mapped[str] = mapped_column(String(20), default="pendente", index=True)
    amount: Mapped[Decimal] = mapped_column(Numeric(14, 2), default=0)
    issued_at: Mapped[date | None] = mapped_column(Date)
    due_date: Mapped[date | None] = mapped_column(Date)
    notes: Mapped[str | None] = mapped_column(Text)
    erpsolid_external_id: Mapped[str | None] = mapped_column(String(60))
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime)


class SalesPayment(Base, TenantMixin, TimestampMixin):
    """Recebimento (cobrança) contra uma fatura — parcial ou total; `SalesInvoice.status`
    vira "paga" quando a soma dos pagamentos atinge `amount` (ver
    commercial/service.py::register_payment)."""

    __tablename__ = "sales_payments"
    __table_args__ = (Index("ix_sales_payments_invoice", "invoice_id"),)

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    invoice_id: Mapped[int] = mapped_column(ForeignKey("sales_invoices.id", ondelete="CASCADE"))
    amount: Mapped[Decimal] = mapped_column(Numeric(14, 2))
    method: Mapped[str | None] = mapped_column(String(20))  # pix|boleto|cartao|transferencia|...
    paid_at: Mapped[date] = mapped_column(Date)
    reference: Mapped[str | None] = mapped_column(String(120))
    notes: Mapped[str | None] = mapped_column(Text)
    created_by_user_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL")
    )
    erpsolid_external_id: Mapped[str | None] = mapped_column(String(60))
