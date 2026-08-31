"""Pipeline comercial: Cliente -> Orçamento -> Aceite -> Venda -> Instalação ->
Faturamento -> Cobrança. Ver app/models/commercial.py para o desenho das tabelas.
"""

from datetime import date, datetime
from decimal import Decimal
from typing import Any, NamedTuple

from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.audit import compute_diff, record_event
from app.models import (
    Company,
    Customer,
    Quote,
    QuoteItem,
    Sale,
    SalesInvoice,
    SalesPayment,
    User,
)


class InvalidStateError(Exception):
    """Levantada quando a operação não é permitida no status atual da entidade
    (ex.: editar um orçamento já enviado). O router traduz pra HTTP 422 —
    ver app/domain/commercial/router.py."""

    def __init__(self, message: str):
        super().__init__(message)
        self.message = message


# ---------------------------------------------------------------------------
# Customers
# ---------------------------------------------------------------------------


class CustomerRow(NamedTuple):
    customer: Customer
    quote_count: int


async def list_customers(
    session: AsyncSession,
    company_id: int,
    page: int,
    page_size: int,
    search: str | None = None,
    active_only: bool = False,
) -> tuple[list[CustomerRow], int]:
    q = select(Customer).where(
        Customer.company_id == company_id,
        Customer.deleted_at.is_(None),
    )
    if search:
        term = f"%{search}%"
        q = q.where(or_(Customer.name.ilike(term), Customer.document.ilike(term)))
    if active_only:
        q = q.where(Customer.active.is_(True))

    total = await session.scalar(select(func.count()).select_from(q.subquery()))
    customers = (
        (
            await session.execute(
                q.order_by(Customer.name.asc()).offset((page - 1) * page_size).limit(page_size)
            )
        )
        .scalars()
        .all()
    )
    if not customers:
        return [], total or 0

    customer_ids = [c.id for c in customers]
    count_rows = (
        await session.execute(
            select(Quote.customer_id, func.count().label("cnt"))
            .where(Quote.customer_id.in_(customer_ids), Quote.deleted_at.is_(None))
            .group_by(Quote.customer_id)
        )
    ).all()
    counts = {r.customer_id: r.cnt for r in count_rows}

    return [CustomerRow(c, counts.get(c.id, 0)) for c in customers], total or 0


async def get_customer(session: AsyncSession, company_id: int, customer_id: int) -> Customer | None:
    return await session.scalar(  # type: ignore[no-any-return]
        select(Customer).where(
            Customer.id == customer_id,
            Customer.company_id == company_id,
            Customer.deleted_at.is_(None),
        )
    )


async def create_customer(
    session: AsyncSession, company_id: int, user_id: int, data: dict[str, Any]
) -> Customer:
    customer = Customer(company_id=company_id, **data)
    session.add(customer)
    await session.flush()
    await record_event(
        session,
        company_id=company_id,
        user_id=user_id,
        entity_type="customer",
        entity_id=customer.id,
        event_type="created",
    )
    await session.commit()
    await session.refresh(customer)
    return customer


async def update_customer(
    session: AsyncSession, company_id: int, user_id: int, customer_id: int, data: dict[str, Any]
) -> Customer | None:
    customer = await get_customer(session, company_id, customer_id)
    if not customer:
        return None
    old = {k: getattr(customer, k) for k in data}
    for k, v in data.items():
        setattr(customer, k, v)
    diff = compute_diff(old, data)
    if diff:
        await record_event(
            session,
            company_id=company_id,
            user_id=user_id,
            entity_type="customer",
            entity_id=customer.id,
            event_type="updated",
            diff=diff,
        )
    await session.commit()
    await session.refresh(customer)
    return customer


async def delete_customer(
    session: AsyncSession, company_id: int, user_id: int, customer_id: int
) -> bool:
    customer = await get_customer(session, company_id, customer_id)
    if not customer:
        return False
    customer.deleted_at = datetime.now()
    await record_event(
        session,
        company_id=company_id,
        user_id=user_id,
        entity_type="customer",
        entity_id=customer.id,
        event_type="deleted",
    )
    await session.commit()
    return True


async def list_customer_options(session: AsyncSession, company_id: int) -> list[Customer]:
    return list(
        (
            await session.execute(
                select(Customer)
                .where(
                    Customer.company_id == company_id,
                    Customer.active.is_(True),
                    Customer.deleted_at.is_(None),
                )
                .order_by(Customer.name.asc())
                .limit(200)
            )
        )
        .scalars()
        .all()
    )


# ---------------------------------------------------------------------------
# Quotes
# ---------------------------------------------------------------------------


async def _generate_number(
    session: AsyncSession,
    model: type[Quote] | type[Sale] | type[SalesInvoice],
    company_id: int,
    prefix: str,
) -> str:
    year = date.today().year
    full_prefix = f"{prefix}-{year}-"
    count = (
        await session.scalar(
            select(func.count()).where(
                model.company_id == company_id,
                model.number.like(f"{full_prefix}%"),
            )
        )
        or 0
    )
    return f"{full_prefix}{count + 1:04d}"


def _line_total(
    quantity: Decimal, unit_price: Decimal, discount_percent: Decimal | None
) -> Decimal:
    gross = quantity * unit_price
    if discount_percent:
        gross -= gross * (discount_percent / Decimal(100))
    return gross.quantize(Decimal("0.01"))


def _apply_totals(quote: Quote, items: list[QuoteItem]) -> None:
    subtotal = sum((i.line_total for i in items), Decimal("0.00"))
    total = subtotal - (quote.discount_amount or Decimal("0.00"))
    quote.subtotal = subtotal
    quote.total = total if total > 0 else Decimal("0.00")


def _build_items(company_id: int, quote_id: int, items: list[dict[str, Any]]) -> list[QuoteItem]:
    built = []
    for i, raw in enumerate(items):
        line_total = _line_total(raw["quantity"], raw["unit_price"], raw.get("discount_percent"))
        built.append(
            QuoteItem(
                company_id=company_id,
                quote_id=quote_id,
                sort_order=i,
                line_total=line_total,
                **raw,
            )
        )
    return built


class QuoteRow(NamedTuple):
    quote: Quote
    customer_name: str | None


async def list_quotes(
    session: AsyncSession,
    company_id: int,
    page: int,
    page_size: int,
    search: str | None = None,
    status: str | None = None,
    customer_id: int | None = None,
) -> tuple[list[QuoteRow], int]:
    q = select(Quote).where(Quote.company_id == company_id, Quote.deleted_at.is_(None))
    if search:
        term = f"%{search}%"
        q = q.where(or_(Quote.title.ilike(term), Quote.number.ilike(term)))
    if status:
        q = q.where(Quote.status == status)
    if customer_id:
        q = q.where(Quote.customer_id == customer_id)

    total = await session.scalar(select(func.count()).select_from(q.subquery()))
    quotes = (
        (
            await session.execute(
                q.order_by(Quote.updated_at.desc()).offset((page - 1) * page_size).limit(page_size)
            )
        )
        .scalars()
        .all()
    )
    if not quotes:
        return [], total or 0

    customer_ids = [q_.customer_id for q_ in quotes]
    rows = (
        await session.execute(
            select(Customer.id, Customer.name).where(Customer.id.in_(customer_ids))
        )
    ).all()
    names = {r.id: r.name for r in rows}

    return [QuoteRow(q_, names.get(q_.customer_id)) for q_ in quotes], total or 0


class QuoteDetail(NamedTuple):
    quote: Quote
    customer_name: str | None
    responsible_name: str | None
    items: list[QuoteItem]


async def _get_quote(session: AsyncSession, company_id: int, quote_id: int) -> Quote | None:
    return await session.scalar(  # type: ignore[no-any-return]
        select(Quote).where(
            Quote.id == quote_id,
            Quote.company_id == company_id,
            Quote.deleted_at.is_(None),
        )
    )


async def _quote_items(session: AsyncSession, quote_id: int) -> list[QuoteItem]:
    return list(
        (
            await session.execute(
                select(QuoteItem)
                .where(QuoteItem.quote_id == quote_id)
                .order_by(QuoteItem.sort_order)
            )
        )
        .scalars()
        .all()
    )


async def get_quote(session: AsyncSession, company_id: int, quote_id: int) -> QuoteDetail | None:
    quote = await _get_quote(session, company_id, quote_id)
    if not quote:
        return None
    customer_name = await session.scalar(
        select(Customer.name).where(Customer.id == quote.customer_id)
    )
    responsible_name = (
        await session.scalar(select(User.name).where(User.id == quote.responsible_user_id))
        if quote.responsible_user_id
        else None
    )
    items = await _quote_items(session, quote_id)
    return QuoteDetail(quote, customer_name, responsible_name, items)


async def create_quote(
    session: AsyncSession,
    company_id: int,
    user_id: int,
    data: dict[str, Any],
    items: list[dict[str, Any]],
) -> Quote:
    if not data.get("number"):
        data["number"] = await _generate_number(session, Quote, company_id, "ORC")
    quote = Quote(
        company_id=company_id,
        created_by_user_id=user_id,
        status="rascunho",
        discount_amount=data.pop("discount_amount", Decimal("0.00")) or Decimal("0.00"),
        **data,
    )
    session.add(quote)
    await session.flush()

    quote_items = _build_items(company_id, quote.id, items)
    for qi in quote_items:
        session.add(qi)
    _apply_totals(quote, quote_items)

    await record_event(
        session,
        company_id=company_id,
        user_id=user_id,
        entity_type="quote",
        entity_id=quote.id,
        event_type="created",
    )
    await session.commit()
    await session.refresh(quote)
    return quote


async def update_quote(
    session: AsyncSession,
    company_id: int,
    user_id: int,
    quote_id: int,
    data: dict[str, Any],
    items: list[dict[str, Any]] | None,
) -> Quote | None:
    quote = await _get_quote(session, company_id, quote_id)
    if not quote:
        return None
    if quote.status != "rascunho":
        raise InvalidStateError(
            "Orçamento só pode ser editado enquanto rascunho — envie um novo se precisar mudar."
        )

    old = {k: getattr(quote, k) for k in data}
    for k, v in data.items():
        setattr(quote, k, v)
    diff = compute_diff(old, data)
    if diff:
        await record_event(
            session,
            company_id=company_id,
            user_id=user_id,
            entity_type="quote",
            entity_id=quote.id,
            event_type="updated",
            diff=diff,
        )

    if items is not None:
        existing = await _quote_items(session, quote_id)
        for qi in existing:
            await session.delete(qi)
        await session.flush()
        new_items = _build_items(company_id, quote_id, items)
        for qi in new_items:
            session.add(qi)
        _apply_totals(quote, new_items)
    else:
        _apply_totals(quote, await _quote_items(session, quote_id))

    await session.commit()
    await session.refresh(quote)
    return quote


async def delete_quote(session: AsyncSession, company_id: int, user_id: int, quote_id: int) -> bool:
    quote = await _get_quote(session, company_id, quote_id)
    if not quote:
        return False
    if quote.status == "aceito":
        raise InvalidStateError("Orçamento aceito já virou venda — cancele a venda em vez disso.")
    quote.deleted_at = datetime.now()
    await record_event(
        session,
        company_id=company_id,
        user_id=user_id,
        entity_type="quote",
        entity_id=quote.id,
        event_type="deleted",
    )
    await session.commit()
    return True


async def send_quote(
    session: AsyncSession, company_id: int, user_id: int, quote_id: int
) -> Quote | None:
    quote = await _get_quote(session, company_id, quote_id)
    if not quote:
        return None
    if quote.status != "rascunho":
        raise InvalidStateError("Só é possível enviar um orçamento em rascunho.")
    items = await _quote_items(session, quote_id)
    if not items:
        raise InvalidStateError("Adicione ao menos um item antes de enviar o orçamento.")

    quote.status = "enviado"
    quote.issued_at = date.today()
    await record_event(
        session,
        company_id=company_id,
        user_id=user_id,
        entity_type="quote",
        entity_id=quote.id,
        event_type="sent",
    )
    await session.commit()
    await session.refresh(quote)
    return quote


async def cancel_quote(
    session: AsyncSession, company_id: int, user_id: int, quote_id: int
) -> Quote | None:
    quote = await _get_quote(session, company_id, quote_id)
    if not quote:
        return None
    if quote.status not in ("rascunho", "enviado"):
        raise InvalidStateError("Orçamento não pode mais ser cancelado nesse status.")
    quote.status = "cancelado"
    await record_event(
        session,
        company_id=company_id,
        user_id=user_id,
        entity_type="quote",
        entity_id=quote.id,
        event_type="cancelled",
    )
    await session.commit()
    await session.refresh(quote)
    return quote


# ---------------------------------------------------------------------------
# Aceite público (sem login) + criação automática da venda
# ---------------------------------------------------------------------------


class PublicQuoteDetail(NamedTuple):
    quote: Quote
    customer_name: str
    company_name: str
    items: list[QuoteItem]
    expired: bool


async def get_quote_for_public(
    session: AsyncSession, company_id: int, quote_id: int
) -> PublicQuoteDetail | None:
    quote = await _get_quote(session, company_id, quote_id)
    if not quote:
        return None
    customer_name = await session.scalar(
        select(Customer.name).where(Customer.id == quote.customer_id)
    )
    company_name = await session.scalar(select(Company.name).where(Company.id == company_id))
    items = await _quote_items(session, quote_id)
    expired = bool(
        quote.status == "enviado" and quote.valid_until and quote.valid_until < date.today()
    )
    return PublicQuoteDetail(quote, customer_name or "", company_name or "", items, expired)


async def _generate_sale_number(session: AsyncSession, company_id: int) -> str:
    return await _generate_number(session, Sale, company_id, "VDA")


async def decide_quote(
    session: AsyncSession,
    company_id: int,
    quote_id: int,
    approved: bool,
    decision_note: str | None,
) -> Quote | None:
    """Aceite/recusa do cliente pelo link público. Cria a `Sale` automaticamente
    ao aprovar — nesse pipeline "aprovado" e "virou venda" são o mesmo evento."""
    quote = await _get_quote(session, company_id, quote_id)
    if not quote:
        return None
    if quote.status != "enviado":
        raise InvalidStateError("Este orçamento não está mais aguardando decisão.")
    if quote.valid_until and quote.valid_until < date.today():
        quote.status = "expirado"
        await session.commit()
        raise InvalidStateError("Este orçamento expirou.")

    quote.status = "aceito" if approved else "recusado"
    quote.decided_at = datetime.now()
    quote.decision_note = decision_note
    await record_event(
        session,
        company_id=company_id,
        user_id=None,
        actor_name="Cliente (link público)",
        entity_type="quote",
        entity_id=quote.id,
        event_type="accepted" if approved else "rejected",
        diff={"decision_note": decision_note} if decision_note else None,
    )

    if approved:
        sale = Sale(
            company_id=company_id,
            number=await _generate_sale_number(session, company_id),
            quote_id=quote.id,
            customer_id=quote.customer_id,
            status="confirmada",
            total_value=quote.total,
            responsible_user_id=quote.responsible_user_id,
            created_by_user_id=quote.created_by_user_id,
        )
        session.add(sale)
        await session.flush()
        await record_event(
            session,
            company_id=company_id,
            user_id=quote.created_by_user_id,
            actor_name="Cliente (link público)" if not quote.created_by_user_id else None,
            entity_type="sale",
            entity_id=sale.id,
            event_type="created",
            diff={"quote_id": quote.id},
        )

    await session.commit()
    await session.refresh(quote)
    return quote


# ---------------------------------------------------------------------------
# Sales
# ---------------------------------------------------------------------------


async def _invoice_totals(session: AsyncSession, sale_id: int) -> tuple[Decimal, Decimal]:
    """(faturado, recebido) de uma venda — soma faturas não canceladas e os
    pagamentos registrados contra elas."""
    invoiced = await session.scalar(
        select(func.coalesce(func.sum(SalesInvoice.amount), 0)).where(
            SalesInvoice.sale_id == sale_id,
            SalesInvoice.deleted_at.is_(None),
            SalesInvoice.status != "cancelada",
        )
    )
    received = await session.scalar(
        select(func.coalesce(func.sum(SalesPayment.amount), 0))
        .select_from(SalesPayment)
        .join(SalesInvoice, SalesInvoice.id == SalesPayment.invoice_id)
        .where(SalesInvoice.sale_id == sale_id, SalesInvoice.deleted_at.is_(None))
    )
    return Decimal(invoiced or 0), Decimal(received or 0)


class SaleRow(NamedTuple):
    sale: Sale
    customer_name: str | None
    invoiced_total: Decimal
    received_total: Decimal


async def list_sales(
    session: AsyncSession,
    company_id: int,
    page: int,
    page_size: int,
    search: str | None = None,
    status: str | None = None,
    installation_status: str | None = None,
) -> tuple[list[SaleRow], int]:
    q = select(Sale).where(Sale.company_id == company_id, Sale.deleted_at.is_(None))
    if search:
        q = q.where(Sale.number.ilike(f"%{search}%"))
    if status:
        q = q.where(Sale.status == status)
    if installation_status:
        q = q.where(Sale.installation_status == installation_status)

    total = await session.scalar(select(func.count()).select_from(q.subquery()))
    sales = (
        (
            await session.execute(
                q.order_by(Sale.updated_at.desc()).offset((page - 1) * page_size).limit(page_size)
            )
        )
        .scalars()
        .all()
    )
    if not sales:
        return [], total or 0

    customer_ids = [s.customer_id for s in sales]
    rows = (
        await session.execute(
            select(Customer.id, Customer.name).where(Customer.id.in_(customer_ids))
        )
    ).all()
    names = {r.id: r.name for r in rows}

    result = []
    for s in sales:
        invoiced, received = await _invoice_totals(session, s.id)
        result.append(SaleRow(s, names.get(s.customer_id), invoiced, received))
    return result, total or 0


class SaleDetail(NamedTuple):
    sale: Sale
    customer_name: str | None
    responsible_name: str | None
    invoices: list[tuple[SalesInvoice, Decimal]]  # (fatura, total pago)


async def _get_sale(session: AsyncSession, company_id: int, sale_id: int) -> Sale | None:
    return await session.scalar(  # type: ignore[no-any-return]
        select(Sale).where(
            Sale.id == sale_id,
            Sale.company_id == company_id,
            Sale.deleted_at.is_(None),
        )
    )


async def get_sale(session: AsyncSession, company_id: int, sale_id: int) -> SaleDetail | None:
    sale = await _get_sale(session, company_id, sale_id)
    if not sale:
        return None
    customer_name = await session.scalar(
        select(Customer.name).where(Customer.id == sale.customer_id)
    )
    responsible_name = (
        await session.scalar(select(User.name).where(User.id == sale.responsible_user_id))
        if sale.responsible_user_id
        else None
    )
    invoices = list(
        (
            await session.execute(
                select(SalesInvoice)
                .where(SalesInvoice.sale_id == sale_id, SalesInvoice.deleted_at.is_(None))
                .order_by(SalesInvoice.created_at.desc())
            )
        )
        .scalars()
        .all()
    )
    invoice_rows = []
    for inv in invoices:
        paid = await session.scalar(
            select(func.coalesce(func.sum(SalesPayment.amount), 0)).where(
                SalesPayment.invoice_id == inv.id
            )
        )
        invoice_rows.append((inv, Decimal(paid or 0)))
    return SaleDetail(sale, customer_name, responsible_name, invoice_rows)


async def update_sale(
    session: AsyncSession, company_id: int, user_id: int, sale_id: int, data: dict[str, Any]
) -> Sale | None:
    sale = await _get_sale(session, company_id, sale_id)
    if not sale:
        return None
    old = {k: getattr(sale, k) for k in data}
    for k, v in data.items():
        setattr(sale, k, v)
    diff = compute_diff(old, data)
    if diff:
        await record_event(
            session,
            company_id=company_id,
            user_id=user_id,
            entity_type="sale",
            entity_id=sale.id,
            event_type="updated",
            diff=diff,
        )
    await session.commit()
    await session.refresh(sale)
    return sale


# ---------------------------------------------------------------------------
# Sales Invoices (Faturamento)
# ---------------------------------------------------------------------------


async def create_invoice(
    session: AsyncSession, company_id: int, user_id: int, sale_id: int, data: dict[str, Any]
) -> SalesInvoice | None:
    sale = await _get_sale(session, company_id, sale_id)
    if not sale:
        return None
    if sale.status == "cancelada":
        raise InvalidStateError("Venda cancelada não pode receber novas faturas.")
    invoice = SalesInvoice(
        company_id=company_id,
        sale_id=sale_id,
        number=await _generate_number(session, SalesInvoice, company_id, "FAT"),
        status="faturada",
        **data,
    )
    session.add(invoice)
    await session.flush()
    await record_event(
        session,
        company_id=company_id,
        user_id=user_id,
        entity_type="sales_invoice",
        entity_id=invoice.id,
        event_type="created",
        diff={"sale_id": sale_id, "amount": str(invoice.amount)},
    )
    await session.commit()
    await session.refresh(invoice)
    return invoice


async def _get_invoice(
    session: AsyncSession, company_id: int, invoice_id: int
) -> SalesInvoice | None:
    return await session.scalar(  # type: ignore[no-any-return]
        select(SalesInvoice).where(
            SalesInvoice.id == invoice_id,
            SalesInvoice.company_id == company_id,
            SalesInvoice.deleted_at.is_(None),
        )
    )


async def update_invoice(
    session: AsyncSession, company_id: int, user_id: int, invoice_id: int, data: dict[str, Any]
) -> SalesInvoice | None:
    invoice = await _get_invoice(session, company_id, invoice_id)
    if not invoice:
        return None
    old = {k: getattr(invoice, k) for k in data}
    for k, v in data.items():
        setattr(invoice, k, v)
    diff = compute_diff(old, data)
    if diff:
        await record_event(
            session,
            company_id=company_id,
            user_id=user_id,
            entity_type="sales_invoice",
            entity_id=invoice.id,
            event_type="updated",
            diff=diff,
        )
    await session.commit()
    await session.refresh(invoice)
    return invoice


# ---------------------------------------------------------------------------
# Sales Payments (Cobrança / Recebimento)
# ---------------------------------------------------------------------------


async def register_payment(
    session: AsyncSession, company_id: int, user_id: int, invoice_id: int, data: dict[str, Any]
) -> SalesPayment | None:
    invoice = await _get_invoice(session, company_id, invoice_id)
    if not invoice:
        return None
    if invoice.status == "cancelada":
        raise InvalidStateError("Fatura cancelada não pode receber pagamentos.")

    payment = SalesPayment(
        company_id=company_id, invoice_id=invoice_id, created_by_user_id=user_id, **data
    )
    session.add(payment)
    await session.flush()

    paid_total = await session.scalar(
        select(func.coalesce(func.sum(SalesPayment.amount), 0)).where(
            SalesPayment.invoice_id == invoice_id
        )
    )
    if Decimal(paid_total or 0) >= invoice.amount:
        invoice.status = "paga"

    await record_event(
        session,
        company_id=company_id,
        user_id=user_id,
        entity_type="sales_invoice",
        entity_id=invoice.id,
        event_type="payment_registered",
        diff={"amount": str(payment.amount), "method": payment.method},
    )
    await session.commit()
    await session.refresh(payment)
    return payment


# ---------------------------------------------------------------------------
# Funil comercial (dashboard)
# ---------------------------------------------------------------------------


class FunnelData(NamedTuple):
    quoted_count: int
    quoted_total: Decimal
    approved_count: int
    approved_total: Decimal
    delivered_count: int
    invoiced_total: Decimal
    received_total: Decimal


async def get_funnel(session: AsyncSession, company_id: int) -> FunnelData:
    quoted = (
        await session.execute(
            select(func.count(), func.coalesce(func.sum(Quote.total), 0)).where(
                Quote.company_id == company_id,
                Quote.deleted_at.is_(None),
                Quote.status.in_(("enviado", "aceito", "recusado", "expirado")),
            )
        )
    ).one()

    approved = (
        await session.execute(
            select(func.count(), func.coalesce(func.sum(Quote.total), 0)).where(
                Quote.company_id == company_id,
                Quote.deleted_at.is_(None),
                Quote.status == "aceito",
            )
        )
    ).one()

    delivered_count = (
        await session.scalar(
            select(func.count()).where(
                Sale.company_id == company_id,
                Sale.deleted_at.is_(None),
                Sale.delivered_at.isnot(None),
            )
        )
        or 0
    )

    invoiced_total = (
        await session.scalar(
            select(func.coalesce(func.sum(SalesInvoice.amount), 0)).where(
                SalesInvoice.company_id == company_id,
                SalesInvoice.deleted_at.is_(None),
                SalesInvoice.status != "cancelada",
            )
        )
        or 0
    )

    received_total = (
        await session.scalar(
            select(func.coalesce(func.sum(SalesPayment.amount), 0)).where(
                SalesPayment.company_id == company_id
            )
        )
        or 0
    )

    return FunnelData(
        quoted_count=quoted[0] or 0,
        quoted_total=Decimal(quoted[1] or 0),
        approved_count=approved[0] or 0,
        approved_total=Decimal(approved[1] or 0),
        delivered_count=delivered_count,
        invoiced_total=Decimal(invoiced_total),
        received_total=Decimal(received_total),
    )
