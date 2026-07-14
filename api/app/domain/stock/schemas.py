from datetime import datetime

from pydantic import BaseModel


class StockItemCreate(BaseModel):
    name: str
    category: str | None = None
    unit: str = "un"
    min_quantity: int = 0
    current_quantity: int = 0
    location_id: int | None = None


class StockItemUpdate(BaseModel):
    name: str | None = None
    category: str | None = None
    unit: str | None = None
    min_quantity: int | None = None
    location_id: int | None = None


class StockItemOut(BaseModel):
    id: int
    name: str
    category: str | None
    unit: str
    min_quantity: int
    current_quantity: int
    location_id: int | None
    location_name: str | None = None
    below_min: bool = False
    created_at: datetime | None
    updated_at: datetime | None


class StockItemList(BaseModel):
    items: list[StockItemOut]
    total: int
    page: int
    page_size: int


class MovementCreate(BaseModel):
    item_id: int
    movement_type: str
    quantity: int
    reason: str | None = None
    work_order_id: int | None = None


class MovementOut(BaseModel):
    id: int
    item_id: int
    item_name: str | None = None
    movement_type: str
    quantity: int
    reason: str | None
    work_order_id: int | None
    user_id: int
    user_name: str | None = None
    created_at: datetime | None


class MovementList(BaseModel):
    items: list[MovementOut]
    total: int
    page: int
    page_size: int
