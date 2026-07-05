"""Testes de ajuste de ponto: solicitação do funcionário (Portal do Colaborador)
e aprovação/rejeição pelo RH."""

import pytest

from app.core.security import create_employee_session_token
from tests.conftest import JWT_SECRET, TENANT_A, auth_header, make_token

PREFIX = "/api/v1"
PUNCHES_URL = f"{PREFIX}/timeclock/punches"
ADJUSTMENTS_URL = f"{PREFIX}/timeclock/adjustments"
MOBILE_ADJUSTMENTS_URL = f"{PREFIX}/timeclock/mobile/adjustments"

HEADERS_A = auth_header(TENANT_A, 1)


def _employee_header(employee_id: int = 1) -> dict[str, str]:
    token = create_employee_session_token(
        employee_id=employee_id, company_id=TENANT_A, secret=JWT_SECRET
    )
    return {"Authorization": f"Bearer {token}"}


def _no_permissions_header() -> dict[str, str]:
    return {"Authorization": f"Bearer {make_token(TENANT_A, 1, [])}"}


@pytest.mark.asyncio
async def test_employee_requests_missing_punch_and_manager_approves(client):
    r = await client.post(
        MOBILE_ADJUSTMENTS_URL,
        json={
            "requested_punched_at": "2026-07-06T08:00:00",
            "requested_punch_type": "in",
            "reason": "Esqueci de bater o ponto na entrada",
        },
        headers=_employee_header(),
    )
    assert r.status_code == 201
    body = r.json()
    assert body["status"] == "pending"
    assert body["punch_id"] is None
    request_id = body["id"]

    r = await client.get(f"{ADJUSTMENTS_URL}?status=pending", headers=HEADERS_A)
    assert r.status_code == 200
    assert any(item["id"] == request_id for item in r.json()["items"])

    r = await client.post(
        f"{ADJUSTMENTS_URL}/{request_id}/review",
        json={"approve": True, "review_notes": "Confirmado com o supervisor"},
        headers=HEADERS_A,
    )
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "approved"
    assert body["resulting_punch_id"] is not None

    r = await client.get(PUNCHES_URL, headers=HEADERS_A)
    matching = [p for p in r.json()["items"] if p["id"] == body["resulting_punch_id"]]
    assert len(matching) == 1
    assert matching[0]["punch_type"] == "in"
    assert matching[0]["source"] == "manual"


@pytest.mark.asyncio
async def test_manager_rejects_adjustment_request(client):
    r = await client.post(
        MOBILE_ADJUSTMENTS_URL,
        json={
            "requested_punched_at": "2026-07-07T08:00:00",
            "requested_punch_type": "in",
            "reason": "Bati o ponto errado",
        },
        headers=_employee_header(),
    )
    request_id = r.json()["id"]

    r = await client.post(
        f"{ADJUSTMENTS_URL}/{request_id}/review",
        json={"approve": False, "review_notes": "Sem evidência do horário alegado"},
        headers=HEADERS_A,
    )
    assert r.status_code == 200
    assert r.json()["status"] == "rejected"
    assert r.json()["resulting_punch_id"] is None


@pytest.mark.asyncio
async def test_cannot_review_request_twice(client):
    r = await client.post(
        MOBILE_ADJUSTMENTS_URL,
        json={
            "requested_punched_at": "2026-07-08T08:00:00",
            "requested_punch_type": "in",
            "reason": "Esqueci de bater o ponto",
        },
        headers=_employee_header(),
    )
    request_id = r.json()["id"]

    r = await client.post(
        f"{ADJUSTMENTS_URL}/{request_id}/review",
        json={"approve": True},
        headers=HEADERS_A,
    )
    assert r.status_code == 200

    r = await client.post(
        f"{ADJUSTMENTS_URL}/{request_id}/review",
        json={"approve": True},
        headers=HEADERS_A,
    )
    assert r.status_code == 409


@pytest.mark.asyncio
async def test_correction_of_existing_punch(client):
    r = await client.post(
        PUNCHES_URL,
        json={"employee_id": 1, "punched_at": "2026-07-09T08:30:00", "punch_type": "in"},
        headers=HEADERS_A,
    )
    punch_id = r.json()["id"]

    r = await client.post(
        MOBILE_ADJUSTMENTS_URL,
        json={
            "punch_id": punch_id,
            "requested_punched_at": "2026-07-09T08:00:00",
            "requested_punch_type": "in",
            "reason": "Bati às 08:00, não 08:30",
        },
        headers=_employee_header(),
    )
    assert r.status_code == 201
    request_id = r.json()["id"]

    r = await client.post(
        f"{ADJUSTMENTS_URL}/{request_id}/review",
        json={"approve": True},
        headers=HEADERS_A,
    )
    assert r.status_code == 200
    assert r.json()["resulting_punch_id"] == punch_id

    r = await client.get(PUNCHES_URL, headers=HEADERS_A)
    corrected = next(p for p in r.json()["items"] if p["id"] == punch_id)
    assert corrected["punched_at"].startswith("2026-07-09T08:00:00")


@pytest.mark.asyncio
async def test_adjustment_request_for_other_employee_punch_rejected(client):
    r = await client.post(
        MOBILE_ADJUSTMENTS_URL,
        json={
            "punch_id": 999999,
            "requested_punched_at": "2026-07-09T08:00:00",
            "requested_punch_type": "in",
            "reason": "Tentativa inválida",
        },
        headers=_employee_header(),
    )
    assert r.status_code == 404


@pytest.mark.asyncio
async def test_employee_lists_only_own_adjustments(client):
    await client.post(
        MOBILE_ADJUSTMENTS_URL,
        json={
            "requested_punched_at": "2026-07-10T08:00:00",
            "requested_punch_type": "in",
            "reason": "Esqueci de bater",
        },
        headers=_employee_header(),
    )
    r = await client.get(MOBILE_ADJUSTMENTS_URL, headers=_employee_header())
    assert r.status_code == 200
    assert all(item["employee_id"] == 1 for item in r.json())


@pytest.mark.asyncio
async def test_adjustment_admin_endpoints_require_permission(client):
    headers = _no_permissions_header()
    r = await client.get(ADJUSTMENTS_URL, headers=headers)
    assert r.status_code == 403

    r = await client.post(f"{ADJUSTMENTS_URL}/1/review", json={"approve": True}, headers=headers)
    assert r.status_code == 403


@pytest.mark.asyncio
async def test_review_nonexistent_request_returns_404(client):
    r = await client.post(
        f"{ADJUSTMENTS_URL}/999999/review", json={"approve": True}, headers=HEADERS_A
    )
    assert r.status_code == 404
