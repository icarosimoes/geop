from datetime import date, datetime, timedelta

from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.sla import compute_sla_status
from app.domain.work_orders.service import STATUS_LABELS
from app.models import FiscalRequest, Sector, WorkOrder


def _parse_period(date_from: str | None, date_to: str | None) -> tuple[datetime, datetime]:
    """Retorna [start, end) em datetime naive. Sem filtros, usa o mês corrente."""
    now = datetime.now()
    if date_from:
        start = datetime.fromisoformat(date_from)
    else:
        start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    end = datetime.fromisoformat(date_to) + timedelta(days=1) if date_to else now
    return start, end


async def _daily_trend(
    session: AsyncSession,
    date_column,
    id_column,
    base_filters: list,
    start: datetime,
    end: datetime,
) -> list[dict]:
    rows = (
        await session.execute(
            select(func.date(date_column), func.count(id_column))
            .where(*base_filters)
            .group_by(func.date(date_column))
        )
    ).all()
    counts = {d.isoformat(): c for d, c in rows}

    trend = []
    day = start.date()
    last_day = (end - timedelta(microseconds=1)).date()
    while day <= last_day:
        trend.append({"date": day.isoformat(), "count": counts.get(day.isoformat(), 0)})
        day += timedelta(days=1)
    return trend


WO_DONE_STATUSES = ("concluida", "validada")


async def build_work_orders_report(
    session: AsyncSession,
    company_id: int,
    date_from: str | None,
    date_to: str | None,
) -> dict:
    start, end = _parse_period(date_from, date_to)
    base = [
        WorkOrder.company_id == company_id,
        WorkOrder.deleted_at.is_(None),
        WorkOrder.created_at >= start,
        WorkOrder.created_at < end,
    ]

    total = await session.scalar(select(func.count(WorkOrder.id)).where(*base)) or 0

    by_status_rows = (
        await session.execute(
            select(WorkOrder.status, func.count(WorkOrder.id))
            .where(*base)
            .group_by(WorkOrder.status)
        )
    ).all()
    by_status = {STATUS_LABELS.get(status, status): count for status, count in by_status_rows}

    completed = (
        await session.scalar(
            select(func.count(WorkOrder.id)).where(*base, WorkOrder.status.in_(WO_DONE_STATUSES))
        )
        or 0
    )
    completion_rate_pct = round(completed / total * 100) if total > 0 else None

    by_sector_rows = (
        await session.execute(
            select(func.coalesce(Sector.name, "Sem setor"), func.count(WorkOrder.id))
            .outerjoin(Sector, Sector.id == WorkOrder.sector_id)
            .where(*base)
            .group_by(Sector.name)
            .order_by(func.count(WorkOrder.id).desc())
            .limit(8)
        )
    ).all()
    by_sector = {name: count for name, count in by_sector_rows}

    now = datetime.now()
    overdue = (
        await session.scalar(
            select(func.count(WorkOrder.id)).where(
                WorkOrder.company_id == company_id,
                WorkOrder.deleted_at.is_(None),
                WorkOrder.status.notin_(WO_DONE_STATUSES),
                or_(
                    (WorkOrder.deadline.isnot(None)) & (WorkOrder.deadline < date.today()),
                    (WorkOrder.sla_deadline.isnot(None)) & (WorkOrder.sla_deadline < now),
                ),
            )
        )
        or 0
    )

    trend = await _daily_trend(session, WorkOrder.created_at, WorkOrder.id, base, start, end)

    return {
        "total": total,
        "by_status": by_status,
        "completion_rate_pct": completion_rate_pct,
        "by_sector": by_sector,
        "overdue": overdue,
        "trend": trend,
    }


async def build_fiscal_sla_report(
    session: AsyncSession,
    company_id: int,
    date_from: str | None,
    date_to: str | None,
) -> dict:
    start, end = _parse_period(date_from, date_to)
    base = [
        FiscalRequest.company_id == company_id,
        FiscalRequest.created_at >= start,
        FiscalRequest.created_at < end,
    ]

    total = await session.scalar(select(func.count(FiscalRequest.id)).where(*base)) or 0

    by_status: dict[str, int] = dict(
        (
            await session.execute(
                select(FiscalRequest.status, func.count(FiscalRequest.id))
                .where(*base)
                .group_by(FiscalRequest.status)
            )
        ).all()  # type: ignore[arg-type]
    )

    by_type: dict[str, int] = dict(
        (
            await session.execute(
                select(FiscalRequest.request_type, func.count(FiscalRequest.id))
                .where(*base)
                .group_by(FiscalRequest.request_type)
                .order_by(func.count(FiscalRequest.id).desc())
                .limit(8)
            )
        ).all()  # type: ignore[arg-type]
    )

    rows = (
        await session.execute(
            select(
                FiscalRequest.created_at,
                FiscalRequest.updated_at,
                FiscalRequest.sla_deadline,
                FiscalRequest.status,
                FiscalRequest.sla_paused_at,
                FiscalRequest.sla_paused_seconds,
            ).where(*base)
        )
    ).all()

    sla_states = {"on_time": 0, "warning": 0, "overdue": 0, "paused": 0, "completed": 0}
    resolution_hours = []
    sla_total = 0
    sla_met = 0
    for row in rows:
        state = compute_sla_status(
            row.sla_deadline, row.status, row.sla_paused_at, row.sla_paused_seconds
        )
        if state:
            sla_states[state] = sla_states.get(state, 0) + 1

        if row.status == "Concluído" and row.sla_deadline is not None:
            sla_total += 1
            if row.updated_at <= row.sla_deadline:
                sla_met += 1
            delta = (row.updated_at - row.created_at).total_seconds() / 3600
            if delta >= 0:
                resolution_hours.append(delta)

    sla_compliance_pct = round(sla_met / sla_total * 100) if sla_total > 0 else None
    avg_resolution_hours = (
        round(sum(resolution_hours) / len(resolution_hours), 1) if resolution_hours else None
    )

    overdue = (
        await session.scalar(
            select(func.count(FiscalRequest.id)).where(
                FiscalRequest.company_id == company_id,
                FiscalRequest.sla_deadline.isnot(None),
                FiscalRequest.sla_deadline < datetime.now(),
                FiscalRequest.status != "Concluído",
            )
        )
        or 0
    )

    trend = await _daily_trend(
        session, FiscalRequest.created_at, FiscalRequest.id, base, start, end
    )

    return {
        "total": total,
        "by_status": by_status,
        "by_type": by_type,
        "sla_compliance_pct": sla_compliance_pct,
        "avg_resolution_hours": avg_resolution_hours,
        "sla_states": sla_states,
        "overdue": overdue,
        "trend": trend,
    }
