import asyncio
import os
from datetime import UTC, datetime, timedelta

import bcrypt
from sqlalchemy import select

from app.core.config import get_settings
from app.core.database import SessionLocal
from app.models import Company, Permission, Plan, PlatformUser, Role, Subscription, User


def password_hash(value: str) -> str:
    return bcrypt.hashpw(value.encode(), bcrypt.gensalt()).decode()


async def seed() -> None:
    settings = get_settings()
    if SessionLocal is None:
        raise RuntimeError("DATABASE_URL não configurada")
    default_password = os.getenv("SEED_DEFAULT_PASSWORD", "Registro@123")
    platform_password = os.getenv("PLATFORM_ADMIN_PASSWORD", "RegistroAdmin@123")
    if settings.environment == "production" and (
        "SEED_DEFAULT_PASSWORD" not in os.environ or "PLATFORM_ADMIN_PASSWORD" not in os.environ
    ):
        raise RuntimeError("senhas de seed devem ser explícitas em produção")

    async with SessionLocal() as session:
        if await session.scalar(select(Company.id).limit(1)):
            return

        wildcard = await session.scalar(select(Permission).filter_by(code="*"))
        if not wildcard:
            wildcard = Permission(code="*", name="Acesso total (administrador)", module="system")
            session.add(wildcard)
            await session.flush()
        else:
            wildcard = await session.merge(wildcard)

        plan = Plan(
            code="professional",
            name="Profissional",
            price_cents=14990,
            features={"occurrences": True, "inspections": True, "reports": True},
            limits={"max_users": 25},
            active=True,
            public=True,
        )
        companies = [
            Company(name="Empresa Demonstração", slug="empresa-demo", email="demo@registro.local"),
            Company(name="Filial Teste", slug="filial-teste", email="filial@registro.local"),
        ]
        session.add_all([plan, *companies])
        await session.flush()

        for index, company in enumerate(companies):
            role = Role(company_id=company.id, code="admin", name="Administrador")
            role.permissions = [wildcard]
            session.add(role)
            await session.flush()
            session.add(
                User(
                    company_id=company.id,
                    role_id=role.id,
                    name="Ícaro Demonstração" if index == 0 else "Ana Filial",
                    email="icaro@registro.local" if index == 0 else "ana@registro.local",
                    password=password_hash(default_password),
                    active=True,
                    email_verified_at=datetime.now(UTC).replace(tzinfo=None),
                )
            )
            session.add(
                Subscription(
                    company_id=company.id,
                    plan_id=plan.id,
                    status="trial",
                    trial_ends_at=(datetime.now(UTC) + timedelta(days=14)).replace(tzinfo=None),
                )
            )

        session.add(
            PlatformUser(
                email="admin@registro.local",
                name="Administrador Registro",
                password_hash=password_hash(platform_password),
                role="super_admin",
                active=True,
            )
        )
        await session.commit()


if __name__ == "__main__":
    asyncio.run(seed())
