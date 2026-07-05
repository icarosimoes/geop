from datetime import date, datetime, time
from typing import Annotated, Literal

from pydantic import BaseModel, Field


class ShiftCreate(BaseModel):
    name: str
    start_time: time
    end_time: time
    break_start: time | None = None
    break_end: time | None = None
    tolerance_minutes: int = 10
    color: str = "#2563eb"


class ShiftUpdate(BaseModel):
    name: str | None = None
    start_time: time | None = None
    end_time: time | None = None
    break_start: time | None = None
    break_end: time | None = None
    tolerance_minutes: int | None = None
    color: str | None = None
    active: bool | None = None


class ShiftSummary(BaseModel):
    id: int
    name: str
    start_time: time
    end_time: time
    break_start: time | None
    break_end: time | None
    tolerance_minutes: int
    color: str
    active: bool


class CalendarEntry(BaseModel):
    date: date
    employee_id: int
    employee_name: str
    shift_id: int | None
    shift_name: str | None
    shift_color: str | None
    start_time: time | None
    end_time: time | None
    source: str


class ScheduleDayUpsert(BaseModel):
    shift_id: int | None = None
    notes: str | None = None


class WeeklyPattern(BaseModel):
    type: Literal["weekly"] = "weekly"
    weekdays: list[int]


class RotatingPattern(BaseModel):
    type: Literal["rotating"] = "rotating"
    work_days: int
    off_days: int


class ScheduleGenerateRequest(BaseModel):
    employee_ids: list[int]
    shift_id: int
    start_date: date
    end_date: date
    pattern: Annotated[WeeklyPattern | RotatingPattern, Field(discriminator="type")]


class ScheduleGenerateResponse(BaseModel):
    affected: int


class TimeClockDeviceCreate(BaseModel):
    name: str
    model: str = "control_id"
    serial_number: str | None = None
    location_id: int | None = None


class TimeClockDeviceUpdate(BaseModel):
    name: str | None = None
    serial_number: str | None = None
    location_id: int | None = None
    active: bool | None = None


class TimeClockDeviceSummary(BaseModel):
    id: int
    name: str
    model: str
    serial_number: str | None
    location_id: int | None
    location: str | None
    webhook_token: str
    active: bool


class TimeClockEnrollmentCreate(BaseModel):
    employee_id: int
    external_id: str


class TimeClockEnrollmentSummary(BaseModel):
    id: int
    employee_id: int
    employee_name: str
    external_id: str


class TimePunchSummary(BaseModel):
    id: int
    employee_id: int | None
    employee_name: str | None
    device_id: int | None
    device_name: str | None
    punched_at: datetime
    punch_type: str | None
    source: str
    status: str | None
    notes: str | None


class TimePunchListResponse(BaseModel):
    items: list[TimePunchSummary]
    total: int
    page: int
    page_size: int


class ManualPunchCreate(BaseModel):
    employee_id: int
    punched_at: datetime
    punch_type: str | None = None
    notes: str | None = None


class PunchUpdate(BaseModel):
    punched_at: datetime | None = None
    punch_type: str | None = None
    notes: str | None = None


# ---------------------------------------------------------------------------
# Banco de horas
# ---------------------------------------------------------------------------


class HourBankEntrySummary(BaseModel):
    id: int
    reference_date: date
    expected_minutes: int
    worked_minutes: int
    balance_minutes: int
    source: str
    notes: str | None


class HourBankSummaryResponse(BaseModel):
    employee_id: int
    balance_minutes: int
    entries: list[HourBankEntrySummary]


class HourBankInitialBalanceCreate(BaseModel):
    effective_date: date
    balance_minutes: int
    notes: str | None = None


class HourBankRecalculateRequest(BaseModel):
    start_date: date
    end_date: date


class HourBankRecalculateResponse(BaseModel):
    affected: int


# ---------------------------------------------------------------------------
# Ajuste de ponto (Portal do Colaborador)
# ---------------------------------------------------------------------------


class PunchAdjustmentCreate(BaseModel):
    punch_id: int | None = None
    requested_punched_at: datetime
    requested_punch_type: str | None = None
    reason: str = Field(min_length=3)


class PunchAdjustmentSummary(BaseModel):
    id: int
    employee_id: int
    employee_name: str
    punch_id: int | None
    requested_punched_at: datetime
    requested_punch_type: str | None
    reason: str
    status: str
    reviewed_by_user_id: int | None
    reviewed_at: datetime | None
    review_notes: str | None
    resulting_punch_id: int | None
    created_at: datetime


class PunchAdjustmentListResponse(BaseModel):
    items: list[PunchAdjustmentSummary]
    total: int
    page: int
    page_size: int


class PunchAdjustmentReview(BaseModel):
    approve: bool
    review_notes: str | None = None


# ---------------------------------------------------------------------------
# Portal do Colaborador (Employee mobile app)
# ---------------------------------------------------------------------------


class EmployeeLoginRequest(BaseModel):
    company_slug: str
    registration_number: str
    pin: str


class EmployeeSessionResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in: int
    must_change_pin: bool
    employee_id: int
    employee_name: str


class EmployeePinChangeRequest(BaseModel):
    old_pin: str | None = None
    new_pin: str


class EmployeePinResetResponse(BaseModel):
    pin: str
    must_change_pin: bool = True


class MobilePunchRequest(BaseModel):
    latitude: float
    longitude: float


class MobilePunchResponse(BaseModel):
    id: int
    punched_at: datetime
    punch_type: str | None
    status: str | None
    distance_m: float | None


class EmployeeStatusResponse(BaseModel):
    next_punch_type: str


class EmployeePayslipSummary(BaseModel):
    id: int
    reference_month: date
    created_at: datetime


class EmployeePayslipListResponse(BaseModel):
    items: list[EmployeePayslipSummary]


class EmployeePayslipUploadResponse(BaseModel):
    id: int
    employee_id: int
    reference_month: date
    attachment_id: int


class EmployeePayslipImportRowResult(BaseModel):
    row: int
    status: str  # "created" | "updated" | "failed"
    employee_name: str | None = None
    reference_month: str | None = None
    error: str | None = None


class EmployeePayslipImportResponse(BaseModel):
    total: int
    created: int
    updated: int
    failed: int
    results: list[EmployeePayslipImportRowResult]
