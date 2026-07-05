"""Testes do Portal do Colaborador: login por PIN, punch mobile com geofencing,
escala e contracheque, e isolamento de escopo entre o token `employee_session`
e o token `access` de User."""

from datetime import date

import pytest

from app.core.rate_limit import limiter
from app.core.security import create_access_token, create_employee_session_token
from app.domain.timeclock.service import hash_pin, haversine_distance_m
from app.models import Attachment, Employee, EmployeeCredential, EmployeePayslip, Location
from tests.conftest import JWT_SECRET, TENANT_A, auth_header


@pytest.fixture(autouse=True)
def _reset_login_rate_limit():
    """/timeclock/mobile/login tem rate limit agressivo (10/minute); sem reset, os
    vários testes deste arquivo somados estourariam o limite dentro da mesma janela."""
    limiter.reset()
    yield
    limiter.reset()

MOBILE_LOGIN_URL = "/api/v1/timeclock/mobile/login"
MOBILE_PIN_URL = "/api/v1/timeclock/mobile/pin"
MOBILE_PUNCH_URL = "/api/v1/timeclock/mobile/punch"
MOBILE_STATUS_URL = "/api/v1/timeclock/mobile/status"
MOBILE_SCHEDULE_URL = "/api/v1/timeclock/mobile/schedule"
MOBILE_PAYSLIPS_URL = "/api/v1/timeclock/mobile/payslips"
DEVICES_URL = "/api/v1/timeclock/devices"
SHIFTS_URL = "/api/v1/timeclock/shifts"
SCHEDULE_URL = "/api/v1/timeclock/schedule"


async def _create_employee_with_pin(
    session,
    *,
    registration_number: str,
    pin: str = "482913",
    with_location: bool = True,
    lat: float = -23.5505,
    lng: float = -46.6333,
    radius: int = 100,
) -> Employee:
    location_id = None
    if with_location:
        location = Location(
            company_id=TENANT_A,
            name=f"Sede {registration_number}",
            latitude=lat,
            longitude=lng,
            geofence_radius_m=radius,
        )
        session.add(location)
        await session.flush()
        location_id = location.id

    employee = Employee(
        company_id=TENANT_A,
        name=f"Colaborador {registration_number}",
        registration_number=registration_number,
        status="active",
        location_id=location_id,
    )
    session.add(employee)
    await session.flush()

    session.add(
        EmployeeCredential(
            company_id=TENANT_A,
            employee_id=employee.id,
            pin_hash=hash_pin(pin),
            must_change_pin=False,
        )
    )
    await session.commit()
    await session.refresh(employee)
    return employee


def _employee_token(employee_id: int, company_id: int = TENANT_A) -> str:
    return create_employee_session_token(
        employee_id=employee_id, company_id=company_id, secret=JWT_SECRET
    )


# ── haversine_distance_m (regra pura) ──


def test_haversine_same_point_is_zero():
    assert haversine_distance_m(-23.5505, -46.6333, -23.5505, -46.6333) == 0


def test_haversine_known_distance_sp_rio():
    # São Paulo -> Rio de Janeiro, distância em linha reta ~ 357km
    distance = haversine_distance_m(-23.5505, -46.6333, -22.9068, -43.1729)
    assert 350_000 < distance < 365_000


# ── Login por PIN ──


@pytest.mark.asyncio
async def test_mobile_login_success(client, session):
    employee = await _create_employee_with_pin(session, registration_number="LOGIN-OK")
    r = await client.post(
        MOBILE_LOGIN_URL,
        json={"company_slug": "hotel-a", "registration_number": "LOGIN-OK", "pin": "482913"},
    )
    assert r.status_code == 200
    body = r.json()
    assert body["employee_id"] == employee.id
    assert body["access_token"]
    assert body["must_change_pin"] is False


@pytest.mark.asyncio
async def test_mobile_login_wrong_pin(client, session):
    await _create_employee_with_pin(session, registration_number="LOGIN-WRONG")
    r = await client.post(
        MOBILE_LOGIN_URL,
        json={"company_slug": "hotel-a", "registration_number": "LOGIN-WRONG", "pin": "000001"},
    )
    assert r.status_code == 401


@pytest.mark.asyncio
async def test_mobile_login_wrong_company_slug(client, session):
    await _create_employee_with_pin(session, registration_number="LOGIN-SLUG")
    r = await client.post(
        MOBILE_LOGIN_URL,
        json={
            "company_slug": "empresa-que-nao-existe",
            "registration_number": "LOGIN-SLUG",
            "pin": "482913",
        },
    )
    assert r.status_code == 401


@pytest.mark.asyncio
async def test_mobile_login_lockout_after_max_attempts(client, session):
    await _create_employee_with_pin(session, registration_number="LOGIN-LOCK")
    for _ in range(5):
        r = await client.post(
            MOBILE_LOGIN_URL,
            json={"company_slug": "hotel-a", "registration_number": "LOGIN-LOCK", "pin": "000000"},
        )
        assert r.status_code == 401

    # Mesmo com o PIN correto, agora está bloqueado temporariamente.
    r = await client.post(
        MOBILE_LOGIN_URL,
        json={"company_slug": "hotel-a", "registration_number": "LOGIN-LOCK", "pin": "482913"},
    )
    assert r.status_code == 423


# ── Isolamento de token: employee_session != access ──


@pytest.mark.asyncio
async def test_employee_session_token_cannot_access_user_routes(client, session):
    employee = await _create_employee_with_pin(session, registration_number="ISO-EMPLOYEE")
    token = _employee_token(employee.id)
    r = await client.get(DEVICES_URL, headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 401


@pytest.mark.asyncio
async def test_user_access_token_cannot_access_mobile_routes(client):
    token = create_access_token(
        subject=1, company_id=TENANT_A, role_id=1, permissions=["*"], secret=JWT_SECRET, minutes=30
    )
    r = await client.post(
        MOBILE_PUNCH_URL,
        json={"latitude": -23.5505, "longitude": -46.6333},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert r.status_code == 401


# ── Punch mobile com geofencing ──


@pytest.mark.asyncio
async def test_mobile_punch_within_radius_success(client, session):
    employee = await _create_employee_with_pin(
        session, registration_number="PUNCH-OK", lat=-23.5505, lng=-46.6333, radius=200
    )
    token = _employee_token(employee.id)
    r = await client.post(
        MOBILE_PUNCH_URL,
        json={"latitude": -23.5505, "longitude": -46.6333},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert r.status_code == 201
    body = r.json()
    assert body["punch_type"] == "in"
    assert body["status"] == "unscheduled"
    assert body["distance_m"] < 1


@pytest.mark.asyncio
async def test_mobile_punch_out_of_range(client, session):
    employee = await _create_employee_with_pin(
        session, registration_number="PUNCH-FAR", lat=-23.5505, lng=-46.6333, radius=50
    )
    token = _employee_token(employee.id)
    # ~1.1km ao norte do ponto configurado, bem fora do raio de 50m
    r = await client.post(
        MOBILE_PUNCH_URL,
        json={"latitude": -23.5605, "longitude": -46.6333},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert r.status_code == 422
    detail = r.json()["detail"]
    assert detail["code"] == "OUT_OF_RANGE"
    assert detail["distance_m"] > 50


@pytest.mark.asyncio
async def test_mobile_punch_location_not_configured(client, session):
    employee = await _create_employee_with_pin(
        session, registration_number="PUNCH-NOLOC", with_location=False
    )
    token = _employee_token(employee.id)
    r = await client.post(
        MOBILE_PUNCH_URL,
        json={"latitude": -23.5505, "longitude": -46.6333},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert r.status_code == 422
    assert r.json()["detail"]["code"] == "LOCATION_NOT_CONFIGURED"


# ── Escala: employee só vê a própria ──


@pytest.mark.asyncio
async def test_mobile_schedule_only_own(client, session):
    employee_a = await _create_employee_with_pin(session, registration_number="SCHED-A")
    employee_b = await _create_employee_with_pin(session, registration_number="SCHED-B")

    shift_resp = await client.post(
        SHIFTS_URL,
        json={"name": "Turno Portal", "start_time": "08:00:00", "end_time": "17:00:00"},
        headers=auth_header(TENANT_A, 1),
    )
    shift_id = shift_resp.json()["id"]

    await client.put(
        f"{SCHEDULE_URL}/{employee_a.id}/2026-09-01",
        json={"shift_id": shift_id},
        headers=auth_header(TENANT_A, 1),
    )
    await client.put(
        f"{SCHEDULE_URL}/{employee_b.id}/2026-09-01",
        json={"shift_id": shift_id},
        headers=auth_header(TENANT_A, 1),
    )

    token_a = _employee_token(employee_a.id)
    r = await client.get(
        f"{MOBILE_SCHEDULE_URL}?start=2026-09-01&end=2026-09-01",
        headers={"Authorization": f"Bearer {token_a}"},
    )
    assert r.status_code == 200
    items = r.json()
    assert len(items) == 1
    assert items[0]["employee_id"] == employee_a.id


# ── Contracheque: employee não baixa o de outro ──


@pytest.mark.asyncio
async def test_payslip_download_forbidden_for_other_employee(client, session):
    employee_a = await _create_employee_with_pin(session, registration_number="PAY-A")
    employee_b = await _create_employee_with_pin(session, registration_number="PAY-B")

    attachment = Attachment(
        company_id=TENANT_A,
        entity_type="employee_payslip",
        entity_id=employee_a.id,
        filename="contracheque.pdf",
        content_type="application/pdf",
        size_bytes=10,
        storage_key="test/employee_payslip/nao-importa.pdf",
        uploaded_by_user_id=1,
    )
    session.add(attachment)
    await session.flush()
    payslip = EmployeePayslip(
        company_id=TENANT_A,
        employee_id=employee_a.id,
        reference_month=date(2026, 9, 1),
        attachment_id=attachment.id,
        uploaded_by_user_id=1,
    )
    session.add(payslip)
    await session.commit()
    await session.refresh(payslip)

    token_b = _employee_token(employee_b.id)
    r = await client.get(
        f"{MOBILE_PAYSLIPS_URL}/{payslip.id}/download",
        headers={"Authorization": f"Bearer {token_b}"},
    )
    assert r.status_code == 404

    token_a = _employee_token(employee_a.id)
    r = await client.get(MOBILE_PAYSLIPS_URL, headers={"Authorization": f"Bearer {token_a}"})
    assert r.status_code == 200
    assert any(p["id"] == payslip.id for p in r.json()["items"])


# ── Gestão de PIN: reset admin + troca pelo funcionário ──


@pytest.mark.asyncio
async def test_admin_reset_pin_then_employee_changes_it(client, session):
    employee = await _create_employee_with_pin(session, registration_number="PIN-FLOW")

    r = await client.post(
        f"/api/v1/timeclock/employees/{employee.id}/pin/reset", headers=auth_header(TENANT_A, 1)
    )
    assert r.status_code == 201
    new_pin = r.json()["pin"]
    assert r.json()["must_change_pin"] is True

    # PIN antigo já não funciona.
    r = await client.post(
        MOBILE_LOGIN_URL,
        json={"company_slug": "hotel-a", "registration_number": "PIN-FLOW", "pin": "482913"},
    )
    assert r.status_code == 401

    # Login com o PIN gerado no reset funciona, e sinaliza troca obrigatória.
    r = await client.post(
        MOBILE_LOGIN_URL,
        json={"company_slug": "hotel-a", "registration_number": "PIN-FLOW", "pin": new_pin},
    )
    assert r.status_code == 200
    body = r.json()
    assert body["must_change_pin"] is True
    token = body["access_token"]

    r = await client.post(
        MOBILE_PIN_URL,
        json={"new_pin": "739284"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert r.status_code == 204

    # O PIN do reset não funciona mais.
    r = await client.post(
        MOBILE_LOGIN_URL,
        json={"company_slug": "hotel-a", "registration_number": "PIN-FLOW", "pin": new_pin},
    )
    assert r.status_code == 401

    # O novo PIN funciona.
    r = await client.post(
        MOBILE_LOGIN_URL,
        json={"company_slug": "hotel-a", "registration_number": "PIN-FLOW", "pin": "739284"},
    )
    assert r.status_code == 200
