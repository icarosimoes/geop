from datetime import UTC, datetime
from uuid import uuid4

from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.audit import compute_diff, record_event
from app.core.cache import invalidate_dashboard
from app.core.sla import calculate_business_deadline, pause_sla, resume_sla
from app.models import Company, FiscalRequest, User


async def _get_company_timezone(session: AsyncSession, company_id: int) -> str:
    tz = await session.scalar(select(Company.timezone).where(Company.id == company_id))
    return tz or "America/Sao_Paulo"


async def list_fiscal_requests(
    session: AsyncSession,
    company_id: int,
    page: int,
    page_size: int,
    search: str | None = None,
) -> tuple[list[FiscalRequest], int]:
    filters = [FiscalRequest.company_id == company_id]
    if search:
        pattern = f"%{search.strip()}%"
        filters.append(
            or_(
                FiscalRequest.protocol.ilike(pattern),
                FiscalRequest.requester.ilike(pattern),
                FiscalRequest.request_type.ilike(pattern),
            )
        )
    total = await session.scalar(select(func.count(FiscalRequest.id)).where(*filters)) or 0
    records = (
        await session.scalars(
            select(FiscalRequest)
            .where(*filters)
            .order_by(FiscalRequest.created_at.desc(), FiscalRequest.id.desc())
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
    ).all()
    return list(records), total


async def create_fiscal_request(
    session: AsyncSession,
    company_id: int,
    user_id: int,
    *,
    request_type: str,
    title: str,
    apartment: str | None,
    requester: str,
    description: str | None,
    status: str,
    payload: dict,
) -> FiscalRequest:
    timezone = await _get_company_timezone(session, company_id)
    sla_deadline = calculate_business_deadline(datetime.now(UTC), timezone=timezone)
    record = FiscalRequest(
        company_id=company_id,
        protocol=f"TMP-{uuid4().hex}",
        request_type=request_type,
        title=title,
        apartment=apartment,
        requester=requester,
        description=description,
        origin="registro",
        status=status,
        sla_deadline=sla_deadline,
        payload=payload,
    )
    session.add(record)
    await session.flush()
    record.protocol = f"REG-{record.id:06d}"
    await record_event(
        session,
        company_id=company_id,
        user_id=user_id,
        entity_type="fiscal_request",
        entity_id=record.id,
        event_type="create",
    )
    await session.commit()
    await invalidate_dashboard(company_id)
    await session.refresh(record)
    return record


async def update_fiscal_request(
    session: AsyncSession,
    company_id: int,
    user_id: int,
    request_id: int,
    updates: dict,
) -> FiscalRequest | None:
    record = await session.scalar(
        select(FiscalRequest).where(
            FiscalRequest.id == request_id,
            FiscalRequest.company_id == company_id,
        )
    )
    if record is None:
        return None
    before = {k: str(getattr(record, k)) for k in updates}
    if record.responsible_user_id is None:
        record.responsible_user_id = user_id
        before["responsible_user_id"] = None
        updates["responsible_user_id"] = user_id

    new_status = updates.get("status")
    if new_status:
        if new_status.casefold() == "em espera" and record.sla_paused_at is None:
            pause_sla(record)
        elif new_status.casefold() != "em espera" and record.sla_paused_at is not None:
            resume_sla(record)

    for field, value in updates.items():
        setattr(record, field, value)
    diff = compute_diff(before, {k: str(v) for k, v in updates.items()})
    if diff:
        await record_event(
            session,
            company_id=company_id,
            user_id=user_id,
            entity_type="fiscal_request",
            entity_id=record.id,
            event_type="update",
            diff=diff,
        )
    await session.commit()
    await invalidate_dashboard(company_id)
    await session.refresh(record)
    return record


async def delete_fiscal_request(
    session: AsyncSession,
    company_id: int,
    user_id: int,
    request_id: int,
) -> bool:
    record = await session.scalar(
        select(FiscalRequest).where(
            FiscalRequest.id == request_id,
            FiscalRequest.company_id == company_id,
        )
    )
    if record is None:
        return False
    await record_event(
        session,
        company_id=company_id,
        user_id=user_id,
        entity_type="fiscal_request",
        entity_id=record.id,
        event_type="delete",
    )
    await session.delete(record)
    await session.commit()
    await invalidate_dashboard(company_id)
    return True
