from datetime import datetime
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import require_session
from app.core.export import generate_xlsx
from app.core.permissions import require_permission
from app.domain.auth.repository import AuthenticatedUser
from app.domain.registries.service import (
    MODELS,
    create_registry,
    delete_registry,
    export_registries,
    list_options,
    list_registries,
    update_registry,
)

router = APIRouter(prefix="/registries", tags=["registries"])


def _geofence_fields(row: object) -> dict[str, float | int | None]:
    latitude = getattr(row, "latitude", None)
    longitude = getattr(row, "longitude", None)
    return {
        "latitude": float(latitude) if latitude is not None else None,
        "longitude": float(longitude) if longitude is not None else None,
        "geofence_radius_m": getattr(row, "geofence_radius_m", None),
    }


class RegistrySummary(BaseModel):
    id: int
    name: str
    category: str
    updated_at: datetime
    latitude: float | None = None
    longitude: float | None = None
    geofence_radius_m: int | None = None


class RegistryListResponse(BaseModel):
    items: list[RegistrySummary]
    total: int
    page: int
    page_size: int


class RegistryCreate(BaseModel):
    name: str
    category: str


class RegistryUpdate(BaseModel):
    name: str | None = None
    latitude: float | None = None
    longitude: float | None = None
    geofence_radius_m: int | None = None


class RegistryOption(BaseModel):
    id: int
    name: str


@router.get("/options/{category}", response_model=list[RegistryOption])
async def registry_options(
    category: str,
    user: Annotated[AuthenticatedUser, require_permission("registry.view")],
    session: Annotated[AsyncSession, Depends(require_session)],
) -> list[RegistryOption]:
    items = await list_options(session, user.company_id, category)
    return [RegistryOption(**i) for i in items]


@router.get("/export")
async def export_registries_endpoint(
    user: Annotated[AuthenticatedUser, require_permission("registry.view")],
    session: Annotated[AsyncSession, Depends(require_session)],
    search: str | None = None,
    category: str | None = None,
) -> StreamingResponse:
    rows = await export_registries(session, user.company_id, search, category)
    headers = ["ID", "Nome", "Categoria", "Atualizado em"]
    data = [[row.id, row.name, row.category, row.updated_at] for row in rows]
    buf = generate_xlsx(title="Cadastros", headers=headers, rows=data)
    return StreamingResponse(
        buf,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": 'attachment; filename="cadastros.xlsx"'},
    )


@router.get("", response_model=RegistryListResponse)
async def list_registries_endpoint(
    user: Annotated[AuthenticatedUser, require_permission("registry.view")],
    session: Annotated[AsyncSession, Depends(require_session)],
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=100)] = 20,
    search: str | None = None,
    category: str | None = None,
) -> RegistryListResponse:
    rows, total = await list_registries(
        session,
        user.company_id,
        page,
        page_size,
        search,
        category,
    )
    return RegistryListResponse(
        items=[
            RegistrySummary(
                id=row.id,
                name=row.name,
                category=row.category,
                updated_at=row.updated_at,
                **_geofence_fields(row),
            )
            for row in rows
        ],
        total=total,
        page=page,
        page_size=page_size,
    )


@router.post("", response_model=RegistrySummary, status_code=201)
async def create_registry_endpoint(
    body: RegistryCreate,
    user: Annotated[AuthenticatedUser, require_permission("registry.create")],
    session: Annotated[AsyncSession, Depends(require_session)],
) -> RegistrySummary:
    if body.category not in MODELS:
        raise HTTPException(
            status_code=400,
            detail={"code": "invalid_category", "valid": list(MODELS.keys())},
        )
    record = await create_registry(session, user.company_id, user.id, body.name, body.category)
    if record is None:
        raise HTTPException(status_code=400, detail={"code": "invalid_category"})
    return RegistrySummary(
        id=record.id,
        name=record.name,
        category=body.category,
        updated_at=record.updated_at,
    )


@router.patch("/{registry_id}", response_model=RegistrySummary)
async def update_registry_endpoint(
    registry_id: int,
    body: RegistryUpdate,
    category: str = Query(..., description="Setor, Local ou Função"),
    user: Annotated[AuthenticatedUser, require_permission("registry.edit")] = None,
    session: Annotated[AsyncSession, Depends(require_session)] = None,
) -> RegistrySummary:
    result = await update_registry(
        session,
        user.company_id,
        user.id,
        registry_id,
        category,
        body.name,
        body.latitude,
        body.longitude,
        body.geofence_radius_m,
    )
    if result == "invalid_category":
        raise HTTPException(status_code=400, detail={"code": "invalid_category"})
    if result is None:
        raise HTTPException(status_code=404, detail={"code": "not_found"})
    return RegistrySummary(
        id=result.id,
        name=result.name,
        category=category,
        updated_at=result.updated_at,
        **_geofence_fields(result),
    )


@router.delete("/{registry_id}", status_code=204)
async def delete_registry_endpoint(
    registry_id: int,
    category: str = Query(..., description="Setor, Local ou Função"),
    user: Annotated[AuthenticatedUser, require_permission("registry.delete")] = None,
    session: Annotated[AsyncSession, Depends(require_session)] = None,
) -> None:
    result = await delete_registry(session, user.company_id, user.id, registry_id, category)
    if result == "invalid_category":
        raise HTTPException(status_code=400, detail={"code": "invalid_category"})
    if result is False:
        raise HTTPException(status_code=404, detail={"code": "not_found"})
