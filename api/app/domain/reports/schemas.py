from pydantic import BaseModel


class ReportTrendDay(BaseModel):
    date: str
    count: int


class OccurrenceReport(BaseModel):
    total: int
    by_status: dict[str, int]
    completion_rate_pct: int | None
    by_sector: dict[str, int]
    overdue: int
    trend: list[ReportTrendDay]


class FiscalRequestSlaReport(BaseModel):
    total: int
    by_status: dict[str, int]
    by_type: dict[str, int]
    sla_compliance_pct: int | None
    avg_resolution_hours: float | None
    sla_states: dict[str, int]
    overdue: int
    trend: list[ReportTrendDay]
