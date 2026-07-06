from typing import Annotated

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import require_session
from app.core.permissions import require_permission
from app.domain.auth.repository import AuthenticatedUser
from app.domain.reports.schemas import FiscalRequestSlaReport, OccurrenceReport
from app.domain.reports.service import build_fiscal_sla_report, build_occurrences_report

router = APIRouter(prefix="/reports", tags=["reports"])


@router.get("/occurrences", response_model=OccurrenceReport)
async def occurrences_report_endpoint(
    user: Annotated[AuthenticatedUser, require_permission("report.view")],
    session: Annotated[AsyncSession, Depends(require_session)],
    date_from: Annotated[str | None, Query()] = None,
    date_to: Annotated[str | None, Query()] = None,
) -> OccurrenceReport:
    data = await build_occurrences_report(session, user.company_id, date_from, date_to)
    return OccurrenceReport(**data)


@router.get("/fiscal-requests-sla", response_model=FiscalRequestSlaReport)
async def fiscal_requests_sla_report_endpoint(
    user: Annotated[AuthenticatedUser, require_permission("report.view")],
    session: Annotated[AsyncSession, Depends(require_session)],
    date_from: Annotated[str | None, Query()] = None,
    date_to: Annotated[str | None, Query()] = None,
) -> FiscalRequestSlaReport:
    data = await build_fiscal_sla_report(session, user.company_id, date_from, date_to)
    return FiscalRequestSlaReport(**data)
