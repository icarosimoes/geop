"""Webhook do provedor de assinatura ICP-Brasil (Clicksign) — evento de
assinatura concluída/recusada volta aqui. A URL carrega um token assinado
(`create_esignature_webhook_token`) com o `company_id`, exatamente como o
link de aceite público em `public_router.py` — é a única forma de resolver
qual tenant o evento pertence antes de rodar `set_tenant_context` (RLS).
Diferente do webhook do Asaas (`platform/webhook_router.py`), que é global
(uma conta Asaas só, da própria plataforma): aqui cada tenant tem sua própria
conta/API key na Clicksign, então a URL precisa ser por tenant."""

from typing import Annotated, Any

import jwt
import structlog
from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings, get_settings
from app.core.dependencies import require_session
from app.core.rate_limit import limiter
from app.core.rls import set_tenant_context
from app.core.security import decode_esignature_webhook_token
from app.domain.commercial.service import handle_clicksign_webhook

logger = structlog.get_logger()

router = APIRouter(prefix="/public/quotes/webhooks", tags=["public-quotes-webhooks"])


@router.post("/clicksign/{webhook_token}")
@limiter.limit("60/minute")
async def clicksign_webhook(
    request: Request,
    webhook_token: str,
    session: Annotated[AsyncSession, Depends(require_session)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> dict[str, Any]:
    try:
        claims = decode_esignature_webhook_token(webhook_token, settings.jwt_secret)
        company_id = int(claims["company_id"])
    except (jwt.InvalidTokenError, KeyError, TypeError, ValueError) as exc:
        raise HTTPException(status_code=401, detail={"code": "invalid_token"}) from exc

    await set_tenant_context(session, company_id)
    payload = await request.json()
    result = await handle_clicksign_webhook(session, company_id, payload)
    logger.info("clicksign_webhook_processed", company_id=company_id, result=result)
    return result
