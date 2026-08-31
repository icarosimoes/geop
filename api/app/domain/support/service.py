from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.support.schemas import SupportRequestCreate
from app.models import SupportRequest


async def create_support_request(
    session: AsyncSession,
    *,
    company_id: int,
    user_id: int,
    payload: SupportRequestCreate,
) -> SupportRequest:
    request = SupportRequest(
        company_id=company_id,
        user_id=user_id,
        subject=payload.subject,
        priority=payload.priority,
        contact_name=payload.contact_name,
        contact_whatsapp=payload.contact_whatsapp,
        message=payload.message,
    )
    session.add(request)
    await session.commit()
    await session.refresh(request)
    return request


async def list_own_support_requests(
    session: AsyncSession,
    *,
    company_id: int,
    user_id: int,
) -> list[SupportRequest]:
    rows = await session.execute(
        select(SupportRequest)
        .where(SupportRequest.company_id == company_id, SupportRequest.user_id == user_id)
        .order_by(SupportRequest.created_at.desc())
    )
    return list(rows.scalars().all())
