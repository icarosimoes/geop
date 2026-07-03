import secrets
from datetime import date, datetime, time, timedelta

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.audit import compute_diff, record_event
from app.core.cache import invalidate_dashboard
from app.models import (
    Location,
    TimeClockDevice,
    TimeClockEnrollment,
    TimePunch,
    User,
    WorkSchedule,
)

WEEKDAY_LABELS = ["Segunda", "Terça", "Quarta", "Quinta", "Sexta", "Sábado", "Domingo"]


# ---------------------------------------------------------------------------
# Escala de trabalho
# ---------------------------------------------------------------------------


async def get_schedule_for_user(
    session: AsyncSession, company_id: int, user_id: int
) -> list[WorkSchedule]:
    rows = (
        await session.execute(
            select(WorkSchedule)
            .where(
                WorkSchedule.company_id == company_id,
                WorkSchedule.user_id == user_id,
                WorkSchedule.deleted_at.is_(None),
            )
            .order_by(WorkSchedule.weekday)
        )
    ).scalars()
    return list(rows)


async def upsert_week(
    session: AsyncSession,
    company_id: int,
    actor_id: int,
    user_id: int,
    entries: list[dict],
) -> list[WorkSchedule]:
    # Inclui linhas com soft delete: a constraint única em
    # (company_id, user_id, weekday) não distingue deleted_at, então um dia
    # reativado precisa reaproveitar a linha existente em vez de inserir uma
    # nova (que colidiria com a linha antiga apagada).
    all_rows = (
        await session.execute(
            select(WorkSchedule).where(
                WorkSchedule.company_id == company_id, WorkSchedule.user_id == user_id
            )
        )
    ).scalars()
    existing = {row.weekday: row for row in all_rows}
    before = {
        weekday: f"{row.start_time}-{row.end_time}"
        for weekday, row in existing.items()
        if row.deleted_at is None
    }
    seen_weekdays = set()
    for entry in entries:
        weekday = entry["weekday"]
        seen_weekdays.add(weekday)
        row = existing.get(weekday)
        if row is None:
            row = WorkSchedule(company_id=company_id, user_id=user_id, weekday=weekday)
            session.add(row)
        row.start_time = entry["start_time"]
        row.end_time = entry["end_time"]
        row.break_start = entry.get("break_start")
        row.break_end = entry.get("break_end")
        row.tolerance_minutes = entry.get("tolerance_minutes", 10)
        row.active = True
        row.deleted_at = None
    for weekday, row in existing.items():
        if weekday not in seen_weekdays and row.deleted_at is None:
            row.deleted_at = datetime.now()

    await session.flush()
    after = {
        entry["weekday"]: f"{entry['start_time']}-{entry['end_time']}" for entry in entries
    }
    diff = compute_diff(before, after)
    if diff:
        await record_event(
            session,
            company_id=company_id,
            user_id=actor_id,
            entity_type="work_schedule",
            entity_id=user_id,
            event_type="update",
            diff=diff,
        )
    await session.commit()
    return await get_schedule_for_user(session, company_id, user_id)


# ---------------------------------------------------------------------------
# Comparação ponto x escala
# ---------------------------------------------------------------------------


def evaluate_status(
    entry: WorkSchedule | None, punched_at: datetime, punch_type: str | None
) -> str:
    if entry is None:
        return "unscheduled"

    tolerance = timedelta(minutes=entry.tolerance_minutes)
    punch_dt = datetime.combine(punched_at.date(), punched_at.time())
    start_dt = datetime.combine(punched_at.date(), entry.start_time)
    end_dt = datetime.combine(punched_at.date(), entry.end_time)

    if punch_type == "out":
        return "early_leave" if punch_dt < end_dt - tolerance else "on_time"
    if punch_type == "in":
        return "late" if punch_dt > start_dt + tolerance else "on_time"

    # Tipo não informado pelo relógio: assume o limite mais próximo do horário batido.
    distance_to_start = abs((punch_dt - start_dt).total_seconds())
    distance_to_end = abs((punch_dt - end_dt).total_seconds())
    if distance_to_start <= distance_to_end:
        return "late" if punch_dt > start_dt + tolerance else "on_time"
    return "early_leave" if punch_dt < end_dt - tolerance else "on_time"


# ---------------------------------------------------------------------------
# Dispositivos
# ---------------------------------------------------------------------------


async def list_devices(session: AsyncSession, company_id: int) -> list[tuple]:
    rows = await session.execute(
        select(TimeClockDevice, Location.name)
        .outerjoin(Location, Location.id == TimeClockDevice.location_id)
        .where(
            TimeClockDevice.company_id == company_id, TimeClockDevice.deleted_at.is_(None)
        )
        .order_by(TimeClockDevice.name)
    )
    return rows.all()


async def create_device(
    session: AsyncSession,
    company_id: int,
    actor_id: int,
    *,
    name: str,
    model: str,
    serial_number: str | None,
    location_id: int | None,
) -> TimeClockDevice:
    record = TimeClockDevice(
        company_id=company_id,
        name=name,
        model=model,
        serial_number=serial_number,
        location_id=location_id,
        webhook_token=secrets.token_hex(24),
    )
    session.add(record)
    await session.flush()
    await record_event(
        session,
        company_id=company_id,
        user_id=actor_id,
        entity_type="time_clock_device",
        entity_id=record.id,
        event_type="create",
    )
    await session.commit()
    await session.refresh(record)
    return record


async def update_device(
    session: AsyncSession, company_id: int, actor_id: int, device_id: int, updates: dict
) -> TimeClockDevice | None:
    record = await session.scalar(
        select(TimeClockDevice).where(
            TimeClockDevice.id == device_id,
            TimeClockDevice.company_id == company_id,
            TimeClockDevice.deleted_at.is_(None),
        )
    )
    if record is None:
        return None
    before = {k: str(getattr(record, k)) for k in updates}
    for field, value in updates.items():
        setattr(record, field, value)
    diff = compute_diff(before, {k: str(v) for k, v in updates.items()})
    if diff:
        await record_event(
            session,
            company_id=company_id,
            user_id=actor_id,
            entity_type="time_clock_device",
            entity_id=record.id,
            event_type="update",
            diff=diff,
        )
    await session.commit()
    await session.refresh(record)
    return record


async def delete_device(
    session: AsyncSession, company_id: int, actor_id: int, device_id: int
) -> bool:
    record = await session.scalar(
        select(TimeClockDevice).where(
            TimeClockDevice.id == device_id,
            TimeClockDevice.company_id == company_id,
            TimeClockDevice.deleted_at.is_(None),
        )
    )
    if record is None:
        return False
    record.deleted_at = datetime.now()
    await record_event(
        session,
        company_id=company_id,
        user_id=actor_id,
        entity_type="time_clock_device",
        entity_id=record.id,
        event_type="delete",
    )
    await session.commit()
    return True


async def get_device_by_token(session: AsyncSession, webhook_token: str) -> TimeClockDevice | None:
    return await session.scalar(
        select(TimeClockDevice).where(
            TimeClockDevice.webhook_token == webhook_token,
            TimeClockDevice.deleted_at.is_(None),
            TimeClockDevice.active.is_(True),
        )
    )


# ---------------------------------------------------------------------------
# Vínculos funcionário <-> matrícula do relógio
# ---------------------------------------------------------------------------


async def list_enrollments(session: AsyncSession, company_id: int) -> list[tuple]:
    rows = await session.execute(
        select(TimeClockEnrollment, User.name)
        .join(User, User.id == TimeClockEnrollment.user_id)
        .where(TimeClockEnrollment.company_id == company_id)
        .order_by(User.name)
    )
    return rows.all()


async def create_enrollment(
    session: AsyncSession, company_id: int, actor_id: int, *, user_id: int, external_id: str
) -> TimeClockEnrollment:
    record = TimeClockEnrollment(company_id=company_id, user_id=user_id, external_id=external_id)
    session.add(record)
    await session.flush()
    await record_event(
        session,
        company_id=company_id,
        user_id=actor_id,
        entity_type="time_clock_enrollment",
        entity_id=record.id,
        event_type="create",
    )
    await session.commit()
    await session.refresh(record)
    return record


async def delete_enrollment(
    session: AsyncSession, company_id: int, actor_id: int, enrollment_id: int
) -> bool:
    record = await session.scalar(
        select(TimeClockEnrollment).where(
            TimeClockEnrollment.id == enrollment_id,
            TimeClockEnrollment.company_id == company_id,
        )
    )
    if record is None:
        return False
    await session.delete(record)
    await record_event(
        session,
        company_id=company_id,
        user_id=actor_id,
        entity_type="time_clock_enrollment",
        entity_id=enrollment_id,
        event_type="delete",
    )
    await session.commit()
    return True


# ---------------------------------------------------------------------------
# Batidas
# ---------------------------------------------------------------------------


async def _schedule_entry_for(
    session: AsyncSession, company_id: int, user_id: int, punched_at: datetime
) -> WorkSchedule | None:
    return await session.scalar(
        select(WorkSchedule).where(
            WorkSchedule.company_id == company_id,
            WorkSchedule.user_id == user_id,
            WorkSchedule.weekday == punched_at.weekday(),
            WorkSchedule.active.is_(True),
            WorkSchedule.deleted_at.is_(None),
        )
    )


async def ingest_punch(
    session: AsyncSession,
    *,
    company_id: int,
    device: TimeClockDevice,
    external_id: str,
    punched_at: datetime,
    punch_type: str | None,
    external_event_id: str | None,
    raw_payload: dict,
) -> TimePunch:
    if external_event_id:
        existing = await session.scalar(
            select(TimePunch).where(
                TimePunch.device_id == device.id,
                TimePunch.external_event_id == external_event_id,
            )
        )
        if existing is not None:
            return existing

    user_id = await session.scalar(
        select(TimeClockEnrollment.user_id).where(
            TimeClockEnrollment.company_id == company_id,
            TimeClockEnrollment.external_id == external_id,
        )
    )
    status = "unscheduled"
    if user_id:
        entry = await _schedule_entry_for(session, company_id, user_id, punched_at)
        status = evaluate_status(entry, punched_at, punch_type)

    record = TimePunch(
        company_id=company_id,
        user_id=user_id,
        device_id=device.id,
        punched_at=punched_at,
        punch_type=punch_type,
        source="device",
        external_event_id=external_event_id,
        status=status,
        raw_payload=raw_payload,
    )
    session.add(record)
    try:
        await session.commit()
    except IntegrityError:
        await session.rollback()
        existing = await session.scalar(
            select(TimePunch).where(
                TimePunch.device_id == device.id,
                TimePunch.external_event_id == external_event_id,
            )
        )
        if existing is not None:
            return existing
        raise
    await invalidate_dashboard(company_id)
    await session.refresh(record)
    return record


async def create_manual_punch(
    session: AsyncSession,
    company_id: int,
    actor_id: int,
    *,
    user_id: int,
    punched_at: datetime,
    punch_type: str | None,
    notes: str | None,
) -> TimePunch:
    entry = await _schedule_entry_for(session, company_id, user_id, punched_at)
    status = evaluate_status(entry, punched_at, punch_type)
    record = TimePunch(
        company_id=company_id,
        user_id=user_id,
        device_id=None,
        punched_at=punched_at,
        punch_type=punch_type,
        source="manual",
        status=status,
        created_by_user_id=actor_id,
        notes=notes,
    )
    session.add(record)
    await session.flush()
    await record_event(
        session,
        company_id=company_id,
        user_id=actor_id,
        entity_type="time_punch",
        entity_id=record.id,
        event_type="create",
    )
    await session.commit()
    await invalidate_dashboard(company_id)
    await session.refresh(record)
    return record


async def update_punch(
    session: AsyncSession, company_id: int, actor_id: int, punch_id: int, updates: dict
) -> TimePunch | None:
    record = await session.scalar(
        select(TimePunch).where(TimePunch.id == punch_id, TimePunch.company_id == company_id)
    )
    if record is None:
        return None
    before = {k: str(getattr(record, k)) for k in updates}
    for field, value in updates.items():
        setattr(record, field, value)
    if record.user_id:
        entry = await _schedule_entry_for(session, company_id, record.user_id, record.punched_at)
        record.status = evaluate_status(entry, record.punched_at, record.punch_type)
    diff = compute_diff(before, {k: str(v) for k, v in updates.items()})
    if diff:
        await record_event(
            session,
            company_id=company_id,
            user_id=actor_id,
            entity_type="time_punch",
            entity_id=record.id,
            event_type="update",
            diff=diff,
        )
    await session.commit()
    await invalidate_dashboard(company_id)
    await session.refresh(record)
    return record


async def list_punches(
    session: AsyncSession,
    company_id: int,
    page: int,
    page_size: int,
    *,
    user_id: int | None = None,
    date_from: date | None = None,
    date_to: date | None = None,
    status: str | None = None,
) -> tuple[list[tuple], int]:
    from sqlalchemy import func

    filters = [TimePunch.company_id == company_id]
    if user_id is not None:
        filters.append(TimePunch.user_id == user_id)
    if date_from is not None:
        filters.append(TimePunch.punched_at >= datetime.combine(date_from, time.min))
    if date_to is not None:
        filters.append(TimePunch.punched_at <= datetime.combine(date_to, time.max))
    if status is not None:
        filters.append(TimePunch.status == status)

    total = await session.scalar(select(func.count(TimePunch.id)).where(*filters)) or 0
    rows = (
        await session.execute(
            select(TimePunch, User.name, TimeClockDevice.name)
            .outerjoin(User, User.id == TimePunch.user_id)
            .outerjoin(TimeClockDevice, TimeClockDevice.id == TimePunch.device_id)
            .where(*filters)
            .order_by(TimePunch.punched_at.desc())
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
    ).all()
    return rows, total


async def monthly_summary(
    session: AsyncSession, company_id: int, user_id: int, year: int, month: int
) -> list[dict]:
    from calendar import monthrange

    schedule_rows = await get_schedule_for_user(session, company_id, user_id)
    schedule = {row.weekday: row for row in schedule_rows}
    days_in_month = monthrange(year, month)[1]

    first_day = date(year, month, 1)
    last_day = date(year, month, days_in_month)
    rows = (
        await session.execute(
            select(TimePunch)
            .where(
                TimePunch.company_id == company_id,
                TimePunch.user_id == user_id,
                TimePunch.punched_at >= datetime.combine(first_day, time.min),
                TimePunch.punched_at <= datetime.combine(last_day, time.max),
            )
            .order_by(TimePunch.punched_at)
        )
    ).scalars()
    punches_by_day: dict[date, list[TimePunch]] = {}
    for punch in rows:
        punches_by_day.setdefault(punch.punched_at.date(), []).append(punch)

    summary = []
    for day_num in range(1, days_in_month + 1):
        current = date(year, month, day_num)
        entry = schedule.get(current.weekday())
        day_punches = punches_by_day.get(current, [])
        if entry is None and not day_punches:
            continue
        statuses = {p.status for p in day_punches if p.status}
        if not day_punches:
            day_status = "absent" if entry else "unscheduled"
        elif "late" in statuses or "early_leave" in statuses:
            day_status = "late" if "late" in statuses else "early_leave"
        else:
            day_status = "on_time"
        summary.append(
            {
                "date": current,
                "expected_start": entry.start_time if entry else None,
                "expected_end": entry.end_time if entry else None,
                "punches": [p.punched_at for p in day_punches],
                "status": day_status,
                "worked_minutes": None,
                "delay_minutes": None,
            }
        )
    return summary
