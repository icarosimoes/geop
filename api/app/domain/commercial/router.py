from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings, get_settings
from app.core.dependencies import require_session
from app.core.permissions import require_permission
from app.core.security import create_quote_acceptance_token
from app.domain.auth.repository import AuthenticatedUser
from app.domain.commercial.schemas import (
    CommercialFunnel,
    CustomerCreate,
    CustomerListResponse,
    CustomerOption,
    CustomerOut,
    CustomerSummary,
    CustomerUpdate,
    QuoteCreate,
    QuoteItemOut,
    QuoteListResponse,
    QuoteOut,
    QuoteSendResponse,
    QuoteSummary,
    QuoteUpdate,
    SaleListResponse,
    SaleOut,
    SalesInvoiceCreate,
    SalesInvoiceOut,
    SalesInvoiceUpdate,
    SalesPaymentCreate,
    SalesPaymentOut,
    SaleSummary,
    SaleUpdate,
)
from app.domain.commercial.service import (
    InvalidStateError,
    QuoteDetail,
    SaleDetail,
    _invoice_totals,
    cancel_quote,
    create_customer,
    create_invoice,
    create_quote,
    delete_customer,
    delete_quote,
    get_customer,
    get_funnel,
    get_quote,
    get_sale,
    list_customer_options,
    list_customers,
    list_quotes,
    list_sales,
    register_payment,
    send_quote,
    update_customer,
    update_invoice,
    update_quote,
    update_sale,
)
from app.models import SalesPayment

router = APIRouter(prefix="/commercial", tags=["commercial"])


def _acceptance_url(settings: Settings, company_id: int, quote_id: int) -> str:
    token = create_quote_acceptance_token(
        quote_id=quote_id, company_id=company_id, secret=settings.jwt_secret
    )
    return f"{settings.registro_web_url}/orcamento/{token}"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _to_quote_out(detail: QuoteDetail, settings: Settings, company_id: int) -> QuoteOut:
    quote = detail.quote
    return QuoteOut(
        id=quote.id,
        number=quote.number,
        customer_id=quote.customer_id,
        customer_name=detail.customer_name,
        title=quote.title,
        status=quote.status,
        responsible_user_id=quote.responsible_user_id,
        responsible_name=detail.responsible_name,
        created_by_user_id=quote.created_by_user_id,
        description=quote.description,
        conditions=quote.conditions,
        notes=quote.notes,
        issued_at=quote.issued_at,
        valid_until=quote.valid_until,
        discount_amount=quote.discount_amount,
        subtotal=quote.subtotal,
        total=quote.total,
        decided_at=quote.decided_at,
        decision_note=quote.decision_note,
        items=[
            QuoteItemOut(
                id=i.id,
                item_type=i.item_type,
                stock_item_id=i.stock_item_id,
                description=i.description,
                unit=i.unit,
                quantity=i.quantity,
                unit_price=i.unit_price,
                discount_percent=i.discount_percent,
                line_total=i.line_total,
                sort_order=i.sort_order,
            )
            for i in detail.items
        ],
        acceptance_url=(
            _acceptance_url(settings, company_id, quote.id) if quote.status == "enviado" else None
        ),
        created_at=quote.created_at,
        updated_at=quote.updated_at,
    )


def _to_sale_out(detail: SaleDetail, invoiced_total, received_total) -> SaleOut:
    sale = detail.sale
    return SaleOut(
        id=sale.id,
        number=sale.number,
        quote_id=sale.quote_id,
        customer_id=sale.customer_id,
        customer_name=detail.customer_name,
        status=sale.status,
        total_value=sale.total_value,
        responsible_user_id=sale.responsible_user_id,
        responsible_name=detail.responsible_name,
        delivered_at=sale.delivered_at,
        installation_status=sale.installation_status,
        installation_scheduled_at=sale.installation_scheduled_at,
        installation_completed_at=sale.installation_completed_at,
        installation_notes=sale.installation_notes,
        notes=sale.notes,
        invoiced_total=invoiced_total,
        received_total=received_total,
        invoices=[_to_invoice_out(inv, paid) for inv, paid in detail.invoices],
        created_at=sale.created_at,
        updated_at=sale.updated_at,
    )


def _to_invoice_out(invoice, paid_total, payments=()) -> SalesInvoiceOut:
    return SalesInvoiceOut(
        id=invoice.id,
        sale_id=invoice.sale_id,
        number=invoice.number,
        nf_number=invoice.nf_number,
        status=invoice.status,
        amount=invoice.amount,
        issued_at=invoice.issued_at,
        due_date=invoice.due_date,
        notes=invoice.notes,
        paid_total=paid_total,
        payments=[
            SalesPaymentOut(
                id=p.id,
                invoice_id=p.invoice_id,
                amount=p.amount,
                method=p.method,
                paid_at=p.paid_at,
                reference=p.reference,
                notes=p.notes,
                created_at=p.created_at,
            )
            for p in payments
        ],
        created_at=invoice.created_at,
        updated_at=invoice.updated_at,
    )


async def _get_quote_detail_or_404(
    session: AsyncSession, company_id: int, quote_id: int
) -> QuoteDetail:
    detail = await get_quote(session, company_id, quote_id)
    if not detail:
        raise HTTPException(status_code=404, detail={"code": "not_found"})
    return detail


async def _get_sale_detail_or_404(
    session: AsyncSession, company_id: int, sale_id: int
) -> SaleDetail:
    detail = await get_sale(session, company_id, sale_id)
    if not detail:
        raise HTTPException(status_code=404, detail={"code": "not_found"})
    return detail


# ---------------------------------------------------------------------------
# Customers
# ---------------------------------------------------------------------------


@router.get("/customers", response_model=CustomerListResponse)
async def list_customers_endpoint(
    user: Annotated[AuthenticatedUser, require_permission("commercial.view")],
    session: Annotated[AsyncSession, Depends(require_session)],
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=100)] = 20,
    search: str | None = None,
    active_only: bool = False,
) -> CustomerListResponse:
    rows, total = await list_customers(
        session, user.company_id, page, page_size, search, active_only
    )
    return CustomerListResponse(
        items=[
            CustomerSummary(
                id=c.id,
                name=c.name,
                document=c.document,
                email=c.email,
                phone=c.phone,
                active=c.active,
                quote_count=cnt,
                updated_at=c.updated_at,
            )
            for c, cnt in rows
        ],
        total=total,
        page=page,
        page_size=page_size,
    )


@router.get("/customers/options", response_model=list[CustomerOption])
async def list_customer_options_endpoint(
    user: Annotated[AuthenticatedUser, require_permission("commercial.view")],
    session: Annotated[AsyncSession, Depends(require_session)],
) -> list[CustomerOption]:
    customers = await list_customer_options(session, user.company_id)
    return [CustomerOption(id=c.id, name=c.name, document=c.document) for c in customers]


@router.get("/customers/{customer_id}", response_model=CustomerOut)
async def get_customer_endpoint(
    customer_id: int,
    user: Annotated[AuthenticatedUser, require_permission("commercial.view")],
    session: Annotated[AsyncSession, Depends(require_session)],
) -> CustomerOut:
    customer = await get_customer(session, user.company_id, customer_id)
    if not customer:
        raise HTTPException(status_code=404, detail={"code": "not_found"})
    return CustomerOut.model_validate(customer)


@router.post("/customers", response_model=CustomerOut, status_code=201)
async def create_customer_endpoint(
    body: CustomerCreate,
    user: Annotated[AuthenticatedUser, require_permission("commercial.create")],
    session: Annotated[AsyncSession, Depends(require_session)],
) -> CustomerOut:
    customer = await create_customer(
        session, user.company_id, user.id, body.model_dump(exclude_none=True)
    )
    return CustomerOut.model_validate(customer)


@router.patch("/customers/{customer_id}", response_model=CustomerOut)
async def update_customer_endpoint(
    customer_id: int,
    body: CustomerUpdate,
    user: Annotated[AuthenticatedUser, require_permission("commercial.edit")],
    session: Annotated[AsyncSession, Depends(require_session)],
) -> CustomerOut:
    customer = await update_customer(
        session, user.company_id, user.id, customer_id, body.model_dump(exclude_none=True)
    )
    if not customer:
        raise HTTPException(status_code=404, detail={"code": "not_found"})
    return CustomerOut.model_validate(customer)


@router.delete("/customers/{customer_id}", status_code=204)
async def delete_customer_endpoint(
    customer_id: int,
    user: Annotated[AuthenticatedUser, require_permission("commercial.delete")],
    session: Annotated[AsyncSession, Depends(require_session)],
) -> None:
    deleted = await delete_customer(session, user.company_id, user.id, customer_id)
    if not deleted:
        raise HTTPException(status_code=404, detail={"code": "not_found"})


# ---------------------------------------------------------------------------
# Quotes
# ---------------------------------------------------------------------------


@router.get("/quotes", response_model=QuoteListResponse)
async def list_quotes_endpoint(
    user: Annotated[AuthenticatedUser, require_permission("commercial.view")],
    session: Annotated[AsyncSession, Depends(require_session)],
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=100)] = 20,
    search: str | None = None,
    status: str | None = None,
    customer_id: int | None = None,
) -> QuoteListResponse:
    rows, total = await list_quotes(
        session, user.company_id, page, page_size, search, status, customer_id
    )
    return QuoteListResponse(
        items=[
            QuoteSummary(
                id=q.id,
                number=q.number,
                customer_id=q.customer_id,
                customer_name=name,
                title=q.title,
                status=q.status,
                total=q.total,
                valid_until=q.valid_until,
                updated_at=q.updated_at,
            )
            for q, name in rows
        ],
        total=total,
        page=page,
        page_size=page_size,
    )


@router.get("/quotes/{quote_id}", response_model=QuoteOut)
async def get_quote_endpoint(
    quote_id: int,
    user: Annotated[AuthenticatedUser, require_permission("commercial.view")],
    session: Annotated[AsyncSession, Depends(require_session)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> QuoteOut:
    detail = await _get_quote_detail_or_404(session, user.company_id, quote_id)
    return _to_quote_out(detail, settings, user.company_id)


@router.post("/quotes", response_model=QuoteOut, status_code=201)
async def create_quote_endpoint(
    body: QuoteCreate,
    user: Annotated[AuthenticatedUser, require_permission("commercial.create")],
    session: Annotated[AsyncSession, Depends(require_session)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> QuoteOut:
    data = body.model_dump(exclude={"items"}, exclude_none=True)
    items = [i.model_dump(exclude_none=True) for i in body.items]
    quote = await create_quote(session, user.company_id, user.id, data, items)
    detail = await _get_quote_detail_or_404(session, user.company_id, quote.id)
    return _to_quote_out(detail, settings, user.company_id)


@router.patch("/quotes/{quote_id}", response_model=QuoteOut)
async def update_quote_endpoint(
    quote_id: int,
    body: QuoteUpdate,
    user: Annotated[AuthenticatedUser, require_permission("commercial.edit")],
    session: Annotated[AsyncSession, Depends(require_session)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> QuoteOut:
    data = body.model_dump(exclude={"items"}, exclude_none=True)
    items = (
        [i.model_dump(exclude_none=True) for i in body.items] if body.items is not None else None
    )
    try:
        quote = await update_quote(session, user.company_id, user.id, quote_id, data, items)
    except InvalidStateError as exc:
        raise HTTPException(
            status_code=422, detail={"code": "invalid_state", "message": exc.message}
        ) from exc
    if not quote:
        raise HTTPException(status_code=404, detail={"code": "not_found"})
    detail = await _get_quote_detail_or_404(session, user.company_id, quote_id)
    return _to_quote_out(detail, settings, user.company_id)


@router.delete("/quotes/{quote_id}", status_code=204)
async def delete_quote_endpoint(
    quote_id: int,
    user: Annotated[AuthenticatedUser, require_permission("commercial.delete")],
    session: Annotated[AsyncSession, Depends(require_session)],
) -> None:
    try:
        deleted = await delete_quote(session, user.company_id, user.id, quote_id)
    except InvalidStateError as exc:
        raise HTTPException(
            status_code=422, detail={"code": "invalid_state", "message": exc.message}
        ) from exc
    if not deleted:
        raise HTTPException(status_code=404, detail={"code": "not_found"})


@router.post("/quotes/{quote_id}/send", response_model=QuoteSendResponse)
async def send_quote_endpoint(
    quote_id: int,
    user: Annotated[AuthenticatedUser, require_permission("commercial.edit")],
    session: Annotated[AsyncSession, Depends(require_session)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> QuoteSendResponse:
    try:
        quote = await send_quote(session, user.company_id, user.id, quote_id)
    except InvalidStateError as exc:
        raise HTTPException(
            status_code=422, detail={"code": "invalid_state", "message": exc.message}
        ) from exc
    if not quote:
        raise HTTPException(status_code=404, detail={"code": "not_found"})
    detail = await _get_quote_detail_or_404(session, user.company_id, quote_id)
    return QuoteSendResponse(
        quote=_to_quote_out(detail, settings, user.company_id),
        acceptance_url=_acceptance_url(settings, user.company_id, quote_id),
    )


@router.post("/quotes/{quote_id}/cancel", response_model=QuoteOut)
async def cancel_quote_endpoint(
    quote_id: int,
    user: Annotated[AuthenticatedUser, require_permission("commercial.edit")],
    session: Annotated[AsyncSession, Depends(require_session)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> QuoteOut:
    try:
        quote = await cancel_quote(session, user.company_id, user.id, quote_id)
    except InvalidStateError as exc:
        raise HTTPException(
            status_code=422, detail={"code": "invalid_state", "message": exc.message}
        ) from exc
    if not quote:
        raise HTTPException(status_code=404, detail={"code": "not_found"})
    detail = await _get_quote_detail_or_404(session, user.company_id, quote_id)
    return _to_quote_out(detail, settings, user.company_id)


# ---------------------------------------------------------------------------
# Sales
# ---------------------------------------------------------------------------


@router.get("/sales", response_model=SaleListResponse)
async def list_sales_endpoint(
    user: Annotated[AuthenticatedUser, require_permission("commercial.view")],
    session: Annotated[AsyncSession, Depends(require_session)],
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=100)] = 20,
    search: str | None = None,
    status: str | None = None,
    installation_status: str | None = None,
) -> SaleListResponse:
    rows, total = await list_sales(
        session, user.company_id, page, page_size, search, status, installation_status
    )
    return SaleListResponse(
        items=[
            SaleSummary(
                id=s.id,
                number=s.number,
                customer_id=s.customer_id,
                customer_name=name,
                status=s.status,
                total_value=s.total_value,
                installation_status=s.installation_status,
                delivered_at=s.delivered_at,
                invoiced_total=invoiced,
                received_total=received,
                updated_at=s.updated_at,
            )
            for s, name, invoiced, received in rows
        ],
        total=total,
        page=page,
        page_size=page_size,
    )


@router.get("/sales/{sale_id}", response_model=SaleOut)
async def get_sale_endpoint(
    sale_id: int,
    user: Annotated[AuthenticatedUser, require_permission("commercial.view")],
    session: Annotated[AsyncSession, Depends(require_session)],
) -> SaleOut:
    detail = await _get_sale_detail_or_404(session, user.company_id, sale_id)
    invoiced, received = await _invoice_totals(session, sale_id)
    return _to_sale_out(detail, invoiced, received)


@router.patch("/sales/{sale_id}", response_model=SaleOut)
async def update_sale_endpoint(
    sale_id: int,
    body: SaleUpdate,
    user: Annotated[AuthenticatedUser, require_permission("commercial.edit")],
    session: Annotated[AsyncSession, Depends(require_session)],
) -> SaleOut:
    sale = await update_sale(
        session, user.company_id, user.id, sale_id, body.model_dump(exclude_none=True)
    )
    if not sale:
        raise HTTPException(status_code=404, detail={"code": "not_found"})
    detail = await _get_sale_detail_or_404(session, user.company_id, sale_id)
    invoiced, received = await _invoice_totals(session, sale_id)
    return _to_sale_out(detail, invoiced, received)


# ---------------------------------------------------------------------------
# Sales Invoices (Faturamento) + Payments (Cobrança)
# ---------------------------------------------------------------------------


@router.post("/sales/{sale_id}/invoices", response_model=SalesInvoiceOut, status_code=201)
async def create_invoice_endpoint(
    sale_id: int,
    body: SalesInvoiceCreate,
    user: Annotated[AuthenticatedUser, require_permission("commercial.edit")],
    session: Annotated[AsyncSession, Depends(require_session)],
) -> SalesInvoiceOut:
    try:
        invoice = await create_invoice(
            session, user.company_id, user.id, sale_id, body.model_dump(exclude_none=True)
        )
    except InvalidStateError as exc:
        raise HTTPException(
            status_code=422, detail={"code": "invalid_state", "message": exc.message}
        ) from exc
    if not invoice:
        raise HTTPException(status_code=404, detail={"code": "not_found"})
    return _to_invoice_out(invoice, paid_total=0)


@router.patch("/invoices/{invoice_id}", response_model=SalesInvoiceOut)
async def update_invoice_endpoint(
    invoice_id: int,
    body: SalesInvoiceUpdate,
    user: Annotated[AuthenticatedUser, require_permission("commercial.edit")],
    session: Annotated[AsyncSession, Depends(require_session)],
) -> SalesInvoiceOut:
    invoice = await update_invoice(
        session, user.company_id, user.id, invoice_id, body.model_dump(exclude_none=True)
    )
    if not invoice:
        raise HTTPException(status_code=404, detail={"code": "not_found"})
    paid_total = await session.scalar(
        select(func.coalesce(func.sum(SalesPayment.amount), 0)).where(
            SalesPayment.invoice_id == invoice_id
        )
    )
    return _to_invoice_out(invoice, paid_total=paid_total or 0)


@router.post("/invoices/{invoice_id}/payments", response_model=SalesPaymentOut, status_code=201)
async def register_payment_endpoint(
    invoice_id: int,
    body: SalesPaymentCreate,
    user: Annotated[AuthenticatedUser, require_permission("commercial.edit")],
    session: Annotated[AsyncSession, Depends(require_session)],
) -> SalesPaymentOut:
    try:
        payment = await register_payment(
            session, user.company_id, user.id, invoice_id, body.model_dump(exclude_none=True)
        )
    except InvalidStateError as exc:
        raise HTTPException(
            status_code=422, detail={"code": "invalid_state", "message": exc.message}
        ) from exc
    if not payment:
        raise HTTPException(status_code=404, detail={"code": "not_found"})
    return SalesPaymentOut(
        id=payment.id,
        invoice_id=payment.invoice_id,
        amount=payment.amount,
        method=payment.method,
        paid_at=payment.paid_at,
        reference=payment.reference,
        notes=payment.notes,
        created_at=payment.created_at,
    )


# ---------------------------------------------------------------------------
# Funil (dashboard)
# ---------------------------------------------------------------------------


@router.get("/funnel", response_model=CommercialFunnel)
async def get_funnel_endpoint(
    user: Annotated[AuthenticatedUser, require_permission("commercial.view")],
    session: Annotated[AsyncSession, Depends(require_session)],
) -> CommercialFunnel:
    funnel = await get_funnel(session, user.company_id)
    return CommercialFunnel(
        quoted_count=funnel.quoted_count,
        quoted_total=funnel.quoted_total,
        approved_count=funnel.approved_count,
        approved_total=funnel.approved_total,
        delivered_count=funnel.delivered_count,
        invoiced_total=funnel.invoiced_total,
        received_total=funnel.received_total,
    )
