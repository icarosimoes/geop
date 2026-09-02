"""Aceite de orçamento pelo cliente, via link público (sem login) — token JWT
assinado carrega `quote_id`+`company_id` (ver
app/core/security.py::create_quote_acceptance_token). Mesma família de padrão
de `timeclock/mobile_auth.py`/`platform/webhook_router.py`: decodifica o token,
seta o `app.current_company_id` do RLS manualmente (`set_tenant_context`) antes
de qualquer query, e só então busca o registro."""

from typing import Annotated

import jwt
import structlog
from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings, get_settings
from app.core.dependencies import require_session
from app.core.rate_limit import limiter
from app.core.rls import set_tenant_context
from app.core.security import decode_quote_acceptance_token
from app.domain.commercial.schemas import (
    PublicQuoteDecision,
    PublicQuoteOut,
    QuoteItemOut,
    SignatureOtpConfirm,
    SignatureOtpRequest,
    SignatureOtpRequestOut,
)
from app.domain.commercial.service import (
    InvalidStateError,
    PublicQuoteDetail,
    SignatureError,
    confirm_signature_otp,
    decide_quote,
    get_quote_for_public,
    request_signature_otp,
)

logger = structlog.get_logger()

router = APIRouter(prefix="/public/quotes", tags=["public-quotes"])


async def _resolve_token(token: str, session: AsyncSession, settings: Settings) -> tuple[int, int]:
    try:
        claims = decode_quote_acceptance_token(token, settings.jwt_secret)
        quote_id = int(claims["sub"])
        company_id = int(claims["company_id"])
    except (jwt.InvalidTokenError, KeyError, TypeError, ValueError) as exc:
        raise HTTPException(status_code=401, detail={"code": "invalid_token"}) from exc

    # Precisa vir antes de qualquer query em tabela com RLS — ver app/core/rls.py.
    await set_tenant_context(session, company_id)
    return quote_id, company_id


def _to_public_quote_out(detail: PublicQuoteDetail) -> PublicQuoteOut:
    return PublicQuoteOut(
        number=detail.quote.number,
        title=detail.quote.title,
        status=detail.quote.status,
        customer_name=detail.customer_name,
        company_name=detail.company_name,
        description=detail.quote.description,
        conditions=detail.quote.conditions,
        notes=detail.quote.notes,
        issued_at=detail.quote.issued_at,
        valid_until=detail.quote.valid_until,
        expired=detail.expired,
        discount_amount=detail.quote.discount_amount,
        subtotal=detail.quote.subtotal,
        total=detail.quote.total,
        decided_at=detail.quote.decided_at,
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
    )


@router.get("/{token}", response_model=PublicQuoteOut)
@limiter.limit("30/minute")
async def get_public_quote(
    request: Request,
    token: str,
    session: Annotated[AsyncSession, Depends(require_session)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> PublicQuoteOut:
    quote_id, company_id = await _resolve_token(token, session, settings)
    detail = await get_quote_for_public(session, company_id, quote_id)
    if not detail:
        raise HTTPException(status_code=404, detail={"code": "not_found"})
    return _to_public_quote_out(detail)


@router.get("/{token}/pdf")
@limiter.limit("15/minute")
async def get_public_quote_pdf(
    request: Request,
    token: str,
    session: Annotated[AsyncSession, Depends(require_session)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> StreamingResponse:
    from app.domain.commercial.pdf import generate_quote_pdf

    quote_id, company_id = await _resolve_token(token, session, settings)
    detail = await get_quote_for_public(session, company_id, quote_id)
    if not detail:
        raise HTTPException(status_code=404, detail={"code": "not_found"})
    buf = generate_quote_pdf(
        company_name=detail.company_name,
        quote=detail.quote,
        customer_name=detail.customer_name,
        items=detail.items,
        signature=detail.signature,
    )
    filename = f"orcamento_{detail.quote.number or detail.quote.id}.pdf"
    return StreamingResponse(
        buf,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.post("/{token}/accept", response_model=PublicQuoteOut)
@limiter.limit("10/minute")
async def accept_public_quote(
    request: Request,
    token: str,
    body: PublicQuoteDecision,
    session: Annotated[AsyncSession, Depends(require_session)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> PublicQuoteOut:
    return await _decide(token, body, approved=True, session=session, settings=settings)


@router.post("/{token}/reject", response_model=PublicQuoteOut)
@limiter.limit("10/minute")
async def reject_public_quote(
    request: Request,
    token: str,
    body: PublicQuoteDecision,
    session: Annotated[AsyncSession, Depends(require_session)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> PublicQuoteOut:
    return await _decide(token, body, approved=False, session=session, settings=settings)


async def _decide(
    token: str,
    body: PublicQuoteDecision,
    *,
    approved: bool,
    session: AsyncSession,
    settings: Settings,
) -> PublicQuoteOut:
    quote_id, company_id = await _resolve_token(token, session, settings)
    try:
        quote = await decide_quote(session, company_id, quote_id, approved, body.decision_note)
    except InvalidStateError as exc:
        raise HTTPException(
            status_code=422, detail={"code": "invalid_state", "message": exc.message}
        ) from exc
    if not quote:
        raise HTTPException(status_code=404, detail={"code": "not_found"})

    logger.info("quote_decided", quote_id=quote_id, company_id=company_id, approved=approved)
    detail = await get_quote_for_public(session, company_id, quote_id)
    assert detail is not None
    return _to_public_quote_out(detail)


@router.post("/{token}/signature/otp", response_model=SignatureOtpRequestOut)
@limiter.limit("5/minute")
async def request_signature_otp_endpoint(
    request: Request,
    token: str,
    body: SignatureOtpRequest,
    session: Annotated[AsyncSession, Depends(require_session)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> SignatureOtpRequestOut:
    quote_id, company_id = await _resolve_token(token, session, settings)
    try:
        signature = await request_signature_otp(
            session,
            company_id,
            quote_id,
            settings,
            signer_name=body.signer_name,
            signer_document=body.signer_document,
            ip=request.client.host if request.client else None,
            user_agent=request.headers.get("user-agent"),
        )
    except InvalidStateError as exc:
        raise HTTPException(
            status_code=422, detail={"code": "invalid_state", "message": exc.message}
        ) from exc
    except SignatureError as exc:
        raise HTTPException(
            status_code=422, detail={"code": exc.code, "message": exc.message}
        ) from exc
    return SignatureOtpRequestOut(status=signature.status, otp_sent_at=signature.otp_sent_at)


@router.post("/{token}/signature/otp/confirm", response_model=PublicQuoteOut)
@limiter.limit("10/minute")
async def confirm_signature_otp_endpoint(
    request: Request,
    token: str,
    body: SignatureOtpConfirm,
    session: Annotated[AsyncSession, Depends(require_session)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> PublicQuoteOut:
    quote_id, company_id = await _resolve_token(token, session, settings)
    try:
        await confirm_signature_otp(session, company_id, quote_id, body.code)
    except InvalidStateError as exc:
        raise HTTPException(
            status_code=422, detail={"code": "invalid_state", "message": exc.message}
        ) from exc
    except SignatureError as exc:
        raise HTTPException(
            status_code=422, detail={"code": exc.code, "message": exc.message}
        ) from exc

    logger.info("quote_signed", quote_id=quote_id, company_id=company_id, method="simples")
    detail = await get_quote_for_public(session, company_id, quote_id)
    assert detail is not None
    return _to_public_quote_out(detail)
