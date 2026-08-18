"""Upsert genérico usado por integrador de dado externo (hoje só o sync erpsolid ->
GEOP) que dedupla por `(company_id, import_source, external_id)` — mesmo índice
único parcial usado do lado erpsolid pra tudo que chega do GEOP (Supplier/
CostCenter/Employee/Payable lá, `services/external_import.py::upsert_by_external_id`
naquele repo). Portado aqui pro sentido contrário, mesmo contrato."""

from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession


async def upsert_by_external_id(
    session: AsyncSession, model: Any, company_id: int, import_source: str, rows: list[dict]
) -> dict[str, int]:
    """`rows` já deve trazer `import_source` no dict (mesmo valor do parâmetro) —
    conferido aqui só como salvaguarda. Retorna `external_id -> id` local."""
    external_ids = [r["external_id"] for r in rows if r.get("external_id")]
    existing_by_external: dict[str, Any] = {}
    if external_ids:
        result = await session.execute(
            select(model).where(
                model.company_id == company_id,
                model.import_source == import_source,
                model.external_id.in_(external_ids),
            )
        )
        existing_by_external = {obj.external_id: obj for obj in result.scalars().all()}

    id_map: dict[str, int] = {}
    for row in rows:
        external_id = row.get("external_id")
        if not external_id:
            continue
        obj = existing_by_external.get(external_id)
        if obj:
            for key, value in row.items():
                setattr(obj, key, value)
        else:
            obj = model(company_id=company_id, **row)
            session.add(obj)
            await session.flush()
        id_map[external_id] = obj.id
    return id_map
