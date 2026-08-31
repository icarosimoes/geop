from datetime import datetime
from typing import Annotated

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth import current_user
from app.core.dependencies import require_session
from app.domain.auth.repository import AuthenticatedUser
from app.domain.dashboard.service import get_metrics

router = APIRouter(prefix="/dashboard", tags=["dashboard"])


class RecentActivity(BaseModel):
    id: int
    title: str
    module: str = ""
    area: str
    owner: str
    status: str
    updated_at: datetime


class TrendDay(BaseModel):
    date: str
    work_orders: int


class WorkOrderKpis(BaseModel):
    total: int
    by_status: dict[str, int]
    by_priority: dict[str, int]
    by_category: dict[str, int]
    avg_resolution_hours: float | None
    sla_compliance_pct: int | None
    overdue: int
    created_week: int
    completed_week: int


class DashboardKpis(BaseModel):
    work_orders: WorkOrderKpis
    trend: list[TrendDay]


class DashboardMetrics(BaseModel):
    open_occurrences: int
    my_occurrences: int
    completed_month: int
    active_users: int
    active_sectors: int
    recent: list[RecentActivity]
    kpis: DashboardKpis


@router.get("/metrics", response_model=DashboardMetrics)
async def get_metrics_endpoint(
    user: Annotated[AuthenticatedUser, Depends(current_user)],
    session: Annotated[AsyncSession, Depends(require_session)],
) -> DashboardMetrics:
    data = await get_metrics(session, user.company_id, user.id)
    return DashboardMetrics(
        open_occurrences=data["open_occurrences"],
        my_occurrences=data["my_occurrences"],
        completed_month=data["completed_month"],
        active_users=data["active_users"],
        active_sectors=data["active_sectors"],
        recent=[RecentActivity(**r) for r in data["recent"]],
        kpis=DashboardKpis(**data["kpis"]),
    )
