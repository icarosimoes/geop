from datetime import datetime
from typing import NamedTuple

from sqlalchemy import String, cast, func, literal_column, select, union_all
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.audit import compute_diff, record_event
from app.models import Function, Location, Sector


class RegistryRow(NamedTuple):
    id: int
    name: str
    category: str
    updated_at: datetime | None


MODELS = {"Setor": Sector, "Local": Location, "Função": Function}


async def list_registries(
    session: AsyncSession,
    company_id: int,
    page: int,
    page_size: int,
    search: str | None = None,
    category: str | None = None,
) -> tuple[list[RegistryRow], int]:
    target_models = {category: MODELS[category]} if category and category in MODELS else MODELS

    if len(target_models) == 1:
        label, model = next(iter(target_models.items()))
        filters = [model.company_id == company_id, model.deleted_at.is_(None)]
        if search:
            filters.append(model.name.ilike(f"%{search.strip()}%"))
        total = (
            await session.scalar(
                select(func.count(model.id)).where(*filters),
            )
            or 0
        )
        columns = [
            model.id,
            model.name,
            cast(literal_column(f"'{label}'"), String).label("category"),
            model.updated_at,
        ]
        if model is Location:
            columns += [model.latitude, model.longitude, model.geofence_radius_m]
        rows = (
            await session.execute(
                select(*columns)
                .where(*filters)
                .order_by(model.name)
                .offset((page - 1) * page_size)
                .limit(page_size)
            )
        ).all()
        return rows, total

    queries = []
    for label, model in target_models.items():
        q = select(
            model.id,
            model.name,
            cast(literal_column(f"'{label}'"), String).label("category"),
            model.updated_at,
        ).where(model.company_id == company_id, model.deleted_at.is_(None))
        if search:
            q = q.where(model.name.ilike(f"%{search.strip()}%"))
        queries.append(q)

    combined = union_all(*queries).subquery()
    total = (
        await session.scalar(
            select(func.count()).select_from(combined),
        )
        or 0
    )
    rows = (
        await session.execute(
            select(combined)
            .order_by(combined.c.category, combined.c.name)
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
    ).all()
    return rows, total


async def export_registries(
    session: AsyncSession,
    company_id: int,
    search: str | None = None,
    category: str | None = None,
) -> list[RegistryRow]:
    from app.core.export import MAX_EXPORT_ROWS

    target_models = {category: MODELS[category]} if category and category in MODELS else MODELS
    queries = []
    for label, model in target_models.items():
        q = select(
            model.id,
            model.name,
            cast(literal_column(f"'{label}'"), String).label("category"),
            model.updated_at,
        ).where(model.company_id == company_id, model.deleted_at.is_(None))
        if search:
            q = q.where(model.name.ilike(f"%{search.strip()}%"))
        queries.append(q)

    combined = union_all(*queries).subquery()
    rows = (
        await session.execute(
            select(combined).order_by(combined.c.category, combined.c.name).limit(MAX_EXPORT_ROWS)
        )
    ).all()
    return rows


async def list_options(
    session: AsyncSession,
    company_id: int,
    category: str,
) -> list:
    model = MODELS.get(category)
    if model is None:
        return []
    rows = (
        await session.execute(
            select(model.id, model.name)
            .where(model.company_id == company_id, model.deleted_at.is_(None))
            .order_by(model.name)
        )
    ).all()
    return [{"id": r.id, "name": r.name} for r in rows]


async def create_registry(
    session: AsyncSession,
    company_id: int,
    user_id: int,
    name: str,
    category: str,
) -> tuple | None:
    model = MODELS.get(category)
    if model is None:
        return None
    record = model(company_id=company_id, name=name)
    session.add(record)
    await session.flush()
    await record_event(
        session,
        company_id=company_id,
        user_id=user_id,
        entity_type="registry",
        entity_id=record.id,
        event_type="create",
    )
    await session.commit()
    await session.refresh(record)
    return record


async def update_registry(
    session: AsyncSession,
    company_id: int,
    user_id: int,
    registry_id: int,
    category: str,
    name: str | None,
    latitude: float | None = None,
    longitude: float | None = None,
    geofence_radius_m: int | None = None,
):
    model = MODELS.get(category)
    if model is None:
        return "invalid_category"
    record = await session.scalar(
        select(model).where(
            model.id == registry_id,
            model.company_id == company_id,
            model.deleted_at.is_(None),
        )
    )
    if record is None:
        return None

    fields = ["name"]
    if model is Location:
        fields += ["latitude", "longitude", "geofence_radius_m"]
    before = {field: getattr(record, field) for field in fields}

    if name is not None:
        record.name = name
    if model is Location:
        if latitude is not None:
            record.latitude = latitude
        if longitude is not None:
            record.longitude = longitude
        if geofence_radius_m is not None:
            record.geofence_radius_m = geofence_radius_m

    after = {field: getattr(record, field) for field in fields}
    await record_event(
        session,
        company_id=company_id,
        user_id=user_id,
        entity_type="registry",
        entity_id=record.id,
        event_type="update",
        diff=compute_diff(before, after),
    )
    await session.commit()
    await session.refresh(record)
    return record


async def delete_registry(
    session: AsyncSession,
    company_id: int,
    user_id: int,
    registry_id: int,
    category: str,
) -> str | bool:
    model = MODELS.get(category)
    if model is None:
        return "invalid_category"
    record = await session.scalar(
        select(model).where(
            model.id == registry_id,
            model.company_id == company_id,
            model.deleted_at.is_(None),
        )
    )
    if record is None:
        return False
    record.deleted_at = datetime.now()
    await record_event(
        session,
        company_id=company_id,
        user_id=user_id,
        entity_type="registry",
        entity_id=record.id,
        event_type="delete",
    )
    await session.commit()
    return True
