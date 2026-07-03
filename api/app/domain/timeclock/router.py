from datetime import date
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import require_session
from app.core.permissions import require_permission
from app.domain.auth.repository import AuthenticatedUser
from app.domain.timeclock.schemas import (
    ManualPunchCreate,
    MonthlySummaryDay,
    MonthlySummaryResponse,
    PunchUpdate,
    TimeClockDeviceCreate,
    TimeClockDeviceSummary,
    TimeClockDeviceUpdate,
    TimeClockEnrollmentCreate,
    TimeClockEnrollmentSummary,
    TimePunchListResponse,
    TimePunchSummary,
    WorkScheduleEntry,
    WorkScheduleUpsert,
    WorkScheduleWeek,
)
from app.domain.timeclock.service import (
    create_device,
    create_enrollment,
    create_manual_punch,
    delete_device,
    delete_enrollment,
    get_schedule_for_user,
    list_devices,
    list_enrollments,
    list_punches,
    monthly_summary,
    update_device,
    update_punch,
    upsert_week,
)

router = APIRouter(prefix="/timeclock", tags=["timeclock"])


@router.get("/schedules/{user_id}", response_model=WorkScheduleWeek)
async def get_schedule_endpoint(
    user_id: int,
    user: Annotated[AuthenticatedUser, require_permission("work_schedule.view")],
    session: Annotated[AsyncSession, Depends(require_session)],
) -> WorkScheduleWeek:
    rows = await get_schedule_for_user(session, user.company_id, user_id)
    return WorkScheduleWeek(
        user_id=user_id,
        entries=[
            WorkScheduleEntry(
                weekday=row.weekday,
                start_time=row.start_time,
                end_time=row.end_time,
                break_start=row.break_start,
                break_end=row.break_end,
                tolerance_minutes=row.tolerance_minutes,
            )
            for row in rows
        ],
    )


@router.put("/schedules/{user_id}", response_model=WorkScheduleWeek)
async def put_schedule_endpoint(
    user_id: int,
    body: WorkScheduleUpsert,
    user: Annotated[AuthenticatedUser, require_permission("work_schedule.manage")],
    session: Annotated[AsyncSession, Depends(require_session)],
) -> WorkScheduleWeek:
    rows = await upsert_week(
        session, user.company_id, user.id, user_id, [e.model_dump() for e in body.entries]
    )
    return WorkScheduleWeek(
        user_id=user_id,
        entries=[
            WorkScheduleEntry(
                weekday=row.weekday,
                start_time=row.start_time,
                end_time=row.end_time,
                break_start=row.break_start,
                break_end=row.break_end,
                tolerance_minutes=row.tolerance_minutes,
            )
            for row in rows
        ],
    )


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
            user_id=enrollment.user_id,
            user_name=user_name,
            external_id=enrollment.external_id,
        )
        for enrollment, user_name in rows
    ]


@router.post("/enrollments", response_model=TimeClockEnrollmentSummary, status_code=201)
async def create_enrollment_endpoint(
    body: TimeClockEnrollmentCreate,
    user: Annotated[AuthenticatedUser, require_permission("timeclock.manage")],
    session: Annotated[AsyncSession, Depends(require_session)],
) -> TimeClockEnrollmentSummary:
    record = await create_enrollment(
        session, user.company_id, user.id, user_id=body.user_id, external_id=body.external_id
    )
    return TimeClockEnrollmentSummary(
        id=record.id, user_id=record.user_id, user_name="", external_id=record.external_id
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
    user_id: int | None = None,
    date_from: date | None = None,
    date_to: date | None = None,
    status: str | None = None,
) -> TimePunchListResponse:
    rows, total = await list_punches(
        session,
        user.company_id,
        page,
        page_size,
        user_id=user_id,
        date_from=date_from,
        date_to=date_to,
        status=status,
    )
    return TimePunchListResponse(
        items=[
            TimePunchSummary(
                id=punch.id,
                user_id=punch.user_id,
                user_name=user_name,
                device_id=punch.device_id,
                device_name=device_name,
                punched_at=punch.punched_at,
                punch_type=punch.punch_type,
                source=punch.source,
                status=punch.status,
                notes=punch.notes,
            )
            for punch, user_name, device_name in rows
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
        user_id=body.user_id,
        punched_at=body.punched_at,
        punch_type=body.punch_type,
        notes=body.notes,
    )
    return TimePunchSummary(
        id=record.id,
        user_id=record.user_id,
        user_name=None,
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
        user_id=record.user_id,
        user_name=None,
        device_id=record.device_id,
        device_name=None,
        punched_at=record.punched_at,
        punch_type=record.punch_type,
        source=record.source,
        status=record.status,
        notes=record.notes,
    )


@router.get("/summary/{user_id}", response_model=MonthlySummaryResponse)
async def monthly_summary_endpoint(
    user_id: int,
    user: Annotated[AuthenticatedUser, require_permission("timeclock.view")],
    session: Annotated[AsyncSession, Depends(require_session)],
    year: int,
    month: Annotated[int, Query(ge=1, le=12)],
) -> MonthlySummaryResponse:
    days = await monthly_summary(session, user.company_id, user_id, year, month)
    return MonthlySummaryResponse(
        user_id=user_id,
        month=f"{year:04d}-{month:02d}",
        days=[MonthlySummaryDay(**day) for day in days],
    )
