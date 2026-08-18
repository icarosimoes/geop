from typing import Annotated

import structlog
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import require_session
from app.core.permissions import require_permission
from app.core.sla import compute_sla_status
from app.domain.auth.repository import AuthenticatedUser
from app.domain.fiscal_requests.schemas import (
    FiscalRequestListResponse,
    FiscalRequestSummary,
    FiscalRequestUpdate,
    FiscalRequestUserCreate,
)
from app.domain.fiscal_requests.service import (
    create_fiscal_request,
    delete_fiscal_request,
    list_fiscal_requests,
    update_fiscal_request,
)

logger = structlog.get_logger()

router = APIRouter(tags=["fiscal-requests"])


def _to_summary(record) -> FiscalRequestSummary:
    return FiscalRequestSummary(
        id=record.id,
        protocol=record.protocol,
        request_type=record.request_type,
        title=record.title,
        apartment=record.apartment,
        requester=record.requester,
        description=record.description,
        reservation_number=record.reservation_number,
        sla_deadline=record.sla_deadline,
        sla_status=compute_sla_status(
            record.sla_deadline, record.status, record.sla_paused_at, record.sla_paused_seconds
        ),
        status=record.status,
        payload=record.payload,
        created_at=record.created_at,
        updated_at=record.updated_at,
    )


@router.get("/fiscal-requests", response_model=FiscalRequestListResponse)
async def list_fiscal_requests_endpoint(
    user: Annotated[AuthenticatedUser, require_permission("fiscal_request.view")],
    session: Annotated[AsyncSession, Depends(require_session)],
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=100)] = 20,
    search: str | None = None,
) -> FiscalRequestListResponse:
    records, total = await list_fiscal_requests(session, user.company_id, page, page_size, search)
    return FiscalRequestListResponse(
        items=[_to_summary(item) for item in records],
        total=total,
        page=page,
        page_size=page_size,
    )


@router.post("/fiscal-requests", response_model=FiscalRequestSummary, status_code=201)
async def create_fiscal_request_endpoint(
    body: FiscalRequestUserCreate,
    user: Annotated[AuthenticatedUser, require_permission("fiscal_request.create")],
    session: Annotated[AsyncSession, Depends(require_session)],
) -> FiscalRequestSummary:
    record = await create_fiscal_request(
        session,
        user.company_id,
        user.id,
        request_type=body.request_type,
        title=body.title,
        apartment=body.apartment,
        requester=body.requester,
        description=body.description,
        status=body.status,
        payload=body.payload,
    )
    return _to_summary(record)


@router.patch("/fiscal-requests/{request_id}", response_model=FiscalRequestSummary)
async def update_fiscal_request_endpoint(
    request_id: int,
    body: FiscalRequestUpdate,
    user: Annotated[AuthenticatedUser, require_permission("fiscal_request.edit")],
    session: Annotated[AsyncSession, Depends(require_session)],
) -> FiscalRequestSummary:
    updates = body.model_dump(exclude_none=True)
    record = await update_fiscal_request(session, user.company_id, user.id, request_id, updates)
    if record is None:
        raise HTTPException(status_code=404, detail={"code": "not_found"})
    return _to_summary(record)


@router.delete("/fiscal-requests/{request_id}", status_code=204)
async def delete_fiscal_request_endpoint(
    request_id: int,
    user: Annotated[AuthenticatedUser, require_permission("fiscal_request.delete")],
    session: Annotated[AsyncSession, Depends(require_session)],
) -> None:
    deleted = await delete_fiscal_request(session, user.company_id, user.id, request_id)
    if not deleted:
        raise HTTPException(status_code=404, detail={"code": "not_found"})
