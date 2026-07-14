from datetime import datetime, timedelta

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.cache import cache_get, cache_set
from app.models import FiscalRequest, Sector, User, WorkOrder

TTL_METRICS = 300
TTL_RECENT = 180
TTL_KPIS = 600

WO_OPEN_STATUSES = ("aberta", "em_andamento", "aguardando_material")
WO_DONE_STATUSES = ("concluida", "validada")


async def get_metrics(
    session: AsyncSession,
    company_id: int,
    user_id: int,
) -> dict:
    cache_key = f"registro:{company_id}:dashboard:metrics:{user_id}"
    hit = await cache_get(cache_key)
    if hit is not None:
        return hit
    base = [WorkOrder.company_id == company_id, WorkOrder.deleted_at.is_(None)]

    open_occurrences = (
        await session.scalar(
            select(func.count(WorkOrder.id)).where(*base, WorkOrder.status.notin_(WO_DONE_STATUSES))
        )
        or 0
    )

    my_occurrences = (
        await session.scalar(
            select(func.count(WorkOrder.id)).where(
                *base,
                WorkOrder.status.notin_(WO_DONE_STATUSES),
                WorkOrder.assigned_user_id == user_id,
            )
        )
        or 0
    )

    open_fiscal = (
        await session.scalar(
            select(func.count(FiscalRequest.id)).where(
                FiscalRequest.company_id == company_id,
                FiscalRequest.status != "Concluído",
            )
        )
        or 0
    )

    now = datetime.now()
    month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    completed_month = (
        await session.scalar(
            select(func.count(WorkOrder.id)).where(
                *base,
                WorkOrder.status.in_(WO_DONE_STATUSES),
                WorkOrder.completed_at >= month_start,
            )
        )
        or 0
    )

    active_users = (
        await session.scalar(
            select(func.count(User.id)).where(
                User.company_id == company_id,
                User.active.is_(True),
                User.deleted_at.is_(None),
            )
        )
        or 0
    )

    active_sectors = (
        await session.scalar(
            select(func.count(Sector.id)).where(
                Sector.company_id == company_id, Sector.deleted_at.is_(None)
            )
        )
        or 0
    )

    recent = await _recent_all(session, company_id)
    kpis = await _compute_kpis(session, company_id)

    result = {
        "open_occurrences": open_occurrences,
        "my_occurrences": my_occurrences,
        "open_fiscal": open_fiscal,
        "completed_month": completed_month,
        "active_users": active_users,
        "active_sectors": active_sectors,
        "recent": recent,
        "kpis": kpis,
    }
    await cache_set(cache_key, result, TTL_METRICS)
    return result


async def _recent_all(session: AsyncSession, company_id: int) -> list[dict]:
    cache_key = f"registro:{company_id}:dashboard:recent"
    hit = await cache_get(cache_key)
    if hit is not None:
        return hit

    from sqlalchemy import text as raw

    sql = raw("""
        SELECT * FROM (
            (SELECT wo.id, wo.title, 'Ordens de Serviço' AS module,
                    COALESCE(s.name, 'Sem setor') AS area,
                    COALESCE(u.name, 'Não atribuído') AS owner,
                    CASE wo.status WHEN 'aberta' THEN 'Aberta'
                                   WHEN 'em_andamento' THEN 'Em andamento'
                                   WHEN 'aguardando_material' THEN 'Aguardando'
                                   WHEN 'concluida' THEN 'Concluída'
                                   WHEN 'validada' THEN 'Validada'
                                   ELSE 'Em andamento' END AS status,
                    wo.updated_at
             FROM work_orders wo
             LEFT JOIN sectors s ON s.id = wo.sector_id
             LEFT JOIN users u ON u.id = wo.assigned_user_id
             WHERE wo.company_id = :cid AND wo.deleted_at IS NULL
             ORDER BY wo.updated_at DESC LIMIT 5)
            UNION ALL
            (SELECT m.id, m.title, 'Reuniões' AS module,
                    COALESCE(m.location, 'Geral') AS area,
                    COALESCE(u.name, 'Não atribuído') AS owner,
                    COALESCE(m.status, 'Agendada') AS status,
                    m.updated_at
             FROM meetings m
             LEFT JOIN users u ON u.id = m.owner_user_id
             WHERE m.company_id = :cid AND m.deleted_at IS NULL
             ORDER BY m.updated_at DESC LIMIT 5)
            UNION ALL
            (SELECT sr.id, sr.title, 'Relatórios de turno' AS module,
                    COALESCE(sr.shift_type, 'Geral') AS area,
                    COALESCE(u.name, 'Não atribuído') AS owner,
                    COALESCE(sr.status, 'Em andamento') AS status,
                    sr.updated_at
             FROM shift_reports sr
             LEFT JOIN users u ON u.id = sr.owner_user_id
             WHERE sr.company_id = :cid AND sr.deleted_at IS NULL
             ORDER BY sr.updated_at DESC LIMIT 5)
            UNION ALL
            (SELECT fr.id, COALESCE(fr.title, fr.request_type) AS title,
                    'Solicitações Fiscais' AS module,
                    COALESCE(fr.request_type, 'Fiscal') AS area,
                    COALESCE(fr.requester, 'Não atribuído') AS owner,
                    COALESCE(fr.status, 'Em andamento') AS status,
                    fr.updated_at
             FROM fiscal_requests fr
             WHERE fr.company_id = :cid
             ORDER BY fr.updated_at DESC LIMIT 5)
            UNION ALL
            (SELECT mr.id, mr.title, 'Inspeções' AS module,
                    COALESCE(mr.category, 'Geral') AS area,
                    COALESCE(u.name, 'Não atribuído') AS owner,
                    COALESCE(mr.status, 'Em andamento') AS status,
                    mr.updated_at
             FROM module_records mr
             LEFT JOIN users u ON u.id = mr.owner_user_id
             WHERE mr.company_id = :cid AND mr.deleted_at IS NULL
               AND mr.module = 'inspecoes'
             ORDER BY mr.updated_at DESC LIMIT 3)
            UNION ALL
            (SELECT mr.id, mr.title, 'Manutenção' AS module,
                    COALESCE(mr.category, 'Geral') AS area,
                    COALESCE(u.name, 'Não atribuído') AS owner,
                    COALESCE(mr.status, 'Em andamento') AS status,
                    mr.updated_at
             FROM maintenance_records mr
             LEFT JOIN users u ON u.id = mr.owner_user_id
             WHERE mr.company_id = :cid AND mr.deleted_at IS NULL
             ORDER BY mr.updated_at DESC LIMIT 3)
            UNION ALL
            (SELECT mr.id, mr.title, 'Auditoria Noturna' AS module,
                    COALESCE(mr.category, 'Geral') AS area,
                    COALESCE(u.name, 'Não atribuído') AS owner,
                    COALESCE(mr.status, 'Em andamento') AS status,
                    mr.updated_at
             FROM module_records mr
             LEFT JOIN users u ON u.id = mr.owner_user_id
             WHERE mr.company_id = :cid AND mr.deleted_at IS NULL
               AND mr.module = 'manutencao'
             ORDER BY mr.updated_at DESC LIMIT 3)
        ) combined
        ORDER BY updated_at DESC
    """)

    rows = (await session.execute(sql, {"cid": company_id})).all()

    result = []
    for row in rows:
        result.append(
            {
                "id": row.id,
                "title": row.title or "Sem título",
                "module": row.module or "",
                "area": row.area or "Geral",
                "owner": row.owner or "Não atribuído",
                "status": row.status or "Em andamento",
                "updated_at": row.updated_at,
            }
        )

    await cache_set(cache_key, result, TTL_RECENT)
    return result


async def _compute_kpis(session: AsyncSession, company_id: int) -> dict:
    cache_key = f"registro:{company_id}:dashboard:kpis"
    hit = await cache_get(cache_key)
    if hit is not None:
        return hit

    now = datetime.now()
    week_ago = now - timedelta(days=7)

    wo_base = [WorkOrder.company_id == company_id, WorkOrder.deleted_at.is_(None)]
    fr_base = [FiscalRequest.company_id == company_id]

    # --- Work Orders ---
    wo_total = await session.scalar(select(func.count(WorkOrder.id)).where(*wo_base)) or 0

    wo_by_status = dict(
        (
            await session.execute(
                select(WorkOrder.status, func.count(WorkOrder.id))
                .where(*wo_base)
                .group_by(WorkOrder.status)
            )
        ).all()
    )

    wo_by_priority = dict(
        (
            await session.execute(
                select(
                    func.coalesce(WorkOrder.priority, "Sem prioridade"),
                    func.count(WorkOrder.id),
                )
                .where(*wo_base)
                .group_by(WorkOrder.priority)
            )
        ).all()
    )

    wo_by_category = dict(
        (
            await session.execute(
                select(
                    func.coalesce(WorkOrder.category, "Geral"),
                    func.count(WorkOrder.id),
                )
                .where(*wo_base)
                .group_by(WorkOrder.category)
            )
        ).all()
    )

    wo_completed = (
        await session.execute(
            select(WorkOrder.started_at, WorkOrder.completed_at).where(
                *wo_base,
                WorkOrder.started_at.isnot(None),
                WorkOrder.completed_at.isnot(None),
            )
        )
    ).all()
    resolution_hours = []
    for row in wo_completed:
        delta = (row.completed_at - row.started_at).total_seconds() / 3600
        if delta >= 0:
            resolution_hours.append(round(delta, 1))
    avg_resolution_hours = (
        round(sum(resolution_hours) / len(resolution_hours), 1) if resolution_hours else None
    )

    wo_sla_total = (
        await session.scalar(
            select(func.count(WorkOrder.id)).where(
                *wo_base,
                WorkOrder.sla_deadline.isnot(None),
                WorkOrder.status.in_(["concluida", "validada"]),
            )
        )
        or 0
    )
    wo_sla_met = (
        await session.scalar(
            select(func.count(WorkOrder.id)).where(
                *wo_base,
                WorkOrder.sla_deadline.isnot(None),
                WorkOrder.status.in_(["concluida", "validada"]),
                WorkOrder.completed_at <= WorkOrder.sla_deadline,
            )
        )
        or 0
    )
    sla_compliance_pct = round(wo_sla_met / wo_sla_total * 100) if wo_sla_total > 0 else None

    wo_overdue = (
        await session.scalar(
            select(func.count(WorkOrder.id)).where(
                *wo_base,
                WorkOrder.sla_deadline.isnot(None),
                WorkOrder.sla_deadline < now,
                WorkOrder.status.notin_(["concluida", "validada"]),
            )
        )
        or 0
    )

    wo_created_week = (
        await session.scalar(
            select(func.count(WorkOrder.id)).where(*wo_base, WorkOrder.created_at >= week_ago)
        )
        or 0
    )
    wo_completed_week = (
        await session.scalar(
            select(func.count(WorkOrder.id)).where(
                *wo_base,
                WorkOrder.completed_at >= week_ago,
                WorkOrder.completed_at.isnot(None),
            )
        )
        or 0
    )

    # --- Fiscal Requests ---
    fr_by_status = dict(
        (
            await session.execute(
                select(FiscalRequest.status, func.count(FiscalRequest.id))
                .where(*fr_base)
                .group_by(FiscalRequest.status)
            )
        ).all()
    )

    fr_by_type = dict(
        (
            await session.execute(
                select(FiscalRequest.request_type, func.count(FiscalRequest.id))
                .where(*fr_base)
                .group_by(FiscalRequest.request_type)
                .order_by(func.count(FiscalRequest.id).desc())
                .limit(8)
            )
        ).all()
    )

    fr_sla_total = (
        await session.scalar(
            select(func.count(FiscalRequest.id)).where(
                *fr_base,
                FiscalRequest.sla_deadline.isnot(None),
                FiscalRequest.status == "Concluído",
            )
        )
        or 0
    )
    fr_sla_met = (
        await session.scalar(
            select(func.count(FiscalRequest.id)).where(
                *fr_base,
                FiscalRequest.sla_deadline.isnot(None),
                FiscalRequest.status == "Concluído",
                FiscalRequest.updated_at <= FiscalRequest.sla_deadline,
            )
        )
        or 0
    )
    fr_sla_compliance = round(fr_sla_met / fr_sla_total * 100) if fr_sla_total > 0 else None

    fr_overdue = (
        await session.scalar(
            select(func.count(FiscalRequest.id)).where(
                *fr_base,
                FiscalRequest.sla_deadline.isnot(None),
                FiscalRequest.sla_deadline < now,
                FiscalRequest.status != "Concluído",
            )
        )
        or 0
    )

    # --- Weekly trend (last 7 days) ---
    trend = []
    for i in range(6, -1, -1):
        day = (now - timedelta(days=i)).date()
        day_start = datetime.combine(day, datetime.min.time())
        day_end = day_start + timedelta(days=1)

        wo_day = (
            await session.scalar(
                select(func.count(WorkOrder.id)).where(
                    *wo_base,
                    WorkOrder.created_at >= day_start,
                    WorkOrder.created_at < day_end,
                )
            )
            or 0
        )
        fr_day = (
            await session.scalar(
                select(func.count(FiscalRequest.id)).where(
                    *fr_base,
                    FiscalRequest.created_at >= day_start,
                    FiscalRequest.created_at < day_end,
                )
            )
            or 0
        )
        trend.append(
            {
                "date": day.isoformat(),
                "work_orders": wo_day,
                "fiscal_requests": fr_day,
            }
        )

    result = {
        "work_orders": {
            "total": wo_total,
            "by_status": wo_by_status,
            "by_priority": wo_by_priority,
            "by_category": wo_by_category,
            "avg_resolution_hours": avg_resolution_hours,
            "sla_compliance_pct": sla_compliance_pct,
            "overdue": wo_overdue,
            "created_week": wo_created_week,
            "completed_week": wo_completed_week,
        },
        "fiscal_requests": {
            "by_status": fr_by_status,
            "by_type": fr_by_type,
            "sla_compliance_pct": fr_sla_compliance,
            "overdue": fr_overdue,
        },
        "trend": trend,
    }
    await cache_set(cache_key, result, TTL_KPIS)
    return result
