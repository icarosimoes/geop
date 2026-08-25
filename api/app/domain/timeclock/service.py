import math
import secrets
from datetime import date, datetime, time, timedelta

import bcrypt
from sqlalchemy import func, literal_column, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.audit import compute_diff, record_event
from app.core.cache import invalidate_dashboard
from app.core.validators import normalize_doc
from app.domain.attachments.service import create_attachment
from app.domain.notifications.service import create_notification
from app.domain.settings.router import get_company_setting
from app.domain.timeclock.schemas import RotatingPattern, WeeklyPattern
from app.models import (
    Company,
    Employee,
    EmployeeCredential,
    EmployeePayslip,
    Holiday,
    HourBankEntry,
    Location,
    Permission,
    PunchAdjustmentRequest,
    PunchExcusal,
    Role,
    ScheduleEntry,
    Sector,
    Shift,
    TimeClockDevice,
    TimeClockEnrollment,
    TimePunch,
    User,
    VacationRequest,
)
from app.models.identity import role_permissions

WEEKDAY_LABELS = ["Segunda", "Terça", "Quarta", "Quinta", "Sexta", "Sábado", "Domingo"]

# Portal do Colaborador: PIN curto (4-6 dígitos) é fraco por natureza — o lockout por
# tentativas e o TTL curto do employee_session token são a mitigação, não uma senha forte.
PIN_MAX_ATTEMPTS = 5
PIN_LOCKOUT_MINUTES = 15
_WEAK_PINS = {
    "000000",
    "111111",
    "222222",
    "333333",
    "444444",
    "555555",
    "666666",
    "777777",
    "888888",
    "999999",
    "123456",
    "654321",
    "012345",
}


# ---------------------------------------------------------------------------
# Turnos
# ---------------------------------------------------------------------------

# Padrões de escala hoteleira usados para pré-cadastrar turnos em toda empresa
# nova (recepção 24h em 3 turnos + comercial + 12x36 para portaria/segurança).
DEFAULT_SHIFTS: list[dict] = [
    {"name": "Manhã", "start_time": time(7, 0), "end_time": time(15, 0), "color": "#2563eb"},
    {"name": "Tarde", "start_time": time(15, 0), "end_time": time(23, 0), "color": "#f59e0b"},
    {"name": "Noite", "start_time": time(23, 0), "end_time": time(7, 0), "color": "#4f46e5"},
    {
        "name": "Comercial",
        "start_time": time(8, 0),
        "end_time": time(18, 0),
        "break_start": time(12, 0),
        "break_end": time(13, 0),
        "color": "#16a34a",
    },
    {
        "name": "12x36 Diurno",
        "start_time": time(7, 0),
        "end_time": time(19, 0),
        "color": "#0891b2",
    },
    {
        "name": "12x36 Noturno",
        "start_time": time(19, 0),
        "end_time": time(7, 0),
        "color": "#7c3aed",
    },
]


async def ensure_default_shifts(session: AsyncSession, company_id: int) -> list[Shift]:
    """Cadastra os turnos padrão para a empresa, se ela ainda não tiver nenhum."""
    existing = await session.scalar(
        select(func.count(Shift.id)).where(
            Shift.company_id == company_id, Shift.deleted_at.is_(None)
        )
    )
    if existing:
        return []
    shifts = [
        Shift(
            company_id=company_id,
            name=spec["name"],
            start_time=spec["start_time"],
            end_time=spec["end_time"],
            break_start=spec.get("break_start"),
            break_end=spec.get("break_end"),
            tolerance_minutes=10,
            color=spec["color"],
        )
        for spec in DEFAULT_SHIFTS
    ]
    session.add_all(shifts)
    await session.flush()
    return shifts


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


async def count_shift_usage(session: AsyncSession, company_id: int, shift_id: int) -> int:
    """Count how many schedule entries reference this shift."""
    from sqlalchemy import func

    count = await session.scalar(
        select(func.count(ScheduleEntry.id)).where(
            ScheduleEntry.company_id == company_id,
            ScheduleEntry.shift_id == shift_id,
        )
    )
    return count or 0


async def delete_shift(
    session: AsyncSession, company_id: int, actor_id: int, shift_id: int
) -> tuple[bool, str | None]:
    """Delete a shift. Returns (success, error_message)."""
    record = await session.scalar(
        select(Shift).where(
            Shift.id == shift_id, Shift.company_id == company_id, Shift.deleted_at.is_(None)
        )
    )
    if record is None:
        return False, None

    usage_count = await count_shift_usage(session, company_id, shift_id)
    if usage_count > 0:
        return False, f"Turno em uso em {usage_count} entrada(s) de escala"

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
    return True, None


# ---------------------------------------------------------------------------
# Calendário de escala
# ---------------------------------------------------------------------------


async def get_calendar(
    session: AsyncSession,
    company_id: int,
    start: date,
    end: date,
    *,
    employee_id: int | None = None,
    shift_id: int | None = None,
) -> list[tuple]:
    filters = [
        ScheduleEntry.company_id == company_id,
        ScheduleEntry.date >= start,
        ScheduleEntry.date <= end,
    ]
    if employee_id is not None:
        filters.append(ScheduleEntry.employee_id == employee_id)
    if shift_id is not None:
        filters.append(ScheduleEntry.shift_id == shift_id)

    rows = await session.execute(
        select(ScheduleEntry, Employee.name, Shift)
        .join(Employee, Employee.id == ScheduleEntry.employee_id)
        .outerjoin(Shift, Shift.id == ScheduleEntry.shift_id)
        .where(*filters)
        .where(Shift.deleted_at.is_(None) | (Shift.id.is_(None)))  # Filter out deleted shifts
        .order_by(ScheduleEntry.date, Employee.name)
    )
    return rows.all()  # type: ignore[return-value]


async def set_schedule_day(
    session: AsyncSession,
    company_id: int,
    actor_id: int,
    employee_id: int,
    target_date: date,
    shift_id: int | None,
    notes: str | None,
) -> ScheduleEntry:
    record = await session.scalar(
        select(ScheduleEntry).where(
            ScheduleEntry.company_id == company_id,
            ScheduleEntry.employee_id == employee_id,
            ScheduleEntry.date == target_date,
        )
    )
    before = f"{record.shift_id}" if record else None
    if record is None:
        record = ScheduleEntry(company_id=company_id, employee_id=employee_id, date=target_date)
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
    employee_ids: list[int],
    shift_id: int,
    start_date: date,
    end_date: date,
    pattern: WeeklyPattern | RotatingPattern,
) -> int:
    affected = 0
    for eid in employee_ids:
        existing_rows = (
            await session.execute(
                select(ScheduleEntry).where(
                    ScheduleEntry.company_id == company_id,
                    ScheduleEntry.employee_id == eid,
                    ScheduleEntry.date >= start_date,
                    ScheduleEntry.date <= end_date,
                )
            )
        ).scalars()
        existing = {row.date: row for row in existing_rows}

        employee_affected = 0
        current = start_date
        while current <= end_date:
            record = existing.get(current)
            if record is not None and record.source == "manual":
                current += timedelta(days=1)
                continue
            on_shift = _is_working_day(pattern, start_date, current)
            if record is None:
                record = ScheduleEntry(company_id=company_id, employee_id=eid, date=current)
                session.add(record)
            record.shift_id = shift_id if on_shift else None
            record.source = "generated"
            employee_affected += 1
            affected += 1
            current += timedelta(days=1)

        # Record audit event per employee (Bug 4 fix)
        if employee_affected > 0:
            await record_event(
                session,
                company_id=company_id,
                user_id=actor_id,
                entity_type="schedule_entry",
                entity_id=eid,
                event_type="generate",
                diff={
                    "period": {"from": str(start_date), "to": str(end_date)},
                    "affected_days": employee_affected,
                },
            )

    await session.commit()
    return affected


async def _resolve_schedule_for_date(
    session: AsyncSession, company_id: int, employee_id: int, target_date: date
) -> tuple[Shift | None, str | None]:
    entry = await session.scalar(
        select(ScheduleEntry).where(
            ScheduleEntry.company_id == company_id,
            ScheduleEntry.employee_id == employee_id,
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


async def _resolve_schedule_for_punch(
    session: AsyncSession, company_id: int, employee_id: int, punched_at: datetime
) -> tuple[Shift | None, str | None]:
    """Resolve a escala aplicável a uma batida, considerando turnos noturnos.

    Uma batida de madrugada (ex.: 06:10) pode pertencer ao turno noturno agendado
    no dia anterior (ex.: 22:00-06:00 de ontem). Se não houver escala para a data
    da própria batida, verifica o dia anterior antes de concluir "unscheduled".
    """
    target_date = punched_at.date()
    shift, forced_status = await _resolve_schedule_for_date(
        session, company_id, employee_id, target_date
    )
    if shift is not None or forced_status == "day_off":
        return shift, forced_status

    previous_date = target_date - timedelta(days=1)
    prev_shift, _ = await _resolve_schedule_for_date(
        session, company_id, employee_id, previous_date
    )
    if (
        prev_shift is not None
        and prev_shift.end_time < prev_shift.start_time
        and punched_at.time() < prev_shift.start_time
    ):
        return prev_shift, None

    return shift, forced_status


# ---------------------------------------------------------------------------
# Comparação ponto x escala
# ---------------------------------------------------------------------------


def evaluate_status(shift: Shift | None, punched_at: datetime, punch_type: str | None) -> str:
    if shift is None:
        return "unscheduled"

    tolerance = timedelta(minutes=shift.tolerance_minutes)
    punch_dt = datetime.combine(punched_at.date(), punched_at.time())

    # Detectar turnos noturnos (que atravessam a meia-noite)
    is_overnight = shift.end_time < shift.start_time

    if is_overnight:
        # Turno noturno: ajustar datas
        # Se a batida está próxima ao início (noite), usa mesma data.
        # Se está próxima ao fim (madrugada do dia seguinte), usa dia seguinte.
        # Heurística: se a hora batida é menor que meio-dia E maior que start_time,
        # ela é provavelmente do início. Senão, é da saída no dia seguinte.

        if punch_dt.time() < shift.start_time:
            # Batida está entre 00:00 e start_time (ex: 06:00)
            # É provável que seja saída da noite anterior
            start_dt = datetime.combine(punched_at.date() - timedelta(days=1), shift.start_time)
            end_dt = datetime.combine(punched_at.date(), shift.end_time)
        else:
            # Batida está entre start_time (ex: 22:00) e 23:59
            # É entrada ou saída da noite
            start_dt = datetime.combine(punched_at.date(), shift.start_time)
            end_dt = datetime.combine(punched_at.date() + timedelta(days=1), shift.end_time)
    else:
        # Turno diurno normal
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
        .where(TimeClockDevice.company_id == company_id, TimeClockDevice.deleted_at.is_(None))
        .order_by(TimeClockDevice.name)
    )
    return rows.all()  # type: ignore[return-value]


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
    return await session.scalar(  # type: ignore[no-any-return]
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
        select(TimeClockEnrollment, Employee.name)
        .join(Employee, Employee.id == TimeClockEnrollment.employee_id)
        .where(TimeClockEnrollment.company_id == company_id)
        .order_by(Employee.name)
    )
    return rows.all()  # type: ignore[return-value]


async def create_enrollment(
    session: AsyncSession, company_id: int, actor_id: int, *, employee_id: int, external_id: str
) -> TimeClockEnrollment:
    record = TimeClockEnrollment(
        company_id=company_id, employee_id=employee_id, external_id=external_id
    )
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
# Feriados (calendário para qualificar HE 100% no espelho de ponto)
# ---------------------------------------------------------------------------


async def list_holidays(
    session: AsyncSession, company_id: int, *, year: int | None = None
) -> list[Holiday]:
    stmt = select(Holiday).where(Holiday.company_id == company_id)
    if year is not None:
        stmt = stmt.where(func.extract("year", Holiday.date) == year)
    stmt = stmt.order_by(Holiday.date)
    return list((await session.scalars(stmt)).all())


async def get_holiday_dates(
    session: AsyncSession, company_id: int, start_date: date, end_date: date
) -> set[date]:
    rows = await session.scalars(
        select(Holiday.date).where(
            Holiday.company_id == company_id,
            Holiday.date >= start_date,
            Holiday.date <= end_date,
        )
    )
    return set(rows.all())


async def create_holiday(
    session: AsyncSession, company_id: int, actor_id: int, *, holiday_date: date, name: str
) -> Holiday:
    record = Holiday(company_id=company_id, date=holiday_date, name=name)
    session.add(record)
    try:
        await session.flush()
    except IntegrityError:
        await session.rollback()
        raise ValueError("duplicate_date") from None
    await record_event(
        session,
        company_id=company_id,
        user_id=actor_id,
        entity_type="holiday",
        entity_id=record.id,
        event_type="create",
    )
    await session.commit()
    await session.refresh(record)
    return record


async def delete_holiday(
    session: AsyncSession, company_id: int, actor_id: int, holiday_id: int
) -> bool:
    record = await session.scalar(
        select(Holiday).where(Holiday.id == holiday_id, Holiday.company_id == company_id)
    )
    if record is None:
        return False
    await session.delete(record)
    await record_event(
        session,
        company_id=company_id,
        user_id=actor_id,
        entity_type="holiday",
        entity_id=holiday_id,
        event_type="delete",
    )
    await session.commit()
    return True


# ---------------------------------------------------------------------------
# Batidas
# ---------------------------------------------------------------------------


async def _compute_punch_status(
    session: AsyncSession,
    company_id: int,
    employee_id: int | None,
    punched_at: datetime,
    punch_type: str | None,
) -> str:
    """Resolve o status (on_time/late/early_leave/unscheduled/day_off) de uma batida,
    reaproveitado por todas as origens de ingestão (device, manual, mobile)."""
    if not employee_id:
        return "unscheduled"
    shift, forced_status = await _resolve_schedule_for_punch(
        session, company_id, employee_id, punched_at
    )
    return forced_status or evaluate_status(shift, punched_at, punch_type)


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

    employee_id = await session.scalar(
        select(TimeClockEnrollment.employee_id).where(
            TimeClockEnrollment.company_id == company_id,
            TimeClockEnrollment.external_id == external_id,
        )
    )
    status = await _compute_punch_status(session, company_id, employee_id, punched_at, punch_type)

    record = TimePunch(
        company_id=company_id,
        employee_id=employee_id,
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
            return existing  # type: ignore[no-any-return]
        raise
    await invalidate_dashboard(company_id)
    await session.refresh(record)
    return record


async def create_manual_punch(
    session: AsyncSession,
    company_id: int,
    actor_id: int,
    *,
    employee_id: int,
    punched_at: datetime,
    punch_type: str | None,
    notes: str | None,
) -> TimePunch:
    status = await _compute_punch_status(session, company_id, employee_id, punched_at, punch_type)
    record = TimePunch(
        company_id=company_id,
        employee_id=employee_id,
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
    if record.employee_id:
        record.status = await _compute_punch_status(
            session, company_id, record.employee_id, record.punched_at, record.punch_type
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
    employee_id: int | None = None,
    date_from: date | None = None,
    date_to: date | None = None,
    status: str | None = None,
) -> tuple[list[tuple], int]:
    from sqlalchemy import func

    filters = [TimePunch.company_id == company_id]
    if employee_id is not None:
        filters.append(TimePunch.employee_id == employee_id)
    if date_from is not None:
        filters.append(TimePunch.punched_at >= datetime.combine(date_from, time.min))
    if date_to is not None:
        filters.append(TimePunch.punched_at <= datetime.combine(date_to, time.max))
    if status is not None:
        filters.append(TimePunch.status == status)

    total = await session.scalar(select(func.count(TimePunch.id)).where(*filters)) or 0
    rows = (
        await session.execute(
            select(TimePunch, Employee.name, TimeClockDevice.name)
            .outerjoin(Employee, Employee.id == TimePunch.employee_id)
            .outerjoin(TimeClockDevice, TimeClockDevice.id == TimePunch.device_id)
            .where(*filters)
            .order_by(TimePunch.punched_at.desc())
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
    ).all()
    return rows, total  # type: ignore[return-value]


# ---------------------------------------------------------------------------
# Banco de horas
# ---------------------------------------------------------------------------


def _resolve_salary(
    employee_salary: float | None, job_title: str | None, cargo_salaries: dict
) -> float | None:
    """Salário individual do funcionário, com fallback para o salário-base do
    cargo (config de tenant) quando o funcionário não tem `salary` cadastrado."""
    if employee_salary is not None:
        return float(employee_salary)
    if job_title and job_title.strip() in cargo_salaries:
        return float(cargo_salaries[job_title.strip()])
    return None


def _shift_expected_minutes(shift: Shift | None) -> int:
    if shift is None:
        return 0
    is_overnight = shift.end_time < shift.start_time
    anchor = date(2000, 1, 1)
    end_anchor = anchor + timedelta(days=1) if is_overnight else anchor
    start_dt = datetime.combine(anchor, shift.start_time)
    end_dt = datetime.combine(end_anchor, shift.end_time)
    total = int((end_dt - start_dt).total_seconds() // 60)
    if shift.break_start and shift.break_end and shift.break_end > shift.break_start:
        break_start_dt = datetime.combine(anchor, shift.break_start)
        break_end_dt = datetime.combine(anchor, shift.break_end)
        total -= int((break_end_dt - break_start_dt).total_seconds() // 60)
    return max(total, 0)


def _pair_punches(punches: list[TimePunch]) -> list[tuple[datetime, datetime]]:
    """Pareia batidas 'in'/'out' em ordem cronológica, retornando os pares
    completos (entrada, saída). Batidas sem tipo definido ou desemparelhadas
    são ignoradas. Turnos noturnos cuja batida de saída cai no dia seguinte
    são contados no dia da batida de saída, não no dia do turno — limitação
    conhecida do MVP."""
    ordered = sorted(punches, key=lambda p: p.punched_at)
    pairs: list[tuple[datetime, datetime]] = []
    open_in: datetime | None = None
    for punch in ordered:
        if punch.punch_type == "in":
            open_in = punch.punched_at
        elif punch.punch_type == "out" and open_in is not None:
            pairs.append((open_in, punch.punched_at))
            open_in = None
    return pairs


def _pair_punches_worked_minutes(punches: list[TimePunch]) -> int:
    total_minutes = sum(
        int((out - inn).total_seconds() // 60) for inn, out in _pair_punches(punches)
    )
    return max(total_minutes, 0)


async def recalculate_hour_bank(
    session: AsyncSession,
    company_id: int,
    actor_id: int,
    employee_id: int,
    start_date: date,
    end_date: date,
) -> int:
    """Recalcula o banco de horas diário (escala x pontos batidos) para o período,
    substituindo os lançamentos 'calculated' já existentes nessas datas."""
    punches = (
        await session.scalars(
            select(TimePunch).where(
                TimePunch.company_id == company_id,
                TimePunch.employee_id == employee_id,
                TimePunch.punched_at >= datetime.combine(start_date, time.min),
                TimePunch.punched_at <= datetime.combine(end_date, time.max),
            )
        )
    ).all()
    punches_by_date: dict[date, list[TimePunch]] = {}
    for punch in punches:
        punches_by_date.setdefault(punch.punched_at.date(), []).append(punch)

    holiday_dates = await get_holiday_dates(session, company_id, start_date, end_date)
    timeclock_settings = await get_company_setting(session, company_id, "timeclock")
    employee_row = (
        await session.execute(
            select(Employee.salary, Employee.job_title).where(
                Employee.id == employee_id, Employee.company_id == company_id
            )
        )
    ).first()
    employee_salary, job_title = employee_row if employee_row else (None, None)
    salary = _resolve_salary(
        employee_salary, job_title, timeclock_settings.get("cargo_salaries", {})
    )
    # Só exclui HE do banco de horas se o toggle estiver ligado E houver um
    # salário resolvível (individual ou por cargo) — sem isso, a HE não teria
    # como ser paga em dinheiro e teria que continuar virando banco de horas.
    overtime_paid_in_cash = bool(timeclock_settings.get("overtime_paid_in_cash")) and bool(salary)

    affected = 0
    current = start_date
    while current <= end_date:
        shift, forced_status = await _resolve_schedule_for_date(
            session, company_id, employee_id, current
        )
        expected_minutes = 0 if forced_status else _shift_expected_minutes(shift)
        worked_minutes = _pair_punches_worked_minutes(punches_by_date.get(current, []))

        is_rest_day = (
            forced_status == "day_off" or current.weekday() == 6 or current in holiday_dates
        )
        if overtime_paid_in_cash:
            # HE (50%/100%) é paga em dinheiro (ver espelho de ponto), não vira
            # saldo de banco de horas — só o déficit (trabalhou menos que o
            # esperado) continua sendo banco de horas negativo.
            overtime_minutes = (
                worked_minutes if is_rest_day else max(0, worked_minutes - expected_minutes)
            )
            balance_minutes = worked_minutes - expected_minutes - overtime_minutes
        else:
            balance_minutes = worked_minutes - expected_minutes

        entry = await session.scalar(
            select(HourBankEntry).where(
                HourBankEntry.company_id == company_id,
                HourBankEntry.employee_id == employee_id,
                HourBankEntry.reference_date == current,
                HourBankEntry.source == "calculated",
            )
        )
        if entry is None:
            entry = HourBankEntry(
                company_id=company_id,
                employee_id=employee_id,
                reference_date=current,
                source="calculated",
            )
            session.add(entry)
        entry.expected_minutes = expected_minutes
        entry.worked_minutes = worked_minutes
        entry.balance_minutes = balance_minutes
        entry.created_by_user_id = actor_id
        affected += 1
        current += timedelta(days=1)

    await session.commit()
    await invalidate_dashboard(company_id)
    return affected


async def set_hour_bank_initial_balance(
    session: AsyncSession,
    company_id: int,
    actor_id: int,
    employee_id: int,
    effective_date: date,
    balance_minutes: int,
    notes: str | None,
) -> HourBankEntry:
    entry = await session.scalar(
        select(HourBankEntry).where(
            HourBankEntry.company_id == company_id,
            HourBankEntry.employee_id == employee_id,
            HourBankEntry.source == "initial_balance",
        )
    )
    if entry is None:
        entry = HourBankEntry(
            company_id=company_id,
            employee_id=employee_id,
            source="initial_balance",
        )
        session.add(entry)
    entry.reference_date = effective_date
    entry.expected_minutes = 0
    entry.worked_minutes = 0
    entry.balance_minutes = balance_minutes
    entry.notes = notes
    entry.created_by_user_id = actor_id
    await session.commit()
    await session.refresh(entry)
    return entry


async def get_hour_bank_summary(
    session: AsyncSession, company_id: int, employee_id: int
) -> tuple[int, list[HourBankEntry]]:
    entries = (
        await session.scalars(
            select(HourBankEntry)
            .where(
                HourBankEntry.company_id == company_id,
                HourBankEntry.employee_id == employee_id,
            )
            .order_by(HourBankEntry.reference_date.desc())
        )
    ).all()
    total_balance = sum(e.balance_minutes for e in entries)
    return total_balance, list(entries)


# ---------------------------------------------------------------------------
# Ajuste de ponto (Portal do Colaborador): solicitação + aprovação
# ---------------------------------------------------------------------------


async def _notify_punch_managers(
    session: AsyncSession,
    company_id: int,
    *,
    title: str,
    body: str,
    entity_type: str,
    entity_id: int,
    exclude_user_id: int | None = None,
) -> None:
    filters = [
        User.company_id == company_id,
        User.active.is_(True),
        User.deleted_at.is_(None),
        Permission.code.in_(["punch_adjustment.manage", "*"]),
    ]
    if exclude_user_id is not None:
        filters.append(User.id != exclude_user_id)
    user_ids = (
        await session.scalars(
            select(User.id)
            .join(Role, Role.id == User.role_id)
            .join(role_permissions, role_permissions.c.role_id == Role.id)
            .join(Permission, Permission.id == role_permissions.c.permission_id)
            .where(*filters)
            .distinct()
        )
    ).all()
    for uid in user_ids:
        await create_notification(
            session,
            company_id=company_id,
            user_id=uid,
            title=title,
            body=body,
            category="create",
            entity_type=entity_type,
            entity_id=entity_id,
        )


async def _notify_punch_adjustment_managers(
    session: AsyncSession, company_id: int, employee_name: str, request_id: int
) -> None:
    await _notify_punch_managers(
        session,
        company_id,
        title=f"Nova solicitação de ajuste de ponto de {employee_name}",
        body="Aguardando aprovação no Portal Administrativo.",
        entity_type="punch_adjustment_request",
        entity_id=request_id,
    )


async def create_punch_adjustment_request(
    session: AsyncSession,
    company_id: int,
    employee_id: int,
    *,
    punch_id: int | None,
    requested_punched_at: datetime,
    requested_punch_type: str | None,
    reason: str,
) -> PunchAdjustmentRequest | None:
    if punch_id is not None:
        exists = await session.scalar(
            select(TimePunch.id).where(
                TimePunch.id == punch_id,
                TimePunch.company_id == company_id,
                TimePunch.employee_id == employee_id,
            )
        )
        if exists is None:
            return None

    record = PunchAdjustmentRequest(
        company_id=company_id,
        employee_id=employee_id,
        punch_id=punch_id,
        requested_punched_at=requested_punched_at,
        requested_punch_type=requested_punch_type,
        reason=reason,
    )
    session.add(record)
    await session.flush()
    employee_name = await session.scalar(select(Employee.name).where(Employee.id == employee_id))
    await _notify_punch_adjustment_managers(
        session, company_id, employee_name or "funcionário", record.id
    )
    await session.commit()
    await session.refresh(record)
    return record


async def list_punch_adjustment_requests(
    session: AsyncSession,
    company_id: int,
    page: int,
    page_size: int,
    *,
    employee_id: int | None = None,
    status: str | None = None,
) -> tuple[list[tuple], int]:
    filters = [PunchAdjustmentRequest.company_id == company_id]
    if employee_id is not None:
        filters.append(PunchAdjustmentRequest.employee_id == employee_id)
    if status is not None:
        filters.append(PunchAdjustmentRequest.status == status)

    total = await session.scalar(select(func.count(PunchAdjustmentRequest.id)).where(*filters)) or 0
    rows = (
        await session.execute(
            select(PunchAdjustmentRequest, Employee.name, Employee.avatar_url)
            .join(Employee, Employee.id == PunchAdjustmentRequest.employee_id)
            .where(*filters)
            .order_by(PunchAdjustmentRequest.created_at.desc())
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
    ).all()
    return rows, total  # type: ignore[return-value]


async def review_punch_adjustment_request(
    session: AsyncSession,
    company_id: int,
    actor_id: int,
    request_id: int,
    *,
    approve: bool,
    review_notes: str | None,
) -> tuple[PunchAdjustmentRequest | None, str | None]:
    record = await session.scalar(
        select(PunchAdjustmentRequest).where(
            PunchAdjustmentRequest.id == request_id,
            PunchAdjustmentRequest.company_id == company_id,
        )
    )
    if record is None:
        return None, "not_found"
    if record.status != "pending":
        return None, "already_reviewed"

    record.reviewed_by_user_id = actor_id
    record.reviewed_at = datetime.now()
    record.review_notes = review_notes

    if approve:
        record.status = "approved"
        if record.punch_id is not None:
            punch = await update_punch(
                session,
                company_id,
                actor_id,
                record.punch_id,
                {
                    "punched_at": record.requested_punched_at,
                    "punch_type": record.requested_punch_type,
                },
            )
            record.resulting_punch_id = punch.id if punch else None
        else:
            punch = await create_manual_punch(
                session,
                company_id,
                actor_id,
                employee_id=record.employee_id,
                punched_at=record.requested_punched_at,
                punch_type=record.requested_punch_type,
                notes=f"Ajuste aprovado (solicitação #{record.id})",
            )
            record.resulting_punch_id = punch.id
    else:
        record.status = "rejected"

    await record_event(
        session,
        company_id=company_id,
        user_id=actor_id,
        entity_type="punch_adjustment_request",
        entity_id=record.id,
        event_type="update",
        diff={"status": {"from": "pending", "to": record.status}},
    )
    await session.commit()
    await session.refresh(record)
    return record, None


async def create_punch_excusal(
    session: AsyncSession,
    company_id: int,
    actor_id: int,
    *,
    employee_id: int,
    reference_date: date,
    minutes: int | None,
    reason: str,
) -> PunchExcusal | None:
    """Abona um dia (ou uma quantidade de minutos) do funcionário, neutralizando
    o impacto no banco de horas sem apagar o lançamento 'calculated' do dia."""
    employee_exists = await session.scalar(
        select(Employee.id).where(
            Employee.id == employee_id,
            Employee.company_id == company_id,
            Employee.deleted_at.is_(None),
        )
    )
    if employee_exists is None:
        return None

    shift, forced_status = await _resolve_schedule_for_date(
        session, company_id, employee_id, reference_date
    )
    expected_minutes = 0 if forced_status else _shift_expected_minutes(shift)
    excused_minutes = minutes if minutes is not None else expected_minutes

    record = PunchExcusal(
        company_id=company_id,
        employee_id=employee_id,
        reference_date=reference_date,
        minutes=minutes,
        reason=reason,
        created_by_user_id=actor_id,
    )
    session.add(record)

    entry = await session.scalar(
        select(HourBankEntry).where(
            HourBankEntry.company_id == company_id,
            HourBankEntry.employee_id == employee_id,
            HourBankEntry.reference_date == reference_date,
            HourBankEntry.source == "excused",
        )
    )
    if entry is None:
        entry = HourBankEntry(
            company_id=company_id,
            employee_id=employee_id,
            reference_date=reference_date,
            source="excused",
        )
        session.add(entry)
    entry.expected_minutes = excused_minutes
    entry.worked_minutes = excused_minutes
    entry.balance_minutes = 0
    entry.notes = reason
    entry.created_by_user_id = actor_id

    await session.flush()
    await record_event(
        session,
        company_id=company_id,
        user_id=actor_id,
        entity_type="punch_excusal",
        entity_id=record.id,
        event_type="create",
    )
    employee_name = await session.scalar(select(Employee.name).where(Employee.id == employee_id))
    await _notify_punch_managers(
        session,
        company_id,
        title=f"Abono de ponto lançado para {employee_name or 'funcionário'}",
        body=f"{excused_minutes} minuto(s) abonado(s) em {reference_date.strftime('%d/%m/%Y')}.",
        entity_type="punch_excusal",
        entity_id=record.id,
        exclude_user_id=actor_id,
    )
    await session.commit()
    await invalidate_dashboard(company_id)
    await session.refresh(record)
    return record


async def list_punch_excusals(
    session: AsyncSession,
    company_id: int,
    page: int,
    page_size: int,
    *,
    employee_id: int | None = None,
) -> tuple[list[tuple], int]:
    filters = [PunchExcusal.company_id == company_id]
    if employee_id is not None:
        filters.append(PunchExcusal.employee_id == employee_id)

    total = await session.scalar(select(func.count(PunchExcusal.id)).where(*filters)) or 0
    rows = (
        await session.execute(
            select(PunchExcusal, Employee.name, Employee.avatar_url)
            .join(Employee, Employee.id == PunchExcusal.employee_id)
            .where(*filters)
            .order_by(PunchExcusal.created_at.desc())
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
    ).all()
    return rows, total  # type: ignore[return-value]


async def get_punch_adjustment_stats(session: AsyncSession, company_id: int) -> dict:
    now = datetime.now()
    months: list[date] = []
    cursor = now.replace(day=1)
    for _ in range(6):
        months.append(cursor.date())
        cursor = (cursor - timedelta(days=1)).replace(day=1)
    months.reverse()
    period_start = datetime.combine(months[0], time.min)

    month_trunc = func.date_trunc(literal_column("'month'"), PunchAdjustmentRequest.created_at)
    trend_rows = (
        await session.execute(
            select(month_trunc, func.count(PunchAdjustmentRequest.id))
            .where(
                PunchAdjustmentRequest.company_id == company_id,
                PunchAdjustmentRequest.created_at >= period_start,
            )
            .group_by(month_trunc)
        )
    ).all()
    counts_by_month = {d.date().replace(day=1).isoformat(): c for d, c in trend_rows}
    monthly_trend = [
        {"month": m.isoformat(), "count": counts_by_month.get(m.isoformat(), 0)} for m in months
    ]

    by_employee_rows = (
        await session.execute(
            select(
                PunchAdjustmentRequest.employee_id,
                Employee.name,
                Employee.avatar_url,
                func.count(PunchAdjustmentRequest.id),
            )
            .join(Employee, Employee.id == PunchAdjustmentRequest.employee_id)
            .where(PunchAdjustmentRequest.company_id == company_id)
            .group_by(PunchAdjustmentRequest.employee_id, Employee.name, Employee.avatar_url)
        )
    ).all()

    ranked_desc = sorted(by_employee_rows, key=lambda r: r[3], reverse=True)
    top_requesters = [
        {"employee_id": eid, "name": name, "avatar_url": avatar, "count": count}
        for eid, name, avatar, count in ranked_desc[:5]
    ]
    least_requesters = [
        {"employee_id": eid, "name": name, "avatar_url": avatar, "count": count}
        for eid, name, avatar, count in sorted(by_employee_rows, key=lambda r: r[3])[:5]
    ]

    return {
        "monthly_trend": monthly_trend,
        "top_requesters": top_requesters,
        "least_requesters": least_requesters,
    }


# ---------------------------------------------------------------------------
# Portal do Colaborador: PIN de acesso (EmployeeCredential)
# ---------------------------------------------------------------------------


def hash_pin(pin: str) -> str:
    return bcrypt.hashpw(pin.encode(), bcrypt.gensalt()).decode()


def verify_pin(pin: str, pin_hash: str) -> bool:
    try:
        return bcrypt.checkpw(pin.encode(), pin_hash.encode())
    except (ValueError, TypeError):
        return False


def _is_weak_pin(pin: str) -> bool:
    """Recusa sequências óbvias. PIN numérico curto é fraco por natureza — isto é
    só uma barreira mínima, a mitigação real é o lockout por tentativas + TTL curto
    do token de sessão."""
    return pin in _WEAK_PINS


async def _record_employee_action(
    session: AsyncSession,
    company_id: int,
    employee_id: int,
    *,
    entity_type: str,
    entity_id: int,
    event_type: str,
    diff: dict | None = None,
) -> None:
    """AuditEvent.user_id é FK obrigatória para `users.id` — não existe conceito de
    "ator = Employee" no schema de auditoria hoje. Quando o employee tem User
    vinculado (`Employee.user_id`), atribuímos o evento a ele; caso contrário,
    a ação (autoatendimento sem User) não gera AuditEvent, para não violar a FK
    nem atribuir o evento a um usuário errado."""
    employee = await session.get(Employee, employee_id)
    if employee is None or employee.user_id is None:
        return
    await record_event(
        session,
        company_id=company_id,
        user_id=employee.user_id,
        entity_type=entity_type,
        entity_id=entity_id,
        event_type=event_type,
        diff=diff,
    )


async def get_employee_credential(
    session: AsyncSession, company_id: int, employee_id: int
) -> EmployeeCredential | None:
    return await session.scalar(  # type: ignore[no-any-return]
        select(EmployeeCredential).where(
            EmployeeCredential.company_id == company_id,
            EmployeeCredential.employee_id == employee_id,
            EmployeeCredential.deleted_at.is_(None),
        )
    )


async def reset_employee_pin(
    session: AsyncSession, company_id: int, actor_id: int, employee_id: int
) -> tuple[str | None, str | None]:
    """Admin gera um novo PIN aleatório de 6 dígitos para o funcionário. Retorna
    (pin_em_texto_puro, error_code) — o texto puro só existe nesse retorno, nunca é
    persistido."""
    employee = await session.scalar(
        select(Employee).where(
            Employee.id == employee_id,
            Employee.company_id == company_id,
            Employee.deleted_at.is_(None),
        )
    )
    if employee is None:
        return None, "not_found"

    new_pin = f"{secrets.randbelow(1_000_000):06d}"
    credential = await get_employee_credential(session, company_id, employee_id)
    if credential is None:
        credential = EmployeeCredential(company_id=company_id, employee_id=employee_id)
        session.add(credential)

    credential.pin_hash = hash_pin(new_pin)
    credential.failed_attempts = 0
    credential.locked_until = None
    credential.must_change_pin = True
    credential.pin_set_at = datetime.now()

    await session.flush()
    await record_event(
        session,
        company_id=company_id,
        user_id=actor_id,
        entity_type="employee_credential",
        entity_id=employee_id,
        event_type="pin_reset",
    )
    await session.commit()
    return new_pin, None


async def set_employee_pin(
    session: AsyncSession,
    company_id: int,
    employee_id: int,
    *,
    old_pin: str | None,
    new_pin: str,
) -> tuple[bool, str | None]:
    """O próprio funcionário define/troca o PIN. Exige o PIN atual, exceto na
    primeira troca obrigatória após um reset administrativo (`must_change_pin`)."""
    if not new_pin.isdigit() or not (4 <= len(new_pin) <= 6):
        return False, "invalid_pin_format"
    if _is_weak_pin(new_pin):
        return False, "weak_pin"

    credential = await get_employee_credential(session, company_id, employee_id)
    if credential is None:
        return False, "not_found"

    if not credential.must_change_pin and (
        not old_pin or not verify_pin(old_pin, credential.pin_hash)
    ):
        return False, "invalid_old_pin"

    credential.pin_hash = hash_pin(new_pin)
    credential.must_change_pin = False
    credential.pin_set_at = datetime.now()
    credential.failed_attempts = 0
    credential.locked_until = None

    await _record_employee_action(
        session,
        company_id,
        employee_id,
        entity_type="employee_credential",
        entity_id=employee_id,
        event_type="pin_change",
    )
    await session.commit()
    return True, None


async def authenticate_employee(
    session: AsyncSession,
    *,
    company_slug: str,
    registration_number: str,
    pin: str,
) -> tuple[Employee | None, str | None]:
    """Resolve company_id pelo slug, autentica o funcionário pelo registration_number
    + PIN, aplicando lockout por tentativas."""
    company = await session.scalar(
        select(Company).where(Company.slug == company_slug, Company.deleted_at.is_(None))
    )
    if company is None:
        return None, "invalid_tenant"

    employee = await session.scalar(
        select(Employee).where(
            Employee.company_id == company.id,
            Employee.registration_number == registration_number,
            Employee.deleted_at.is_(None),
            Employee.status == "active",
        )
    )
    if employee is None:
        return None, "invalid_credentials"

    credential = await get_employee_credential(session, company.id, employee.id)
    if credential is None:
        return None, "invalid_credentials"

    if credential.locked_until and credential.locked_until > datetime.now():
        return None, "locked"

    if not verify_pin(pin, credential.pin_hash):
        credential.failed_attempts += 1
        if credential.failed_attempts >= PIN_MAX_ATTEMPTS:
            credential.locked_until = datetime.now() + timedelta(minutes=PIN_LOCKOUT_MINUTES)
        await session.commit()
        return None, "invalid_credentials"

    credential.failed_attempts = 0
    credential.locked_until = None
    await session.commit()
    return employee, None


# ---------------------------------------------------------------------------
# Portal do Colaborador: punch mobile com geofencing
# ---------------------------------------------------------------------------

EARTH_RADIUS_M = 6_371_000


def haversine_distance_m(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Distância em metros entre duas coordenadas (fórmula de Haversine). Função
    pura, sem I/O, testável isoladamente."""
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    d_phi = math.radians(lat2 - lat1)
    d_lambda = math.radians(lon2 - lon1)
    a = math.sin(d_phi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(d_lambda / 2) ** 2
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    return EARTH_RADIUS_M * c


async def get_next_expected_punch_type(
    session: AsyncSession, company_id: int, employee_id: int
) -> str:
    """Próximo tipo de batida esperado (in/out) para hoje, sem side effect."""
    today = date.today()
    last = await session.scalar(
        select(TimePunch)
        .where(
            TimePunch.company_id == company_id,
            TimePunch.employee_id == employee_id,
            TimePunch.punched_at >= datetime.combine(today, time.min),
            TimePunch.punched_at <= datetime.combine(today, time.max),
        )
        .order_by(TimePunch.punched_at.desc())
        .limit(1)
    )
    if last is None or last.punch_type == "out":
        return "in"
    return "out"


async def create_mobile_punch(
    session: AsyncSession,
    company_id: int,
    employee_id: int,
    *,
    latitude: float,
    longitude: float,
) -> tuple[TimePunch | None, str | None, float | None]:
    """Cria uma batida mobile validando geofencing contra a Location do employee.

    Retorna (punch, error_code, distance_m). error_code é None em caso de sucesso,
    "LOCATION_NOT_CONFIGURED" se o employee não tiver Location com lat/lng
    configurados (nunca deixamos passar sem geofencing silenciosamente), ou
    "OUT_OF_RANGE" se a distância exceder o raio configurado (distance_m sempre
    presente nesse caso).
    """
    employee = await session.scalar(
        select(Employee).where(
            Employee.id == employee_id,
            Employee.company_id == company_id,
            Employee.deleted_at.is_(None),
        )
    )
    if employee is None or employee.location_id is None:
        return None, "LOCATION_NOT_CONFIGURED", None

    location = await session.scalar(
        select(Location).where(
            Location.id == employee.location_id,
            Location.company_id == company_id,
            Location.deleted_at.is_(None),
        )
    )
    if location is None or location.latitude is None or location.longitude is None:
        return None, "LOCATION_NOT_CONFIGURED", None

    distance_m = haversine_distance_m(
        float(location.latitude), float(location.longitude), latitude, longitude
    )
    if distance_m > location.geofence_radius_m:
        return None, "OUT_OF_RANGE", distance_m

    punch_type = await get_next_expected_punch_type(session, company_id, employee_id)
    punched_at = datetime.now()
    status = await _compute_punch_status(session, company_id, employee_id, punched_at, punch_type)

    record = TimePunch(
        company_id=company_id,
        employee_id=employee_id,
        device_id=None,
        punched_at=punched_at,
        punch_type=punch_type,
        source="mobile",
        status=status,
        created_by_user_id=None,
        latitude=latitude,
        longitude=longitude,
        distance_m=distance_m,
    )
    session.add(record)
    await session.flush()
    await _record_employee_action(
        session,
        company_id,
        employee_id,
        entity_type="time_punch",
        entity_id=record.id,
        event_type="create",
        diff={"source": "mobile", "distance_m": round(distance_m, 2)},
    )
    await session.commit()
    await invalidate_dashboard(company_id)
    await session.refresh(record)
    return record, None, distance_m


# ---------------------------------------------------------------------------
# Portal do Colaborador: contracheques
# ---------------------------------------------------------------------------


async def list_employee_payslips(
    session: AsyncSession, company_id: int, employee_id: int
) -> list[EmployeePayslip]:
    rows = (
        await session.execute(
            select(EmployeePayslip)
            .where(
                EmployeePayslip.company_id == company_id,
                EmployeePayslip.employee_id == employee_id,
                EmployeePayslip.deleted_at.is_(None),
            )
            .order_by(EmployeePayslip.reference_month.desc())
        )
    ).scalars()
    return list(rows)


async def get_employee_payslip_for_download(
    session: AsyncSession, company_id: int, employee_id: int, payslip_id: int
) -> EmployeePayslip | None:
    """Nunca confia no payslip_id recebido sem checar que pertence a esse employee."""
    return await session.scalar(  # type: ignore[no-any-return]
        select(EmployeePayslip).where(
            EmployeePayslip.id == payslip_id,
            EmployeePayslip.company_id == company_id,
            EmployeePayslip.employee_id == employee_id,
            EmployeePayslip.deleted_at.is_(None),
        )
    )


async def create_employee_payslip(
    session: AsyncSession,
    company_id: int,
    actor_id: int,
    *,
    employee_id: int,
    reference_month: date,
    attachment_id: int,
) -> EmployeePayslip:
    record = EmployeePayslip(
        company_id=company_id,
        employee_id=employee_id,
        reference_month=reference_month,
        attachment_id=attachment_id,
        uploaded_by_user_id=actor_id,
    )
    session.add(record)
    await session.flush()
    await record_event(
        session,
        company_id=company_id,
        user_id=actor_id,
        entity_type="employee_payslip",
        entity_id=record.id,
        event_type="create",
        diff={"employee_id": employee_id, "reference_month": str(reference_month)},
    )
    await session.commit()
    await session.refresh(record)
    return record


MAX_PAYSLIP_IMPORT_ROWS = 500


async def get_employee_by_cpf(session: AsyncSession, company_id: int, cpf: str) -> Employee | None:
    digits = normalize_doc(cpf)
    if not digits:
        return None
    return await session.scalar(  # type: ignore[no-any-return]
        select(Employee).where(
            Employee.company_id == company_id,
            Employee.cpf == digits,
            Employee.deleted_at.is_(None),
        )
    )


async def get_employee_by_registration_number(
    session: AsyncSession, company_id: int, registration_number: str
) -> Employee | None:
    registration_number = registration_number.strip()
    if not registration_number:
        return None
    return await session.scalar(  # type: ignore[no-any-return]
        select(Employee).where(
            Employee.company_id == company_id,
            Employee.registration_number == registration_number,
            Employee.deleted_at.is_(None),
        )
    )


async def upsert_employee_payslip(
    session: AsyncSession,
    company_id: int,
    actor_id: int,
    *,
    employee_id: int,
    reference_month: date,
    attachment_id: int,
) -> tuple[EmployeePayslip, bool]:
    """Get-or-create por (employee_id, reference_month) — reimportar a mesma
    competência troca o anexo em vez de falhar na unique constraint, já que o
    contador pode reenviar um contracheque corrigido."""
    existing = await session.scalar(
        select(EmployeePayslip).where(
            EmployeePayslip.company_id == company_id,
            EmployeePayslip.employee_id == employee_id,
            EmployeePayslip.reference_month == reference_month,
            EmployeePayslip.deleted_at.is_(None),
        )
    )
    if existing is None:
        record = await create_employee_payslip(
            session,
            company_id,
            actor_id,
            employee_id=employee_id,
            reference_month=reference_month,
            attachment_id=attachment_id,
        )
        return record, True

    old_attachment_id = existing.attachment_id
    existing.attachment_id = attachment_id
    await session.flush()
    await record_event(
        session,
        company_id=company_id,
        user_id=actor_id,
        entity_type="employee_payslip",
        entity_id=existing.id,
        event_type="update",
        diff={"attachment_id": {"old": old_attachment_id, "new": attachment_id}},
    )
    await session.commit()
    await session.refresh(existing)
    return existing, False


async def import_employee_payslips(
    session: AsyncSession,
    company_id: int,
    actor_id: int,
    rows: list[dict[str, str]],
    files: dict[str, bytes],
) -> list[dict]:
    """Casa cada linha do manifesto (CPF ou matrícula + competência + nome do
    arquivo no zip) a um funcionário e cria/atualiza o EmployeePayslip. Reaproveita
    create_attachment para validação/armazenamento do PDF — nenhuma lógica de
    upload duplicada. Uma linha inválida não interrompe as demais."""
    results: list[dict] = []

    for index, raw_row in enumerate(rows[:MAX_PAYSLIP_IMPORT_ROWS], start=1):
        cpf = (raw_row.get("cpf") or "").strip()
        matricula = (raw_row.get("matricula") or "").strip()
        competencia = (raw_row.get("competencia") or "").strip()
        arquivo = (raw_row.get("arquivo") or "").strip()

        employee = None
        if cpf:
            employee = await get_employee_by_cpf(session, company_id, cpf)
        if employee is None and matricula:
            employee = await get_employee_by_registration_number(session, company_id, matricula)
        if employee is None:
            results.append(
                {"row": index, "status": "failed", "error": "funcionario_nao_encontrado"}
            )
            continue

        try:
            reference_month = datetime.strptime(competencia, "%Y-%m").date().replace(day=1)
        except ValueError:
            results.append(
                {
                    "row": index,
                    "status": "failed",
                    "employee_name": employee.name,
                    "error": "competencia_invalida",
                }
            )
            continue

        data = files.get(arquivo)
        if data is None:
            results.append(
                {
                    "row": index,
                    "status": "failed",
                    "employee_name": employee.name,
                    "error": "arquivo_nao_encontrado_no_zip",
                }
            )
            continue

        attachment = await create_attachment(
            session,
            company_id,
            actor_id,
            entity_type="employee_payslip",
            entity_id=employee.id,
            filename=arquivo,
            content_type="application/pdf",
            data=data,
            skip_audit=True,
        )
        if isinstance(attachment, str):
            results.append(
                {
                    "row": index,
                    "status": "failed",
                    "employee_name": employee.name,
                    "reference_month": competencia,
                    "error": attachment,
                }
            )
            continue

        _, created = await upsert_employee_payslip(
            session,
            company_id,
            actor_id,
            employee_id=employee.id,
            reference_month=reference_month,
            attachment_id=attachment.id,
        )
        results.append(
            {
                "row": index,
                "status": "created" if created else "updated",
                "employee_name": employee.name,
                "reference_month": competencia,
            }
        )

    return results


# ---------------------------------------------------------------------------
# Requisições de Férias
# ---------------------------------------------------------------------------

async def _notify_vacation_managers(
    session: AsyncSession, company_id: int, employee_name: str, request_id: int
) -> None:
    await _notify_punch_managers(
        session,
        company_id,
        title=f"Nova solicitação de férias de {employee_name}",
        body="Aguardando aprovação no Portal Administrativo.",
        entity_type="vacation_request",
        entity_id=request_id,
    )


async def _calc_working_days(
    session: AsyncSession,
    company_id: int,
    start_date: date,
    end_date: date,
) -> int:
    """Conta dias úteis no período excluindo fins de semana e feriados cadastrados."""
    holiday_dates = await get_holiday_dates(session, company_id, start_date, end_date)
    holiday_set = {h for h in holiday_dates}
    working = 0
    current = start_date
    while current <= end_date:
        if current.weekday() < 5 and current not in holiday_set:  # 0=Seg … 4=Sex
            working += 1
        current += timedelta(days=1)
    return working


async def create_vacation_request(
    session: AsyncSession,
    company_id: int,
    employee_id: int,
    *,
    start_date: date,
    end_date: date,
    notes: str | None,
) -> tuple[VacationRequest | None, str | None]:
    """Cria uma solicitação de férias. Retorna (record, None) em sucesso ou
    (None, código_de_erro) em falha."""
    if end_date < start_date:
        return None, "end_before_start"
    days = (end_date - start_date).days + 1
    if days < 1:
        return None, "invalid_period"

    # Valida se o funcionário está ativo
    emp_status = await session.scalar(
        select(Employee.status).where(
            Employee.id == employee_id, Employee.company_id == company_id
        )
    )
    if emp_status is None:
        return None, "employee_not_found"
    if emp_status != "active":
        return None, "employee_inactive"

    working_days = await _calc_working_days(session, company_id, start_date, end_date)
    record = VacationRequest(
        company_id=company_id,
        employee_id=employee_id,
        start_date=start_date,
        end_date=end_date,
        days=days,
        working_days=working_days,
        notes=notes,
        status="pending",
    )
    session.add(record)
    await session.flush()
    employee_name = await session.scalar(select(Employee.name).where(Employee.id == employee_id))
    await _notify_vacation_managers(
        session, company_id, employee_name or "funcionário", record.id
    )
    await session.commit()
    await session.refresh(record)
    return record, None


async def list_vacation_requests(
    session: AsyncSession,
    company_id: int,
    page: int,
    page_size: int,
    *,
    employee_id: int | None = None,
    status: str | None = None,
    sector_id: int | None = None,
) -> tuple[list[tuple], int]:
    filters = [VacationRequest.company_id == company_id]
    if employee_id is not None:
        filters.append(VacationRequest.employee_id == employee_id)
    if status is not None:
        filters.append(VacationRequest.status == status)
    if sector_id is not None:
        filters.append(Employee.sector_id == sector_id)

    base_q = (
        select(VacationRequest, Employee.name, Employee.avatar_url, Sector.name)
        .join(Employee, Employee.id == VacationRequest.employee_id)
        .outerjoin(Sector, Sector.id == Employee.sector_id)
        .where(*filters)
    )
    total = await session.scalar(
        select(func.count()).select_from(base_q.subquery())
    ) or 0
    rows = (
        await session.execute(
            base_q
            .order_by(VacationRequest.created_at.desc())
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
    ).all()
    return rows, total  # type: ignore[return-value]


async def review_vacation_request(
    session: AsyncSession,
    company_id: int,
    actor_id: int,
    request_id: int,
    *,
    approve: bool,
    review_notes: str | None,
) -> tuple[VacationRequest | None, str | None]:
    record = await session.scalar(
        select(VacationRequest).where(
            VacationRequest.id == request_id,
            VacationRequest.company_id == company_id,
        )
    )
    if record is None:
        return None, "not_found"
    if record.status != "pending":
        return None, "already_reviewed"

    record.status = "approved" if approve else "rejected"
    record.reviewed_by_user_id = actor_id
    record.reviewed_at = datetime.now()
    record.review_notes = review_notes
    await session.commit()
    await session.refresh(record)
    return record, None


async def cancel_vacation_request(
    session: AsyncSession,
    company_id: int,
    employee_id: int,
    request_id: int,
) -> tuple[VacationRequest | None, str | None]:
    record = await session.scalar(
        select(VacationRequest).where(
            VacationRequest.id == request_id,
            VacationRequest.company_id == company_id,
            VacationRequest.employee_id == employee_id,
        )
    )
    if record is None:
        return None, "not_found"
    if record.status not in ("pending",):
        return None, "cannot_cancel"

    record.status = "cancelled"
    await session.commit()
    await session.refresh(record)
    return record, None


async def get_vacation_request_stats(session: AsyncSession, company_id: int) -> dict:
    now = datetime.now()
    months: list[date] = []
    cursor = now.replace(day=1)
    for _ in range(6):
        months.append(cursor.date())
        cursor = (cursor - timedelta(days=1)).replace(day=1)
    months.reverse()
    period_start = datetime.combine(months[0], time.min)

    month_trunc = func.date_trunc(literal_column("'month'"), VacationRequest.created_at)
    trend_rows = (
        await session.execute(
            select(month_trunc, func.count(VacationRequest.id))
            .where(
                VacationRequest.company_id == company_id,
                VacationRequest.created_at >= period_start,
            )
            .group_by(month_trunc)
        )
    ).all()
    counts_by_month = {d.date().replace(day=1).isoformat(): c for d, c in trend_rows}
    monthly_trend = [
        {"month": m.isoformat(), "count": counts_by_month.get(m.isoformat(), 0)} for m in months
    ]

    # Contagem por status
    status_rows = (
        await session.execute(
            select(VacationRequest.status, func.count(VacationRequest.id))
            .where(VacationRequest.company_id == company_id)
            .group_by(VacationRequest.status)
        )
    ).all()
    by_status = {s: c for s, c in status_rows}

    # Próximas férias aprovadas (próximos 60 dias)
    upcoming = await session.scalar(
        select(func.count(VacationRequest.id)).where(
            VacationRequest.company_id == company_id,
            VacationRequest.status == "approved",
            VacationRequest.start_date >= now.date(),
            VacationRequest.start_date <= (now + timedelta(days=60)).date(),
        )
    ) or 0

    return {
        "monthly_trend": monthly_trend,
        "pending": by_status.get("pending", 0),
        "approved_total": by_status.get("approved", 0),
        "upcoming_60d": upcoming,
    }


async def create_vacation_request_for_employee(
    session: AsyncSession,
    company_id: int,
    actor_id: int,
    employee_id: int,
    *,
    start_date: date,
    end_date: date,
    notes: str | None,
) -> tuple[VacationRequest | None, str | None]:
    """Cria uma solicitação de férias diretamente aprovada pelo RH
    (sem passar por pending — criação administrativa é aprovação implícita)."""
    if end_date < start_date:
        return None, "end_before_start"
    days = (end_date - start_date).days + 1

    # Valida se o funcionário existe e está ativo
    emp_status = await session.scalar(
        select(Employee.status).where(
            Employee.id == employee_id, Employee.company_id == company_id
        )
    )
    if emp_status is None:
        return None, "employee_not_found"
    if emp_status != "active":
        return None, "employee_inactive"

    working_days = await _calc_working_days(session, company_id, start_date, end_date)
    record = VacationRequest(
        company_id=company_id,
        employee_id=employee_id,
        start_date=start_date,
        end_date=end_date,
        days=days,
        working_days=working_days,
        notes=notes,
        status="approved",
        reviewed_by_user_id=actor_id,
        reviewed_at=datetime.now(),
        review_notes="Cadastro direto pelo RH.",
    )
    session.add(record)
    await session.commit()
    await session.refresh(record)
    return record, None


async def get_employee_vacation_entitlement(
    session: AsyncSession,
    company_id: int,
    employee_id: int,
) -> dict | None:
    """Calcula direito de férias CLT com base na data de admissão.
    CLT: 30 dias após 12 meses de serviço (proporcional antes disso)."""
    row = await session.execute(
        select(Employee.hire_date, Employee.status, Employee.name).where(
            Employee.id == employee_id, Employee.company_id == company_id
        )
    )
    emp = row.one_or_none()
    if emp is None:
        return None
    hire_date_str, status, name = emp
    if not hire_date_str:
        return {
            "employee_id": employee_id,
            "hire_date": None,
            "months_employed": None,
            "entitlement_days": 0,
            "entitlement_note": "Data de admissão não cadastrada.",
        }
    today = date.today()
    try:
        hd = date.fromisoformat(hire_date_str)
    except ValueError:
        return {
            "employee_id": employee_id,
            "hire_date": hire_date_str,
            "months_employed": None,
            "entitlement_days": 0,
            "entitlement_note": "Data de admissão com formato inválido.",
        }
    months = (today.year - hd.year) * 12 + (today.month - hd.month)
    if today.day < hd.day:
        months -= 1
    if months < 0:
        months = 0
    if months >= 12:
        entitlement = 30
        note = f"Admitido há {months} meses — direito a 30 dias de férias."
    else:
        entitlement = months * 2  # 2,5 dias por mês aproximado
        note = (
            f"Admitido há {months} mês(es) — direito proporcional a "
            f"aproximadamente {entitlement} dias de férias."
        )
    return {
        "employee_id": employee_id,
        "hire_date": hire_date_str,
        "months_employed": months,
        "entitlement_days": entitlement,
        "entitlement_note": note,
    }
