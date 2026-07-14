from datetime import datetime
from typing import NamedTuple

from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.audit import compute_diff, record_event
from app.models import Location, StockItem, StockMovement, User
from app.models.operations import MOVEMENT_TYPES


class StockItemRow(NamedTuple):
    item: StockItem
    location_name: str | None


class StockMovementRow(NamedTuple):
    movement: StockMovement
    item_name: str
    user_name: str


async def list_items(
    session: AsyncSession,
    company_id: int,
    page: int,
    page_size: int,
    search: str | None = None,
    below_min_only: bool = False,
) -> tuple[list[StockItemRow], int]:
    filters = [
        StockItem.company_id == company_id,
        StockItem.deleted_at.is_(None),
    ]
    if search:
        pattern = f"%{search.strip()}%"
        filters.append(or_(StockItem.name.ilike(pattern), StockItem.category.ilike(pattern)))
    if below_min_only:
        filters.append(StockItem.current_quantity < StockItem.min_quantity)

    total = (
        await session.scalar(
            select(func.count(StockItem.id)).where(*filters),
        )
        or 0
    )

    loc = Location.__table__.alias("loc")
    rows = (
        await session.execute(
            select(StockItem, loc.c.name.label("location_name"))
            .outerjoin(loc, loc.c.id == StockItem.location_id)
            .where(*filters)
            .order_by(StockItem.name)
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
    ).all()
    return rows, total


async def get_item(
    session: AsyncSession,
    company_id: int,
    item_id: int,
) -> StockItemRow | None:
    loc = Location.__table__.alias("loc")
    return (
        await session.execute(
            select(StockItem, loc.c.name.label("location_name"))
            .outerjoin(loc, loc.c.id == StockItem.location_id)
            .where(
                StockItem.id == item_id,
                StockItem.company_id == company_id,
                StockItem.deleted_at.is_(None),
            )
        )
    ).first()


async def create_item(
    session: AsyncSession,
    company_id: int,
    user_id: int,
    **fields,
) -> StockItemRow:
    rec = StockItem(company_id=company_id, **fields)
    session.add(rec)
    await session.flush()
    await record_event(
        session,
        company_id=company_id,
        user_id=user_id,
        entity_type="stock_item",
        entity_id=rec.id,
        event_type="create",
    )
    await session.commit()
    await session.refresh(rec)
    return await get_item(session, company_id, rec.id)


async def update_item(
    session: AsyncSession,
    company_id: int,
    user_id: int,
    item_id: int,
    updates: dict,
) -> StockItemRow | None:
    rec = await session.scalar(
        select(StockItem).where(
            StockItem.id == item_id,
            StockItem.company_id == company_id,
            StockItem.deleted_at.is_(None),
        )
    )
    if rec is None:
        return None
    before = {k: str(getattr(rec, k)) for k in updates}
    for field, value in updates.items():
        setattr(rec, field, value)
    diff = compute_diff(before, {k: str(v) for k, v in updates.items()})
    if diff:
        await record_event(
            session,
            company_id=company_id,
            user_id=user_id,
            entity_type="stock_item",
            entity_id=rec.id,
            event_type="update",
            diff=diff,
        )
    await session.commit()
    return await get_item(session, company_id, item_id)


async def delete_item(
    session: AsyncSession,
    company_id: int,
    user_id: int,
    item_id: int,
) -> bool:
    rec = await session.scalar(
        select(StockItem).where(
            StockItem.id == item_id,
            StockItem.company_id == company_id,
            StockItem.deleted_at.is_(None),
        )
    )
    if rec is None:
        return False
    rec.deleted_at = datetime.now()
    await record_event(
        session,
        company_id=company_id,
        user_id=user_id,
        entity_type="stock_item",
        entity_id=rec.id,
        event_type="delete",
    )
    await session.commit()
    return True


async def create_movement(
    session: AsyncSession,
    company_id: int,
    user_id: int,
    *,
    item_id: int,
    movement_type: str,
    quantity: int,
    reason: str | None,
    work_order_id: int | None,
) -> dict:
    if movement_type not in MOVEMENT_TYPES:
        raise ValueError(f"Tipo inválido: {movement_type}")
    if quantity <= 0:
        raise ValueError("Quantidade deve ser positiva")

    item = await session.scalar(
        select(StockItem).where(
            StockItem.id == item_id,
            StockItem.company_id == company_id,
            StockItem.deleted_at.is_(None),
        )
    )
    if item is None:
        raise ValueError("Item não encontrado")

    if movement_type == "entrada":
        item.current_quantity += quantity
    elif movement_type == "saida":
        if item.current_quantity < quantity:
            raise ValueError(
                f"Estoque insuficiente ({item.current_quantity} disponível)",
            )
        item.current_quantity -= quantity
    else:
        item.current_quantity = quantity

    mov = StockMovement(
        company_id=company_id,
        item_id=item_id,
        movement_type=movement_type,
        quantity=quantity,
        reason=reason,
        work_order_id=work_order_id,
        user_id=user_id,
    )
    session.add(mov)
    await session.flush()
    await record_event(
        session,
        company_id=company_id,
        user_id=user_id,
        entity_type="stock_item",
        entity_id=item_id,
        event_type="update",
        diff={"movimento": movement_type, "quantidade": str(quantity)},
    )
    await session.commit()
    await session.refresh(mov)

    user_name = await session.scalar(
        select(User.name).where(User.id == user_id),
    )
    return {
        "movement": mov,
        "item_name": item.name,
        "user_name": user_name,
    }


async def list_movements(
    session: AsyncSession,
    company_id: int,
    page: int,
    page_size: int,
    item_id: int | None = None,
) -> tuple[list[StockMovementRow], int]:
    filters = [StockMovement.company_id == company_id]
    if item_id:
        filters.append(StockMovement.item_id == item_id)

    total = (
        await session.scalar(
            select(func.count(StockMovement.id)).where(*filters),
        )
        or 0
    )

    rows = (
        await session.execute(
            select(
                StockMovement,
                StockItem.name.label("item_name"),
                User.name.label("user_name"),
            )
            .join(StockItem, StockItem.id == StockMovement.item_id)
            .join(User, User.id == StockMovement.user_id)
            .where(*filters)
            .order_by(StockMovement.created_at.desc())
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
    ).all()
    return rows, total
