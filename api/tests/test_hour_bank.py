"""Testes do banco de horas: cálculo diário (escala x pontos), saldo inicial e
isolamento por permissão."""

import pytest

from tests.conftest import TENANT_A, auth_header

PREFIX = "/api/v1"
SHIFTS_URL = f"{PREFIX}/timeclock/shifts"
SCHEDULE_URL = f"{PREFIX}/timeclock/schedule"
PUNCHES_URL = f"{PREFIX}/timeclock/punches"

HEADERS_A = auth_header(TENANT_A, 1)


def _no_permissions_header() -> dict[str, str]:
    from tests.conftest import make_token

    return {"Authorization": f"Bearer {make_token(TENANT_A, 1, [])}"}


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
async def test_recalculate_hour_bank_matches_exact_shift(client):
    # 2026-07-06 é uma segunda-feira (weekday=0).
    await _schedule_employee(client, start_date="2026-07-06", end_date="2026-07-06", weekday=0)

    await client.post(
        PUNCHES_URL,
        json={"employee_id": 1, "punched_at": "2026-07-06T08:00:00", "punch_type": "in"},
        headers=HEADERS_A,
    )
    await client.post(
        PUNCHES_URL,
        json={"employee_id": 1, "punched_at": "2026-07-06T17:00:00", "punch_type": "out"},
        headers=HEADERS_A,
    )

    r = await client.post(
        f"{PREFIX}/timeclock/hour-bank/1/recalculate",
        json={"start_date": "2026-07-06", "end_date": "2026-07-06"},
        headers=HEADERS_A,
    )
    assert r.status_code == 200
    assert r.json()["affected"] == 1

    r = await client.get(f"{PREFIX}/timeclock/hour-bank/1", headers=HEADERS_A)
    assert r.status_code == 200
    body = r.json()
    assert body["balance_minutes"] == 0
    entry = next(e for e in body["entries"] if e["reference_date"] == "2026-07-06")
    assert entry["expected_minutes"] == 540
    assert entry["worked_minutes"] == 540
    assert entry["source"] == "calculated"


@pytest.mark.asyncio
async def test_recalculate_hour_bank_with_overtime(client):
    await _schedule_employee(client, start_date="2026-07-13", end_date="2026-07-13", weekday=0)

    await client.post(
        PUNCHES_URL,
        json={"employee_id": 1, "punched_at": "2026-07-13T08:00:00", "punch_type": "in"},
        headers=HEADERS_A,
    )
    await client.post(
        PUNCHES_URL,
        json={"employee_id": 1, "punched_at": "2026-07-13T19:00:00", "punch_type": "out"},
        headers=HEADERS_A,
    )

    await client.post(
        f"{PREFIX}/timeclock/hour-bank/1/recalculate",
        json={"start_date": "2026-07-13", "end_date": "2026-07-13"},
        headers=HEADERS_A,
    )
    r = await client.get(f"{PREFIX}/timeclock/hour-bank/1", headers=HEADERS_A)
    entry = next(e for e in r.json()["entries"] if e["reference_date"] == "2026-07-13")
    # 11h trabalhadas (660min) - 9h esperadas (540min) = +120min de saldo.
    assert entry["balance_minutes"] == 120


@pytest.mark.asyncio
async def test_set_initial_balance_adds_to_total(client):
    r = await client.post(
        f"{PREFIX}/timeclock/hour-bank/1/initial-balance",
        json={"effective_date": "2026-01-01", "balance_minutes": 300, "notes": "Migração do V1"},
        headers=HEADERS_A,
    )
    assert r.status_code == 201
    initial_entry = next(e for e in r.json()["entries"] if e["source"] == "initial_balance")
    assert initial_entry["balance_minutes"] == 300

    # Reenviar saldo inicial substitui o lançamento anterior, não soma.
    r = await client.post(
        f"{PREFIX}/timeclock/hour-bank/1/initial-balance",
        json={"effective_date": "2026-01-01", "balance_minutes": 200, "notes": "Correção"},
        headers=HEADERS_A,
    )
    initial_entries = [e for e in r.json()["entries"] if e["source"] == "initial_balance"]
    assert len(initial_entries) == 1
    assert initial_entries[0]["balance_minutes"] == 200


@pytest.mark.asyncio
async def test_hour_bank_requires_permission(client):
    headers = _no_permissions_header()
    r = await client.get(f"{PREFIX}/timeclock/hour-bank/1", headers=headers)
    assert r.status_code == 403

    r = await client.post(
        f"{PREFIX}/timeclock/hour-bank/1/recalculate",
        json={"start_date": "2026-07-06", "end_date": "2026-07-06"},
        headers=headers,
    )
    assert r.status_code == 403


@pytest.mark.asyncio
async def test_recalculate_invalid_range_rejected(client):
    r = await client.post(
        f"{PREFIX}/timeclock/hour-bank/1/recalculate",
        json={"start_date": "2026-07-06", "end_date": "2026-07-01"},
        headers=HEADERS_A,
    )
    assert r.status_code == 422
