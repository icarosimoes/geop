"""Testes de escala de trabalho e ponto eletrônico (Control iD via webhook)."""

from datetime import datetime, time

import pytest

from app.domain.timeclock.service import evaluate_status
from app.models import Shift
from tests.conftest import TENANT_A, auth_header

HEADERS_A = auth_header(TENANT_A, 1)
SHIFTS_URL = "/api/v1/timeclock/shifts"
SCHEDULE_URL = "/api/v1/timeclock/schedule"
DEVICES_URL = "/api/v1/timeclock/devices"
ENROLLMENTS_URL = "/api/v1/timeclock/enrollments"
PUNCHES_URL = "/api/v1/timeclock/punches"


def _shift(**overrides) -> Shift:
    shift = Shift(
        company_id=TENANT_A,
        name="Turno de teste",
        start_time=time(8, 0),
        end_time=time(17, 0),
        tolerance_minutes=10,
        color="#2563eb",
    )
    for key, value in overrides.items():
        setattr(shift, key, value)
    return shift


def _overnight_shift(**overrides) -> Shift:
    shift = Shift(
        company_id=TENANT_A,
        name="Turno noturno",
        start_time=time(22, 0),
        end_time=time(6, 0),
        tolerance_minutes=10,
        color="#111827",
    )
    for key, value in overrides.items():
        setattr(shift, key, value)
    return shift


# ── evaluate_status (regra pura) ──


def test_evaluate_status_no_schedule_is_unscheduled():
    assert evaluate_status(None, datetime(2026, 7, 6, 8, 0), "in") == "unscheduled"


def test_evaluate_status_on_time_entry():
    shift = _shift()
    assert evaluate_status(shift, datetime(2026, 7, 6, 8, 5), "in") == "on_time"


def test_evaluate_status_late_entry():
    shift = _shift()
    assert evaluate_status(shift, datetime(2026, 7, 6, 8, 20), "in") == "late"


def test_evaluate_status_early_leave():
    shift = _shift()
    assert evaluate_status(shift, datetime(2026, 7, 6, 16, 30), "out") == "early_leave"


def test_evaluate_status_on_time_leave():
    shift = _shift()
    assert evaluate_status(shift, datetime(2026, 7, 6, 17, 5), "out") == "on_time"


def test_evaluate_status_infers_type_when_missing_closer_to_start():
    shift = _shift()
    assert evaluate_status(shift, datetime(2026, 7, 6, 8, 20), None) == "late"


def test_evaluate_status_infers_type_when_missing_closer_to_end():
    shift = _shift()
    assert evaluate_status(shift, datetime(2026, 7, 6, 16, 30), None) == "early_leave"


# ── evaluate_status: turno noturno (Bug 3) ──


def test_evaluate_status_overnight_entry_on_time():
    shift = _overnight_shift()
    # Entrada às 22:05 do dia da escala: dentro da tolerância
    assert evaluate_status(shift, datetime(2026, 7, 6, 22, 5), "in") == "on_time"


def test_evaluate_status_overnight_entry_late():
    shift = _overnight_shift()
    # Entrada às 22:20 do dia da escala: atrasado
    assert evaluate_status(shift, datetime(2026, 7, 6, 22, 20), "in") == "late"


def test_evaluate_status_overnight_exit_next_day_on_time():
    shift = _overnight_shift()
    # Saída às 06:10 do dia SEGUINTE ao da escala: dentro da tolerância
    assert evaluate_status(shift, datetime(2026, 7, 7, 6, 10), "out") == "on_time"


def test_evaluate_status_overnight_exit_next_day_early():
    shift = _overnight_shift()
    # Saída às 05:00 do dia seguinte: bem antes do fim do turno (06:00)
    assert evaluate_status(shift, datetime(2026, 7, 7, 5, 0), "out") == "early_leave"


def test_evaluate_status_overnight_infers_type_near_start():
    shift = _overnight_shift()
    # Batida às 22:05 sem tipo informado: mais perto do início (22:00) do que do fim (06:00 do dia seguinte)
    assert evaluate_status(shift, datetime(2026, 7, 6, 22, 5), None) == "on_time"


def test_evaluate_status_overnight_infers_type_near_end():
    shift = _overnight_shift()
    # Batida às 06:05 do dia seguinte sem tipo informado: mais perto do fim
    assert evaluate_status(shift, datetime(2026, 7, 7, 6, 5), None) == "on_time"


# ── Turnos via API ──


@pytest.mark.asyncio
async def test_create_and_list_shifts(client):
    r = await client.post(
        SHIFTS_URL,
        json={
            "name": "Manhã",
            "start_time": "08:00:00",
            "end_time": "17:00:00",
            "tolerance_minutes": 10,
            "color": "#2563eb",
        },
        headers=HEADERS_A,
    )
    assert r.status_code == 201
    shift = r.json()
    assert shift["name"] == "Manhã"
    assert shift["color"] == "#2563eb"
    shift_id = shift["id"]

    r = await client.get(SHIFTS_URL, headers=HEADERS_A)
    assert r.status_code == 200
    assert any(s["id"] == shift_id for s in r.json())


@pytest.mark.asyncio
async def test_delete_shift_blocked_when_in_use(client):
    """Bug 2: não pode deletar turno referenciado em ScheduleEntry."""
    shift_resp = await client.post(
        SHIFTS_URL,
        json={"name": "Em uso", "start_time": "08:00:00", "end_time": "17:00:00"},
        headers=HEADERS_A,
    )
    shift_id = shift_resp.json()["id"]

    await client.put(
        f"{SCHEDULE_URL}/1/2026-08-10",
        json={"shift_id": shift_id},
        headers=HEADERS_A,
    )

    r = await client.delete(f"{SHIFTS_URL}/{shift_id}", headers=HEADERS_A)
    assert r.status_code == 409
    assert r.json()["detail"]["code"] == "shift_in_use"


@pytest.mark.asyncio
async def test_delete_shift_allowed_when_unused(client):
    shift_resp = await client.post(
        SHIFTS_URL,
        json={"name": "Sem uso", "start_time": "08:00:00", "end_time": "17:00:00"},
        headers=HEADERS_A,
    )
    shift_id = shift_resp.json()["id"]

    r = await client.delete(f"{SHIFTS_URL}/{shift_id}", headers=HEADERS_A)
    assert r.status_code == 204


# ── Calendário de escala via API ──


@pytest.mark.asyncio
async def test_set_schedule_day_and_get_calendar(client):
    shift_resp = await client.post(
        SHIFTS_URL,
        json={
            "name": "Padrão",
            "start_time": "08:00:00",
            "end_time": "17:00:00",
            "tolerance_minutes": 10,
            "color": "#3b82f6",
        },
        headers=HEADERS_A,
    )
    shift_id = shift_resp.json()["id"]

    r = await client.put(
        f"{SCHEDULE_URL}/1/2026-06-06",
        json={"shift_id": shift_id},
        headers=HEADERS_A,
    )
    assert r.status_code == 200
    assert r.json()["shift_id"] == shift_id

    r = await client.get(
        f"{SCHEDULE_URL}?start=2026-06-06&end=2026-06-06&employee_id=1", headers=HEADERS_A
    )
    assert r.status_code == 200
    items = r.json()
    assert any(e["date"] == "2026-06-06" and e["shift_id"] == shift_id for e in items)


@pytest.mark.asyncio
async def test_set_schedule_day_with_day_off(client):
    r = await client.put(
        f"{SCHEDULE_URL}/1/2026-06-07",
        json={"shift_id": None},
        headers=HEADERS_A,
    )
    assert r.status_code == 200
    assert r.json()["shift_id"] is None

    r = await client.get(
        f"{SCHEDULE_URL}?start=2026-06-07&end=2026-06-07&employee_id=1", headers=HEADERS_A
    )
    items = r.json()
    assert any(e["date"] == "2026-06-07" and e["shift_id"] is None for e in items)


@pytest.mark.asyncio
async def test_generate_schedule_weekly(client):
    shift_resp = await client.post(
        SHIFTS_URL,
        json={
            "name": "Seg-Sex",
            "start_time": "09:00:00",
            "end_time": "18:00:00",
            "tolerance_minutes": 5,
            "color": "#059669",
        },
        headers=HEADERS_A,
    )
    shift_id = shift_resp.json()["id"]

    r = await client.post(
        f"{SCHEDULE_URL}/generate",
        json={
            "employee_ids": [1],
            "shift_id": shift_id,
            "start_date": "2026-06-15",
            "end_date": "2026-06-19",
            "pattern": {"type": "weekly", "weekdays": [0, 1, 2, 3, 4]},
        },
        headers=HEADERS_A,
    )
    assert r.status_code == 200
    assert r.json()["affected"] == 5

    r = await client.get(
        f"{SCHEDULE_URL}?start=2026-06-15&end=2026-06-19&employee_id=1", headers=HEADERS_A
    )
    items = r.json()
    assert len(items) == 5
    assert all(e["shift_id"] == shift_id for e in items)


@pytest.mark.asyncio
async def test_generate_schedule_rotating(client):
    shift_resp = await client.post(
        SHIFTS_URL,
        json={
            "name": "12x36",
            "start_time": "06:00:00",
            "end_time": "18:00:00",
            "tolerance_minutes": 10,
            "color": "#dc2626",
        },
        headers=HEADERS_A,
    )
    shift_id = shift_resp.json()["id"]

    r = await client.post(
        f"{SCHEDULE_URL}/generate",
        json={
            "employee_ids": [1],
            "shift_id": shift_id,
            "start_date": "2026-05-01",
            "end_date": "2026-05-10",
            "pattern": {"type": "rotating", "work_days": 1, "off_days": 2},
        },
        headers=HEADERS_A,
    )
    assert r.status_code == 200
    assert r.json()["affected"] == 10

    r = await client.get(
        f"{SCHEDULE_URL}?start=2026-05-01&end=2026-05-10&employee_id=1", headers=HEADERS_A
    )
    items = r.json()
    assert len(items) == 10
    working_days = sum(1 for e in items if e["shift_id"] == shift_id)
    assert working_days >= 3


@pytest.mark.asyncio
async def test_generate_schedule_records_audit_per_employee(client, session):
    """Bug 4: generate_schedule registra um AuditEvent por employee afetado (entity_id=employee_id)."""
    from sqlalchemy import select

    from app.models import AuditEvent

    shift_resp = await client.post(
        SHIFTS_URL,
        json={"name": "Auditado", "start_time": "08:00:00", "end_time": "17:00:00"},
        headers=HEADERS_A,
    )
    shift_id = shift_resp.json()["id"]

    r = await client.post(
        f"{SCHEDULE_URL}/generate",
        json={
            "employee_ids": [1],
            "shift_id": shift_id,
            "start_date": "2026-09-01",
            "end_date": "2026-09-05",
            "pattern": {"type": "weekly", "weekdays": [0, 1, 2, 3, 4]},
        },
        headers=HEADERS_A,
    )
    assert r.status_code == 200

    events = (
        (
            await session.execute(
                select(AuditEvent).where(
                    AuditEvent.company_id == TENANT_A,
                    AuditEvent.entity_type == "schedule_entry",
                    AuditEvent.entity_id == 1,
                )
            )
        )
        .scalars()
        .all()
    )
    assert len(events) >= 1
    assert all(e.entity_id == 1 for e in events)


@pytest.mark.asyncio
async def test_manual_day_not_overwritten_by_generate(client):
    shift_resp = await client.post(
        SHIFTS_URL,
        json={"name": "Turno A", "start_time": "08:00:00", "end_time": "17:00:00"},
        headers=HEADERS_A,
    )
    shift_id = shift_resp.json()["id"]

    shift2_resp = await client.post(
        SHIFTS_URL,
        json={"name": "Turno B", "start_time": "18:00:00", "end_time": "22:00:00"},
        headers=HEADERS_A,
    )
    shift2_id = shift2_resp.json()["id"]

    await client.put(
        f"{SCHEDULE_URL}/1/2026-04-08",
        json={"shift_id": shift2_id},
        headers=HEADERS_A,
    )

    await client.post(
        f"{SCHEDULE_URL}/generate",
        json={
            "employee_ids": [1],
            "shift_id": shift_id,
            "start_date": "2026-04-07",
            "end_date": "2026-04-10",
            "pattern": {"type": "weekly", "weekdays": [0, 1, 2, 3, 4]},
        },
        headers=HEADERS_A,
    )

    r = await client.get(
        f"{SCHEDULE_URL}?start=2026-04-08&end=2026-04-08&employee_id=1", headers=HEADERS_A
    )
    items = r.json()
    assert items[0]["shift_id"] == shift2_id


# ── Dispositivos e vínculos ──


@pytest.mark.asyncio
async def test_create_device_and_enrollment(client):
    r = await client.post(DEVICES_URL, json={"name": "Recepção"}, headers=HEADERS_A)
    assert r.status_code == 201
    device = r.json()
    assert device["webhook_token"]
    assert device["model"] == "control_id"

    r = await client.post(
        ENROLLMENTS_URL, json={"employee_id": 1, "external_id": "0001"}, headers=HEADERS_A
    )
    assert r.status_code == 201
    assert r.json()["external_id"] == "0001"


# ── Webhook de ingestão ──


@pytest.mark.asyncio
async def test_webhook_ingests_punch_and_matches_schedule(client):
    shift_resp = await client.post(
        SHIFTS_URL,
        json={"name": "Turno", "start_time": "08:00:00", "end_time": "17:00:00"},
        headers=HEADERS_A,
    )
    shift_id = shift_resp.json()["id"]

    await client.post(
        f"{SCHEDULE_URL}/generate",
        json={
            "employee_ids": [1],
            "shift_id": shift_id,
            "start_date": "2026-07-06",
            "end_date": "2026-07-06",
            "pattern": {"type": "weekly", "weekdays": [0]},
        },
        headers=HEADERS_A,
    )

    device_resp = await client.post(DEVICES_URL, json={"name": "Portaria"}, headers=HEADERS_A)
    token = device_resp.json()["webhook_token"]
    await client.post(
        ENROLLMENTS_URL, json={"employee_id": 1, "external_id": "0099"}, headers=HEADERS_A
    )

    payload = {
        "external_id": "0099",
        "timestamp": "2026-07-06T08:25:00",
        "type": "in",
        "event_id": "evt-1",
    }
    r = await client.post(f"/api/v1/integrations/control-id/{token}/punches", json=payload)
    assert r.status_code == 200
    assert r.json()["processed"] == 1

    r = await client.get(PUNCHES_URL, headers=HEADERS_A)
    items = r.json()["items"]
    assert any(i["status"] == "late" and i["employee_id"] == 1 for i in items)


@pytest.mark.asyncio
async def test_webhook_dedupes_by_event_id(client):
    device_resp = await client.post(DEVICES_URL, json={"name": "Cozinha"}, headers=HEADERS_A)
    device_id = device_resp.json()["id"]
    token = device_resp.json()["webhook_token"]

    payload = {
        "external_id": "sem-vinculo",
        "timestamp": "2026-07-06T09:00:00",
        "event_id": "evt-dup",
    }
    r1 = await client.post(f"/api/v1/integrations/control-id/{token}/punches", json=payload)
    r2 = await client.post(f"/api/v1/integrations/control-id/{token}/punches", json=payload)
    assert r1.status_code == 200
    assert r2.status_code == 200

    r = await client.get(f"{PUNCHES_URL}?status=unscheduled", headers=HEADERS_A)
    matching = [i for i in r.json()["items"] if i["device_id"] == device_id]
    assert len(matching) == 1


@pytest.mark.asyncio
async def test_webhook_rejects_invalid_token(client):
    r = await client.post(
        "/api/v1/integrations/control-id/token-invalido/punches",
        json={"external_id": "x", "timestamp": "2026-07-06T09:00:00"},
    )
    assert r.status_code == 401


@pytest.mark.asyncio
async def test_manual_punch_and_correction(client):
    shift_resp = await client.post(
        SHIFTS_URL,
        json={"name": "Turno", "start_time": "08:00:00", "end_time": "17:00:00"},
        headers=HEADERS_A,
    )
    shift_id = shift_resp.json()["id"]

    await client.post(
        f"{SCHEDULE_URL}/generate",
        json={
            "employee_ids": [1],
            "shift_id": shift_id,
            "start_date": "2026-07-06",
            "end_date": "2026-07-06",
            "pattern": {"type": "weekly", "weekdays": [0]},
        },
        headers=HEADERS_A,
    )

    r = await client.post(
        PUNCHES_URL,
        json={"employee_id": 1, "punched_at": "2026-07-06T08:00:00", "punch_type": "in"},
        headers=HEADERS_A,
    )
    assert r.status_code == 201
    punch_id = r.json()["id"]
    assert r.json()["source"] == "manual"

    r = await client.patch(
        f"{PUNCHES_URL}/{punch_id}",
        json={"notes": "Esqueceu de bater, corrigido pelo gestor"},
        headers=HEADERS_A,
    )
    assert r.status_code == 200
    assert "corrigido" in r.json()["notes"]


@pytest.mark.asyncio
async def test_webhook_overnight_shift_exit_next_day(client):
    """Bug 3 fim a fim: turno 22:00-06:00, saída de madrugada do dia seguinte deve casar com a escala do dia anterior."""
    shift_resp = await client.post(
        SHIFTS_URL,
        json={"name": "Noite", "start_time": "22:00:00", "end_time": "06:00:00", "tolerance_minutes": 10},
        headers=HEADERS_A,
    )
    shift_id = shift_resp.json()["id"]

    await client.post(
        f"{SCHEDULE_URL}/generate",
        json={
            "employee_ids": [1],
            "shift_id": shift_id,
            "start_date": "2026-08-01",
            "end_date": "2026-08-01",
            "pattern": {"type": "weekly", "weekdays": [5]},
        },
        headers=HEADERS_A,
    )

    device_resp = await client.post(DEVICES_URL, json={"name": "Portaria Noturna"}, headers=HEADERS_A)
    token = device_resp.json()["webhook_token"]
    await client.post(
        ENROLLMENTS_URL, json={"employee_id": 1, "external_id": "0077"}, headers=HEADERS_A
    )

    entry_payload = {
        "external_id": "0077",
        "timestamp": "2026-08-01T22:05:00",
        "type": "in",
        "event_id": "evt-night-in",
    }
    r = await client.post(f"/api/v1/integrations/control-id/{token}/punches", json=entry_payload)
    assert r.status_code == 200

    exit_payload = {
        "external_id": "0077",
        "timestamp": "2026-08-02T06:10:00",
        "type": "out",
        "event_id": "evt-night-out",
    }
    r = await client.post(f"/api/v1/integrations/control-id/{token}/punches", json=exit_payload)
    assert r.status_code == 200

    r = await client.get(PUNCHES_URL, headers=HEADERS_A)
    items = r.json()["items"]
    entry = next(i for i in items if i["punched_at"].startswith("2026-08-01T22:05"))
    exit_ = next(i for i in items if i["punched_at"].startswith("2026-08-02T06:10"))
    assert entry["status"] == "on_time"
    assert exit_["status"] == "on_time"
