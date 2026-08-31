from collections.abc import AsyncIterator

from fastapi import HTTPException
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import PlatformSessionLocal, SessionLocal


async def require_session() -> AsyncIterator[AsyncSession]:
    if SessionLocal is None:
        raise HTTPException(
            status_code=503,
            detail={"code": "database_unavailable", "message": "Banco não configurado"},
        )
    async with SessionLocal() as session:
        try:
            yield session
        except Exception:
            await session.rollback()
            raise
        finally:
            try:
                await session.execute(text("RESET app.current_company_id"))
            except Exception:
                await session.rollback()


async def require_platform_session() -> AsyncIterator[AsyncSession]:
    """Equivalente a `require_session`, mas na engine/role de plataforma
    (`registro_platform`, BYPASSRLS) — ver app/core/database.py. Usada só pelas
    rotas `/platform/*`, que leem/escrevem entre tenants por natureza. Sem
    `RESET app.current_company_id` no `finally`: essa role ignora RLS
    independente do GUC, então não há estado de tenant pra vazar entre reuses
    da connection pool."""
    if PlatformSessionLocal is None:
        raise HTTPException(
            status_code=503,
            detail={"code": "database_unavailable", "message": "Banco não configurado"},
        )
    async with PlatformSessionLocal() as session:
        try:
            yield session
        except Exception:
            await session.rollback()
            raise
