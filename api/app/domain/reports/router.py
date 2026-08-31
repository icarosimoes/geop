from typing import Annotated

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import require_session
from app.core.permissions import require_permission
from app.domain.auth.repository import AuthenticatedUser
from app.domain.reports.schemas import WorkOrderReport
from app.domain.reports.service import build_work_orders_report

router = APIRouter(prefix="/reports", tags=["reports"])


@router.get("/work-orders", response_model=WorkOrderReport)
async def work_orders_report_endpoint(
    user: Annotated[AuthenticatedUser, require_permission("report.view")],
    session: Annotated[AsyncSession, Depends(require_session)],
    date_from: Annotated[str | None, Query()] = None,
    date_to: Annotated[str | None, Query()] = None,
) -> WorkOrderReport:
    data = await build_work_orders_report(session, user.company_id, date_from, date_to)
    return WorkOrderReport(**data)
