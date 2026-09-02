"""Pipeline comercial: Cliente -> Orçamento -> Aceite -> Venda -> Instalação ->
Faturamento -> Cobrança. Ver app/models/commercial.py para o desenho das tabelas.
"""

import hashlib
import secrets
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal
from typing import Any, NamedTuple

import bcrypt
import structlog
from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.audit import compute_diff, record_event
from app.core.config import Settings
from app.core.security import create_esignature_webhook_token, create_quote_acceptance_token
from app.models import (
    Company,
    Customer,
    Quote,
    QuoteItem,
    QuoteSignature,
    Sale,
    SalesInvoice,
    SalesPayment,
    User,
)

logger = structlog.get_logger()

OTP_RESEND_COOLDOWN = timedelta(seconds=60)
OTP_EXPIRY = timedelta(minutes=10)
OTP_MAX_ATTEMPTS = 5


class SignatureError(Exception):
    """Erro de negócio do fluxo de assinatura (código expirado/errado demais
    vezes, etc.) — o router traduz pra HTTP 422, mesmo padrão de
    `InvalidStateError`."""

    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code
        self.message = message


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
    signature: QuoteSignature | None


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
    signature = await _get_signature(session, company_id, quote_id)
    return QuoteDetail(quote, customer_name, responsible_name, items, signature)


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


def build_acceptance_url(settings: Settings, company_id: int, quote_id: int) -> str:
    token = create_quote_acceptance_token(
        quote_id=quote_id, company_id=company_id, secret=settings.jwt_secret
    )
    return f"{settings.registro_web_url}/orcamento/{token}"


def _format_brl(value: Decimal) -> str:
    return f"R$ {value:,.2f}".replace(",", "@").replace(".", ",").replace("@", ".")


async def _send_quote_email(
    session: AsyncSession, company_id: int, quote: Quote, settings: Settings
) -> None:
    """Dispara o email com o link de aceite pro cliente. Melhor esforço: uma
    falha no Brevo (ou cliente sem email cadastrado) não pode reverter o envio
    do orçamento em si, que já foi commitado antes desta chamada."""
    row = (
        await session.execute(
            select(Customer.name, Customer.email).where(Customer.id == quote.customer_id)
        )
    ).one_or_none()
    if not row or not row.email:
        logger.info(
            "quote_email_skipped_no_customer_email", quote_id=quote.id, company_id=company_id
        )
        return

    company_name = await session.scalar(select(Company.name).where(Company.id == company_id)) or ""

    from app.domain.platform.service import get_effective_email_config
    from app.domain.settings.router import get_company_setting
    from app.integrations.brevo import send_email

    brevo = await get_company_setting(session, company_id, "brevo")
    api_key = brevo.get("api_key")
    from_address = brevo.get("from_address")
    from_name = brevo.get("from_name")
    if not api_key:
        (
            platform_api_key,
            platform_from_address,
            platform_from_name,
        ) = await get_effective_email_config(session, settings)
        api_key = platform_api_key
        from_address = from_address or platform_from_address
        from_name = from_name or platform_from_name
    if not api_key:
        logger.info("quote_email_skipped_no_brevo_key", quote_id=quote.id, company_id=company_id)
        return
    from_address = from_address or "noreply@registro.app"
    from_name = from_name or company_name or "GEOP"

    acceptance_url = build_acceptance_url(settings, company_id, quote.id)
    valid_until_line = (
        f"<p>Válido até {quote.valid_until.strftime('%d/%m/%Y')}.</p>" if quote.valid_until else ""
    )
    html = (
        f"<h2>Orçamento {quote.number or quote.id}</h2>"
        f"<p>Olá {row.name},</p>"
        f"<p>{company_name} enviou um novo orçamento pra você: <strong>{quote.title}</strong>.</p>"
        f"<p>Valor total: {_format_brl(quote.total)}</p>"
        f"{valid_until_line}"
        f'<p><a href="{acceptance_url}">Ver orçamento e decidir</a></p>'
        f"<p>Este link é pessoal e não requer login.</p>"
    )
    try:
        await send_email(
            api_key=api_key,
            from_address=from_address,
            from_name=from_name,
            to_email=row.email,
            to_name=row.name,
            subject=f"Orçamento {quote.number or quote.id} — {company_name}",
            html=html,
        )
    except Exception:
        logger.warning("quote_email_send_failed", quote_id=quote.id, company_id=company_id)


async def send_quote(
    session: AsyncSession, company_id: int, user_id: int, quote_id: int, settings: Settings
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
    await _send_quote_email(session, company_id, quote, settings)
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
    signature: QuoteSignature | None


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
    signature = await _get_signature(session, company_id, quote_id)
    return PublicQuoteDetail(
        quote, customer_name or "", company_name or "", items, expired, signature
    )


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
# Assinatura eletrônica (evolução do aceite público acima)
#
# Dois métodos, ambos terminando em `decide_quote(..., approved=True)` — não
# duplicam a criação da `Sale`:
#   - "simples": nome + CPF do cliente + código de 6 dígitos enviado por
#     e-mail (OTP), com hash do PDF/IP/user-agent como trilha de evidência.
#     Sem custo de terceiro; validade jurídica pelo Código Civil (art. 219),
#     não pela presunção forte da MP 2.200-2/2001.
#   - "icp_brasil": delega a um provedor credenciado junto às Autoridades
#     Certificadoras (hoje: Clicksign, ver app/integrations/esignature/),
#     cobrindo certificado A1/A3 e certificado em nuvem — dá a presunção da
#     MP 2.200-2/2001. Só é iniciado por um usuário interno
#     (POST /commercial/quotes/{id}/signature/icp), o cliente assina no site
#     do provedor e o resultado volta por webhook.
# ---------------------------------------------------------------------------


async def _get_signature(
    session: AsyncSession, company_id: int, quote_id: int
) -> QuoteSignature | None:
    return await session.scalar(  # type: ignore[no-any-return]
        select(QuoteSignature).where(
            QuoteSignature.quote_id == quote_id,
            QuoteSignature.company_id == company_id,
        )
    )


async def _get_or_create_signature(
    session: AsyncSession, company_id: int, quote_id: int, method: str
) -> QuoteSignature:
    signature = await _get_signature(session, company_id, quote_id)
    if signature:
        signature.method = method
        return signature
    signature = QuoteSignature(company_id=company_id, quote_id=quote_id, method=method)
    session.add(signature)
    await session.flush()
    return signature


def _generate_otp_code() -> str:
    return f"{secrets.randbelow(1_000_000):06d}"


async def request_signature_otp(
    session: AsyncSession,
    company_id: int,
    quote_id: int,
    settings: Settings,
    *,
    signer_name: str,
    signer_document: str,
    ip: str | None,
    user_agent: str | None,
) -> QuoteSignature:
    quote = await _get_quote(session, company_id, quote_id)
    if not quote:
        raise InvalidStateError("Orçamento não encontrado.")
    if quote.status != "enviado":
        raise InvalidStateError("Este orçamento não está mais aguardando decisão.")

    row = (
        await session.execute(select(Customer.email).where(Customer.id == quote.customer_id))
    ).scalar_one_or_none()
    if not row:
        raise SignatureError(
            "no_customer_email",
            "Cliente sem e-mail cadastrado — não é possível enviar o código de confirmação.",
        )

    signature = await _get_or_create_signature(session, company_id, quote_id, "simples")
    if signature.otp_sent_at and datetime.now(UTC).replace(tzinfo=None) - signature.otp_sent_at < (
        OTP_RESEND_COOLDOWN
    ):
        raise SignatureError("otp_cooldown", "Aguarde um minuto antes de reenviar o código.")

    code = _generate_otp_code()
    signature.signer_name = signer_name
    signature.signer_document = signer_document
    signature.signer_email = row
    signature.ip_address = ip
    signature.user_agent = user_agent
    signature.otp_code_hash = bcrypt.hashpw(code.encode(), bcrypt.gensalt()).decode()
    signature.otp_sent_at = datetime.now(UTC).replace(tzinfo=None)
    signature.otp_attempts = 0
    signature.status = "otp_enviado"

    company_name = await session.scalar(select(Company.name).where(Company.id == company_id)) or ""
    await _send_otp_email(session, company_id, quote, row, code, company_name, settings)

    await session.commit()
    await session.refresh(signature)
    return signature


async def _send_otp_email(
    session: AsyncSession,
    company_id: int,
    quote: Quote,
    to_email: str,
    code: str,
    company_name: str,
    settings: Settings,
) -> None:
    from app.domain.platform.service import get_effective_email_config
    from app.domain.settings.router import get_company_setting
    from app.integrations.brevo import send_email

    brevo = await get_company_setting(session, company_id, "brevo")
    api_key = brevo.get("api_key")
    from_address = brevo.get("from_address")
    from_name = brevo.get("from_name")
    if not api_key:
        (
            platform_api_key,
            platform_from_address,
            platform_from_name,
        ) = await get_effective_email_config(session, settings)
        api_key = platform_api_key
        from_address = from_address or platform_from_address
        from_name = from_name or platform_from_name
    if not api_key:
        logger.warning("signature_otp_email_skipped_no_brevo_key", quote_id=quote.id)
        raise SignatureError(
            "email_not_configured", "Envio de e-mail não configurado — contate o fornecedor."
        )
    from_address = from_address or "noreply@registro.app"
    from_name = from_name or company_name or "GEOP"

    html = (
        f"<h2>Código de confirmação — {quote.number or quote.id}</h2>"
        f"<p>Use o código abaixo pra confirmar sua assinatura do orçamento "
        f"<strong>{quote.title}</strong>:</p>"
        f"<p style='font-size:28px;font-weight:bold;letter-spacing:4px'>{code}</p>"
        f"<p>Válido por 10 minutos. Se você não solicitou isso, ignore este e-mail.</p>"
    )
    try:
        result = await send_email(
            api_key=api_key,
            from_address=from_address,
            from_name=from_name,
            to_email=to_email,
            subject=f"Código de confirmação — {quote.number or quote.id}",
            html=html,
        )
    except Exception as exc:
        logger.warning("signature_otp_email_send_failed", quote_id=quote.id)
        raise SignatureError("email_send_failed", "Falha ao enviar o e-mail com o código.") from exc
    # `send_email` (app/integrations/brevo.py) não levanta em falha HTTP — devolve
    # {"error": True, ...} — achado ao testar este fluxo manualmente contra uma API
    # key inválida: sem este check, um erro 401 do Brevo virava "código enviado"
    # silenciosamente pro cliente, que nunca recebia nada.
    if result.get("error"):
        logger.warning(
            "signature_otp_email_send_failed", quote_id=quote.id, status=result.get("status")
        )
        raise SignatureError("email_send_failed", "Falha ao enviar o e-mail com o código.")


async def confirm_signature_otp(
    session: AsyncSession, company_id: int, quote_id: int, code: str
) -> Quote:
    quote = await _get_quote(session, company_id, quote_id)
    if not quote:
        raise InvalidStateError("Orçamento não encontrado.")
    signature = await _get_signature(session, company_id, quote_id)
    if not signature or not signature.otp_code_hash or signature.status != "otp_enviado":
        raise SignatureError("no_otp_pending", "Solicite um código antes de confirmar.")
    otp_age = datetime.now(UTC).replace(tzinfo=None) - (signature.otp_sent_at or datetime.min)
    if otp_age > OTP_EXPIRY:
        raise SignatureError("otp_expired", "Código expirado — solicite um novo.")
    if signature.otp_attempts >= OTP_MAX_ATTEMPTS:
        raise SignatureError("otp_locked", "Muitas tentativas — solicite um novo código.")

    if not bcrypt.checkpw(code.encode(), signature.otp_code_hash.encode()):
        signature.otp_attempts += 1
        await session.commit()
        raise SignatureError("otp_invalid", "Código incorreto.")

    from app.domain.attachments.service import create_attachment
    from app.domain.commercial.pdf import generate_quote_pdf

    items = await _quote_items(session, quote_id)
    customer_name = signature.signer_name or ""
    company_name = await session.scalar(select(Company.name).where(Company.id == company_id)) or ""
    base_pdf = generate_quote_pdf(
        company_name=company_name, quote=quote, customer_name=customer_name, items=items
    ).getvalue()

    signature.status = "assinado"
    signature.otp_verified_at = datetime.now(UTC).replace(tzinfo=None)
    signature.signed_at = signature.otp_verified_at
    signature.document_hash = hashlib.sha256(base_pdf).hexdigest()

    # PDF final com a página de evidência anexada, guardado como Attachment —
    # o hash acima se refere só ao `base_pdf` (sem essa página), calculado
    # ANTES dela existir (ver docstring de `_signature_section` em pdf.py).
    final_pdf = generate_quote_pdf(
        company_name=company_name,
        quote=quote,
        customer_name=customer_name,
        items=items,
        signature=signature,
    ).getvalue()
    if quote.created_by_user_id:
        attachment = await create_attachment(
            session,
            company_id,
            quote.created_by_user_id,
            entity_type="quote",
            entity_id=quote.id,
            filename=f"orcamento_assinado_{quote.number or quote.id}.pdf",
            content_type="application/pdf",
            data=final_pdf,
            skip_audit=True,
        )
        if not isinstance(attachment, str):
            signature.signed_pdf_attachment_id = attachment.id

    await record_event(
        session,
        company_id=company_id,
        user_id=None,
        actor_name=f"{signature.signer_name} (assinatura eletrônica)",
        entity_type="quote",
        entity_id=quote.id,
        event_type="signature_confirmed",
        diff={
            "method": "simples",
            "signer_document": signature.signer_document,
            "document_hash": signature.document_hash,
        },
    )
    await session.flush()

    decided = await decide_quote(session, company_id, quote_id, True, None)
    assert decided is not None
    return decided


async def start_icp_signature(
    session: AsyncSession, company_id: int, quote_id: int, settings: Settings
) -> str:
    """Só via rota autenticada — dispara o envelope Clicksign e devolve o
    `sign_url` que o usuário interno envia ao cliente (mesmo canal de e-mail
    do aceite simples)."""
    from app.domain.settings.router import get_company_setting

    quote = await _get_quote(session, company_id, quote_id)
    if not quote:
        raise InvalidStateError("Orçamento não encontrado.")
    if quote.status != "enviado":
        raise InvalidStateError("Este orçamento não está mais aguardando decisão.")

    esign = await get_company_setting(session, company_id, "esignature")
    api_key = esign.get("api_key")
    if not api_key:
        raise SignatureError(
            "not_configured", "Configure a integração de assinatura ICP-Brasil antes de usar."
        )

    customer = (
        await session.execute(
            select(Customer.name, Customer.email, Customer.document).where(
                Customer.id == quote.customer_id
            )
        )
    ).one_or_none()
    if not customer or not customer.email:
        raise SignatureError(
            "no_customer_email", "Cliente sem e-mail cadastrado — obrigatório pro provedor."
        )

    from app.domain.commercial.pdf import generate_quote_pdf
    from app.integrations.esignature import clicksign

    items = await _quote_items(session, quote_id)
    company_name = await session.scalar(select(Company.name).where(Company.id == company_id)) or ""
    pdf_bytes = generate_quote_pdf(
        company_name=company_name, quote=quote, customer_name=customer.name, items=items
    ).getvalue()

    webhook_token = create_esignature_webhook_token(
        company_id=company_id, secret=settings.jwt_secret
    )
    callback_url = f"{settings.api_public_url}/public/quotes/webhooks/clicksign/{webhook_token}"

    result = await clicksign.create_envelope(
        api_key=api_key,
        pdf_bytes=pdf_bytes,
        filename=f"orcamento_{quote.number or quote.id}.pdf",
        signer_name=customer.name,
        signer_email=customer.email,
        signer_document=customer.document,
        callback_url=callback_url,
    )

    signature = await _get_or_create_signature(session, company_id, quote_id, "icp_brasil")
    signature.status = "pendente"
    signature.provider = "clicksign"
    signature.provider_envelope_id = result.external_id
    signature.signer_name = customer.name
    signature.signer_email = customer.email
    signature.signer_document = customer.document
    signature.document_hash = hashlib.sha256(pdf_bytes).hexdigest()

    await record_event(
        session,
        company_id=company_id,
        user_id=None,
        actor_name="Sistema (assinatura ICP-Brasil solicitada)",
        entity_type="quote",
        entity_id=quote.id,
        event_type="icp_signature_requested",
        diff={"provider_envelope_id": result.external_id},
    )
    await session.commit()
    return result.sign_url


async def handle_clicksign_webhook(
    session: AsyncSession, company_id: int, payload: dict[str, Any]
) -> dict[str, Any]:
    from app.domain.attachments.service import create_attachment
    from app.domain.settings.router import get_company_setting
    from app.integrations.esignature import clicksign

    event = clicksign.parse_webhook(payload)
    signature = await session.scalar(
        select(QuoteSignature).where(
            QuoteSignature.company_id == company_id,
            QuoteSignature.provider_envelope_id == event.external_id,
        )
    )
    if not signature:
        return {"status": "ignored", "reason": "unknown_envelope"}
    if signature.status == "assinado":
        return {"status": "already_processed"}
    if event.status != "signed":
        signature.status = "recusado" if event.status == "refused" else signature.status
        await session.commit()
        return {"status": "noop", "provider_status": event.status}

    quote = await _get_quote(session, company_id, signature.quote_id)
    if not quote:
        return {"status": "ignored", "reason": "quote_not_found"}

    esign = await get_company_setting(session, company_id, "esignature")
    api_key = esign.get("api_key", "")
    signed_pdf = await clicksign.download_signed_document(
        api_key=api_key, external_id=event.external_id
    )

    signature.status = "assinado"
    signature.signed_at = datetime.now(UTC).replace(tzinfo=None)
    signature.certificate_info = event.certificate_info

    if quote.created_by_user_id:
        attachment = await create_attachment(
            session,
            company_id,
            quote.created_by_user_id,
            entity_type="quote",
            entity_id=quote.id,
            filename=f"orcamento_assinado_{quote.number or quote.id}.pdf",
            content_type="application/pdf",
            data=signed_pdf,
        )
        if not isinstance(attachment, str):
            signature.signed_pdf_attachment_id = attachment.id
    else:
        logger.warning(
            "clicksign_signed_pdf_not_attached_no_creator", quote_id=quote.id, company_id=company_id
        )

    await record_event(
        session,
        company_id=company_id,
        user_id=None,
        actor_name=f"{signature.signer_name} (assinatura ICP-Brasil)",
        entity_type="quote",
        entity_id=quote.id,
        event_type="signature_confirmed",
        diff={"method": "icp_brasil", "provider": "clicksign"},
    )

    await decide_quote(session, company_id, signature.quote_id, True, None)
    return {"status": "signed"}


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
