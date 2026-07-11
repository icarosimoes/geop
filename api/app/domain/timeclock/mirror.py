"""Espelho de ponto: grade diária de batidas + horas extras/adicional noturno.

Regras assumidas (simplificações conscientes, documentadas para o usuário):
- HE 50%: minutos trabalhados além do esperado em dia normal.
- HE 100%: minutos trabalhados além do esperado em dia de descanso (domingo,
  folga agendada ou feriado cadastrado em `holidays` — ver `get_holiday_dates`).
- Adicional noturno: minutos trabalhados entre 22h-05h, com a "hora noturna
  reduzida" da CLT (art. 73 §1º: cada hora noturna equivale a 52min30s de
  relógio, ou seja, 60/52.5 ≈ 1.142857 "horas" por hora real trabalhada) somada
  ao adicional de 20% sobre a hora noturna. Simplificação: aplicamos a soma dos
  dois efeitos (redução + adicional) como um único percentual sobre os minutos
  noturnos reais, em vez de recalcular a jornada em "horas noturnas".
- Valor em R$ da hora extra: só calculado quando a config de tenant
  `timeclock.overtime_paid_in_cash` está ligada e o funcionário tem `salary`
  preenchido. O valor da hora é `salary / jornada_mensal_esperada_em_horas`,
  onde a jornada mensal é a soma dos minutos esperados de escala de todos os
  dias do mês corrente do dia em questão (ver `_monthly_expected_minutes`).
"""

import calendar
from datetime import date, datetime, time, timedelta

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.settings.router import get_company_setting
from app.domain.timeclock.service import (
    _pair_punches,
    _resolve_salary,
    _resolve_schedule_for_date,
    _shift_expected_minutes,
    get_holiday_dates,
)
from app.models import Employee, Sector, TimePunch

NIGHT_START = time(22, 0)
NIGHT_END = time(5, 0)
NIGHT_DIFFERENTIAL_RATE = 0.20
# CLT art. 73 §1º: a hora noturna equivale a 52min30s de relógio.
NIGHT_HOUR_REDUCTION_FACTOR = 60 / 52.5
# Efeito combinado: redução da hora noturna (a mais) + adicional noturno de 20%,
# aplicado como um único percentual sobre os minutos noturnos reais trabalhados.
NIGHT_COMBINED_RATE = (NIGHT_HOUR_REDUCTION_FACTOR - 1) + NIGHT_DIFFERENTIAL_RATE
# HE 50%: hora normal + 50%. HE 100%: hora normal em dobro.
OVERTIME_50_RATE = 1.5
OVERTIME_100_RATE = 2.0


def _night_differential_minutes(pair_in: datetime, pair_out: datetime) -> int:
    total = 0
    day = pair_in.date() - timedelta(days=1)
    last_day = pair_out.date()
    while day <= last_day:
        window_start = datetime.combine(day, NIGHT_START)
        window_end = window_start + timedelta(hours=NIGHT_END.hour + 24 - NIGHT_START.hour)
        overlap_start = max(pair_in, window_start)
        overlap_end = min(pair_out, window_end)
        if overlap_end > overlap_start:
            total += int((overlap_end - overlap_start).total_seconds() // 60)
        day += timedelta(days=1)
    return round(total * NIGHT_COMBINED_RATE)


async def _monthly_expected_minutes(
    session: AsyncSession, company_id: int, employee_id: int, year: int, month: int
) -> int:
    """Soma os minutos de escala esperados em todos os dias do mês, usada como
    divisor para converter salário mensal em valor de hora (ver módulo)."""
    days_in_month = calendar.monthrange(year, month)[1]
    total = 0
    for day_num in range(1, days_in_month + 1):
        current = date(year, month, day_num)
        shift, forced_status = await _resolve_schedule_for_date(
            session, company_id, employee_id, current
        )
        total += 0 if forced_status else _shift_expected_minutes(shift)
    return total


async def _hourly_rate(
    session: AsyncSession,
    company_id: int,
    employee_id: int,
    salary: float | None,
    day: date,
    cache: dict[tuple[int, int], int],
) -> float | None:
    if not salary:
        return None
    cache_key = (day.year, day.month)
    if cache_key not in cache:
        cache[cache_key] = await _monthly_expected_minutes(
            session, company_id, employee_id, day.year, day.month
        )
    monthly_minutes = cache[cache_key]
    if monthly_minutes <= 0:
        return None
    return salary / (monthly_minutes / 60)


async def build_day_mirror(
    session: AsyncSession,
    company_id: int,
    employee_id: int,
    day: date,
    holiday_dates: set[date] | None = None,
    hourly_rate: float | None = None,
) -> dict:
    shift, forced_status = await _resolve_schedule_for_date(session, company_id, employee_id, day)
    expected_minutes = 0 if forced_status else _shift_expected_minutes(shift)

    punches = (
        await session.scalars(
            select(TimePunch).where(
                TimePunch.company_id == company_id,
                TimePunch.employee_id == employee_id,
                TimePunch.punched_at >= datetime.combine(day, time.min),
                TimePunch.punched_at <= datetime.combine(day, time.max),
            )
        )
    ).all()
    pairs = _pair_punches(list(punches))

    worked_minutes = sum(int((out - inn).total_seconds() // 60) for inn, out in pairs)
    worked_minutes = max(worked_minutes, 0)

    break_minutes = 0
    if len(pairs) >= 2:
        break_minutes = max(0, int((pairs[1][0] - pairs[0][1]).total_seconds() // 60))

    night_differential_minutes = sum(_night_differential_minutes(inn, out) for inn, out in pairs)

    is_holiday = day in holiday_dates if holiday_dates else False
    is_rest_day = forced_status == "day_off" or day.weekday() == 6 or is_holiday
    overtime_minutes = max(0, worked_minutes - expected_minutes)
    overtime_50 = 0 if is_rest_day else overtime_minutes
    overtime_100 = overtime_minutes if is_rest_day else 0

    overtime_50_value = None
    overtime_100_value = None
    if hourly_rate is not None:
        overtime_50_value = round((overtime_50 / 60) * hourly_rate * OVERTIME_50_RATE, 2)
        overtime_100_value = round((overtime_100 / 60) * hourly_rate * OVERTIME_100_RATE, 2)

    credit_minutes = max(0, worked_minutes - expected_minutes)
    debit_minutes = max(0, expected_minutes - worked_minutes)
    balance_minutes = worked_minutes - expected_minutes

    notes = ""
    if forced_status == "day_off":
        notes = "Folga"
    elif forced_status == "unscheduled":
        notes = "Sem escala"
    if is_holiday:
        notes = f"{notes} / Feriado" if notes else "Feriado"

    return {
        "date": day,
        "first_in": pairs[0][0] if len(pairs) >= 1 else None,
        "first_out": pairs[0][1] if len(pairs) >= 1 else None,
        "second_in": pairs[1][0] if len(pairs) >= 2 else None,
        "second_out": pairs[1][1] if len(pairs) >= 2 else None,
        "credit_minutes": credit_minutes,
        "debit_minutes": debit_minutes,
        "break_minutes": break_minutes,
        "worked_minutes": worked_minutes,
        "overtime_50_minutes": overtime_50,
        "overtime_100_minutes": overtime_100,
        "overtime_50_value": overtime_50_value,
        "overtime_100_value": overtime_100_value,
        "night_differential_minutes": night_differential_minutes,
        "balance_minutes": balance_minutes,
        "notes": notes,
    }


async def build_employee_mirror(
    session: AsyncSession,
    company_id: int,
    employee_id: int,
    date_from: date,
    date_to: date,
) -> dict | None:
    employee_row = (
        await session.execute(
            select(
                Employee.name, Employee.avatar_url, Sector.name, Employee.salary, Employee.job_title
            )
            .outerjoin(Sector, Sector.id == Employee.sector_id)
            .where(
                Employee.id == employee_id,
                Employee.company_id == company_id,
                Employee.deleted_at.is_(None),
            )
        )
    ).first()
    if employee_row is None:
        return None
    employee_name, avatar_url, sector_name, employee_salary, job_title = employee_row
    holiday_dates = await get_holiday_dates(session, company_id, date_from, date_to)
    timeclock_settings = await get_company_setting(session, company_id, "timeclock")
    salary = _resolve_salary(
        employee_salary, job_title, timeclock_settings.get("cargo_salaries", {})
    )
    overtime_paid_in_cash = bool(timeclock_settings.get("overtime_paid_in_cash")) and salary

    rate_cache: dict[tuple[int, int], int] = {}
    days = []
    current = date_from
    while current <= date_to:
        hourly_rate = None
        if overtime_paid_in_cash:
            hourly_rate = await _hourly_rate(
                session, company_id, employee_id, salary, current, rate_cache
            )
        day_mirror = await build_day_mirror(
            session, company_id, employee_id, current, holiday_dates, hourly_rate
        )
        days.append(day_mirror)
        current += timedelta(days=1)

    totals = {
        "credit_minutes": sum(d["credit_minutes"] for d in days),
        "debit_minutes": sum(d["debit_minutes"] for d in days),
        "break_minutes": sum(d["break_minutes"] for d in days),
        "worked_minutes": sum(d["worked_minutes"] for d in days),
        "overtime_50_minutes": sum(d["overtime_50_minutes"] for d in days),
        "overtime_100_minutes": sum(d["overtime_100_minutes"] for d in days),
        "night_differential_minutes": sum(d["night_differential_minutes"] for d in days),
        "balance_minutes": sum(d["balance_minutes"] for d in days),
        "overtime_50_value": (
            round(sum(d["overtime_50_value"] for d in days), 2) if overtime_paid_in_cash else None
        ),
        "overtime_100_value": (
            round(sum(d["overtime_100_value"] for d in days), 2) if overtime_paid_in_cash else None
        ),
    }

    return {
        "employee_id": employee_id,
        "employee_name": employee_name,
        "employee_avatar_url": avatar_url,
        "sector_name": sector_name,
        "days": days,
        "totals": totals,
    }


async def build_sector_mirrors(
    session: AsyncSession,
    company_id: int,
    sector_id: int,
    date_from: date,
    date_to: date,
) -> list[dict]:
    """Gera o espelho de ponto de todos os funcionários ativos de um setor.

    Reaproveita build_employee_mirror por funcionário — sem otimização de
    N+1 entre funcionários (aceitável para o tamanho de equipe de um hotel;
    revisar se um tenant com centenas de funcionários por setor virar gargalo).
    """
    employee_ids = (
        await session.scalars(
            select(Employee.id)
            .where(
                Employee.company_id == company_id,
                Employee.sector_id == sector_id,
                Employee.deleted_at.is_(None),
                Employee.status == "active",
            )
            .order_by(Employee.name)
        )
    ).all()

    mirrors = []
    for employee_id in employee_ids:
        mirror = await build_employee_mirror(session, company_id, employee_id, date_from, date_to)
        if mirror is not None:
            mirrors.append(mirror)
    return mirrors
