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
    seconds: int = 60,
) -> str:
    """Handoff de SSO erpsolid -> GEOP: o erpsolid assina este token (com
    `erpsolid_sso_shared_secret`, nunca com o `jwt_secret` interno de nenhum dos
    dois lados) e o usuário chega no GEOP com ele na URL. TTL curto de propósito
    — é um token de troca única, não uma sessão."""
    now = datetime.now(UTC)
    return jwt.encode(
        {
            "company_id": company_id,
            "email": email,
            "name": name,
            "type": "erpsolid_sso",
            "iat": now,
            "exp": now + timedelta(seconds=seconds),
        },
        secret,
        algorithm=ALGORITHM,
    )


def decode_erpsolid_sso_token(token: str, secret: str) -> dict[str, Any]:
    payload: dict[str, Any] = jwt.decode(token, secret, algorithms=[ALGORITHM])
    if payload.get("type") != "erpsolid_sso":
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
