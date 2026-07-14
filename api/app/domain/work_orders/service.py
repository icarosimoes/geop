from datetime import datetime, timedelta
from typing import NamedTuple

from sqlalchemy import delete as sa_delete
from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.audit import compute_diff, record_event
from app.core.cache import invalidate_dashboard
from app.core.pagination import CursorPage, paginate_by_cursor
from app.integrations.notifications import notify_record_event
from app.models import Sector, User, WorkOrder, WorkOrderParticipant
from app.models.operations import WORK_ORDER_STATUSES


async def list_categories(session: AsyncSession, company_id: int) -> list[str]:
    from app.models import CompanySetting

    result = await session.execute(
        select(WorkOrder.category)
        .where(
            WorkOrder.company_id == company_id,
            WorkOrder.category.isnot(None),
            WorkOrder.deleted_at.is_(None),
        )
        .distinct()
    )
    used = {row[0] for row in result.fetchall()}

    setting = (
        await session.execute(
            select(CompanySetting).where(
                CompanySetting.company_id == company_id,
                CompanySetting.key == "work_order_categories",
            )
        )
    ).scalar_one_or_none()
    configured = set(setting.value.get("items", [])) if setting else set()

    return sorted(used | configured)


class WorkOrderRow(NamedTuple):
    order: WorkOrder
    assigned_name: str | None
    created_by_name: str | None
    sector_name: str | None


TRANSITIONS: dict[str, list[str]] = {
    "aberta": ["em_andamento"],
    "em_andamento": ["aberta", "aguardando_material", "concluida"],
    "aguardando_material": ["em_andamento", "aberta", "concluida"],
    "concluida": ["validada", "em_andamento"],
    "validada": [],
}

STATUS_LABELS: dict[str, str] = {
    "aberta": "Aberta",
    "em_andamento": "Em andamento",
    "aguardando_material": "Aguardando",
    "concluida": "Concluída",
    "validada": "Validada",
}


async def _sync_participants(
    session: AsyncSession, work_order_id: int, participant_ids: list[int]
) -> None:
    await session.execute(
        sa_delete(WorkOrderParticipant).where(
            WorkOrderParticipant.work_order_id == work_order_id
        )
    )
    for uid in participant_ids:
        session.add(WorkOrderParticipant(work_order_id=work_order_id, user_id=uid))


async def _get_participants(session: AsyncSession, work_order_id: int) -> list[tuple[int, str]]:
    rows = (
        await session.execute(
            select(WorkOrderParticipant.user_id, User.name)
            .join(User, User.id == WorkOrderParticipant.user_id)
            .where(WorkOrderParticipant.work_order_id == work_order_id)
            .order_by(User.name)
        )
    ).all()
    return [(uid, name) for uid, name in rows]


async def list_orders(
    session: AsyncSession,
    company_id: int,
    page: int,
    page_size: int,
    search: str | None = None,
    status: str | None = None,
    priority: str | None = None,
) -> tuple[list[WorkOrderRow], int]:
    assigned = User.__table__.alias("assigned")
    created_by = User.__table__.alias("created_by")

    filters = [
        WorkOrder.company_id == company_id,
        WorkOrder.deleted_at.is_(None),
    ]
    if search:
        pattern = f"%{search.strip()}%"
        filters.append(
            or_(
                WorkOrder.title.ilike(pattern),
                WorkOrder.description.ilike(pattern),
            )
        )
    if status:
        filters.append(WorkOrder.status == status)
    if priority:
        filters.append(WorkOrder.priority == priority)

    total = await session.scalar(select(func.count(WorkOrder.id)).where(*filters)) or 0

    rows = (
        await session.execute(
            select(
                WorkOrder,
                assigned.c.name.label("assigned_name"),
                created_by.c.name.label("created_by_name"),
                Sector.name.label("sector_name"),
            )
            .outerjoin(assigned, assigned.c.id == WorkOrder.assigned_user_id)
            .outerjoin(created_by, created_by.c.id == WorkOrder.created_by_user_id)
            .outerjoin(Sector, Sector.id == WorkOrder.sector_id)
            .where(*filters)
            .order_by(WorkOrder.updated_at.desc())
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
    ).all()
    return rows, total


async def list_orders_cursor(
    session: AsyncSession,
    company_id: int,
    limit: int = 20,
    cursor: str | None = None,
    search: str | None = None,
    status: str | None = None,
    priority: str | None = None,
) -> CursorPage:
    assigned = User.__table__.alias("assigned")
    created_by = User.__table__.alias("created_by")

    filters = [WorkOrder.company_id == company_id, WorkOrder.deleted_at.is_(None)]
    if search:
        pattern = f"%{search.strip()}%"
        filters.append(or_(WorkOrder.title.ilike(pattern), WorkOrder.description.ilike(pattern)))
    if status:
        filters.append(WorkOrder.status == status)
    if priority:
        filters.append(WorkOrder.priority == priority)

    stmt = (
        select(
            WorkOrder,
            assigned.c.name.label("assigned_name"),
            created_by.c.name.label("created_by_name"),
            Sector.name.label("sector_name"),
        )
        .outerjoin(assigned, assigned.c.id == WorkOrder.assigned_user_id)
        .outerjoin(created_by, created_by.c.id == WorkOrder.created_by_user_id)
        .outerjoin(Sector, Sector.id == WorkOrder.sector_id)
        .where(*filters)
    )
    return await paginate_by_cursor(
        session, stmt, id_column=WorkOrder.id, cursor=cursor, limit=limit
    )


async def get_order(
    session: AsyncSession,
    company_id: int,
    order_id: int,
) -> tuple | None:
    assigned = User.__table__.alias("assigned")
    created_by = User.__table__.alias("created_by")

    row = (
        await session.execute(
            select(
                WorkOrder,
                assigned.c.name.label("assigned_name"),
                created_by.c.name.label("created_by_name"),
                Sector.name.label("sector_name"),
            )
            .outerjoin(assigned, assigned.c.id == WorkOrder.assigned_user_id)
            .outerjoin(created_by, created_by.c.id == WorkOrder.created_by_user_id)
            .outerjoin(Sector, Sector.id == WorkOrder.sector_id)
            .where(
                WorkOrder.id == order_id,
                WorkOrder.company_id == company_id,
                WorkOrder.deleted_at.is_(None),
            )
        )
    ).first()
    if row is None:
        return None
    participants = await _get_participants(session, row[0].id)
    return (*row, participants)


async def create_order(
    session: AsyncSession,
    company_id: int,
    user_id: int,
    user_name: str,
    user_email: str,
    *,
    title: str,
    description: str | None,
    comments: str | None = None,
    unit: str | None = None,
    deadline=None,
    priority: str | None,
    category: str | None,
    location_id: int | None,
    sector_id: int | None = None,
    maintenance_id: int | None,
    assigned_user_id: int | None,
    notify_user_ids: list[int] | None,
    sla_hours: int | None,
    participant_ids: list[int] | None = None,
) -> tuple | None:
    sla_deadline = None
    if sla_hours:
        sla_deadline = datetime.now() + timedelta(hours=sla_hours)

    rec = WorkOrder(
        company_id=company_id,
        title=title,
        description=description,
        comments=comments,
        unit=unit,
        deadline=deadline,
        status="aberta",
        priority=priority,
        category=category,
        location_id=location_id,
        sector_id=sector_id,
        maintenance_id=maintenance_id,
        assigned_user_id=assigned_user_id,
        created_by_user_id=user_id,
        notify_user_ids=notify_user_ids,
        sla_hours=sla_hours,
        sla_deadline=sla_deadline,
    )
    session.add(rec)
    await session.flush()
    if participant_ids:
        await _sync_participants(session, rec.id, participant_ids)
    await record_event(
        session,
        company_id=company_id,
        user_id=user_id,
        entity_type="work_order",
        entity_id=rec.id,
        event_type="create",
    )
    await session.commit()
    await invalidate_dashboard(company_id)
    await session.refresh(rec)

    await notify_record_event(
        session,
        company_id=company_id,
        actor_name=user_name,
        actor_email=user_email,
        event="create",
        title=rec.title,
        module="Ordem de Serviço",
        owner_user_id=assigned_user_id,
        notify_user_ids=notify_user_ids,
    )

    return await get_order(session, company_id, rec.id)


async def update_order(
    session: AsyncSession,
    company_id: int,
    user_id: int,
    user_name: str,
    user_email: str,
    order_id: int,
    updates: dict,
) -> tuple | None:
    rec = await session.scalar(
        select(WorkOrder).where(
            WorkOrder.id == order_id,
            WorkOrder.company_id == company_id,
            WorkOrder.deleted_at.is_(None),
        )
    )
    if rec is None:
        return None

    participant_ids = updates.pop("participant_ids", None)

    before = {k: str(getattr(rec, k)) for k in updates if k != "notify_user_ids"}
    for field, value in updates.items():
        setattr(rec, field, value)

    if participant_ids is not None:
        await _sync_participants(session, rec.id, participant_ids)

    diff = compute_diff(
        before,
        {k: str(v) for k, v in updates.items() if k != "notify_user_ids"},
    )
    if diff:
        await record_event(
            session,
            company_id=company_id,
            user_id=user_id,
            entity_type="work_order",
            entity_id=rec.id,
            event_type="update",
            diff=diff,
        )
    await session.commit()
    await invalidate_dashboard(company_id)

    if diff:
        detail = "; ".join(f"{k}: {v}" for k, v in diff.items())
        await notify_record_event(
            session,
            company_id=company_id,
            actor_name=user_name,
            actor_email=user_email,
            event="update",
            title=rec.title,
            module="Ordem de Serviço",
            owner_user_id=rec.assigned_user_id,
            created_by_user_id=rec.created_by_user_id,
            notify_user_ids=rec.notify_user_ids,
            detail=detail,
        )

    return await get_order(session, company_id, order_id)


async def transition_order(
    session: AsyncSession,
    company_id: int,
    user_id: int,
    user_name: str,
    user_email: str,
    order_id: int,
    target_status: str,
    notes: str | None = None,
) -> tuple | None:
    if target_status not in WORK_ORDER_STATUSES:
        raise ValueError(f"Status inválido: {target_status}")

    rec = await session.scalar(
        select(WorkOrder).where(
            WorkOrder.id == order_id,
            WorkOrder.company_id == company_id,
            WorkOrder.deleted_at.is_(None),
        )
    )
    if rec is None:
        return None

    allowed = TRANSITIONS.get(rec.status, [])
    if target_status not in allowed:
        from_label = STATUS_LABELS.get(rec.status, rec.status)
        to_label = STATUS_LABELS.get(target_status, target_status)
        raise ValueError(f"Transição não permitida: {from_label} → {to_label}")

    old_status = rec.status
    rec.status = target_status

    now = datetime.now()
    if target_status == "em_andamento" and rec.started_at is None:
        rec.started_at = now
    elif target_status == "concluida":
        rec.completed_at = now
    elif target_status == "validada":
        rec.validated_at = now
        rec.validated_by_user_id = user_id

    diff = {
        "status": {
            "from": STATUS_LABELS.get(old_status, old_status),
            "to": STATUS_LABELS.get(target_status, target_status),
        }
    }

    await record_event(
        session,
        company_id=company_id,
        user_id=user_id,
        entity_type="work_order",
        entity_id=rec.id,
        event_type="update",
        diff=diff,
    )
    await session.commit()
    await invalidate_dashboard(company_id)

    detail = f"Status: {STATUS_LABELS.get(old_status)} → {STATUS_LABELS.get(target_status)}"
    if notes:
        detail += f" | {notes}"
    await notify_record_event(
        session,
        company_id=company_id,
        actor_name=user_name,
        actor_email=user_email,
        event="update",
        title=rec.title,
        module="Ordem de Serviço",
        owner_user_id=rec.assigned_user_id,
        created_by_user_id=rec.created_by_user_id,
        notify_user_ids=rec.notify_user_ids,
        detail=detail,
    )

    return await get_order(session, company_id, order_id)


async def delete_order(
    session: AsyncSession,
    company_id: int,
    user_id: int,
    order_id: int,
) -> bool:
    rec = await session.scalar(
        select(WorkOrder).where(
            WorkOrder.id == order_id,
            WorkOrder.company_id == company_id,
            WorkOrder.deleted_at.is_(None),
        )
    )
    if rec is None:
        return False
    rec.deleted_at = datetime.now()
    await record_event(
        session,
        company_id=company_id,
        user_id=user_id,
        entity_type="work_order",
        entity_id=rec.id,
        event_type="delete",
    )
    await session.commit()
    await invalidate_dashboard(company_id)
    return True


async def count_by_status(
    session: AsyncSession,
    company_id: int,
) -> dict[str, int]:
    rows = (
        await session.execute(
            select(WorkOrder.status, func.count(WorkOrder.id))
            .where(
                WorkOrder.company_id == company_id,
                WorkOrder.deleted_at.is_(None),
            )
            .group_by(WorkOrder.status)
        )
    ).all()
    return {status: count for status, count in rows}


async def export_orders(
    session: AsyncSession,
    company_id: int,
    search: str | None = None,
) -> list:
    from app.core.export import MAX_EXPORT_ROWS

    assigned = User.__table__.alias("assigned")

    filters = [WorkOrder.company_id == company_id, WorkOrder.deleted_at.is_(None)]
    if search:
        pattern = f"%{search.strip()}%"
        filters.append(or_(WorkOrder.title.ilike(pattern), WorkOrder.description.ilike(pattern)))
    rows = (
        await session.execute(
            select(
                WorkOrder,
                Sector.name.label("sector_name"),
                assigned.c.name.label("assigned_name"),
            )
            .outerjoin(Sector, Sector.id == WorkOrder.sector_id)
            .outerjoin(assigned, assigned.c.id == WorkOrder.assigned_user_id)
            .where(*filters)
            .order_by(WorkOrder.updated_at.desc(), WorkOrder.id.desc())
            .limit(MAX_EXPORT_ROWS)
        )
    ).all()
    return rows


async def clone_order(
    session: AsyncSession,
    company_id: int,
    user_id: int,
    user_name: str,
    user_email: str,
    order_id: int,
) -> tuple | None:
    original = await session.scalar(
        select(WorkOrder).where(
            WorkOrder.id == order_id,
            WorkOrder.company_id == company_id,
            WorkOrder.deleted_at.is_(None),
        )
    )
    if original is None:
        return None

    participants = await _get_participants(session, original.id)
    p_ids = [uid for uid, _ in participants]

    return await create_order(
        session,
        company_id,
        user_id,
        user_name,
        user_email,
        title=f"Cópia de {original.title}",
        description=original.description,
        comments=original.comments,
        unit=original.unit,
        deadline=original.deadline,
        priority=original.priority,
        category=original.category,
        location_id=original.location_id,
        sector_id=original.sector_id,
        maintenance_id=original.maintenance_id,
        assigned_user_id=original.assigned_user_id,
        notify_user_ids=original.notify_user_ids,
        sla_hours=original.sla_hours,
        participant_ids=p_ids,
    )
