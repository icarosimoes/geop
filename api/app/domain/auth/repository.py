from dataclasses import dataclass

from sqlalchemy import Integer, String, bindparam, select, text
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models import Company, Role, User


@dataclass(frozen=True)
class AuthenticatedUser:
    id: int
    name: str
    email: str
    phone: str | None
    password_hash: str
    company_id: int
    company_name: str
    role_id: int | None
    role_name: str | None
    permissions: list[str]


def map_user(user: User) -> AuthenticatedUser:
    return AuthenticatedUser(
        id=user.id,
        name=user.name,
        email=user.email,
        phone=user.phone,
        password_hash=user.password,
        company_id=user.company_id,
        company_name=user.company.name,
        role_id=user.role_id,
        role_name=user.role.name if user.role else None,
        permissions=sorted(permission.code for permission in user.role.permissions)
        if user.role
        else [],
    )


async def find_active_users_by_email(
    session: AsyncSession,
    email: str,
    company_id: int | None = None,
) -> list[AuthenticatedUser]:
    """Login (passo 1, antes de saber a empresa) precisa achar a quais empresas um
    e-mail pertence — cross-tenant por natureza, o que sustenta o fluxo
    `422 multi_tenant`. Isso não dá pra fazer com o GUC de RLS de uma role
    restrita (não existe um único `company_id` pra setar antes de saber a
    resposta), então passa pela function `SECURITY DEFINER`
    `find_login_candidates` (migration `20260831_0071`) em vez de um SELECT
    direto em `users`.

    A function já devolve nome da empresa, role e permissões prontos (não só a
    linha de `users`): um `selectinload(Role)` feito depois pela ORM seria uma
    query separada, fora do bypass da function e sem um único `company_id` pra
    escopar via RLS (o e-mail pode casar com usuários de mais de uma empresa) —
    ver docstring da migration.
    """
    rows = (
        (
            await session.execute(
                text("SELECT * FROM find_login_candidates(:email, :company_id)").bindparams(
                    bindparam("email", type_=String),
                    bindparam("company_id", type_=Integer),
                ),
                {"email": email.lower(), "company_id": company_id},
            )
        )
        .mappings()
        .all()
    )
    return [
        AuthenticatedUser(
            id=row["id"],
            name=row["name"],
            email=row["email"],
            phone=row["phone"],
            password_hash=row["password"],
            company_id=row["company_id"],
            company_name=row["company_name"],
            role_id=row["role_id"],
            role_name=row["role_name"],
            permissions=sorted(row["permissions"] or []),
        )
        for row in rows
    ]


async def find_active_user_by_id(
    session: AsyncSession,
    user_id: int,
    company_id: int,
) -> AuthenticatedUser | None:
    query = (
        select(User)
        .join(Company)
        .options(
            selectinload(User.company),
            selectinload(User.role).selectinload(Role.permissions),
        )
        .where(
            User.id == user_id,
            User.company_id == company_id,
            User.active.is_(True),
            User.deleted_at.is_(None),
            Company.status == "active",
            Company.deleted_at.is_(None),
        )
    )
    user = (await session.execute(query)).scalar_one_or_none()
    return map_user(user) if user else None
