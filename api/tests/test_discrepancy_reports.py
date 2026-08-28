"""Testes de conferência de discrepâncias: CRUD, fechamento, isolamento e PDF."""

import pytest

from tests.conftest import TENANT_A, TENANT_B, auth_header, make_token

PREFIX = "/api/v1"
REPORTS_URL = f"{PREFIX}/discrepancy-reports"
REGISTRIES_URL = f"{PREFIX}/registries"

HEADERS_A = auth_header(TENANT_A, 1)
HEADERS_B = auth_header(TENANT_B, 1)


async def _create_location(client, headers, name="Local Teste"):
    r = await client.post(REGISTRIES_URL, json={"name": name, "category": "Local"}, headers=headers)
    assert r.status_code == 201
    return r.json()["id"]


@pytest.mark.asyncio
async def test_discrepancy_report_crud(client):
    location_id = await _create_location(client, HEADERS_A)

    r = await client.post(
        REPORTS_URL,
        json={
            "report_date": "2026-08-20",
            "observations": "Conferência de rotina",
            "entries": [
                {"location_id": location_id, "first_code": "OK", "second_code": "OK"},
            ],
        },
        headers=HEADERS_A,
    )
    assert r.status_code == 201
    body = r.json()
    report_id = body["id"]
    assert body["status"] == "draft"
    assert body["entry_count"] == 1
    assert body["discrepancy_count"] == 0

    r = await client.get(
        REPORTS_URL,
        params={"date_from": "2026-08-20", "date_to": "2026-08-20"},
        headers=HEADERS_A,
    )
    assert r.status_code == 200
    assert any(item["id"] == report_id for item in r.json()["items"])

    r = await client.get(f"{REPORTS_URL}/{report_id}", headers=HEADERS_A)
    assert r.status_code == 200
    assert r.json()["entries"][0]["location_name"] == "Local Teste"

    r = await client.patch(
        f"{REPORTS_URL}/{report_id}",
        json={"observations": "Atualizado"},
        headers=HEADERS_A,
    )
    assert r.status_code == 200
    assert r.json()["observations"] == "Atualizado"

    r = await client.delete(f"{REPORTS_URL}/{report_id}", headers=HEADERS_A)
    assert r.status_code == 204

    r = await client.get(f"{REPORTS_URL}/{report_id}", headers=HEADERS_A)
    assert r.status_code == 404


@pytest.mark.asyncio
async def test_discrepancy_summary_counts_divergences(client):
    loc_a = await _create_location(client, HEADERS_A, "Local A")
    loc_b = await _create_location(client, HEADERS_A, "Local B")

    r = await client.post(
        REPORTS_URL,
        json={
            "report_date": "2026-08-21",
            "entries": [
                {"location_id": loc_a, "first_code": "OK", "second_code": "OK"},
                {"location_id": loc_b, "first_code": "OK", "second_code": "FALTA"},
            ],
        },
        headers=HEADERS_A,
    )
    assert r.status_code == 201
    body = r.json()
    assert body["entry_count"] == 2
    assert body["discrepancy_count"] == 1
    codes = {c["code"]: c["count"] for c in body["code_summary"]}
    assert codes["OK"] == 3
    assert codes["FALTA"] == 1


@pytest.mark.asyncio
async def test_discrepancy_report_duplicate_location_rejected(client):
    location_id = await _create_location(client, HEADERS_A)

    r = await client.post(
        REPORTS_URL,
        json={
            "report_date": "2026-08-22",
            "entries": [
                {"location_id": location_id, "first_code": "OK"},
                {"location_id": location_id, "first_code": "FALTA"},
            ],
        },
        headers=HEADERS_A,
    )
    assert r.status_code == 422


@pytest.mark.asyncio
async def test_closed_report_cannot_be_edited(client):
    location_id = await _create_location(client, HEADERS_A)
    r = await client.post(
        REPORTS_URL,
        json={
            "report_date": "2026-08-23",
            "status": "closed",
            "entries": [{"location_id": location_id, "first_code": "OK"}],
        },
        headers=HEADERS_A,
    )
    report_id = r.json()["id"]

    r = await client.patch(
        f"{REPORTS_URL}/{report_id}",
        json={"observations": "Não deveria salvar"},
        headers=HEADERS_A,
    )
    assert r.status_code == 422


@pytest.mark.asyncio
async def test_discrepancy_report_cross_tenant_isolation(client):
    location_id = await _create_location(client, HEADERS_A)
    r = await client.post(
        REPORTS_URL,
        json={
            "report_date": "2026-08-24",
            "entries": [{"location_id": location_id, "first_code": "OK"}],
        },
        headers=HEADERS_A,
    )
    report_id = r.json()["id"]

    r = await client.get(f"{REPORTS_URL}/{report_id}", headers=HEADERS_B)
    assert r.status_code == 404

    r = await client.get(REPORTS_URL, headers=HEADERS_B)
    assert r.status_code == 200
    assert not any(item["id"] == report_id for item in r.json()["items"])


@pytest.mark.asyncio
async def test_discrepancy_report_rejects_location_from_other_tenant(client):
    location_b = await _create_location(client, HEADERS_B, "Local do Tenant B")

    r = await client.post(
        REPORTS_URL,
        json={
            "report_date": "2026-08-25",
            "entries": [{"location_id": location_b, "first_code": "OK"}],
        },
        headers=HEADERS_A,
    )
    assert r.status_code == 422


@pytest.mark.asyncio
async def test_discrepancy_report_requires_permission(client):
    location_id = await _create_location(client, HEADERS_A)
    r = await client.post(
        REPORTS_URL,
        json={
            "report_date": "2026-08-26",
            "entries": [{"location_id": location_id, "first_code": "OK"}],
        },
        headers=HEADERS_A,
    )
    report_id = r.json()["id"]

    no_perm_headers = {"Authorization": f"Bearer {make_token(TENANT_A, 1, [])}"}
    r = await client.get(REPORTS_URL, headers=no_perm_headers)
    assert r.status_code == 403

    r = await client.get(f"{REPORTS_URL}/{report_id}/pdf", headers=no_perm_headers)
    assert r.status_code == 403


@pytest.mark.asyncio
async def test_discrepancy_report_pdf(client):
    location_id = await _create_location(client, HEADERS_A)
    r = await client.post(
        REPORTS_URL,
        json={
            "report_date": "2026-08-27",
            "entries": [{"location_id": location_id, "first_code": "OK", "second_code": "FALTA"}],
        },
        headers=HEADERS_A,
    )
    report_id = r.json()["id"]

    r = await client.get(f"{REPORTS_URL}/{report_id}/pdf", headers=HEADERS_A)
    assert r.status_code == 200
    assert r.headers["content-type"] == "application/pdf"
    assert r.content[:4] == b"%PDF"
