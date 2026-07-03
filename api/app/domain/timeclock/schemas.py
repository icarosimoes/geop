from datetime import date, datetime, time

from pydantic import BaseModel


class WorkScheduleEntry(BaseModel):
    weekday: int
    start_time: time
    end_time: time
    break_start: time | None = None
    break_end: time | None = None
    tolerance_minutes: int = 10


class WorkScheduleWeek(BaseModel):
    user_id: int
    entries: list[WorkScheduleEntry]


class WorkScheduleUpsert(BaseModel):
    entries: list[WorkScheduleEntry]


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
    user_id: int
    external_id: str


class TimeClockEnrollmentSummary(BaseModel):
    id: int
    user_id: int
    user_name: str
    external_id: str


class TimePunchSummary(BaseModel):
    id: int
    user_id: int | None
    user_name: str | None
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
    user_id: int
    punched_at: datetime
    punch_type: str | None = None
    notes: str | None = None


class PunchUpdate(BaseModel):
    punched_at: datetime | None = None
    punch_type: str | None = None
    notes: str | None = None


class MonthlySummaryDay(BaseModel):
    date: date
    expected_start: time | None
    expected_end: time | None
    punches: list[datetime]
    status: str
    worked_minutes: int | None
    delay_minutes: int | None


class MonthlySummaryResponse(BaseModel):
    user_id: int
    month: str
    days: list[MonthlySummaryDay]
