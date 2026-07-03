"""Testes de escala de trabalho e ponto eletrônico (Control iD via webhook)."""

from datetime import datetime, time

import pytest

from app.domain.timeclock.service import evaluate_status
from app.models import WorkSchedule
from tests.conftest import TENANT_A, auth_header

HEADERS_A = auth_header(TENANT_A, 1)
SCHEDULE_URL = "/api/v1/timeclock/schedules/1"
DEVICES_URL = "/api/v1/timeclock/devices"
ENROLLMENTS_URL = "/api/v1/timeclock/enrollments"
PUNCHES_URL = "/api/v1/timeclock/punches"


def _entry(**overrides) -> WorkSchedule:
    entry = WorkSchedule(
        company_id=TENANT_A,
        user_id=1,
        weekday=0,
        start_time=time(8, 0),
        end_time=time(17, 0),
        tolerance_minutes=10,
    )
    for key, value in overrides.items():
        setattr(entry, key, value)
    return entry


# ── evaluate_status (regra pura) ──


def test_evaluate_status_no_schedule_is_unscheduled():
    assert evaluate_status(None, datetime(2026, 7, 6, 8, 0), "in") == "unscheduled"


def test_evaluate_status_on_time_entry():
    entry = _entry()
    assert evaluate_status(entry, datetime(2026, 7, 6, 8, 5), "in") == "on_time"


def test_evaluate_status_late_entry():
    entry = _entry()
    assert evaluate_status(entry, datetime(2026, 7, 6, 8, 20), "in") == "late"


def test_evaluate_status_early_leave():
    entry = _entry()
    assert evaluate_status(entry, datetime(2026, 7, 6, 16, 30), "out") == "early_leave"


def test_evaluate_status_on_time_leave():
    entry = _entry()
    assert evaluate_status(entry, datetime(2026, 7, 6, 17, 5), "out") == "on_time"


def test_evaluate_status_infers_type_when_missing_closer_to_start():
    entry = _entry()
    assert evaluate_status(entry, datetime(2026, 7, 6, 8, 20), None) == "late"


def test_evaluate_status_infers_type_when_missing_closer_to_end():
    entry = _entry()
    assert evaluate_status(entry, datetime(2026, 7, 6, 16, 30), None) == "early_leave"


# ── Escala via API ──


@pytest.mark.asyncio
async def test_put_and_get_schedule(client):
    body = {
        "entries": [
            {"weekday": 0, "start_time": "08:00:00", "end_time": "17:00:00"},
            {"weekday": 1, "start_time": "08:00:00", "end_time": "17:00:00"},
        ]
    }
    r = await client.put(SCHEDULE_URL, json=body, headers=HEADERS_A)
    assert r.status_code == 200
    assert len(r.json()["entries"]) == 2

    r = await client.get(SCHEDULE_URL, headers=HEADERS_A)
    assert r.status_code == 200
    weekdays = {e["weekday"] for e in r.json()["entries"]}
    assert weekdays == {0, 1}


@pytest.mark.asyncio
async def test_put_schedule_removes_dropped_days(client):
    body = {"entries": [{"weekday": 0, "start_time": "08:00:00", "end_time": "17:00:00"}]}
    await client.put(SCHEDULE_URL, json=body, headers=HEADERS_A)
    body2 = {"entries": [{"weekday": 2, "start_time": "09:00:00", "end_time": "18:00:00"}]}
    r = await client.put(SCHEDULE_URL, json=body2, headers=HEADERS_A)
    weekdays = {e["weekday"] for e in r.json()["entries"]}
    assert weekdays == {2}


# ── Dispositivos e vínculos ──


@pytest.mark.asyncio
async def test_create_device_and_enrollment(client):
    r = await client.post(DEVICES_URL, json={"name": "Recepção"}, headers=HEADERS_A)
    assert r.status_code == 201
    device = r.json()
    assert device["webhook_token"]
    assert device["model"] == "control_id"

    r = await client.post(
        ENROLLMENTS_URL, json={"user_id": 1, "external_id": "0001"}, headers=HEADERS_A
    )
    assert r.status_code == 201
    assert r.json()["external_id"] == "0001"


# ── Webhook de ingestão ──


@pytest.mark.asyncio
async def test_webhook_ingests_punch_and_matches_schedule(client):
    await client.put(
        SCHEDULE_URL,
        json={"entries": [{"weekday": 0, "start_time": "08:00:00", "end_time": "17:00:00"}]},
        headers=HEADERS_A,
    )
    device_resp = await client.post(DEVICES_URL, json={"name": "Portaria"}, headers=HEADERS_A)
    token = device_resp.json()["webhook_token"]
    await client.post(
        ENROLLMENTS_URL, json={"user_id": 1, "external_id": "0099"}, headers=HEADERS_A
    )

    # segunda-feira (weekday 0), atrasado
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
    assert any(i["status"] == "late" and i["user_id"] == 1 for i in items)


@pytest.mark.asyncio
async def test_webhook_dedupes_by_event_id(client):
    device_resp = await client.post(DEVICES_URL, json={"name": "Cozinha"}, headers=HEADERS_A)
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
    matching = [i for i in r.json()["items"] if i["notes"] is None]
    # apenas uma batida deve existir para o event_id duplicado
    assert len([i for i in matching if i["punch_type"] is None]) <= 1


@pytest.mark.asyncio
async def test_webhook_rejects_invalid_token(client):
    r = await client.post(
        "/api/v1/integrations/control-id/token-invalido/punches",
        json={"external_id": "x", "timestamp": "2026-07-06T09:00:00"},
    )
    assert r.status_code == 401


@pytest.mark.asyncio
async def test_manual_punch_and_correction(client):
    await client.put(
        SCHEDULE_URL,
        json={"entries": [{"weekday": 0, "start_time": "08:00:00", "end_time": "17:00:00"}]},
        headers=HEADERS_A,
    )
    r = await client.post(
        PUNCHES_URL,
        json={"user_id": 1, "punched_at": "2026-07-06T08:00:00", "punch_type": "in"},
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
