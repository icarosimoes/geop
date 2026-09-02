from datetime import UTC, datetime, timedelta
from typing import Any

import bcrypt
import jwt

ALGORITHM = "HS256"


def verify_laravel_password(password: str, password_hash: str) -> bool:
    try:
        return bcrypt.checkpw(password.encode(), password_hash.encode())
    except (ValueError, TypeError):
        return False


def create_access_token(
    *,
    subject: int,
    company_id: int,
    role_id: int | None,
    permissions: list[str],
    secret: str,
    minutes: int,
) -> str:
    now = datetime.now(UTC)
    payload: dict[str, Any] = {
        "sub": str(subject),
        "company_id": company_id,
        "role_id": role_id,
        "permissions": permissions,
        "type": "access",
        "iat": now,
        "exp": now + timedelta(minutes=minutes),
    }
    return jwt.encode(payload, secret, algorithm=ALGORITHM)


def create_platform_token(
    *,
    subject: int,
    role: str,
    secret: str,
    minutes: int,
) -> str:
    now = datetime.now(UTC)
    return jwt.encode(
        {
            "sub": str(subject),
            "role": role,
            "type": "platform_access",
            "iat": now,
            "exp": now + timedelta(minutes=minutes),
        },
        secret,
        algorithm=ALGORITHM,
    )


def create_refresh_token(
    *,
    subject: int,
    company_id: int,
    secret: str,
    days: int,
) -> str:
    now = datetime.now(UTC)
    payload: dict[str, Any] = {
        "sub": str(subject),
        "company_id": company_id,
        "type": "refresh",
        "iat": now,
        "exp": now + timedelta(days=days),
    }
    return jwt.encode(payload, secret, algorithm=ALGORITHM)


def decode_refresh_token(token: str, secret: str) -> dict[str, Any]:
    payload: dict[str, Any] = jwt.decode(token, secret, algorithms=[ALGORITHM])
    if payload.get("type") != "refresh":
        raise jwt.InvalidTokenError("tipo de token inválido")
    return payload


def decode_access_token(token: str, secret: str) -> dict[str, Any]:
    payload: dict[str, Any] = jwt.decode(token, secret, algorithms=[ALGORITHM])
    if payload.get("type") != "access":
        raise jwt.InvalidTokenError("tipo de token inválido")
    return payload


def decode_platform_token(token: str, secret: str) -> dict[str, Any]:
    payload: dict[str, Any] = jwt.decode(token, secret, algorithms=[ALGORITHM])
    if payload.get("type") != "platform_access":
        raise jwt.InvalidTokenError("tipo de token inválido")
    return payload


def create_platform_refresh_token(
    *,
    subject: int,
    role: str,
    secret: str,
    days: int,
) -> str:
    now = datetime.now(UTC)
    return jwt.encode(
        {
            "sub": str(subject),
            "role": role,
            "type": "platform_refresh",
            "iat": now,
            "exp": now + timedelta(days=days),
        },
        secret,
        algorithm=ALGORITHM,
    )


def decode_platform_refresh_token(token: str, secret: str) -> dict[str, Any]:
    payload: dict[str, Any] = jwt.decode(token, secret, algorithms=[ALGORITHM])
    if payload.get("type") != "platform_refresh":
        raise jwt.InvalidTokenError("tipo de token inválido")
    return payload


def create_invite_token(
    *,
    user_id: int,
    company_id: int,
    secret: str,
    hours: int = 48,
) -> str:
    now = datetime.now(UTC)
    return jwt.encode(
        {
            "sub": str(user_id),
            "company_id": company_id,
            "type": "invite",
            "iat": now,
            "exp": now + timedelta(hours=hours),
        },
        secret,
        algorithm=ALGORITHM,
    )


def decode_invite_token(token: str, secret: str) -> dict[str, Any]:
    payload: dict[str, Any] = jwt.decode(token, secret, algorithms=[ALGORITHM])
    if payload.get("type") != "invite":
        raise jwt.InvalidTokenError("tipo de token inválido")
    return payload


def create_impersonation_token(
    *,
    subject: int,
    company_id: int,
    secret: str,
    minutes: int = 2,
) -> str:
    now = datetime.now(UTC)
    return jwt.encode(
        {
            "sub": str(subject),
            "company_id": company_id,
            "type": "impersonation",
            "iat": now,
            "exp": now + timedelta(minutes=minutes),
        },
        secret,
        algorithm=ALGORITHM,
    )


def decode_impersonation_token(token: str, secret: str) -> dict[str, Any]:
    payload: dict[str, Any] = jwt.decode(token, secret, algorithms=[ALGORITHM])
    if payload.get("type") != "impersonation":
        raise jwt.InvalidTokenError("tipo de token inválido")
    return payload


def create_erpsolid_sso_token(
    *,
    company_id: int,
    email: str,
    name: str,
    secret: str,
    role: str | None = None,
    seconds: int = 60,
) -> str:
    """Handoff de SSO erpsolid -> GEOP: o erpsolid assina este token (com
    `erpsolid_sso_shared_secret`, nunca com o `jwt_secret` interno de nenhum dos
    dois lados) e o usuário chega no GEOP com ele na URL. TTL curto de propósito
    — é um token de troca única, não uma sessão. `role` é o `CompanyUser.role` de
    lá ("admin" promove o usuário a admin no GEOP também, ver
    `resolve_or_provision_sso_user`)."""
    now = datetime.now(UTC)
    payload: dict = {
        "company_id": company_id,
        "email": email,
        "name": name,
        "type": "erpsolid_sso",
        "iat": now,
        "exp": now + timedelta(seconds=seconds),
    }
    if role is not None:
        payload["role"] = role
    return jwt.encode(payload, secret, algorithm=ALGORITHM)


def decode_erpsolid_sso_token(token: str, secret: str) -> dict[str, Any]:
    payload: dict[str, Any] = jwt.decode(token, secret, algorithms=[ALGORITHM])
    if payload.get("type") != "erpsolid_sso":
        raise jwt.InvalidTokenError("tipo de token inválido")
    return payload


def create_email_oauth_state_token(
    *,
    company_id: int,
    user_id: int,
    account_name: str,
    secret: str,
    seconds: int = 600,
) -> str:
    """State do fluxo OAuth2 do Google (email_client): assinado com o jwt_secret
    normal (não é handoff entre sistemas diferentes, é o próprio GEOP se
    autenticando através do redirect do browser) — dispensa storage de sessão
    pendente no servidor. TTL curto: cobre só o tempo do usuário na tela de
    consentimento do Google, não uma sessão."""
    now = datetime.now(UTC)
    payload = {
        "company_id": company_id,
        "user_id": user_id,
        "account_name": account_name,
        "type": "email_oauth_state",
        "iat": now,
        "exp": now + timedelta(seconds=seconds),
    }
    return jwt.encode(payload, secret, algorithm=ALGORITHM)


def decode_email_oauth_state_token(token: str, secret: str) -> dict[str, Any]:
    payload: dict[str, Any] = jwt.decode(token, secret, algorithms=[ALGORITHM])
    if payload.get("type") != "email_oauth_state":
        raise jwt.InvalidTokenError("tipo de token inválido")
    return payload


def create_employee_session_token(
    *,
    employee_id: int,
    company_id: int,
    secret: str,
    minutes: int = 60,
) -> str:
    """Token do Portal do Colaborador. Namespace estritamente separado do `access`
    de User: sem `permissions`/`role_id`, para impedir escalada de acesso a rotas
    administrativas via `require_permission`."""
    now = datetime.now(UTC)
    payload: dict[str, Any] = {
        "sub": str(employee_id),
        "company_id": company_id,
        "type": "employee_session",
        "iat": now,
        "exp": now + timedelta(minutes=minutes),
    }
    return jwt.encode(payload, secret, algorithm=ALGORITHM)


def decode_employee_session_token(token: str, secret: str) -> dict[str, Any]:
    payload: dict[str, Any] = jwt.decode(token, secret, algorithms=[ALGORITHM])
    if payload.get("type") != "employee_session":
        raise jwt.InvalidTokenError("tipo de token inválido")
    return payload


def create_quote_acceptance_token(
    *,
    quote_id: int,
    company_id: int,
    secret: str,
    days: int = 90,
) -> str:
    """Link público de aceite de orçamento — o cliente abre sem login. `company_id`
    vai assinado no claim (não é lido de sessão nenhuma, já que não há uma) pra
    permitir `set_tenant_context` ANTES de qualquer query em `quotes` (RLS, ver
    app/core/rls.py). O token em si não é a única trava: o endpoint público só
    aceita a decisão enquanto `Quote.status == "enviado"` e `valid_until` não
    passou — decidir uma vez (ou o orçamento expirar) invalida o link mesmo
    dentro da janela de `days`, sem precisar revogar o JWT."""
    now = datetime.now(UTC)
    payload: dict[str, Any] = {
        "sub": str(quote_id),
        "company_id": company_id,
        "type": "quote_acceptance",
        "iat": now,
        "exp": now + timedelta(days=days),
    }
    return jwt.encode(payload, secret, algorithm=ALGORITHM)


def decode_quote_acceptance_token(token: str, secret: str) -> dict[str, Any]:
    payload: dict[str, Any] = jwt.decode(token, secret, algorithms=[ALGORITHM])
    if payload.get("type") != "quote_acceptance":
        raise jwt.InvalidTokenError("tipo de token inválido")
    return payload


def create_esignature_webhook_token(*, company_id: int, secret: str) -> str:
    """URL fixa que o tenant cola no painel do provedor de assinatura (Clicksign)
    pra receber os eventos do envelope — não expira (é configurado uma vez, fora
    do fluxo de request/response) e não carrega `sub` de usuário, só o
    `company_id` pra permitir `set_tenant_context` antes de resolver o webhook
    (mesmo motivo do claim em `create_quote_acceptance_token`)."""
    payload: dict[str, Any] = {
        "company_id": company_id,
        "type": "esignature_webhook",
        "iat": datetime.now(UTC),
    }
    return jwt.encode(payload, secret, algorithm=ALGORITHM)


def decode_esignature_webhook_token(token: str, secret: str) -> dict[str, Any]:
    payload: dict[str, Any] = jwt.decode(token, secret, algorithms=[ALGORITHM])
    if payload.get("type") != "esignature_webhook":
        raise jwt.InvalidTokenError("tipo de token inválido")
    return payload
