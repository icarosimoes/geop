import csv
import io
import zipfile
from datetime import date
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, UploadFile
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import require_session
from app.core.permissions import require_permission
from app.domain.attachments.service import create_attachment
from app.domain.auth.repository import AuthenticatedUser
from app.domain.timeclock.schemas import (
    CalendarEntry,
    EmployeePayslipImportResponse,
    EmployeePayslipImportRowResult,
    EmployeePayslipUploadResponse,
    EmployeePinResetResponse,
    HourBankInitialBalanceCreate,
    HourBankRecalculateRequest,
    HourBankRecalculateResponse,
    HourBankSummaryResponse,
    ManualPunchCreate,
    PunchAdjustmentListResponse,
    PunchAdjustmentReview,
    PunchAdjustmentSummary,
    PunchUpdate,
    ScheduleDayUpsert,
    ScheduleGenerateRequest,
    ScheduleGenerateResponse,
    ShiftCreate,
    ShiftSummary,
    ShiftUpdate,
    TimeClockDeviceCreate,
    TimeClockDeviceSummary,
    TimeClockDeviceUpdate,
    TimeClockEnrollmentCreate,
    TimeClockEnrollmentSummary,
    TimePunchListResponse,
    TimePunchSummary,
)
from app.domain.timeclock.service import (
    create_device,
    create_employee_payslip,
    create_enrollment,
    create_manual_punch,
    create_shift,
    delete_device,
    delete_enrollment,
    delete_shift,
    generate_schedule,
    get_calendar,
    get_hour_bank_summary,
    import_employee_payslips,
    list_devices,
    list_enrollments,
    list_punch_adjustment_requests,
    list_punches,
    list_shifts,
    recalculate_hour_bank,
    reset_employee_pin,
    review_punch_adjustment_request,
    set_hour_bank_initial_balance,
    set_schedule_day,
    update_device,
    update_punch,
    update_shift,
)

router = APIRouter(prefix="/timeclock", tags=["timeclock"])


def _shift_summary(shift) -> ShiftSummary:
    return ShiftSummary(
        id=shift.id,
        name=shift.name,
        start_time=shift.start_time,
        end_time=shift.end_time,
        break_start=shift.break_start,
        break_end=shift.break_end,
        tolerance_minutes=shift.tolerance_minutes,
        color=shift.color,
        active=shift.active,
    )


@router.get("/shifts", response_model=list[ShiftSummary])
async def list_shifts_endpoint(
    user: Annotated[AuthenticatedUser, require_permission("shift.view")],
    session: Annotated[AsyncSession, Depends(require_session)],
) -> list[ShiftSummary]:
    rows = await list_shifts(session, user.company_id)
    return [_shift_summary(row) for row in rows]


@router.post("/shifts", response_model=ShiftSummary, status_code=201)
async def create_shift_endpoint(
    body: ShiftCreate,
    user: Annotated[AuthenticatedUser, require_permission("shift.manage")],
    session: Annotated[AsyncSession, Depends(require_session)],
) -> ShiftSummary:
    record = await create_shift(
        session,
        user.company_id,
        user.id,
        name=body.name,
        start_time=body.start_time,
        end_time=body.end_time,
        break_start=body.break_start,
        break_end=body.break_end,
        tolerance_minutes=body.tolerance_minutes,
        color=body.color,
    )
    return _shift_summary(record)


@router.patch("/shifts/{shift_id}", response_model=ShiftSummary)
async def update_shift_endpoint(
    shift_id: int,
    body: ShiftUpdate,
    user: Annotated[AuthenticatedUser, require_permission("shift.manage")],
    session: Annotated[AsyncSession, Depends(require_session)],
) -> ShiftSummary:
    updates = body.model_dump(exclude_none=True)
    record = await update_shift(session, user.company_id, user.id, shift_id, updates)
    if record is None:
        raise HTTPException(status_code=404, detail={"code": "not_found"})
    return _shift_summary(record)


@router.delete("/shifts/{shift_id}", status_code=204)
async def delete_shift_endpoint(
    shift_id: int,
    user: Annotated[AuthenticatedUser, require_permission("shift.manage")],
    session: Annotated[AsyncSession, Depends(require_session)],
) -> None:
    deleted, error = await delete_shift(session, user.company_id, user.id, shift_id)
    if not deleted:
        if error:
            raise HTTPException(status_code=409, detail={"code": "shift_in_use", "message": error})
        raise HTTPException(status_code=404, detail={"code": "not_found"})


@router.get("/schedule", response_model=list[CalendarEntry])
async def get_calendar_endpoint(
    user: Annotated[AuthenticatedUser, require_permission("schedule.view")],
    session: Annotated[AsyncSession, Depends(require_session)],
    start: date,
    end: date,
    employee_id: int | None = None,
    shift_id: int | None = None,
) -> list[CalendarEntry]:
    rows = await get_calendar(
        session,
        user.company_id,
        start,
        end,
        employee_id=employee_id,
        shift_id=shift_id,
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


@router.put("/schedule/{employee_id}/{target_date}", response_model=CalendarEntry)
async def set_schedule_day_endpoint(
    employee_id: int,
    target_date: date,
    body: ScheduleDayUpsert,
    user: Annotated[AuthenticatedUser, require_permission("schedule.manage")],
    session: Annotated[AsyncSession, Depends(require_session)],
) -> CalendarEntry:
    await set_schedule_day(
        session, user.company_id, user.id, employee_id, target_date, body.shift_id, body.notes
    )
    rows = await get_calendar(
        session, user.company_id, target_date, target_date, employee_id=employee_id
    )
    entry, employee_name, shift = rows[0]
    return CalendarEntry(
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


@router.post("/schedule/generate", response_model=ScheduleGenerateResponse)
async def generate_schedule_endpoint(
    body: ScheduleGenerateRequest,
    user: Annotated[AuthenticatedUser, require_permission("schedule.manage")],
    session: Annotated[AsyncSession, Depends(require_session)],
) -> ScheduleGenerateResponse:
    affected = await generate_schedule(
        session,
        user.company_id,
        user.id,
        employee_ids=body.employee_ids,
        shift_id=body.shift_id,
        start_date=body.start_date,
        end_date=body.end_date,
        pattern=body.pattern,
    )
    return ScheduleGenerateResponse(affected=affected)


@router.get("/devices", response_model=list[TimeClockDeviceSummary])
async def list_devices_endpoint(
    user: Annotated[AuthenticatedUser, require_permission("timeclock.manage")],
    session: Annotated[AsyncSession, Depends(require_session)],
) -> list[TimeClockDeviceSummary]:
    rows = await list_devices(session, user.company_id)
    return [
        TimeClockDeviceSummary(
            id=device.id,
            name=device.name,
            model=device.model,
            serial_number=device.serial_number,
            location_id=device.location_id,
            location=location_name,
            webhook_token=device.webhook_token,
            active=device.active,
        )
        for device, location_name in rows
    ]


@router.post("/devices", response_model=TimeClockDeviceSummary, status_code=201)
async def create_device_endpoint(
    body: TimeClockDeviceCreate,
    user: Annotated[AuthenticatedUser, require_permission("timeclock.manage")],
    session: Annotated[AsyncSession, Depends(require_session)],
) -> TimeClockDeviceSummary:
    record = await create_device(
        session,
        user.company_id,
        user.id,
        name=body.name,
        model=body.model,
        serial_number=body.serial_number,
        location_id=body.location_id,
    )
    return TimeClockDeviceSummary(
        id=record.id,
        name=record.name,
        model=record.model,
        serial_number=record.serial_number,
        location_id=record.location_id,
        location=None,
        webhook_token=record.webhook_token,
        active=record.active,
    )


@router.patch("/devices/{device_id}", response_model=TimeClockDeviceSummary)
async def update_device_endpoint(
    device_id: int,
    body: TimeClockDeviceUpdate,
    user: Annotated[AuthenticatedUser, require_permission("timeclock.manage")],
    session: Annotated[AsyncSession, Depends(require_session)],
) -> TimeClockDeviceSummary:
    updates = body.model_dump(exclude_none=True)
    record = await update_device(session, user.company_id, user.id, device_id, updates)
    if record is None:
        raise HTTPException(status_code=404, detail={"code": "not_found"})
    return TimeClockDeviceSummary(
        id=record.id,
        name=record.name,
        model=record.model,
        serial_number=record.serial_number,
        location_id=record.location_id,
        location=None,
        webhook_token=record.webhook_token,
        active=record.active,
    )


@router.delete("/devices/{device_id}", status_code=204)
async def delete_device_endpoint(
    device_id: int,
    user: Annotated[AuthenticatedUser, require_permission("timeclock.manage")],
    session: Annotated[AsyncSession, Depends(require_session)],
) -> None:
    deleted = await delete_device(session, user.company_id, user.id, device_id)
    if not deleted:
        raise HTTPException(status_code=404, detail={"code": "not_found"})


@router.get("/enrollments", response_model=list[TimeClockEnrollmentSummary])
async def list_enrollments_endpoint(
    user: Annotated[AuthenticatedUser, require_permission("timeclock.manage")],
    session: Annotated[AsyncSession, Depends(require_session)],
) -> list[TimeClockEnrollmentSummary]:
    rows = await list_enrollments(session, user.company_id)
    return [
        TimeClockEnrollmentSummary(
            id=enrollment.id,
            employee_id=enrollment.employee_id,
            employee_name=employee_name,
            external_id=enrollment.external_id,
        )
        for enrollment, employee_name in rows
    ]


@router.post("/enrollments", response_model=TimeClockEnrollmentSummary, status_code=201)
async def create_enrollment_endpoint(
    body: TimeClockEnrollmentCreate,
    user: Annotated[AuthenticatedUser, require_permission("timeclock.manage")],
    session: Annotated[AsyncSession, Depends(require_session)],
) -> TimeClockEnrollmentSummary:
    record = await create_enrollment(
        session,
        user.company_id,
        user.id,
        employee_id=body.employee_id,
        external_id=body.external_id,
    )
    return TimeClockEnrollmentSummary(
        id=record.id,
        employee_id=record.employee_id,
        employee_name="",
        external_id=record.external_id,
    )


@router.delete("/enrollments/{enrollment_id}", status_code=204)
async def delete_enrollment_endpoint(
    enrollment_id: int,
    user: Annotated[AuthenticatedUser, require_permission("timeclock.manage")],
    session: Annotated[AsyncSession, Depends(require_session)],
) -> None:
    deleted = await delete_enrollment(session, user.company_id, user.id, enrollment_id)
    if not deleted:
        raise HTTPException(status_code=404, detail={"code": "not_found"})


@router.get("/punches", response_model=TimePunchListResponse)
async def list_punches_endpoint(
    user: Annotated[AuthenticatedUser, require_permission("timeclock.view")],
    session: Annotated[AsyncSession, Depends(require_session)],
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=100)] = 20,
    employee_id: int | None = None,
    date_from: date | None = None,
    date_to: date | None = None,
    status: str | None = None,
) -> TimePunchListResponse:
    rows, total = await list_punches(
        session,
        user.company_id,
        page,
        page_size,
        employee_id=employee_id,
        date_from=date_from,
        date_to=date_to,
        status=status,
    )
    return TimePunchListResponse(
        items=[
            TimePunchSummary(
                id=punch.id,
                employee_id=punch.employee_id,
                employee_name=employee_name,
                device_id=punch.device_id,
                device_name=device_name,
                punched_at=punch.punched_at,
                punch_type=punch.punch_type,
                source=punch.source,
                status=punch.status,
                notes=punch.notes,
            )
            for punch, employee_name, device_name in rows
        ],
        total=total,
        page=page,
        page_size=page_size,
    )


@router.post("/punches", response_model=TimePunchSummary, status_code=201)
async def create_manual_punch_endpoint(
    body: ManualPunchCreate,
    user: Annotated[AuthenticatedUser, require_permission("timeclock.manage")],
    session: Annotated[AsyncSession, Depends(require_session)],
) -> TimePunchSummary:
    record = await create_manual_punch(
        session,
        user.company_id,
        user.id,
        employee_id=body.employee_id,
        punched_at=body.punched_at,
        punch_type=body.punch_type,
        notes=body.notes,
    )
    return TimePunchSummary(
        id=record.id,
        employee_id=record.employee_id,
        employee_name=None,
        device_id=record.device_id,
        device_name=None,
        punched_at=record.punched_at,
        punch_type=record.punch_type,
        source=record.source,
        status=record.status,
        notes=record.notes,
    )


@router.post(
    "/employees/{employee_id}/pin/reset",
    response_model=EmployeePinResetResponse,
    status_code=201,
)
async def reset_employee_pin_endpoint(
    employee_id: int,
    user: Annotated[AuthenticatedUser, require_permission("timeclock.manage")],
    session: Annotated[AsyncSession, Depends(require_session)],
) -> EmployeePinResetResponse:
    """RH gera um PIN novo para o Portal do Colaborador. O funcionário é obrigado
    a trocá-lo no primeiro login (must_change_pin=True)."""
    new_pin, error = await reset_employee_pin(session, user.company_id, user.id, employee_id)
    if error is not None:
        raise HTTPException(status_code=404, detail={"code": "not_found"})
    return EmployeePinResetResponse(pin=new_pin)


@router.post(
    "/employees/{employee_id}/payslips",
    response_model=EmployeePayslipUploadResponse,
    status_code=201,
)
async def upload_employee_payslip_endpoint(
    employee_id: int,
    reference_month: date,
    file: UploadFile,
    user: Annotated[AuthenticatedUser, require_permission("timeclock.manage")],
    session: Annotated[AsyncSession, Depends(require_session)],
) -> EmployeePayslipUploadResponse:
    """RH faz upload do contracheque (PDF) de um mês. Reaproveita o fluxo genérico
    de anexos (app/domain/attachments/service.py) para armazenamento/validação, e
    guarda apenas o metadado de competência em EmployeePayslip."""
    data = await file.read()
    attachment = await create_attachment(
        session,
        user.company_id,
        user.id,
        entity_type="employee_payslip",
        entity_id=employee_id,
        filename=file.filename or "contracheque.pdf",
        content_type=file.content_type or "application/pdf",
        data=data,
        skip_audit=True,
    )
    if isinstance(attachment, str):
        raise HTTPException(status_code=422, detail={"code": "invalid_file", "message": attachment})

    record = await create_employee_payslip(
        session,
        user.company_id,
        user.id,
        employee_id=employee_id,
        reference_month=reference_month.replace(day=1),
        attachment_id=attachment.id,
    )
    return EmployeePayslipUploadResponse(
        id=record.id,
        employee_id=record.employee_id,
        reference_month=record.reference_month,
        attachment_id=record.attachment_id,
    )


@router.post(
    "/employees/payslips/import",
    response_model=EmployeePayslipImportResponse,
)
async def import_employee_payslips_endpoint(
    manifest: UploadFile,
    archive: UploadFile,
    user: Annotated[AuthenticatedUser, require_permission("timeclock.manage")],
    session: Annotated[AsyncSession, Depends(require_session)],
) -> EmployeePayslipImportResponse:
    """RH sobe um ZIP com os PDFs de contracheque de uma competência + um manifesto
    CSV (cpf ou matricula, competencia, arquivo) casando cada PDF a um funcionário.
    Não depende de nenhum ERP/sistema de folha específico — funciona com qualquer
    contador, já que CPF é universal. Reaproveita o fluxo genérico de attachments."""
    if not (manifest.filename or "").lower().endswith(".csv"):
        raise HTTPException(status_code=400, detail={"code": "invalid_manifest_type"})
    if not (archive.filename or "").lower().endswith(".zip"):
        raise HTTPException(status_code=400, detail={"code": "invalid_archive_type"})

    manifest_raw = await manifest.read()
    try:
        manifest_text = manifest_raw.decode("utf-8-sig")
    except UnicodeDecodeError as exc:
        raise HTTPException(status_code=400, detail={"code": "invalid_encoding"}) from exc

    rows = list(csv.DictReader(io.StringIO(manifest_text)))
    if not rows:
        raise HTTPException(status_code=400, detail={"code": "empty_manifest"})

    archive_raw = await archive.read()
    files: dict[str, bytes] = {}
    try:
        with zipfile.ZipFile(io.BytesIO(archive_raw)) as zf:
            for info in zf.infolist():
                if info.is_dir():
                    continue
                name = info.filename
                if name.startswith("/") or ".." in name.split("/"):
                    raise HTTPException(status_code=400, detail={"code": "invalid_archive_entry"})
                files[name.rsplit("/", 1)[-1]] = zf.read(info)
    except zipfile.BadZipFile as exc:
        raise HTTPException(status_code=400, detail={"code": "invalid_archive"}) from exc

    results = await import_employee_payslips(session, user.company_id, user.id, rows, files)
    created = sum(1 for r in results if r["status"] == "created")
    updated = sum(1 for r in results if r["status"] == "updated")
    failed = sum(1 for r in results if r["status"] == "failed")
    return EmployeePayslipImportResponse(
        total=len(results),
        created=created,
        updated=updated,
        failed=failed,
        results=[EmployeePayslipImportRowResult(**r) for r in results],
    )


@router.patch("/punches/{punch_id}", response_model=TimePunchSummary)
async def update_punch_endpoint(
    punch_id: int,
    body: PunchUpdate,
    user: Annotated[AuthenticatedUser, require_permission("timeclock.manage")],
    session: Annotated[AsyncSession, Depends(require_session)],
) -> TimePunchSummary:
    updates = body.model_dump(exclude_none=True)
    record = await update_punch(session, user.company_id, user.id, punch_id, updates)
    if record is None:
        raise HTTPException(status_code=404, detail={"code": "not_found"})
    return TimePunchSummary(
        id=record.id,
        employee_id=record.employee_id,
        employee_name=None,
        device_id=record.device_id,
        device_name=None,
        punched_at=record.punched_at,
        punch_type=record.punch_type,
        source=record.source,
        status=record.status,
        notes=record.notes,
    )


# ---------------------------------------------------------------------------
# Banco de horas
# ---------------------------------------------------------------------------


def _hour_bank_summary_response(
    employee_id: int, total_balance: int, entries: list
) -> HourBankSummaryResponse:
    from app.domain.timeclock.schemas import HourBankEntrySummary

    return HourBankSummaryResponse(
        employee_id=employee_id,
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


@router.get("/hour-bank/{employee_id}", response_model=HourBankSummaryResponse)
async def get_hour_bank_endpoint(
    employee_id: int,
    user: Annotated[AuthenticatedUser, require_permission("hour_bank.view")],
    session: Annotated[AsyncSession, Depends(require_session)],
) -> HourBankSummaryResponse:
    total_balance, entries = await get_hour_bank_summary(session, user.company_id, employee_id)
    return _hour_bank_summary_response(employee_id, total_balance, entries)


@router.post("/hour-bank/{employee_id}/recalculate", response_model=HourBankRecalculateResponse)
async def recalculate_hour_bank_endpoint(
    employee_id: int,
    body: HourBankRecalculateRequest,
    user: Annotated[AuthenticatedUser, require_permission("hour_bank.manage")],
    session: Annotated[AsyncSession, Depends(require_session)],
) -> HourBankRecalculateResponse:
    if body.end_date < body.start_date:
        raise HTTPException(status_code=422, detail={"code": "invalid_range"})
    affected = await recalculate_hour_bank(
        session, user.company_id, user.id, employee_id, body.start_date, body.end_date
    )
    return HourBankRecalculateResponse(affected=affected)


@router.post(
    "/hour-bank/{employee_id}/initial-balance",
    response_model=HourBankSummaryResponse,
    status_code=201,
)
async def set_hour_bank_initial_balance_endpoint(
    employee_id: int,
    body: HourBankInitialBalanceCreate,
    user: Annotated[AuthenticatedUser, require_permission("hour_bank.manage")],
    session: Annotated[AsyncSession, Depends(require_session)],
) -> HourBankSummaryResponse:
    await set_hour_bank_initial_balance(
        session,
        user.company_id,
        user.id,
        employee_id,
        body.effective_date,
        body.balance_minutes,
        body.notes,
    )
    total_balance, entries = await get_hour_bank_summary(session, user.company_id, employee_id)
    return _hour_bank_summary_response(employee_id, total_balance, entries)


# ---------------------------------------------------------------------------
# Ajuste de ponto: aprovação (RH/gestor)
# ---------------------------------------------------------------------------


def _punch_adjustment_summary(record, employee_name: str) -> PunchAdjustmentSummary:
    return PunchAdjustmentSummary(
        id=record.id,
        employee_id=record.employee_id,
        employee_name=employee_name,
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


@router.get("/adjustments", response_model=PunchAdjustmentListResponse)
async def list_punch_adjustments_endpoint(
    user: Annotated[AuthenticatedUser, require_permission("punch_adjustment.view")],
    session: Annotated[AsyncSession, Depends(require_session)],
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=100)] = 20,
    employee_id: int | None = None,
    status: str | None = None,
) -> PunchAdjustmentListResponse:
    rows, total = await list_punch_adjustment_requests(
        session, user.company_id, page, page_size, employee_id=employee_id, status=status
    )
    return PunchAdjustmentListResponse(
        items=[_punch_adjustment_summary(record, employee_name) for record, employee_name in rows],
        total=total,
        page=page,
        page_size=page_size,
    )


@router.post("/adjustments/{request_id}/review", response_model=PunchAdjustmentSummary)
async def review_punch_adjustment_endpoint(
    request_id: int,
    body: PunchAdjustmentReview,
    user: Annotated[AuthenticatedUser, require_permission("punch_adjustment.manage")],
    session: Annotated[AsyncSession, Depends(require_session)],
) -> PunchAdjustmentSummary:
    record, error = await review_punch_adjustment_request(
        session,
        user.company_id,
        user.id,
        request_id,
        approve=body.approve,
        review_notes=body.review_notes,
    )
    if error == "not_found":
        raise HTTPException(status_code=404, detail={"code": "not_found"})
    if error == "already_reviewed":
        raise HTTPException(status_code=409, detail={"code": "already_reviewed"})
    assert record is not None
    return _punch_adjustment_summary(record, "")
