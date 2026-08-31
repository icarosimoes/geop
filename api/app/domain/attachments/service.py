from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.audit import record_event
from app.core.storage import (
    build_object_key,
    delete_file,
    upload_file,
    validate_file,
)
from app.models import Attachment

ALLOWED_ENTITY_TYPES = {
    "work_order",
    "procedure",
    "module_record",
    "employee_payslip",
    "contract",
    "quote",
}


async def create_attachment(
    session: AsyncSession,
    company_id: int,
    user_id: int,
    *,
    entity_type: str,
    entity_id: int,
    filename: str,
    content_type: str,
    data: bytes,
    max_per_entity: int = 20,
    skip_audit: bool = False,
) -> Attachment | str:
    if entity_type not in ALLOWED_ENTITY_TYPES:
        return f"entity_type inválido: {entity_type}"

    error = validate_file(filename, content_type, len(data), data)
    if error:
        return error

    count = (
        await session.scalar(
            select(func.count(Attachment.id)).where(
                Attachment.company_id == company_id,
                Attachment.entity_type == entity_type,
                Attachment.entity_id == entity_id,
            )
        )
        or 0
    )
    if count >= max_per_entity:
        return f"Limite de {max_per_entity} anexos por registro atingido"

    key = build_object_key(company_id, entity_type, entity_id, filename)
    upload_file(data, key, content_type)

    record = Attachment(
        company_id=company_id,
        entity_type=entity_type,
        entity_id=entity_id,
        filename=filename,
        content_type=content_type,
        size_bytes=len(data),
        storage_key=key,
        uploaded_by_user_id=user_id,
    )
    session.add(record)
    if not skip_audit:
        await record_event(
            session,
            company_id=company_id,
            user_id=user_id,
            entity_type=entity_type,
            entity_id=entity_id,
            event_type="attachment_add",
            diff={"filename": filename, "content_type": content_type, "size_bytes": len(data)},
        )
    await session.commit()
    await session.refresh(record)
    return record


async def list_attachments(
    session: AsyncSession,
    company_id: int,
    entity_type: str,
    entity_id: int,
) -> tuple[list[Attachment], int]:
    filters = [
        Attachment.company_id == company_id,
        Attachment.entity_type == entity_type,
        Attachment.entity_id == entity_id,
    ]
    total = (
        await session.scalar(
            select(func.count(Attachment.id)).where(*filters),
        )
        or 0
    )
    records = (
        await session.scalars(
            select(Attachment).where(*filters).order_by(Attachment.created_at.asc())
        )
    ).all()
    return list(records), total


async def get_attachment(
    session: AsyncSession,
    company_id: int,
    attachment_id: int,
) -> Attachment | None:
    return await session.scalar(
        select(Attachment).where(
            Attachment.id == attachment_id,
            Attachment.company_id == company_id,
        )
    )


async def delete_attachment(
    session: AsyncSession,
    company_id: int,
    attachment_id: int,
    user_id: int | None = None,
) -> bool:
    record = await get_attachment(session, company_id, attachment_id)
    if record is None:
        return False
    delete_file(record.storage_key)
    if user_id is not None:
        await record_event(
            session,
            company_id=company_id,
            user_id=user_id,
            entity_type=record.entity_type,
            entity_id=record.entity_id,
            event_type="attachment_remove",
            diff={"filename": record.filename},
        )
    await session.delete(record)
    await session.commit()
    return True
