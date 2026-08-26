"""Portal do Colaborador: ponto, escala e contracheque via app do funcionário.

Autenticado por um token `employee_session` completamente separado do fluxo de
`User`/`current_user` (ver app/domain/timeclock/mobile_auth.py). Nenhuma rota
aqui aceita `access` token de User, e nenhuma rota de `User` aceita este token.
"""

import re
from datetime import date
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings, get_settings
from app.core.dependencies import require_session
from app.core.rate_limit import limiter
from app.core.security import create_employee_session_token
from app.core.storage import download_file
from app.domain.timeclock.mobile_auth import AuthenticatedEmployee, require_employee_session
from app.domain.timeclock.schemas import (
    CalendarEntry,
    EmployeeLoginRequest,
    EmployeePayslipListResponse,
    EmployeePayslipSummary,
    EmployeePinChangeRequest,
    EmployeeSessionResponse,
    EmployeeStatusResponse,
    EmployeeVacationEntitlement,
    HourBankEntrySummary,
    HourBankSummaryResponse,
    MobilePunchRequest,
    MobilePunchResponse,
    PunchAdjustmentCreate,
    PunchAdjustmentSummary,
    VacationRequestCreate,
    VacationRequestSummary,
)
from app.domain.timeclock.service import (
    authenticate_employee,
    cancel_vacation_request,
    create_mobile_punch,
    create_punch_adjustment_request,
    create_vacation_request,
    get_calendar,
    get_employee_credential,
    get_employee_payslip_for_download,
    get_employee_vacation_entitlement,
    get_hour_bank_summary,
    get_next_expected_punch_type,
    list_employee_payslips,
    list_punch_adjustment_requests,
    list_vacation_requests,
    set_employee_pin,
)

_UNSAFE_FILENAME_RE = re.compile(r"[^a-zA-Z0-9_\s\-.\(\)]")

router = APIRouter(prefix="/timeclock/mobile", tags=["timeclock-mobile"])


@router.post("/login", response_model=EmployeeSessionResponse)
@limiter.limit("10/minute")
async def mobile_login(
    request: Request,
    body: EmployeeLoginRequest,
    session: Annotated[AsyncSession, Depends(require_session)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> EmployeeSessionResponse:
    employee, error = await authenticate_employee(
        session,
        company_slug=body.company_slug,
        registration_number=body.registration_number,
        pin=body.pin,
    )
    if error == "locked":
        raise HTTPException(
            status_code=423,
            detail={"code": "locked", "message": "PIN bloqueado temporariamente"},
        )
    if error is not None or employee is None:
        raise HTTPException(
            status_code=401,
            detail={"code": "invalid_credentials", "message": "Matrícula ou PIN inválidos"},
        )

    minutes = 60
    token = create_employee_session_token(
        employee_id=employee.id,
        company_id=employee.company_id,
        secret=settings.jwt_secret,
        minutes=minutes,
    )
    credential = await get_employee_credential(session, employee.company_id, employee.id)
    return EmployeeSessionResponse(
        access_token=token,
        expires_in=minutes * 60,
        must_change_pin=bool(credential and credential.must_change_pin),
        employee_id=employee.id,
        employee_name=employee.name,
    )


@router.post("/pin", status_code=204)
async def mobile_change_pin(
    body: EmployeePinChangeRequest,
    employee: Annotated[AuthenticatedEmployee, Depends(require_employee_session)],
    session: Annotated[AsyncSession, Depends(require_session)],
) -> None:
    ok, error = await set_employee_pin(
        session,
        employee.company_id,
        employee.employee_id,
        old_pin=body.old_pin,
        new_pin=body.new_pin,
    )
    if not ok:
        status_code = 404 if error == "not_found" else 422
        raise HTTPException(status_code=status_code, detail={"code": error})


@router.post("/punch", response_model=MobilePunchResponse, status_code=201)
@limiter.limit("30/minute")
async def mobile_punch(
    request: Request,
    body: MobilePunchRequest,
    employee: Annotated[AuthenticatedEmployee, Depends(require_employee_session)],
    session: Annotated[AsyncSession, Depends(require_session)],
) -> MobilePunchResponse:
    punch, error, distance_m = await create_mobile_punch(
        session,
        employee.company_id,
        employee.employee_id,
        latitude=body.latitude,
        longitude=body.longitude,
    )
    if error == "LOCATION_NOT_CONFIGURED":
        raise HTTPException(
            status_code=422,
            detail={
                "code": "LOCATION_NOT_CONFIGURED",
                "message": "Local de trabalho sem geofencing configurado",
            },
        )
    if error == "OUT_OF_RANGE":
        raise HTTPException(
            status_code=422,
            detail={
                "code": "OUT_OF_RANGE",
                "message": "Fora do raio permitido para bater o ponto",
                "distance_m": round(distance_m, 2) if distance_m is not None else None,
            },
        )
    assert punch is not None
    return MobilePunchResponse(
        id=punch.id,
        punched_at=punch.punched_at,
        punch_type=punch.punch_type,
        status=punch.status,
        distance_m=float(punch.distance_m) if punch.distance_m is not None else None,
    )


@router.get("/status", response_model=EmployeeStatusResponse)
async def mobile_status(
    employee: Annotated[AuthenticatedEmployee, Depends(require_employee_session)],
    session: Annotated[AsyncSession, Depends(require_session)],
) -> EmployeeStatusResponse:
    next_type = await get_next_expected_punch_type(
        session, employee.company_id, employee.employee_id
    )
    return EmployeeStatusResponse(next_punch_type=next_type)


@router.get("/schedule", response_model=list[CalendarEntry])
async def mobile_schedule(
    employee: Annotated[AuthenticatedEmployee, Depends(require_employee_session)],
    session: Annotated[AsyncSession, Depends(require_session)],
    start: date,
    end: date,
) -> list[CalendarEntry]:
    rows = await get_calendar(
        session,
        employee.company_id,
        start,
        end,
        employee_id=employee.employee_id,
    )
    return [
        CalendarEntry(
            date=entry.date,
            employee_id=entry.employee_id,
            employee_name=employee_name,
            shift_id=shift.id if shift else None,
            shift_name=shift.name if shift else None,
            shift_color=shift.color if shift else None,
            start_time=shift.start_time if shift else None,
            end_time=shift.end_time if shift else None,
            source=entry.source,
        )
        for entry, employee_name, shift in rows
    ]


@router.get("/payslips", response_model=EmployeePayslipListResponse)
async def mobile_list_payslips(
    employee: Annotated[AuthenticatedEmployee, Depends(require_employee_session)],
    session: Annotated[AsyncSession, Depends(require_session)],
) -> EmployeePayslipListResponse:
    records = await list_employee_payslips(session, employee.company_id, employee.employee_id)
    return EmployeePayslipListResponse(
        items=[
            EmployeePayslipSummary(
                id=r.id, reference_month=r.reference_month, created_at=r.created_at
            )
            for r in records
        ]
    )


@router.get("/payslips/{payslip_id}/download")
async def mobile_download_payslip(
    payslip_id: int,
    employee: Annotated[AuthenticatedEmployee, Depends(require_employee_session)],
    session: Annotated[AsyncSession, Depends(require_session)],
) -> StreamingResponse:
    payslip = await get_employee_payslip_for_download(
        session, employee.company_id, employee.employee_id, payslip_id
    )
    if payslip is None:
        raise HTTPException(status_code=404, detail={"code": "not_found"})

    from app.domain.attachments.service import get_attachment

    attachment = await get_attachment(session, employee.company_id, payslip.attachment_id)
    if attachment is None:
        raise HTTPException(status_code=404, detail={"code": "not_found"})

    buf, content_type = download_file(attachment.storage_key)
    safe_name = _UNSAFE_FILENAME_RE.sub("_", attachment.filename).strip(". ") or "contracheque.pdf"
    return StreamingResponse(
        buf,
        media_type=content_type,
        headers={
            "Content-Disposition": f'attachment; filename="{safe_name}"',
            "X-Content-Type-Options": "nosniff",
            "Content-Security-Policy": "default-src 'none'; style-src 'unsafe-inline'",
            "X-Frame-Options": "DENY",
            "Cache-Control": "no-store",
        },
    )


@router.get("/hour-bank", response_model=HourBankSummaryResponse)
async def mobile_hour_bank(
    employee: Annotated[AuthenticatedEmployee, Depends(require_employee_session)],
    session: Annotated[AsyncSession, Depends(require_session)],
) -> HourBankSummaryResponse:
    total_balance, entries = await get_hour_bank_summary(
        session, employee.company_id, employee.employee_id
    )
    return HourBankSummaryResponse(
        employee_id=employee.employee_id,
        balance_minutes=total_balance,
        entries=[
            HourBankEntrySummary(
                id=e.id,
                reference_date=e.reference_date,
                expected_minutes=e.expected_minutes,
                worked_minutes=e.worked_minutes,
                balance_minutes=e.balance_minutes,
                source=e.source,
                notes=e.notes,
            )
            for e in entries
        ],
    )


@router.post("/adjustments", response_model=PunchAdjustmentSummary, status_code=201)
@limiter.limit("20/minute")
async def mobile_create_adjustment(
    request: Request,
    body: PunchAdjustmentCreate,
    employee: Annotated[AuthenticatedEmployee, Depends(require_employee_session)],
    session: Annotated[AsyncSession, Depends(require_session)],
) -> PunchAdjustmentSummary:
    record = await create_punch_adjustment_request(
        session,
        employee.company_id,
        employee.employee_id,
        punch_id=body.punch_id,
        requested_punched_at=body.requested_punched_at,
        requested_punch_type=body.requested_punch_type,
        reason=body.reason,
    )
    if record is None:
        raise HTTPException(status_code=404, detail={"code": "punch_not_found"})
    return PunchAdjustmentSummary(
        id=record.id,
        employee_id=record.employee_id,
        employee_name="",
        punch_id=record.punch_id,
        requested_punched_at=record.requested_punched_at,
        requested_punch_type=record.requested_punch_type,
        reason=record.reason,
        status=record.status,
        reviewed_by_user_id=record.reviewed_by_user_id,
        reviewed_at=record.reviewed_at,
        review_notes=record.review_notes,
        resulting_punch_id=record.resulting_punch_id,
        created_at=record.created_at,
    )


@router.get("/adjustments", response_model=list[PunchAdjustmentSummary])
async def mobile_list_adjustments(
    employee: Annotated[AuthenticatedEmployee, Depends(require_employee_session)],
    session: Annotated[AsyncSession, Depends(require_session)],
) -> list[PunchAdjustmentSummary]:
    rows, _ = await list_punch_adjustment_requests(
        session, employee.company_id, page=1, page_size=50, employee_id=employee.employee_id
    )
    return [
        PunchAdjustmentSummary(
            id=record.id,
            employee_id=record.employee_id,
            employee_name=employee_name,
            employee_avatar_url=avatar_url,
            punch_id=record.punch_id,
            requested_punched_at=record.requested_punched_at,
            requested_punch_type=record.requested_punch_type,
            reason=record.reason,
            status=record.status,
            reviewed_by_user_id=record.reviewed_by_user_id,
            reviewed_at=record.reviewed_at,
            review_notes=record.review_notes,
            resulting_punch_id=record.resulting_punch_id,
            created_at=record.created_at,
        )
        for record, employee_name, avatar_url in rows
    ]


# ---------------------------------------------------------------------------
# Requisições de Férias — Portal do Colaborador
# ---------------------------------------------------------------------------


def _vacation_summary(
    rec, emp_name: str, avatar_url: str | None, sector_name: str | None = None
) -> VacationRequestSummary:
    return VacationRequestSummary(
        id=rec.id,
        employee_id=rec.employee_id,
        employee_name=emp_name,
        employee_avatar_url=avatar_url,
        employee_sector_name=sector_name,
        start_date=rec.start_date,
        end_date=rec.end_date,
        days=rec.days,
        working_days=rec.working_days,
        notes=rec.notes,
        status=rec.status,
        reviewed_by_user_id=rec.reviewed_by_user_id,
        reviewed_at=rec.reviewed_at,
        review_notes=rec.review_notes,
        created_at=rec.created_at,
    )


@router.post("/vacation-requests", response_model=VacationRequestSummary, status_code=201)
async def mobile_create_vacation_request(
    body: VacationRequestCreate,
    employee: Annotated[AuthenticatedEmployee, Depends(require_employee_session)],
    session: Annotated[AsyncSession, Depends(require_session)],
) -> VacationRequestSummary:
    record, error = await create_vacation_request(
        session,
        employee.company_id,
        employee.employee_id,
        start_date=body.start_date,
        end_date=body.end_date,
        notes=body.notes,
    )
    if error == "end_before_start":
        raise HTTPException(
            status_code=422,
            detail={"code": error, "message": "A data de fim deve ser após a data de início."},
        )
    if error in ("employee_not_found", "employee_inactive"):
        raise HTTPException(
            status_code=422,
            detail={"code": error, "message": "Colaborador inativo ou não encontrado."},
        )
    if error or record is None:
        raise HTTPException(
            status_code=422,
            detail={"code": error or "invalid", "message": "Período inválido."},
        )
    # Busca com join para garantir employee_name, avatar_url e sector_name
    rows, _ = await list_vacation_requests(
        session,
        employee.company_id,
        1,
        1,
        employee_id=employee.employee_id,
    )
    for rec, emp_name, avatar_url, sector_name in rows:
        if rec.id == record.id:
            return _vacation_summary(rec, emp_name, avatar_url, sector_name)
    return _vacation_summary(record, "", None)


@router.get("/vacation-requests", response_model=list[VacationRequestSummary])
async def mobile_list_vacation_requests(
    employee: Annotated[AuthenticatedEmployee, Depends(require_employee_session)],
    session: Annotated[AsyncSession, Depends(require_session)],
) -> list[VacationRequestSummary]:
    rows, _ = await list_vacation_requests(
        session,
        employee.company_id,
        1,
        50,
        employee_id=employee.employee_id,
    )
    return [
        _vacation_summary(rec, emp_name, avatar_url, sector_name)
        for rec, emp_name, avatar_url, sector_name in rows
    ]


@router.delete("/vacation-requests/{request_id}", status_code=204)
async def mobile_cancel_vacation_request(
    request_id: int,
    employee: Annotated[AuthenticatedEmployee, Depends(require_employee_session)],
    session: Annotated[AsyncSession, Depends(require_session)],
) -> None:
    _, error = await cancel_vacation_request(
        session,
        employee.company_id,
        employee.employee_id,
        request_id,
    )
    if error == "not_found":
        raise HTTPException(
            status_code=404,
            detail={"code": "not_found", "message": "Solicitação não encontrada."},
        )
    if error == "cannot_cancel":
        raise HTTPException(
            status_code=409,
            detail={
                "code": "cannot_cancel",
                "message": "Apenas solicitações pendentes podem ser canceladas.",
            },
        )


@router.get("/vacation-entitlement", response_model=EmployeeVacationEntitlement)
async def mobile_vacation_entitlement(
    employee: Annotated[AuthenticatedEmployee, Depends(require_employee_session)],
    session: Annotated[AsyncSession, Depends(require_session)],
) -> EmployeeVacationEntitlement:
    """Retorna o direito de férias do colaborador com base na data de admissão (CLT)."""
    data = await get_employee_vacation_entitlement(
        session, employee.company_id, employee.employee_id
    )
    if data is None:
        raise HTTPException(status_code=404, detail={"code": "not_found"})
    return EmployeeVacationEntitlement(**data)
