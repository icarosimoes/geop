import secrets
from datetime import date, datetime, time, timedelta

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.audit import compute_diff, record_event
from app.core.cache import invalidate_dashboard
from app.domain.timeclock.schemas import RotatingPattern, WeeklyPattern
from app.models import (
    Location,
    ScheduleEntry,
    Sector,
    Shift,
    TimeClockDevice,
    TimeClockEnrollment,
    TimePunch,
    User,
)

WEEKDAY_LABELS = ["Segunda", "Terça", "Quarta", "Quinta", "Sexta", "Sábado", "Domingo"]


# ---------------------------------------------------------------------------
# Turnos
# ---------------------------------------------------------------------------


async def list_shifts(session: AsyncSession, company_id: int) -> list[Shift]:
    rows = (
        await session.execute(
            select(Shift)
            .where(Shift.company_id == company_id, Shift.deleted_at.is_(None))
            .order_by(Shift.name)
        )
    ).scalars()
    return list(rows)


async def create_shift(
    session: AsyncSession,
    company_id: int,
    actor_id: int,
    *,
    name: str,
    start_time: time,
    end_time: time,
    break_start: time | None,
    break_end: time | None,
    tolerance_minutes: int,
    color: str,
) -> Shift:
    record = Shift(
        company_id=company_id,
        name=name,
        start_time=start_time,
        end_time=end_time,
        break_start=break_start,
        break_end=break_end,
        tolerance_minutes=tolerance_minutes,
        color=color,
    )
    session.add(record)
    await session.flush()
    await record_event(
        session,
        company_id=company_id,
        user_id=actor_id,
        entity_type="shift",
        entity_id=record.id,
        event_type="create",
    )
    await session.commit()
    await session.refresh(record)
    return record


async def update_shift(
    session: AsyncSession, company_id: int, actor_id: int, shift_id: int, updates: dict
) -> Shift | None:
    record = await session.scalar(
        select(Shift).where(
            Shift.id == shift_id, Shift.company_id == company_id, Shift.deleted_at.is_(None)
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
            entity_type="shift",
            entity_id=record.id,
            event_type="update",
            diff=diff,
        )
    await session.commit()
    await session.refresh(record)
    return record


async def delete_shift(
    session: AsyncSession, company_id: int, actor_id: int, shift_id: int
) -> bool:
    record = await session.scalar(
        select(Shift).where(
            Shift.id == shift_id, Shift.company_id == company_id, Shift.deleted_at.is_(None)
        )
    )
    if record is None:
        return False
    record.deleted_at = datetime.now()
    await record_event(
        session,
        company_id=company_id,
        user_id=actor_id,
        entity_type="shift",
        entity_id=record.id,
        event_type="delete",
    )
    await session.commit()
    return True


# ---------------------------------------------------------------------------
# Calendário de escala
# ---------------------------------------------------------------------------


async def get_calendar(
    session: AsyncSession,
    company_id: int,
    start: date,
    end: date,
    *,
    user_id: int | None = None,
    sector_id: int | None = None,
    shift_id: int | None = None,
) -> list[tuple]:
    filters = [
        ScheduleEntry.company_id == company_id,
        ScheduleEntry.date >= start,
        ScheduleEntry.date <= end,
    ]
    if user_id is not None:
        filters.append(ScheduleEntry.user_id == user_id)
    if sector_id is not None:
        filters.append(User.sector_id == sector_id)
    if shift_id is not None:
        filters.append(ScheduleEntry.shift_id == shift_id)

    rows = await session.execute(
        select(ScheduleEntry, User.name, User.sector_id, Sector.name, Shift)
        .join(User, User.id == ScheduleEntry.user_id)
        .outerjoin(Sector, Sector.id == User.sector_id)
        .outerjoin(Shift, Shift.id == ScheduleEntry.shift_id)
        .where(*filters)
        .order_by(ScheduleEntry.date, User.name)
    )
    return rows.all()


async def set_schedule_day(
    session: AsyncSession,
    company_id: int,
    actor_id: int,
    user_id: int,
    target_date: date,
    shift_id: int | None,
    notes: str | None,
) -> ScheduleEntry:
    record = await session.scalar(
        select(ScheduleEntry).where(
            ScheduleEntry.company_id == company_id,
            ScheduleEntry.user_id == user_id,
            ScheduleEntry.date == target_date,
        )
    )
    before = f"{record.shift_id}" if record else None
    if record is None:
        record = ScheduleEntry(company_id=company_id, user_id=user_id, date=target_date)
        session.add(record)
    record.shift_id = shift_id
    record.source = "manual"
    record.notes = notes
    await session.flush()
    diff = compute_diff({"shift_id": before}, {"shift_id": f"{shift_id}"})
    if diff:
        await record_event(
            session,
            company_id=company_id,
            user_id=actor_id,
            entity_type="schedule_entry",
            entity_id=record.id,
            event_type="update",
            diff=diff,
        )
    await session.commit()
    await session.refresh(record)
    return record


def _is_working_day(
    pattern: WeeklyPattern | RotatingPattern, start_date: date, target_date: date
) -> bool:
    if isinstance(pattern, WeeklyPattern):
        return target_date.weekday() in pattern.weekdays
    cycle = pattern.work_days + pattern.off_days
    offset = (target_date - start_date).days % cycle
    return offset < pattern.work_days


async def generate_schedule(
    session: AsyncSession,
    company_id: int,
    actor_id: int,
    *,
    user_ids: list[int],
    shift_id: int,
    start_date: date,
    end_date: date,
    pattern: WeeklyPattern | RotatingPattern,
) -> int:
    affected = 0
    for uid in user_ids:
        existing_rows = (
            await session.execute(
                select(ScheduleEntry).where(
                    ScheduleEntry.company_id == company_id,
                    ScheduleEntry.user_id == uid,
                    ScheduleEntry.date >= start_date,
                    ScheduleEntry.date <= end_date,
                )
            )
        ).scalars()
        existing = {row.date: row for row in existing_rows}

        current = start_date
        while current <= end_date:
            record = existing.get(current)
            if record is not None and record.source == "manual":
                current += timedelta(days=1)
                continue
            on_shift = _is_working_day(pattern, start_date, current)
            if record is None:
                record = ScheduleEntry(company_id=company_id, user_id=uid, date=current)
                session.add(record)
            record.shift_id = shift_id if on_shift else None
            record.source = "generated"
            affected += 1
            current += timedelta(days=1)

    if affected:
        await record_event(
            session,
            company_id=company_id,
            user_id=actor_id,
            entity_type="schedule_entry",
            entity_id=shift_id,
            event_type="generate",
            diff={
                "user_ids": {"from": None, "to": user_ids},
                "period": {"from": str(start_date), "to": str(end_date)},
            },
        )
    await session.commit()
    return affected


async def _resolve_schedule_for_date(
    session: AsyncSession, company_id: int, user_id: int, target_date: date
) -> tuple[Shift | None, str | None]:
    entry = await session.scalar(
        select(ScheduleEntry).where(
            ScheduleEntry.company_id == company_id,
            ScheduleEntry.user_id == user_id,
            ScheduleEntry.date == target_date,
        )
    )
    if entry is None:
        return None, "unscheduled"
    if entry.shift_id is None:
        return None, "day_off"
    shift = await session.scalar(
        select(Shift).where(Shift.id == entry.shift_id, Shift.deleted_at.is_(None))
    )
    return shift, None


# ---------------------------------------------------------------------------
# Comparação ponto x escala
# ---------------------------------------------------------------------------


def evaluate_status(shift: Shift | None, punched_at: datetime, punch_type: str | None) -> str:
    if shift is None:
        return "unscheduled"

    tolerance = timedelta(minutes=shift.tolerance_minutes)
    punch_dt = datetime.combine(punched_at.date(), punched_at.time())
    start_dt = datetime.combine(punched_at.date(), shift.start_time)
    end_dt = datetime.combine(punched_at.date(), shift.end_time)

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
        shift, forced_status = await _resolve_schedule_for_date(
            session, company_id, user_id, punched_at.date()
        )
        status = forced_status or evaluate_status(shift, punched_at, punch_type)

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
    shift, forced_status = await _resolve_schedule_for_date(
        session, company_id, user_id, punched_at.date()
    )
    status = forced_status or evaluate_status(shift, punched_at, punch_type)
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
        shift, forced_status = await _resolve_schedule_for_date(
            session, company_id, record.user_id, record.punched_at.date()
        )
        record.status = (
            forced_status
            or evaluate_status(shift, record.punched_at, record.punch_type)
        )
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
