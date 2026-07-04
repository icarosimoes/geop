from datetime import date
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import require_session
from app.core.permissions import require_permission
from app.domain.auth.repository import AuthenticatedUser
from app.domain.timeclock.schemas import (
    CalendarEntry,
    ManualPunchCreate,
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
    create_enrollment,
    create_manual_punch,
    create_shift,
    delete_device,
    delete_enrollment,
    delete_shift,
    generate_schedule,
    get_calendar,
    list_devices,
    list_enrollments,
    list_punches,
    list_shifts,
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
