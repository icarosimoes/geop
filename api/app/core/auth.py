from typing import Annotated

import jwt
import structlog
from fastapi import Depends, HTTPException
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings, get_settings
from app.core.dependencies import require_session
from app.core.rls import set_tenant_context
from app.core.security import decode_access_token
from app.domain.auth.repository import AuthenticatedUser, find_active_user_by_id

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/login")


async def current_user(
    token: Annotated[str, Depends(oauth2_scheme)],
    session: Annotated[AsyncSession, Depends(require_session)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> AuthenticatedUser:
    try:
        claims = decode_access_token(token, settings.jwt_secret)
        cid = int(claims["company_id"])
        # Precisa vir antes de qualquer query em tabela com RLS — ver
        # app/core/rls.py. company_id já é confiável aqui (claim de um JWT com
        # assinatura validada por decode_access_token).
        await set_tenant_context(session, cid)
        user = await find_active_user_by_id(session, int(claims["sub"]), cid)
    except (jwt.InvalidTokenError, KeyError, TypeError, ValueError) as exc:
        raise HTTPException(status_code=401, detail={"code": "invalid_token"}) from exc
    if user is None:
        raise HTTPException(status_code=401, detail={"code": "inactive_user"})
    structlog.contextvars.bind_contextvars(company_id=cid, user_id=user.id)
    return user
