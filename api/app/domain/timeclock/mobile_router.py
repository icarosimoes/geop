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
    MobilePunchRequest,
    MobilePunchResponse,
)
from app.domain.timeclock.service import (
    authenticate_employee,
    create_mobile_punch,
    get_calendar,
    get_employee_credential,
    get_employee_payslip_for_download,
    get_next_expected_punch_type,
    list_employee_payslips,
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
