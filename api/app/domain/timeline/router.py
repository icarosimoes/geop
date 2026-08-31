from datetime import datetime
from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth import current_user
from app.core.dependencies import require_session
from app.domain.auth.repository import AuthenticatedUser
from app.domain.timeline.service import (
    VALID_ENTITY_TYPES,
    add_comment,
    get_timeline,
    get_timeline_cursor,
    verify_entity_access,
)

router = APIRouter(prefix="/timeline", tags=["timeline"])


class TimelineEntry(BaseModel):
    id: int
    event_type: str
    user: str
    message: str | None = None
    changes: dict[str, Any] | None = None
    created_at: datetime


class TimelineResponse(BaseModel):
    items: list[TimelineEntry]


class TimelineCursorResponse(BaseModel):
    items: list[TimelineEntry]
    next_cursor: str | None
    has_more: bool


class CommentCreate(BaseModel):
    message: str


@router.get("/{entity_type}/{entity_id}/cursor", response_model=TimelineCursorResponse)
async def get_timeline_cursor_endpoint(
    entity_type: str,
    entity_id: int,
    user: Annotated[AuthenticatedUser, Depends(current_user)],
    session: Annotated[AsyncSession, Depends(require_session)],
    limit: Annotated[int, Query(ge=1, le=200)] = 50,
    cursor: str | None = None,
) -> TimelineCursorResponse:
    if entity_type not in VALID_ENTITY_TYPES:
        raise HTTPException(status_code=400, detail={"code": "invalid_entity_type"})
    if not await verify_entity_access(session, entity_type, entity_id, user.company_id, user.id):
        raise HTTPException(status_code=404, detail={"code": "not_found"})

    result = await get_timeline_cursor(
        session, user.company_id, entity_type, entity_id, limit, cursor
    )
    return TimelineCursorResponse(
        items=[TimelineEntry(**item) for item in result.items],
        next_cursor=result.next_cursor,
        has_more=result.has_more,
    )


@router.get("/{entity_type}/{entity_id}", response_model=TimelineResponse)
async def get_timeline_endpoint(
    entity_type: str,
    entity_id: int,
    user: Annotated[AuthenticatedUser, Depends(current_user)],
    session: Annotated[AsyncSession, Depends(require_session)],
) -> TimelineResponse:
    if entity_type not in VALID_ENTITY_TYPES:
        raise HTTPException(status_code=400, detail={"code": "invalid_entity_type"})
    if not await verify_entity_access(session, entity_type, entity_id, user.company_id, user.id):
        raise HTTPException(status_code=404, detail={"code": "not_found"})

    items = await get_timeline(session, user.company_id, entity_type, entity_id)
    return TimelineResponse(items=[TimelineEntry(**item) for item in items])


@router.post("/{entity_type}/{entity_id}/comment", response_model=TimelineEntry, status_code=201)
async def add_comment_endpoint(
    entity_type: str,
    entity_id: int,
    body: CommentCreate,
    user: Annotated[AuthenticatedUser, Depends(current_user)],
    session: Annotated[AsyncSession, Depends(require_session)],
) -> TimelineEntry:
    if entity_type not in VALID_ENTITY_TYPES:
        raise HTTPException(status_code=400, detail={"code": "invalid_entity_type"})
    if not body.message.strip():
        raise HTTPException(status_code=422, detail={"code": "empty_message"})
    if not await verify_entity_access(session, entity_type, entity_id, user.company_id, user.id):
        raise HTTPException(status_code=404, detail={"code": "not_found"})

    result = await add_comment(
        session,
        user.company_id,
        user.id,
        user.name,
        user.email,
        entity_type,
        entity_id,
        body.message.strip(),
    )
    return TimelineEntry(**result)
