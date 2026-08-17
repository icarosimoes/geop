from datetime import UTC, datetime
from typing import Annotated

import bcrypt
import jwt
from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.security import OAuth2PasswordBearer
from pydantic import BaseModel, field_validator
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings, get_settings
from app.core.dependencies import require_session
from app.core.rate_limit import limiter
from app.core.security import (
    create_access_token,
    create_refresh_token,
    decode_access_token,
    decode_erpsolid_sso_token,
    decode_impersonation_token,
    decode_invite_token,
    decode_refresh_token,
)
from app.domain.auth.repository import find_active_user_by_id
from app.domain.auth.schemas import (
    LoginRequest,
    TokenResponse,
    UserResponse,
    validate_password_strength,
)
from app.domain.auth.service import (
    MultiTenantResult,
    SsoCompanyNotFoundError,
    SsoUserInactiveError,
    authenticate,
    resolve_or_provision_sso_user,
    to_response,
)

router = APIRouter(prefix="/auth", tags=["auth"])
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/login")


@router.post("/login")
@limiter.limit("10/minute")
async def login(
    request: Request,
    payload: LoginRequest,
    session: Annotated[AsyncSession, Depends(require_session)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> TokenResponse:
    result = await authenticate(
        session,
        payload.email,
        payload.password,
        settings,
        company_id=payload.company_id,
    )
    if result is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"code": "invalid_credentials", "message": "E-mail ou senha inválidos"},
        )
    if isinstance(result, MultiTenantResult):
        raise HTTPException(
            status_code=422,
            detail={
                "code": "multi_tenant",
                "message": "Selecione a empresa",
                "tenants": [{"id": t.id, "name": t.name} for t in result.tenants],
            },
        )
    return result


@router.get("/me", response_model=UserResponse)
async def me(
    token: Annotated[str, Depends(oauth2_scheme)],
    session: Annotated[AsyncSession, Depends(require_session)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> UserResponse:
    try:
        claims = decode_access_token(token, settings.jwt_secret)
        user_id, company_id = int(claims["sub"]), int(claims["company_id"])
    except (jwt.InvalidTokenError, KeyError, TypeError, ValueError) as exc:
        raise HTTPException(
            status_code=401,
            detail={"code": "invalid_token", "message": "Sessão inválida"},
        ) from exc
    user = await find_active_user_by_id(session, user_id, company_id)
    if user is None:
        raise HTTPException(
            status_code=401,
            detail={"code": "inactive_user", "message": "Usuário indisponível"},
        )
    return to_response(user)


class RefreshRequest(BaseModel):
    refresh_token: str


@router.post("/refresh")
@limiter.limit("20/minute")
async def refresh(
    request: Request,
    body: RefreshRequest,
    session: Annotated[AsyncSession, Depends(require_session)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> TokenResponse:
    try:
        claims = decode_refresh_token(body.refresh_token, settings.jwt_secret)
        user_id, company_id = int(claims["sub"]), int(claims["company_id"])
    except (jwt.InvalidTokenError, KeyError, TypeError, ValueError) as exc:
        raise HTTPException(
            status_code=401,
            detail={"code": "invalid_refresh_token", "message": "Refresh token inválido"},
        ) from exc
    user = await find_active_user_by_id(session, user_id, company_id)
    if user is None:
        raise HTTPException(
            status_code=401,
            detail={"code": "inactive_user", "message": "Usuário indisponível"},
        )
    access = create_access_token(
        subject=user.id,
        company_id=user.company_id,
        role_id=user.role_id,
        permissions=user.permissions,
        secret=settings.jwt_secret,
        minutes=settings.access_token_minutes,
    )
    refresh_tok = create_refresh_token(
        subject=user.id,
        company_id=user.company_id,
        secret=settings.jwt_secret,
        days=settings.refresh_token_days,
    )
    return TokenResponse(
        access_token=access,
        refresh_token=refresh_tok,
        expires_in=settings.access_token_minutes * 60,
        user=to_response(user),
    )


class ImpersonateRequest(BaseModel):
    ticket: str


@router.post("/impersonate")
@limiter.limit("10/minute")
async def impersonate(
    request: Request,
    body: ImpersonateRequest,
    session: Annotated[AsyncSession, Depends(require_session)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> TokenResponse:
    try:
        claims = decode_impersonation_token(body.ticket, settings.jwt_secret)
        user_id, company_id = int(claims["sub"]), int(claims["company_id"])
    except (jwt.InvalidTokenError, KeyError, TypeError, ValueError) as exc:
        raise HTTPException(
            status_code=401,
            detail={
                "code": "invalid_impersonation_token",
                "message": "Ticket inválido ou expirado",
            },
        ) from exc
    user = await find_active_user_by_id(session, user_id, company_id)
    if user is None:
        raise HTTPException(
            status_code=401,
            detail={"code": "inactive_user", "message": "Usuário indisponível"},
        )
    access = create_access_token(
        subject=user.id,
        company_id=user.company_id,
        role_id=user.role_id,
        permissions=user.permissions,
        secret=settings.jwt_secret,
        minutes=settings.access_token_minutes,
    )
    refresh_tok = create_refresh_token(
        subject=user.id,
        company_id=user.company_id,
        secret=settings.jwt_secret,
        days=settings.refresh_token_days,
    )
    return TokenResponse(
        access_token=access,
        refresh_token=refresh_tok,
        expires_in=settings.access_token_minutes * 60,
        user=to_response(user),
    )


class SsoExchangeRequest(BaseModel):
    token: str


@router.post("/sso/exchange")
@limiter.limit("20/minute")
async def sso_exchange(
    request: Request,
    body: SsoExchangeRequest,
    session: Annotated[AsyncSession, Depends(require_session)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> TokenResponse:
    """Troca o token de handoff assinado pelo erpsolid (ver `create_erpsolid_sso_token`
    lá) por uma sessão real do GEOP. Público de propósito — o próprio token, assinado
    com um segredo que só os dois lados conhecem, é a credencial."""
    if not settings.erpsolid_sso_shared_secret:
        raise HTTPException(
            status_code=400,
            detail={"code": "sso_not_configured", "message": "SSO com o ERP não está habilitado"},
        )
    try:
        claims = decode_erpsolid_sso_token(body.token, settings.erpsolid_sso_shared_secret)
        company_id = int(claims["company_id"])
        email = str(claims["email"])
        name = str(claims["name"])
    except (jwt.InvalidTokenError, KeyError, TypeError, ValueError) as exc:
        raise HTTPException(
            status_code=400,
            detail={
                "code": "invalid_sso_token",
                "message": "Link expirado, peça pra abrir o GEOP de novo a partir do ERP",
            },
        ) from exc

    try:
        user = await resolve_or_provision_sso_user(
            session, company_id=company_id, email=email, name=name
        )
    except SsoCompanyNotFoundError as exc:
        raise HTTPException(
            status_code=400,
            detail={"code": "company_not_found", "message": "Empresa não encontrada no GEOP"},
        ) from exc
    except SsoUserInactiveError as exc:
        raise HTTPException(
            status_code=401,
            detail={"code": "inactive_user", "message": "Usuário indisponível"},
        ) from exc

    access = create_access_token(
        subject=user.id,
        company_id=user.company_id,
        role_id=user.role_id,
        permissions=user.permissions,
        secret=settings.jwt_secret,
        minutes=settings.access_token_minutes,
    )
    refresh_tok = create_refresh_token(
        subject=user.id,
        company_id=user.company_id,
        secret=settings.jwt_secret,
        days=settings.refresh_token_days,
    )
    return TokenResponse(
        access_token=access,
        refresh_token=refresh_tok,
        expires_in=settings.access_token_minutes * 60,
        user=to_response(user),
    )


class SetPasswordRequest(BaseModel):
    token: str
    password: str

    @field_validator("password")
    @classmethod
    def check_password(cls, v: str) -> str:
        return validate_password_strength(v)


@router.post("/set-password")
@limiter.limit("5/minute")
async def set_password(
    request: Request,
    body: SetPasswordRequest,
    session: Annotated[AsyncSession, Depends(require_session)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> dict:
    try:
        claims = decode_invite_token(body.token, settings.jwt_secret)
        user_id = int(claims["sub"])
        company_id = int(claims["company_id"])
    except (jwt.InvalidTokenError, KeyError, TypeError, ValueError) as exc:
        raise HTTPException(
            status_code=401,
            detail={"code": "invalid_token", "message": "Token de convite inválido ou expirado"},
        ) from exc

    from app.models import User

    record = await session.scalar(
        select(User).where(
            User.id == user_id,
            User.company_id == company_id,
            User.deleted_at.is_(None),
        )
    )
    if record is None:
        raise HTTPException(status_code=404, detail={"code": "not_found"})

    record.password = bcrypt.hashpw(body.password.encode(), bcrypt.gensalt()).decode()
    record.email_verified_at = datetime.now(UTC)

    from app.core.audit import record_event

    await record_event(
        session,
        company_id=company_id,
        user_id=user_id,
        entity_type="user",
        entity_id=user_id,
        event_type="set_password",
    )
    await session.commit()
    return {"ok": True}
