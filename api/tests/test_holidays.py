"""Testes de feriados: CRUD, HE 100% no espelho e espelho por setor."""

import pytest

from tests.conftest import TENANT_A, auth_header

PREFIX = "/api/v1"
HOLIDAYS_URL = f"{PREFIX}/timeclock/holidays"
SHIFTS_URL = f"{PREFIX}/timeclock/shifts"
SCHEDULE_URL = f"{PREFIX}/timeclock/schedule"
PUNCHES_URL = f"{PREFIX}/timeclock/punches"
MIRROR_URL = f"{PREFIX}/timeclock/mirror"
EMPLOYEES_URL = f"{PREFIX}/employees"

HEADERS_A = auth_header(TENANT_A, 1)


@pytest.mark.asyncio
async def test_holiday_crud(client):
    r = await client.post(
        HOLIDAYS_URL, json={"date": "2026-09-07", "name": "Independência"}, headers=HEADERS_A
    )
    assert r.status_code == 201
    holiday_id = r.json()["id"]

    r = await client.get(HOLIDAYS_URL, headers=HEADERS_A)
    assert r.status_code == 200
    assert any(h["id"] == holiday_id for h in r.json())

    r = await client.get(f"{HOLIDAYS_URL}?year=2026", headers=HEADERS_A)
    assert any(h["id"] == holiday_id for h in r.json())
    r = await client.get(f"{HOLIDAYS_URL}?year=2027", headers=HEADERS_A)
    assert not any(h["id"] == holiday_id for h in r.json())

    r = await client.delete(f"{HOLIDAYS_URL}/{holiday_id}", headers=HEADERS_A)
    assert r.status_code == 204

    r = await client.get(HOLIDAYS_URL, headers=HEADERS_A)
    assert not any(h["id"] == holiday_id for h in r.json())


@pytest.mark.asyncio
async def test_holiday_duplicate_date_conflicts(client):
    r = await client.post(
        HOLIDAYS_URL,
        json={"date": "2026-11-15", "name": "Proclamação da República"},
        headers=HEADERS_A,
    )
    assert r.status_code == 201

    r = await client.post(
        HOLIDAYS_URL, json={"date": "2026-11-15", "name": "Duplicado"}, headers=HEADERS_A
    )
    assert r.status_code == 409
    assert r.json()["detail"]["code"] == "duplicate_date"


@pytest.mark.asyncio
async def test_mirror_overtime_100_on_holiday(client):
    # 2026-08-11 é uma terça-feira (weekday=1) — não é domingo nem folga agendada,
    # então sem o feriado cadastrado o excedente contaria como HE 50%.
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
            "start_date": "2026-08-11",
            "end_date": "2026-08-11",
            "pattern": {"type": "weekly", "weekdays": [1]},
        },
        headers=HEADERS_A,
    )
    await client.post(
        HOLIDAYS_URL, json={"date": "2026-08-11", "name": "Feriado de teste"}, headers=HEADERS_A
    )

    await client.post(
        PUNCHES_URL,
        json={"employee_id": 1, "punched_at": "2026-08-11T08:00:00", "punch_type": "in"},
        headers=HEADERS_A,
    )
    await client.post(
        PUNCHES_URL,
        json={"employee_id": 1, "punched_at": "2026-08-11T19:00:00", "punch_type": "out"},
        headers=HEADERS_A,
    )

    r = await client.get(
        MIRROR_URL,
        params={"employee_id": 1, "date_from": "2026-08-11", "date_to": "2026-08-11"},
        headers=HEADERS_A,
    )
    assert r.status_code == 200
    day = r.json()["days"][0]
    # Esperado 540min (9h), trabalhado 660min (11h) -> 120min excedentes.
    assert day["overtime_50_minutes"] == 0
    assert day["overtime_100_minutes"] == 120
    assert "Feriado" in day["notes"]


@pytest.mark.asyncio
async def test_mirror_night_differential_uses_reduced_hour(client):
    # Batida integralmente dentro da janela noturna (22h-23h = 60min reais).
    await client.post(
        PUNCHES_URL,
        json={"employee_id": 1, "punched_at": "2026-08-12T22:00:00", "punch_type": "in"},
        headers=HEADERS_A,
    )
    await client.post(
        PUNCHES_URL,
        json={"employee_id": 1, "punched_at": "2026-08-12T23:00:00", "punch_type": "out"},
        headers=HEADERS_A,
    )

    r = await client.get(
        MIRROR_URL,
        params={"employee_id": 1, "date_from": "2026-08-12", "date_to": "2026-08-12"},
        headers=HEADERS_A,
    )
    assert r.status_code == 200
    day = r.json()["days"][0]
    # 60 * ((60/52.5 - 1) + 0.20) = 60 * 12/35 ≈ 20.57 -> arredonda para 21.
    # (Simplificação anterior, sem hora reduzida, resultaria em 12.)
    assert day["night_differential_minutes"] == 21


@pytest.mark.asyncio
async def test_mirror_by_sector(client):
    r = await client.post(
        "/api/v1/registries", json={"name": "Cozinha Teste", "category": "Setor"}, headers=HEADERS_A
    )
    assert r.status_code == 201
    sector_id = r.json()["id"]

    r = await client.patch(f"{EMPLOYEES_URL}/1", json={"sector_id": sector_id}, headers=HEADERS_A)
    assert r.status_code == 200

    r = await client.get(
        f"{PREFIX}/timeclock/mirror/by-sector",
        params={"sector_id": sector_id, "date_from": "2026-08-01", "date_to": "2026-08-01"},
        headers=HEADERS_A,
    )
    assert r.status_code == 200
    mirrors = r.json()["mirrors"]
    assert len(mirrors) == 1
    assert mirrors[0]["employee_id"] == 1
