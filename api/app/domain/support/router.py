from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth import current_user
from app.core.dependencies import require_session
from app.domain.auth.repository import AuthenticatedUser
from app.domain.support.schemas import SupportRequestCreate, SupportRequestCreated
from app.models import SupportRequest

router = APIRouter(prefix="/support", tags=["support"])


@router.post("/request", response_model=SupportRequestCreated, status_code=201)
async def create_support_request(
    payload: SupportRequestCreate,
    user: Annotated[AuthenticatedUser, Depends(current_user)],
    session: Annotated[AsyncSession, Depends(require_session)],
) -> SupportRequestCreated:
    request = SupportRequest(
        company_id=user.company_id,
        user_id=user.id,
        contact_name=payload.contact_name,
        contact_whatsapp=payload.contact_whatsapp,
        message=payload.message,
    )
    session.add(request)
    await session.commit()
    await session.refresh(request)
    return SupportRequestCreated(id=request.id, status=request.status)
