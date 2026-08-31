from collections.abc import AsyncIterator

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.core.config import get_settings
from app.models.base import Base

settings = get_settings()

engine = (
    create_async_engine(
        settings.database_url,
        echo=settings.database_echo,
        pool_pre_ping=True,
        pool_recycle=1800,
    )
    if settings.database_url
    else None
)

SessionLocal = async_sessionmaker(engine, expire_on_commit=False) if engine else None

# Rotas `/platform/*` leem/escrevem entre tenants por natureza (billing,
# assinaturas, métricas de todas as empresas) — incompatível com o GUC de
# tenant único que a role restrita de `engine` (acima) exige. Usa uma engine e
# uma role (`registro_platform`, BYPASSRLS) separadas; sem
# `database_platform_url` configurada, cai para a mesma engine/role de sempre
# (comportamento anterior, uma role só). Ver migration `20260831_0070` e
# app/core/dependencies.py::require_platform_session.
_platform_database_url = settings.database_platform_url or settings.database_url
platform_engine = (
    create_async_engine(
        _platform_database_url,
        echo=settings.database_echo,
        pool_pre_ping=True,
        pool_recycle=1800,
    )
    if _platform_database_url
    else None
)

PlatformSessionLocal = (
    async_sessionmaker(platform_engine, expire_on_commit=False) if platform_engine else None
)

# Scripts administrativos rodados manualmente (app/seed.py,
# app/backfill_default_shifts.py) criam Company/User/Role/Subscription pra
# múltiplos tenants de uma vez, sem GUC de tenant nenhum — mesma natureza da
# role de migration (dona das tabelas, roda `alembic upgrade head`), não da
# role restrita de runtime. Sem `database_migration_url` configurada, cai pra
# `database_url` (comportamento anterior, uma role só).
_migration_database_url = settings.database_migration_url or settings.database_url
migration_engine = (
    create_async_engine(
        _migration_database_url,
        echo=settings.database_echo,
        pool_pre_ping=True,
        pool_recycle=1800,
    )
    if _migration_database_url
    else None
)

MigrationSessionLocal = (
    async_sessionmaker(migration_engine, expire_on_commit=False) if migration_engine else None
)

__all__ = [
    "Base",
    "MigrationSessionLocal",
    "PlatformSessionLocal",
    "SessionLocal",
    "engine",
    "get_session",
    "migration_engine",
    "platform_engine",
]


async def get_session() -> AsyncIterator[AsyncSession]:
    if SessionLocal is None:
        raise RuntimeError("DATABASE_URL não configurada")
    async with SessionLocal() as session:
        yield session
