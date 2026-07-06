"""Testes de HE paga em dinheiro: salário do funcionário, toggle de config
`timeclock.overtime_paid_in_cash` e seus efeitos no espelho de ponto e no
banco de horas."""

import pytest

from tests.conftest import TENANT_A, auth_header

PREFIX = "/api/v1"
SHIFTS_URL = f"{PREFIX}/timeclock/shifts"
SCHEDULE_URL = f"{PREFIX}/timeclock/schedule"
PUNCHES_URL = f"{PREFIX}/timeclock/punches"
MIRROR_URL = f"{PREFIX}/timeclock/mirror"
EMPLOYEES_URL = f"{PREFIX}/employees"
TIMECLOCK_SETTINGS_URL = f"{PREFIX}/settings/timeclock"

HEADERS_A = auth_header(TENANT_A, 1)


async def _schedule_employee(client, *, start_date: str, end_date: str, weekday: int) -> int:
    shift_resp = await client.post(
        SHIFTS_URL,
        json={"name": "Comercial", "start_time": "08:00:00", "end_time": "17:00:00"},
        headers=HEADERS_A,
    )
    shift_id = shift_resp.json()["id"]
    await client.post(
        f"{SCHEDULE_URL}/generate",
        json={
            "employee_ids": [1],
            "shift_id": shift_id,
            "start_date": start_date,
            "end_date": end_date,
            "pattern": {"type": "weekly", "weekdays": [weekday]},
        },
        headers=HEADERS_A,
    )
    return shift_id


@pytest.mark.asyncio
async def test_employee_salary_crud(client):
    r = await client.patch(f"{EMPLOYEES_URL}/1", json={"salary": 3500.50}, headers=HEADERS_A)
    assert r.status_code == 200

    r = await client.get(f"{EMPLOYEES_URL}/1", headers=HEADERS_A)
    assert r.status_code == 200
    assert r.json()["salary"] == 3500.50


@pytest.mark.asyncio
async def test_timeclock_settings_toggle_defaults_off_and_persists(client):
    r = await client.get(TIMECLOCK_SETTINGS_URL, headers=HEADERS_A)
    assert r.status_code == 200
    assert r.json()["overtime_paid_in_cash"] is False

    r = await client.post(
        TIMECLOCK_SETTINGS_URL, json={"overtime_paid_in_cash": True}, headers=HEADERS_A
    )
    assert r.status_code == 200
    assert r.json()["overtime_paid_in_cash"] is True

    r = await client.get(TIMECLOCK_SETTINGS_URL, headers=HEADERS_A)
    assert r.json()["overtime_paid_in_cash"] is True

    # Restaura o estado para não vazar para outros testes deste módulo.
    await client.post(
        TIMECLOCK_SETTINGS_URL, json={"overtime_paid_in_cash": False}, headers=HEADERS_A
    )


@pytest.mark.asyncio
async def test_mirror_overtime_value_computed_when_toggle_on_and_salary_set(client):
    # Turno comercial 08:00-17:00 (540min esperados/dia), duas semanas úteis
    # (seg-sex) de agosto/2026 usadas como jornada mensal de referência.
    # Evita 2026-08-01/02, usados por outro teste de virada de turno noturno.
    shift_resp = await client.post(
        SHIFTS_URL,
        json={"name": "Comercial HE", "start_time": "08:00:00", "end_time": "17:00:00"},
        headers=HEADERS_A,
    )
    shift_id = shift_resp.json()["id"]
    await client.post(
        f"{SCHEDULE_URL}/generate",
        json={
            "employee_ids": [1],
            "shift_id": shift_id,
            "start_date": "2026-08-03",
            "end_date": "2026-08-14",
            "pattern": {"type": "weekly", "weekdays": [0, 1, 2, 3, 4]},
        },
        headers=HEADERS_A,
    )

    r = await client.patch(f"{EMPLOYEES_URL}/1", json={"salary": 4400.0}, headers=HEADERS_A)
    assert r.status_code == 200

    await client.post(
        TIMECLOCK_SETTINGS_URL, json={"overtime_paid_in_cash": True}, headers=HEADERS_A
    )

    # 2026-08-10 é segunda-feira: trabalha 2h a mais que o esperado (HE 50%).
    await client.post(
        PUNCHES_URL,
        json={"employee_id": 1, "punched_at": "2026-08-10T08:00:00", "punch_type": "in"},
        headers=HEADERS_A,
    )
    await client.post(
        PUNCHES_URL,
        json={"employee_id": 1, "punched_at": "2026-08-10T19:00:00", "punch_type": "out"},
        headers=HEADERS_A,
    )

    r = await client.get(
        MIRROR_URL,
        params={"employee_id": 1, "date_from": "2026-08-10", "date_to": "2026-08-10"},
        headers=HEADERS_A,
    )
    assert r.status_code == 200
    day = r.json()["days"][0]
    assert day["overtime_50_minutes"] == 120
    assert day["overtime_50_value"] is not None
    assert day["overtime_50_value"] > 0

    # Jornada mensal esperada: só os dias efetivamente escalados neste teste
    # contam (dias fora do range ficam "unscheduled" = 0 minutos esperados) —
    # 10 dias úteis (seg-sex) entre 03/08 e 14/08/2026.
    monthly_minutes = 10 * 540
    hourly_rate = 4400.0 / (monthly_minutes / 60)
    expected_value = round((120 / 60) * hourly_rate * 1.5, 2)
    assert day["overtime_50_value"] == expected_value

    # Desliga o toggle: valor some, mesmo com salário cadastrado.
    await client.post(
        TIMECLOCK_SETTINGS_URL, json={"overtime_paid_in_cash": False}, headers=HEADERS_A
    )
    r = await client.get(
        MIRROR_URL,
        params={"employee_id": 1, "date_from": "2026-08-10", "date_to": "2026-08-10"},
        headers=HEADERS_A,
    )
    day = r.json()["days"][0]
    assert day["overtime_50_value"] is None


@pytest.mark.asyncio
async def test_hour_bank_excludes_overtime_when_paid_in_cash(client):
    await _schedule_employee(client, start_date="2026-07-20", end_date="2026-07-20", weekday=0)

    await client.post(
        PUNCHES_URL,
        json={"employee_id": 1, "punched_at": "2026-07-20T08:00:00", "punch_type": "in"},
        headers=HEADERS_A,
    )
    await client.post(
        PUNCHES_URL,
        json={"employee_id": 1, "punched_at": "2026-07-20T19:00:00", "punch_type": "out"},
        headers=HEADERS_A,
    )

    await client.post(
        TIMECLOCK_SETTINGS_URL, json={"overtime_paid_in_cash": True}, headers=HEADERS_A
    )
    try:
        await client.post(
            f"{PREFIX}/timeclock/hour-bank/1/recalculate",
            json={"start_date": "2026-07-20", "end_date": "2026-07-20"},
            headers=HEADERS_A,
        )
        r = await client.get(f"{PREFIX}/timeclock/hour-bank/1", headers=HEADERS_A)
        entry = next(e for e in r.json()["entries"] if e["reference_date"] == "2026-07-20")
        # 11h trabalhadas - 9h esperadas = 2h de HE, paga em dinheiro -> não
        # entra no banco de horas (balance 0), diferente do caso padrão (120).
        assert entry["balance_minutes"] == 0
    finally:
        await client.post(
            TIMECLOCK_SETTINGS_URL, json={"overtime_paid_in_cash": False}, headers=HEADERS_A
        )


@pytest.mark.asyncio
async def test_overtime_value_falls_back_to_cargo_salary(client):
    """Funcionário sem `salary` individual usa o salário-base do cargo
    (config `timeclock.cargo_salaries`) para calcular o valor da HE."""
    r = await client.post(
        EMPLOYEES_URL,
        json={"name": "Camareira Teste", "cpf": "52998224725", "job_title": "Camareira"},
        headers=HEADERS_A,
    )
    assert r.status_code == 201
    employee_id = r.json()["id"]

    shift_resp = await client.post(
        SHIFTS_URL,
        json={"name": "Comercial Cargo", "start_time": "08:00:00", "end_time": "17:00:00"},
        headers=HEADERS_A,
    )
    shift_id = shift_resp.json()["id"]
    await client.post(
        f"{SCHEDULE_URL}/generate",
        json={
            "employee_ids": [employee_id],
            "shift_id": shift_id,
            "start_date": "2026-09-07",
            "end_date": "2026-09-07",
            "pattern": {"type": "weekly", "weekdays": [0]},
        },
        headers=HEADERS_A,
    )

    await client.post(
        TIMECLOCK_SETTINGS_URL,
        json={"overtime_paid_in_cash": True, "cargo_salaries": {"Camareira": 2200.0}},
        headers=HEADERS_A,
    )
    try:
        await client.post(
            PUNCHES_URL,
            json={"employee_id": employee_id, "punched_at": "2026-09-07T08:00:00", "punch_type": "in"},
            headers=HEADERS_A,
        )
        await client.post(
            PUNCHES_URL,
            json={"employee_id": employee_id, "punched_at": "2026-09-07T19:00:00", "punch_type": "out"},
            headers=HEADERS_A,
        )

        r = await client.get(
            MIRROR_URL,
            params={
                "employee_id": employee_id,
                "date_from": "2026-09-07",
                "date_to": "2026-09-07",
            },
            headers=HEADERS_A,
        )
        assert r.status_code == 200
        day = r.json()["days"][0]
        assert day["overtime_50_minutes"] == 120
        assert day["overtime_50_value"] is not None
        assert day["overtime_50_value"] > 0

        # Banco de horas também não deve bancar a HE, mesmo sem salary
        # individual (o cargo resolve o salário).
        await client.post(
            f"{PREFIX}/timeclock/hour-bank/{employee_id}/recalculate",
            json={"start_date": "2026-09-07", "end_date": "2026-09-07"},
            headers=HEADERS_A,
        )
        r = await client.get(f"{PREFIX}/timeclock/hour-bank/{employee_id}", headers=HEADERS_A)
        entry = next(e for e in r.json()["entries"] if e["reference_date"] == "2026-09-07")
        assert entry["balance_minutes"] == 0
    finally:
        await client.post(
            TIMECLOCK_SETTINGS_URL,
            json={"overtime_paid_in_cash": False, "cargo_salaries": {}},
            headers=HEADERS_A,
        )
