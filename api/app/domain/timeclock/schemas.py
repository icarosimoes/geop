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
    user_id: int
    user_name: str
    sector_id: int | None
    sector_name: str | None
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
    user_ids: list[int]
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
