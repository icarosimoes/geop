"""Cadastra os turnos padrão (Manhã, Tarde, Noite, Comercial, 12x36) em toda
empresa que ainda não tenha nenhum turno cadastrado.

Uso:
    .venv/bin/python -m app.backfill_default_shifts
"""

import asyncio

from sqlalchemy import select

from app.core.database import MigrationSessionLocal
from app.domain.timeclock.service import ensure_default_shifts
from app.models import Company


async def backfill() -> None:
    if MigrationSessionLocal is None:
        raise RuntimeError("DATABASE_URL não configurada")
    async with MigrationSessionLocal() as session:
        companies = (
            (await session.execute(select(Company).where(Company.deleted_at.is_(None))))
            .scalars()
            .all()
        )
        for company in companies:
            created = await ensure_default_shifts(session, company.id)
            if created:
                print(f"[{company.slug}] {len(created)} turnos criados")
            else:
                print(f"[{company.slug}] já possui turnos, ignorado")
        await session.commit()


if __name__ == "__main__":
    asyncio.run(backfill())
