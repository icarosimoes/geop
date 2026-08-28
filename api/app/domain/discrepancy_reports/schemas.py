from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, Field

DiscrepancyStatus = Literal["draft", "submitted", "closed"]


class DiscrepancyEntryInput(BaseModel):
    location_id: int = Field(gt=0)
    first_code: str | None = Field(default=None, max_length=40)
    second_code: str | None = Field(default=None, max_length=40)
    notes: str | None = None


class DiscrepancyEntryOut(DiscrepancyEntryInput):
    id: int
    location_name: str


class DiscrepancyReportCreate(BaseModel):
    report_date: date
    prepared_by_user_id: int | None = Field(default=None, gt=0)
    checked_by_user_id: int | None = Field(default=None, gt=0)
    received_by_user_id: int | None = Field(default=None, gt=0)
    status: DiscrepancyStatus = "draft"
    observations: str | None = None
    entries: list[DiscrepancyEntryInput] = Field(default_factory=list)


class DiscrepancyReportUpdate(BaseModel):
    report_date: date | None = None
    prepared_by_user_id: int | None = Field(default=None, gt=0)
    checked_by_user_id: int | None = Field(default=None, gt=0)
    received_by_user_id: int | None = Field(default=None, gt=0)
    status: DiscrepancyStatus | None = None
    observations: str | None = None
    entries: list[DiscrepancyEntryInput] | None = None


class DiscrepancyCodeCount(BaseModel):
    code: str
    count: int


class DiscrepancyReportSummary(BaseModel):
    id: int
    report_date: date
    status: DiscrepancyStatus
    prepared_by_user_id: int | None
    prepared_by_name: str | None
    entry_count: int
    discrepancy_count: int
    updated_at: datetime


class DiscrepancyReportDetail(DiscrepancyReportSummary):
    checked_by_user_id: int | None
    checked_by_name: str | None
    received_by_user_id: int | None
    received_by_name: str | None
    observations: str | None
    entries: list[DiscrepancyEntryOut]
    code_summary: list[DiscrepancyCodeCount]
    created_at: datetime


class DiscrepancyReportListResponse(BaseModel):
    items: list[DiscrepancyReportSummary]
    total: int
    page: int
    page_size: int
