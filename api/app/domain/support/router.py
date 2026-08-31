from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth import current_user
from app.core.dependencies import require_session
from app.domain.auth.repository import AuthenticatedUser
from app.domain.support import service
from app.domain.support.schemas import (
    SupportRequestCreate,
    SupportRequestCreated,
    SupportRequestOut,
)

router = APIRouter(prefix="/support", tags=["support"])


@router.post("/request", response_model=SupportRequestCreated, status_code=201)
async def create_support_request(
    payload: SupportRequestCreate,
    user: Annotated[AuthenticatedUser, Depends(current_user)],
    session: Annotated[AsyncSession, Depends(require_session)],
) -> SupportRequestCreated:
    request = await service.create_support_request(
        session, company_id=user.company_id, user_id=user.id, payload=payload
    )
    return SupportRequestCreated(id=request.id, status=request.status)


@router.get("/requests", response_model=list[SupportRequestOut])
async def list_my_support_requests(
    user: Annotated[AuthenticatedUser, Depends(current_user)],
    session: Annotated[AsyncSession, Depends(require_session)],
) -> list[SupportRequestOut]:
    requests = await service.list_own_support_requests(
        session, company_id=user.company_id, user_id=user.id
    )
    return [
        SupportRequestOut(
            id=r.id,
            subject=r.subject,
            priority=r.priority,
            contact_name=r.contact_name,
            contact_whatsapp=r.contact_whatsapp,
            message=r.message,
            status=r.status,
            response_message=r.response_message,
            created_at=r.created_at,
            updated_at=r.updated_at,
        )
        for r in requests
    ]
