import secrets
from dataclasses import dataclass
from datetime import UTC, datetime

import bcrypt
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings
from app.core.security import create_access_token, create_refresh_token, verify_laravel_password
from app.domain.auth.repository import (
    AuthenticatedUser,
    find_active_user_by_id,
    find_active_users_by_email,
)
from app.domain.auth.schemas import TenantOption, TokenResponse, UserResponse
from app.models import Company, Role, User


def to_response(user: AuthenticatedUser) -> UserResponse:
    return UserResponse(
        id=user.id,
        name=user.name,
        email=user.email,
        phone=user.phone,
        company_id=user.company_id,
        role_id=user.role_id,
        role_name=user.role_name,
        permissions=user.permissions,
    )


@dataclass
class MultiTenantResult:
    tenants: list[TenantOption]


class SsoCompanyNotFoundError(Exception):
    """`company_id` do token de SSO não corresponde a nenhuma empresa ativa no GEOP."""


class SsoUserInactiveError(Exception):
    """Já existe um User com esse e-mail no tenant, mas está inativo/desligado —
    SSO não deve reativar silenciosamente uma conta que foi desativada de propósito."""


DEFAULT_SSO_ROLE_CODE = "colaborador"


async def _ensure_default_sso_role(session: AsyncSession, company_id: int) -> int:
    """Role least-privilege (sem nenhuma Permission) usada para provisionar o
    primeiro acesso de um usuário que chegou via SSO do erpsolid — não existe
    hoje nenhum conceito de "role padrão" no GEOP (roles são sempre escolhidas
    explicitamente ao convidar um usuário), então criamos uma sob demanda."""
    role_id = await session.scalar(
        select(Role.id).where(Role.company_id == company_id, Role.code == DEFAULT_SSO_ROLE_CODE)
    )
    if role_id is not None:
        return role_id
    role = Role(company_id=company_id, code=DEFAULT_SSO_ROLE_CODE, name="Colaborador")
    session.add(role)
    await session.flush()
    return role.id


async def resolve_or_provision_sso_user(
    session: AsyncSession,
    *,
    company_id: int,
    email: str,
    name: str,
) -> AuthenticatedUser:
    """Resolve o User do handoff de SSO erpsolid -> GEOP, provisionando na hora
    se for o primeiro acesso desse e-mail nesse tenant (o usuário já chegou
    autenticado pelo ERP, então confiamos no e-mail do claim)."""
    company = await session.scalar(
        select(Company).where(
            Company.id == company_id,
            Company.status == "active",
            Company.deleted_at.is_(None),
        )
    )
    if company is None:
        raise SsoCompanyNotFoundError()

    existing_id = await session.scalar(
        select(User.id).where(
            User.company_id == company_id,
            User.email == email.lower(),
            User.deleted_at.is_(None),
        )
    )
    if existing_id is not None:
        user = await find_active_user_by_id(session, existing_id, company_id)
        if user is None:
            raise SsoUserInactiveError()
        return user

    role_id = await _ensure_default_sso_role(session, company_id)
    unusable_password = bcrypt.hashpw(secrets.token_urlsafe(32).encode(), bcrypt.gensalt()).decode()
    record = User(
        company_id=company_id,
        role_id=role_id,
        name=name,
        email=email.lower(),
        password=unusable_password,
        active=True,
        email_verified_at=datetime.now(UTC).replace(tzinfo=None),
    )
    session.add(record)
    await session.commit()

    user = await find_active_user_by_id(session, record.id, company_id)
    assert user is not None  # acabamos de criar e commitar — não pode sumir aqui
    return user


async def authenticate(
    session: AsyncSession,
    email: str,
    password: str,
    settings: Settings,
    company_id: int | None = None,
) -> TokenResponse | MultiTenantResult | None:
    users = await find_active_users_by_email(session, email, company_id)
    authenticated_users = [
        user for user in users if verify_laravel_password(password, user.password_hash)
    ]

    if len(authenticated_users) > 1:
        return MultiTenantResult(
            tenants=[
                TenantOption(id=user.company_id, name=user.company_name)
                for user in authenticated_users
            ],
        )

    if not authenticated_users:
        return None

    user = authenticated_users[0]

    access = create_access_token(
        subject=user.id,
        company_id=user.company_id,
        role_id=user.role_id,
        permissions=user.permissions,
        secret=settings.jwt_secret,
        minutes=settings.access_token_minutes,
    )
    refresh = create_refresh_token(
        subject=user.id,
        company_id=user.company_id,
        secret=settings.jwt_secret,
        days=settings.refresh_token_days,
    )
    return TokenResponse(
        access_token=access,
        refresh_token=refresh,
        expires_in=settings.access_token_minutes * 60,
        user=to_response(user),
    )
