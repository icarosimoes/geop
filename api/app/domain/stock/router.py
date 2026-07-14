from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import require_session
from app.core.permissions import require_permission
from app.domain.auth.repository import AuthenticatedUser
from app.domain.stock import schemas
from app.domain.stock.service import (
    create_item,
    create_movement,
    delete_item,
    get_item,
    list_items,
    list_movements,
    update_item,
)

router = APIRouter(prefix="/stock", tags=["stock"])


def _item_to_out(row) -> schemas.StockItemOut:
    item = row[0]
    return schemas.StockItemOut(
        id=item.id,
        name=item.name,
        category=item.category,
        unit=item.unit,
        min_quantity=item.min_quantity,
        current_quantity=item.current_quantity,
        location_id=item.location_id,
        location_name=row.location_name,
        below_min=item.current_quantity < item.min_quantity,
        created_at=item.created_at,
        updated_at=item.updated_at,
    )


def _mov_to_out(row) -> schemas.MovementOut:
    mov = row[0]
    return schemas.MovementOut(
        id=mov.id,
        item_id=mov.item_id,
        item_name=row.item_name,
        movement_type=mov.movement_type,
        quantity=mov.quantity,
        reason=mov.reason,
        work_order_id=mov.work_order_id,
        user_id=mov.user_id,
        user_name=row.user_name,
        created_at=mov.created_at,
    )


@router.get("/items", response_model=schemas.StockItemList)
async def list_stock_items(
    user: Annotated[AuthenticatedUser, require_permission("stock.view")],
    session: Annotated[AsyncSession, Depends(require_session)],
    page: int = 1,
    page_size: int = 25,
    search: str | None = None,
    below_min: bool = False,
):
    rows, total = await list_items(
        session,
        user.company_id,
        page,
        page_size,
        search,
        below_min,
    )
    return schemas.StockItemList(
        items=[_item_to_out(r) for r in rows],
        total=total,
        page=page,
        page_size=page_size,
    )


@router.get("/items/{item_id}", response_model=schemas.StockItemOut)
async def get_stock_item(
    item_id: int,
    user: Annotated[AuthenticatedUser, require_permission("stock.view")],
    session: Annotated[AsyncSession, Depends(require_session)],
):
    row = await get_item(session, user.company_id, item_id)
    if row is None:
        raise HTTPException(404, detail="Item não encontrado")
    return _item_to_out(row)


@router.post("/items", response_model=schemas.StockItemOut, status_code=201)
async def create_stock_item(
    body: schemas.StockItemCreate,
    user: Annotated[AuthenticatedUser, require_permission("stock.create")],
    session: Annotated[AsyncSession, Depends(require_session)],
):
    row = await create_item(
        session,
        user.company_id,
        user.id,
        **body.model_dump(),
    )
    return _item_to_out(row)


@router.patch("/items/{item_id}", response_model=schemas.StockItemOut)
async def update_stock_item(
    item_id: int,
    body: schemas.StockItemUpdate,
    user: Annotated[AuthenticatedUser, require_permission("stock.edit")],
    session: Annotated[AsyncSession, Depends(require_session)],
):
    updates = body.model_dump(exclude_unset=True)
    if not updates:
        raise HTTPException(422, detail="Nenhum campo alterado")
    row = await update_item(
        session,
        user.company_id,
        user.id,
        item_id,
        updates,
    )
    if row is None:
        raise HTTPException(404, detail="Item não encontrado")
    return _item_to_out(row)


@router.delete("/items/{item_id}", status_code=204)
async def delete_stock_item(
    item_id: int,
    user: Annotated[AuthenticatedUser, require_permission("stock.delete")],
    session: Annotated[AsyncSession, Depends(require_session)],
):
    if not await delete_item(
        session,
        user.company_id,
        user.id,
        item_id,
    ):
        raise HTTPException(404, detail="Item não encontrado")


@router.post("/movements", response_model=schemas.MovementOut, status_code=201)
async def create_stock_movement(
    body: schemas.MovementCreate,
    user: Annotated[AuthenticatedUser, require_permission("stock.edit")],
    session: Annotated[AsyncSession, Depends(require_session)],
):
    try:
        data = await create_movement(
            session,
            user.company_id,
            user.id,
            **body.model_dump(),
        )
    except ValueError as exc:
        raise HTTPException(422, detail=str(exc)) from None
    mov = data["movement"]
    return schemas.MovementOut(
        id=mov.id,
        item_id=mov.item_id,
        item_name=data["item_name"],
        movement_type=mov.movement_type,
        quantity=mov.quantity,
        reason=mov.reason,
        work_order_id=mov.work_order_id,
        user_id=mov.user_id,
        user_name=data["user_name"],
        created_at=mov.created_at,
    )


@router.get("/movements", response_model=schemas.MovementList)
async def list_stock_movements(
    user: Annotated[AuthenticatedUser, require_permission("stock.view")],
    session: Annotated[AsyncSession, Depends(require_session)],
    page: int = 1,
    page_size: int = 25,
    item_id: int | None = None,
):
    rows, total = await list_movements(
        session,
        user.company_id,
        page,
        page_size,
        item_id,
    )
    return schemas.MovementList(
        items=[_mov_to_out(r) for r in rows],
        total=total,
        page=page,
        page_size=page_size,
    )
