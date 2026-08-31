from pydantic import BaseModel


class ReportTrendDay(BaseModel):
    date: str
    count: int


class WorkOrderReport(BaseModel):
    total: int
    by_status: dict[str, int]
    completion_rate_pct: int | None
    by_sector: dict[str, int]
    overdue: int
    trend: list[ReportTrendDay]
