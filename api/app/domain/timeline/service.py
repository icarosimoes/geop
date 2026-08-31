from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.audit import record_event
from app.core.pagination import CursorPage, decode_cursor, encode_cursor
from app.integrations.notifications import notify_record_event
from app.models import (
    AuditEvent,
    Employee,
    Meeting,
    ModuleRecord,
    Procedure,
    ShiftReport,
    SupportRequest,
    User,
    WorkOrder,
)

VALID_ENTITY_TYPES = {
    "work_order",
    "procedure",
    "meeting",
    "shift_report",
    "inspecoes",
    "diarios-obra",
    "manutencao",
    "mural",
    "employee",
    "support_request",
}

ENTITY_MODEL_MAP: dict[str, Any] = {
    "work_order": WorkOrder,
    "procedure": Procedure,
    "meeting": Meeting,
    "shift_report": ShiftReport,
    "employee": Employee,
    "support_request": SupportRequest,
}

# Chamados de suporte são pessoais (só o autor + a plataforma veem/comentam) —
# diferente do resto do timeline, que é por empresa. `verify_entity_access`
# aplica esse filtro extra só pra este entity_type quando `user_id` é passado.
OWNER_SCOPED_ENTITY_TYPES = {"support_request"}

MODULE_SLUG_ENTITY_TYPES = {
    "inspecoes",
    "diarios-obra",
    "manutencao",
    "mural",
}


async def verify_entity_access(
    session: AsyncSession,
    entity_type: str,
    entity_id: int,
    company_id: int,
    user_id: int | None = None,
) -> bool:
    if entity_type in ENTITY_MODEL_MAP:
        model = ENTITY_MODEL_MAP[entity_type]
        filters = [model.id == entity_id, model.company_id == company_id]
        if hasattr(model, "deleted_at"):
            filters.append(model.deleted_at.is_(None))
        if entity_type in OWNER_SCOPED_ENTITY_TYPES and user_id is not None:
            filters.append(model.user_id == user_id)
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


def _serialize_event(event: AuditEvent, user_name: str | None) -> dict:
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
    return {
        "id": event.id,
        "event_type": event.event_type,
        # user_name vem do join com User (ator do tenant); actor_name é o
        # fallback pra atores sem linha em `users` (ex.: admin da plataforma) —
        # ver app/models/operations.py::AuditEvent.
        "user": user_name or event.actor_name or "—",
        "message": message,
        "changes": changes,
        "created_at": event.created_at,
    }


async def get_timeline(
    session: AsyncSession,
    company_id: int,
    entity_type: str,
    entity_id: int,
) -> list[dict]:
    rows = (
        await session.execute(
            select(AuditEvent, User.name)
            .outerjoin(User, User.id == AuditEvent.user_id)
            .where(
                AuditEvent.company_id == company_id,
                AuditEvent.entity_type == entity_type,
                AuditEvent.entity_id == entity_id,
            )
            .order_by(AuditEvent.created_at.asc(), AuditEvent.id.asc())
        )
    ).all()
    return [_serialize_event(event, user_name) for event, user_name in rows]


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
            .outerjoin(User, User.id == AuditEvent.user_id)
            .where(*filters)
            .order_by(AuditEvent.created_at.asc(), AuditEvent.id.asc())
            .limit(limit + 1)
        )
    ).all()

    has_more = len(rows) > limit
    rows = rows[:limit]
    items = [_serialize_event(event, user_name) for event, user_name in rows]

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
    event = await record_event(
        session,
        company_id=company_id,
        user_id=user_id,
        entity_type=entity_type,
        entity_id=entity_id,
        event_type="comment",
        diff={"message": message},
    )

    module_labels = {
        "work_order": "Ordens de Serviço",
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

    await session.commit()

    assert event is not None  # event_type="comment" sempre tem diff não-vazio
    return {
        "id": event.id,
        "event_type": "comment",
        "user": user_name,
        "message": message,
        "created_at": event.created_at,
    }
