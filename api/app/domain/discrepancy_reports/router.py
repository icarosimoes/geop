from datetime import date
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import require_session
from app.core.permissions import require_permission
from app.domain.auth.repository import AuthenticatedUser
from app.domain.discrepancy_reports import service
from app.domain.discrepancy_reports.schemas import (
    DiscrepancyCodeCount,
    DiscrepancyEntryOut,
    DiscrepancyReportCreate,
    DiscrepancyReportDetail,
    DiscrepancyReportListResponse,
    DiscrepancyReportSummary,
    DiscrepancyReportUpdate,
    DiscrepancyStatus,
)

router = APIRouter(prefix="/discrepancy-reports", tags=["discrepancy-reports"])


def _summary(row: service.DiscrepancyReportRow) -> DiscrepancyReportSummary:
    report = row.report
    return DiscrepancyReportSummary(
        id=report.id,
        report_date=report.report_date,
        status=report.status,
        prepared_by_user_id=report.prepared_by_user_id,
        prepared_by_name=row.prepared_by_name,
        entry_count=row.entry_count,
        discrepancy_count=row.discrepancy_count,
        updated_at=report.updated_at,
    )


def _detail(detail: service.DiscrepancyReportDetail) -> DiscrepancyReportDetail:
    report = detail.report
    entries = [
        DiscrepancyEntryOut(
            id=entry.id,
            location_id=entry.location_id,
            location_name=location_name,
            first_code=entry.first_code,
            second_code=entry.second_code,
            notes=entry.notes,
        )
        for entry, location_name in detail.entries
    ]
    return DiscrepancyReportDetail(
        id=report.id,
        report_date=report.report_date,
        status=report.status,
        prepared_by_user_id=report.prepared_by_user_id,
        prepared_by_name=detail.prepared_by_name,
        checked_by_user_id=report.checked_by_user_id,
        checked_by_name=detail.checked_by_name,
        received_by_user_id=report.received_by_user_id,
        received_by_name=detail.received_by_name,
        observations=report.observations,
        entry_count=len(entries),
        discrepancy_count=sum(item.first_code != item.second_code for item in entries),
        entries=entries,
        code_summary=[
            DiscrepancyCodeCount(code=code, count=count)
            for code, count in sorted(service.code_summary(detail.entries).items())
        ],
        updated_at=report.updated_at,
        created_at=report.created_at,
    )


@router.get("", response_model=DiscrepancyReportListResponse)
async def list_discrepancy_reports(
    user: Annotated[AuthenticatedUser, require_permission("discrepancy_report.view")],
    session: Annotated[AsyncSession, Depends(require_session)],
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=100)] = 20,
    date_from: date | None = None,
    date_to: date | None = None,
    status: DiscrepancyStatus | None = None,
) -> DiscrepancyReportListResponse:
    rows, total = await service.list_reports(
        session, user.company_id, page, page_size, date_from, date_to, status
    )
    return DiscrepancyReportListResponse(
        items=[_summary(row) for row in rows],
        total=total,
        page=page,
        page_size=page_size,
    )


@router.get("/{report_id}", response_model=DiscrepancyReportDetail)
async def get_discrepancy_report(
    report_id: int,
    user: Annotated[AuthenticatedUser, require_permission("discrepancy_report.view")],
    session: Annotated[AsyncSession, Depends(require_session)],
) -> DiscrepancyReportDetail:
    detail = await service.get_report(session, user.company_id, report_id)
    if detail is None:
        raise HTTPException(status_code=404, detail={"code": "not_found"})
    return _detail(detail)


@router.post("", response_model=DiscrepancyReportDetail, status_code=201)
async def create_discrepancy_report(
    payload: DiscrepancyReportCreate,
    user: Annotated[AuthenticatedUser, require_permission("discrepancy_report.create")],
    session: Annotated[AsyncSession, Depends(require_session)],
) -> DiscrepancyReportDetail:
    return _detail(
        await service.create_report(
            session,
            user.company_id,
            user.id,
            payload.model_dump(),
        )
    )


@router.patch("/{report_id}", response_model=DiscrepancyReportDetail)
async def update_discrepancy_report(
    report_id: int,
    payload: DiscrepancyReportUpdate,
    user: Annotated[AuthenticatedUser, require_permission("discrepancy_report.edit")],
    session: Annotated[AsyncSession, Depends(require_session)],
) -> DiscrepancyReportDetail:
    updates = payload.model_dump(exclude_unset=True)
    if not updates:
        raise HTTPException(status_code=422, detail={"code": "no_fields"})
    return _detail(
        await service.update_report(session, user.company_id, user.id, report_id, updates)
    )


@router.get("/{report_id}/pdf")
async def discrepancy_report_pdf(
    report_id: int,
    user: Annotated[AuthenticatedUser, require_permission("discrepancy_report.view")],
    session: Annotated[AsyncSession, Depends(require_session)],
) -> StreamingResponse:
    detail = await service.get_report(session, user.company_id, report_id)
    if detail is None:
        raise HTTPException(status_code=404, detail={"code": "not_found"})

    from app.domain.discrepancy_reports.pdf import generate_discrepancy_report_pdf

    buf = generate_discrepancy_report_pdf(
        company_name=user.company_name,
        detail=detail,
        checked_by_name=detail.checked_by_name,
        received_by_name=detail.received_by_name,
    )
    filename = f"conferencia_discrepancias_{report_id}.pdf"
    return StreamingResponse(
        buf,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.delete("/{report_id}", status_code=204)
async def delete_discrepancy_report(
    report_id: int,
    user: Annotated[AuthenticatedUser, require_permission("discrepancy_report.delete")],
    session: Annotated[AsyncSession, Depends(require_session)],
) -> None:
    deleted = await service.delete_report(session, user.company_id, user.id, report_id)
    if not deleted:
        raise HTTPException(status_code=404, detail={"code": "not_found"})
