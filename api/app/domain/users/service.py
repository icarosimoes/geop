import logging
import secrets
from datetime import datetime
from typing import NamedTuple

import bcrypt
from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.audit import compute_diff, record_event
from app.core.config import get_settings
from app.core.storage import build_object_key, upload_file, validate_file
from app.models import Role, Sector, User


class UserRow(NamedTuple):
    user: User
    role_name: str | None
    sector_name: str | None


logger = logging.getLogger(__name__)


async def _role_name(session: AsyncSession, role_id: int | None) -> str | None:
    if not role_id:
        return None
    return await session.scalar(select(Role.name).where(Role.id == role_id))


async def list_users(
    session: AsyncSession,
    company_id: int,
    page: int,
    page_size: int,
    search: str | None = None,
) -> tuple[list[UserRow], int]:
    filters = [User.company_id == company_id, User.deleted_at.is_(None)]
    if search:
        pattern = f"%{search.strip()}%"
        filters.append(or_(User.name.ilike(pattern), User.email.ilike(pattern)))
    total = await session.scalar(select(func.count(User.id)).where(*filters)) or 0
    rows = (
        await session.execute(
            select(User, Role.name, Sector.name)
            .outerjoin(Role, Role.id == User.role_id)
            .outerjoin(Sector, Sector.id == User.sector_id)
            .where(*filters)
            .order_by(User.name)
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
    ).all()
    return rows, total


async def search_users(
    session: AsyncSession,
    company_id: int,
    q: str,
) -> list[User]:
    filters = [User.company_id == company_id, User.deleted_at.is_(None), User.active.is_(True)]
    if q.strip():
        pattern = f"%{q.strip()}%"
        filters.append(or_(User.name.ilike(pattern), User.email.ilike(pattern)))
    rows = (
        (await session.execute(select(User).where(*filters).order_by(User.name).limit(10)))
        .scalars()
        .all()
    )
    return list(rows)


async def create_user(
    session: AsyncSession,
    company_id: int,
    actor_id: int,
    *,
    name: str,
    email: str,
    phone: str | None,
    password: str,
    role_id: int | None,
    active: bool,
    job_title: str | None = None,
    sector_id: int | None = None,
) -> User | None:
    existing = await session.scalar(
        select(User.id).where(
            User.company_id == company_id,
            User.email == email.lower(),
            User.deleted_at.is_(None),
        )
    )
    if existing:
        return None

    password_hash = bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()
    record = User(
        company_id=company_id,
        name=name,
        email=email.lower(),
        phone=phone,
        password=password_hash,
        role_id=role_id,
        active=active,
        job_title=job_title,
        sector_id=sector_id,
    )
    session.add(record)
    await session.flush()
    await record_event(
        session,
        company_id=company_id,
        user_id=actor_id,
        entity_type="user",
        entity_id=record.id,
        event_type="create",
    )
    await session.commit()
    await session.refresh(record)
    return record


async def update_user(
    session: AsyncSession,
    company_id: int,
    actor_id: int,
    user_id: int,
    updates: dict,
) -> User | None:
    record = await session.scalar(
        select(User).where(
            User.id == user_id,
            User.company_id == company_id,
            User.deleted_at.is_(None),
        )
    )
    if record is None:
        return None

    if "password" in updates:
        updates["password"] = bcrypt.hashpw(updates["password"].encode(), bcrypt.gensalt()).decode()

    before = {}
    for k in updates:
        before[k] = "***" if k == "password" else str(getattr(record, k))

    for field, value in updates.items():
        setattr(record, field, value)

    after = {k: "***" if k == "password" else str(v) for k, v in updates.items()}
    diff = compute_diff(before, after)
    if diff:
        await record_event(
            session,
            company_id=company_id,
            user_id=actor_id,
            entity_type="user",
            entity_id=record.id,
            event_type="update",
            diff=diff,
        )
    await session.commit()
    await session.refresh(record)
    return record


async def update_profile(
    session: AsyncSession,
    user_id: int,
    company_id: int,
    updates: dict,
) -> User | None:
    record = await session.scalar(
        select(User).where(
            User.id == user_id,
            User.company_id == company_id,
            User.deleted_at.is_(None),
        )
    )
    if record is None:
        return None

    if "password" in updates:
        updates["password"] = bcrypt.hashpw(updates["password"].encode(), bcrypt.gensalt()).decode()

    before = {k: ("***" if k == "password" else str(getattr(record, k))) for k in updates}
    for field, value in updates.items():
        setattr(record, field, value)
    after = {k: ("***" if k == "password" else str(v)) for k, v in updates.items()}
    diff = compute_diff(before, after)
    if diff:
        await record_event(
            session,
            company_id=company_id,
            user_id=user_id,
            entity_type="user",
            entity_id=record.id,
            event_type="update_profile",
            diff=diff,
        )
    await session.commit()
    await session.refresh(record)
    return record


async def delete_user(
    session: AsyncSession,
    company_id: int,
    actor_id: int,
    user_id: int,
) -> bool:
    record = await session.scalar(
        select(User).where(
            User.id == user_id,
            User.company_id == company_id,
            User.deleted_at.is_(None),
        )
    )
    if record is None:
        return False
    record.deleted_at = datetime.now()
    record.active = False
    await record_event(
        session,
        company_id=company_id,
        user_id=actor_id,
        entity_type="user",
        entity_id=record.id,
        event_type="delete",
    )
    await session.commit()
    return True


async def get_role_name(session: AsyncSession, role_id: int | None) -> str | None:
    return await _role_name(session, role_id)


async def get_sector_name(session: AsyncSession, sector_id: int | None) -> str | None:
    if not sector_id:
        return None
    return await session.scalar(
        select(Sector.name).where(Sector.id == sector_id, Sector.deleted_at.is_(None))
    )


async def invite_user(
    session: AsyncSession,
    company_id: int,
    actor_id: int,
    *,
    name: str,
    email: str,
    phone: str | None = None,
    role_id: int | None = None,
    job_title: str | None = None,
    sector_id: int | None = None,
    active: bool = True,
) -> User | None:
    temp_password = secrets.token_urlsafe(24)
    record = await create_user(
        session,
        company_id,
        actor_id,
        name=name,
        email=email,
        phone=phone,
        password=temp_password,
        role_id=role_id,
        active=active,
        job_title=job_title,
        sector_id=sector_id,
    )
    if record is None:
        return None

    from app.core.security import create_invite_token

    settings = get_settings()
    token = create_invite_token(
        user_id=record.id,
        company_id=company_id,
        secret=settings.jwt_secret,
    )
    invite_url = f"{settings.registro_web_url}/definir-senha?token={token}"

    from app.domain.platform.service import get_effective_email_config
    from app.integrations.brevo import send_email

    api_key, from_address, from_name = await get_effective_email_config(session, settings)
    await send_email(
        api_key=api_key,
        from_address=from_address,
        from_name=from_name,
        to_email=record.email,
        to_name=record.name,
        subject="Bem-vindo ao GEOP — Defina sua senha",
        html=(
            f"<h2>Bem-vindo ao GEOP</h2>"
            f"<p>Olá {record.name},</p>"
            f"<p>Você foi convidado para acessar o sistema. "
            f"Clique no link abaixo para definir sua senha:</p>"
            f'<p><a href="{invite_url}">Definir minha senha</a></p>'
            f"<p>Este link expira em 48 horas.</p>"
        ),
    )
    logger.info("invite_sent user_id=%s email=%s", record.id, record.email)
    return record


async def upload_avatar(
    session: AsyncSession,
    company_id: int,
    actor_id: int,
    user_id: int,
    *,
    data: bytes,
    filename: str,
    content_type: str,
) -> User | None:
    record = await session.scalar(
        select(User).where(
            User.id == user_id,
            User.company_id == company_id,
            User.deleted_at.is_(None),
        )
    )
    if record is None:
        return None

    error = validate_file(filename, content_type, len(data), data)
    if error:
        raise ValueError(error)

    if content_type not in {"image/jpeg", "image/png", "image/webp"}:
        raise ValueError("Avatar deve ser JPEG, PNG ou WebP")

    settings = get_settings()
    key = build_object_key(company_id, "avatar", user_id, filename)
    upload_file(data, key, content_type)

    old_url = record.avatar_url
    record.avatar_url = f"{settings.s3_public_url}/{settings.s3_bucket}/{key}"

    await record_event(
        session,
        company_id=company_id,
        user_id=actor_id,
        entity_type="user",
        entity_id=record.id,
        event_type="update",
        diff={"avatar_url": {"from": old_url or "", "to": record.avatar_url}},
    )
    await session.commit()
    await session.refresh(record)
    return record
