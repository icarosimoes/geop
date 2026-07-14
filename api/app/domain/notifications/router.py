from datetime import datetime
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth import current_user
from app.core.dependencies import require_session
from app.domain.auth.repository import AuthenticatedUser
from app.domain.notifications.schemas import (
    NotificationListResponse,
    NotificationOut,
    PreferenceOut,
    PreferenceUpdate,
)
from app.models import Notification, NotificationPreference

router = APIRouter(prefix="/notifications", tags=["notifications"])

VALID_MODULES = [
    "work_orders",
    "fiscal_requests",
    "meetings",
    "shift_reports",
    "procedures",
    "inspections",
    "maintenance",
    "modules",
]


@router.get("", response_model=NotificationListResponse)
async def list_notifications(
    user: Annotated[AuthenticatedUser, Depends(current_user)],
    session: Annotated[AsyncSession, Depends(require_session)],
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=100)] = 20,
    unread_only: bool = False,
) -> NotificationListResponse:
    base_filters = [
        Notification.company_id == user.company_id,
        Notification.user_id == user.id,
    ]
    filters = list(base_filters)
    if unread_only:
        filters.append(Notification.read_at.is_(None))

    total = await session.scalar(select(func.count(Notification.id)).where(*filters)) or 0
    unread = (
        await session.scalar(
            select(func.count(Notification.id)).where(*base_filters, Notification.read_at.is_(None))
        )
        or 0
    )

    rows = (
        await session.scalars(
            select(Notification)
            .where(*filters)
            .order_by(Notification.created_at.desc(), Notification.id.desc())
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
    ).all()
    return NotificationListResponse(
        items=[
            NotificationOut(
                id=n.id,
                title=n.title,
                body=n.body,
                category=n.category,
                entity_type=n.entity_type,
                entity_id=n.entity_id,
                read_at=n.read_at,
                email_sent_at=n.email_sent_at,
                created_at=n.created_at,
            )
            for n in rows
        ],
        total=total,
        unread=unread,
        page=page,
        page_size=page_size,
    )


@router.patch("/{notification_id}/read", response_model=NotificationOut)
async def mark_as_read(
    notification_id: int,
    user: Annotated[AuthenticatedUser, Depends(current_user)],
    session: Annotated[AsyncSession, Depends(require_session)],
) -> NotificationOut:
    record = await session.scalar(
        select(Notification).where(
            Notification.id == notification_id,
            Notification.company_id == user.company_id,
            Notification.user_id == user.id,
        )
    )
    if record is None:
        raise HTTPException(status_code=404, detail={"code": "not_found"})
    if record.read_at is None:
        record.read_at = datetime.now()
        await session.commit()
        await session.refresh(record)
    return NotificationOut(
        id=record.id,
        title=record.title,
        body=record.body,
        category=record.category,
        entity_type=record.entity_type,
        entity_id=record.entity_id,
        read_at=record.read_at,
        email_sent_at=record.email_sent_at,
        created_at=record.created_at,
    )


@router.post("/read-all", status_code=204)
async def mark_all_as_read(
    user: Annotated[AuthenticatedUser, Depends(current_user)],
    session: Annotated[AsyncSession, Depends(require_session)],
) -> None:
    await session.execute(
        update(Notification)
        .where(
            Notification.company_id == user.company_id,
            Notification.user_id == user.id,
            Notification.read_at.is_(None),
        )
        .values(read_at=datetime.now())
    )
    await session.commit()


# ── Preferências de notificação ──


@router.get("/preferences", response_model=list[PreferenceOut])
async def list_preferences(
    user: Annotated[AuthenticatedUser, Depends(current_user)],
    session: Annotated[AsyncSession, Depends(require_session)],
) -> list[PreferenceOut]:
    rows = (
        await session.scalars(
            select(NotificationPreference).where(
                NotificationPreference.company_id == user.company_id,
                NotificationPreference.user_id == user.id,
            )
        )
    ).all()
    saved = {r.module: r for r in rows}
    result: list[PreferenceOut] = []
    for mod in VALID_MODULES:
        if mod in saved:
            r = saved[mod]
            result.append(PreferenceOut(module=mod, in_app=r.in_app, email=r.email))
        else:
            result.append(PreferenceOut(module=mod, in_app=True, email=True))
    return result


@router.put("/preferences/{module}", response_model=PreferenceOut)
async def update_preference(
    module: str,
    body: PreferenceUpdate,
    user: Annotated[AuthenticatedUser, Depends(current_user)],
    session: Annotated[AsyncSession, Depends(require_session)],
) -> PreferenceOut:
    if module not in VALID_MODULES:
        raise HTTPException(status_code=400, detail={"code": "invalid_module"})
    row = await session.scalar(
        select(NotificationPreference).where(
            NotificationPreference.company_id == user.company_id,
            NotificationPreference.user_id == user.id,
            NotificationPreference.module == module,
        )
    )
    if row:
        row.in_app = body.in_app
        row.email = body.email
    else:
        row = NotificationPreference(
            company_id=user.company_id,
            user_id=user.id,
            module=module,
            in_app=body.in_app,
            email=body.email,
        )
        session.add(row)
    await session.commit()
    return PreferenceOut(module=module, in_app=row.in_app, email=row.email)
