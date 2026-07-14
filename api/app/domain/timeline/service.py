from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.audit import record_event
from app.core.pagination import CursorPage, decode_cursor, encode_cursor
from app.integrations.notifications import notify_record_event
from app.models import (
    AuditEvent,
    Employee,
    FiscalRequest,
    Meeting,
    ModuleRecord,
    Procedure,
    ShiftReport,
    User,
    WorkOrder,
)

VALID_ENTITY_TYPES = {
    "work_order",
    "fiscal_request",
    "procedure",
    "meeting",
    "shift_report",
    "inspecoes",
    "diarios-obra",
    "manutencao",
    "mural",
    "employee",
}

ENTITY_MODEL_MAP: dict[str, Any] = {
    "work_order": WorkOrder,
    "fiscal_request": FiscalRequest,
    "procedure": Procedure,
    "meeting": Meeting,
    "shift_report": ShiftReport,
    "employee": Employee,
}

MODULE_SLUG_ENTITY_TYPES = {
    "inspecoes",
    "diarios-obra",
    "manutencao",
    "mural",
}


async def verify_entity_access(
    session: AsyncSession, entity_type: str, entity_id: int, company_id: int
) -> bool:
    if entity_type in ENTITY_MODEL_MAP:
        model = ENTITY_MODEL_MAP[entity_type]
        filters = [model.id == entity_id, model.company_id == company_id]
        if hasattr(model, "deleted_at"):
            filters.append(model.deleted_at.is_(None))
        exists = await session.scalar(select(model.id).where(*filters))
    elif entity_type in MODULE_SLUG_ENTITY_TYPES:
        exists = await session.scalar(
            select(ModuleRecord.id).where(
                ModuleRecord.id == entity_id,
                ModuleRecord.company_id == company_id,
                ModuleRecord.module == entity_type,
                ModuleRecord.deleted_at.is_(None),
            )
        )
    else:
        return False
    return exists is not None


async def get_timeline(
    session: AsyncSession,
    company_id: int,
    entity_type: str,
    entity_id: int,
) -> list[dict]:
    rows = (
        await session.execute(
            select(AuditEvent, User.name)
            .join(User, User.id == AuditEvent.user_id)
            .where(
                AuditEvent.company_id == company_id,
                AuditEvent.entity_type == entity_type,
                AuditEvent.entity_id == entity_id,
            )
            .order_by(AuditEvent.created_at.asc(), AuditEvent.id.asc())
        )
    ).all()

    items = []
    for event, user_name in rows:
        message = None
        changes = None
        if event.event_type == "comment":
            message = event.diff.get("message") if event.diff else None
        elif event.event_type == "attachment_add":
            message = f'Anexou "{event.diff.get("filename", "?")}"' if event.diff else None
        elif event.event_type == "attachment_remove":
            message = f'Removeu anexo "{event.diff.get("filename", "?")}"' if event.diff else None
        elif event.diff:
            changes = event.diff
        items.append(
            {
                "id": event.id,
                "event_type": event.event_type,
                "user": user_name,
                "message": message,
                "changes": changes,
                "created_at": event.created_at,
            }
        )
    return items


async def get_timeline_cursor(
    session: AsyncSession,
    company_id: int,
    entity_type: str,
    entity_id: int,
    limit: int = 50,
    cursor: str | None = None,
) -> CursorPage:
    filters = [
        AuditEvent.company_id == company_id,
        AuditEvent.entity_type == entity_type,
        AuditEvent.entity_id == entity_id,
    ]
    if cursor:
        after_id = decode_cursor(cursor)
        if after_id is not None:
            filters.append(AuditEvent.id > after_id)

    rows = (
        await session.execute(
            select(AuditEvent, User.name)
            .join(User, User.id == AuditEvent.user_id)
            .where(*filters)
            .order_by(AuditEvent.created_at.asc(), AuditEvent.id.asc())
            .limit(limit + 1)
        )
    ).all()

    has_more = len(rows) > limit
    rows = rows[:limit]

    items = []
    for event, user_name in rows:
        message = None
        changes = None
        if event.event_type == "comment":
            message = event.diff.get("message") if event.diff else None
        elif event.event_type == "attachment_add":
            message = f'Anexou "{event.diff.get("filename", "?")}"' if event.diff else None
        elif event.event_type == "attachment_remove":
            message = f'Removeu anexo "{event.diff.get("filename", "?")}"' if event.diff else None
        elif event.diff:
            changes = event.diff
        items.append(
            {
                "id": event.id,
                "event_type": event.event_type,
                "user": user_name,
                "message": message,
                "changes": changes,
                "created_at": event.created_at,
            }
        )

    next_cursor = None
    if has_more and items:
        next_cursor = encode_cursor(items[-1]["id"])

    return CursorPage(items=items, next_cursor=next_cursor, has_more=has_more)


async def add_comment(
    session: AsyncSession,
    company_id: int,
    user_id: int,
    user_name: str,
    user_email: str,
    entity_type: str,
    entity_id: int,
    message: str,
) -> dict:
    await record_event(
        session,
        company_id=company_id,
        user_id=user_id,
        entity_type=entity_type,
        entity_id=entity_id,
        event_type="comment",
        diff={"message": message},
    )
    await session.commit()

    event = await session.scalar(
        select(AuditEvent)
        .where(
            AuditEvent.company_id == company_id,
            AuditEvent.entity_type == entity_type,
            AuditEvent.entity_id == entity_id,
            AuditEvent.event_type == "comment",
        )
        .order_by(AuditEvent.id.desc())
        .limit(1)
    )

    module_labels = {
        "work_order": "Ordens de Serviço",
        "fiscal_request": "Solicitações Fiscais",
    }
    module_label = module_labels.get(entity_type, entity_type)

    if entity_type == "work_order":
        record = await session.scalar(
            select(WorkOrder).where(
                WorkOrder.id == entity_id,
                WorkOrder.company_id == company_id,
            )
        )
        if record:
            await notify_record_event(
                session,
                company_id=company_id,
                actor_name=user_name,
                actor_email=user_email,
                event="comment",
                title=record.title,
                module=module_label,
                owner_user_id=record.assigned_user_id,
                created_by_user_id=record.created_by_user_id,
                notify_user_ids=record.notify_user_ids,
                detail=message,
            )
    elif entity_type == "fiscal_request":
        record = await session.scalar(
            select(FiscalRequest).where(
                FiscalRequest.id == entity_id,
                FiscalRequest.company_id == company_id,
            )
        )
        if record:
            await notify_record_event(
                session,
                company_id=company_id,
                actor_name=user_name,
                actor_email=user_email,
                event="comment",
                title=record.title or record.request_type,
                module=module_label,
                owner_user_id=record.responsible_user_id,
                created_by_user_id=record.requester_user_id,
                detail=message,
            )

    from datetime import datetime

    return {
        "id": event.id if event else 0,
        "event_type": "comment",
        "user": user_name,
        "message": message,
        "created_at": event.created_at if event else datetime.now(),
    }
