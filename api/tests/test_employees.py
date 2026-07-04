"""Testes do cadastro de funcionários (Employee, separado de User)."""

import pytest

from tests.conftest import TENANT_A, TENANT_B, auth_header

HEADERS_A = auth_header(TENANT_A, 1)
HEADERS_B = auth_header(TENANT_B, 2)
EMPLOYEES_URL = "/api/v1/employees"


@pytest.mark.asyncio
async def test_create_and_get_employee(client):
    r = await client.post(
        EMPLOYEES_URL,
        json={"name": "Maria Souza", "cpf": "11122233344", "phone": "11988887777"},
        headers=HEADERS_A,
    )
    assert r.status_code == 201
    employee = r.json()
    assert employee["name"] == "Maria Souza"
    assert employee["cpf"] == "11122233344"
    assert employee["status"] == "active"
    employee_id = employee["id"]

    r = await client.get(f"{EMPLOYEES_URL}/{employee_id}", headers=HEADERS_A)
    assert r.status_code == 200
    assert r.json()["name"] == "Maria Souza"


@pytest.mark.asyncio
async def test_list_employees_paginated(client):
    r = await client.get(EMPLOYEES_URL, headers=HEADERS_A)
    assert r.status_code == 200
    body = r.json()
    assert "items" in body
    assert "total" in body
    assert body["page"] == 1
    assert body["page_size"] == 20


@pytest.mark.asyncio
async def test_update_employee(client):
    r = await client.post(
        EMPLOYEES_URL,
        json={"name": "Carlos Lima"},
        headers=HEADERS_A,
    )
    employee_id = r.json()["id"]

    r = await client.patch(
        f"{EMPLOYEES_URL}/{employee_id}",
        json={"phone": "11955554444", "status": "inactive"},
        headers=HEADERS_A,
    )
    assert r.status_code == 200
    assert r.json()["phone"] == "11955554444"
    assert r.json()["status"] == "inactive"


@pytest.mark.asyncio
async def test_delete_employee_is_soft_delete(client):
    r = await client.post(
        EMPLOYEES_URL,
        json={"name": "Pedro Alves"},
        headers=HEADERS_A,
    )
    employee_id = r.json()["id"]

    r = await client.delete(f"{EMPLOYEES_URL}/{employee_id}", headers=HEADERS_A)
    assert r.status_code == 204

    r = await client.get(f"{EMPLOYEES_URL}/{employee_id}", headers=HEADERS_A)
    assert r.status_code == 404

    r = await client.get(EMPLOYEES_URL, headers=HEADERS_A)
    assert not any(e["id"] == employee_id for e in r.json()["items"])


@pytest.mark.asyncio
async def test_cpf_unique_per_company(client):
    r = await client.post(
        EMPLOYEES_URL,
        json={"name": "Ana Costa", "cpf": "99988877766"},
        headers=HEADERS_A,
    )
    assert r.status_code == 201

    r = await client.post(
        EMPLOYEES_URL,
        json={"name": "Ana Costa Duplicada", "cpf": "99988877766"},
        headers=HEADERS_A,
    )
    assert r.status_code in (400, 409, 422)


@pytest.mark.asyncio
async def test_cpf_can_repeat_across_companies(client):
    r = await client.post(
        EMPLOYEES_URL,
        json={"name": "Funcionário Tenant A", "cpf": "55566677788"},
        headers=HEADERS_A,
    )
    assert r.status_code == 201

    r = await client.post(
        EMPLOYEES_URL,
        json={"name": "Funcionário Tenant B", "cpf": "55566677788"},
        headers=HEADERS_B,
    )
    assert r.status_code == 201


@pytest.mark.asyncio
async def test_tenant_isolation_employees(client):
    r = await client.post(
        EMPLOYEES_URL,
        json={"name": "Só do Tenant A"},
        headers=HEADERS_A,
    )
    employee_id = r.json()["id"]

    r = await client.get(f"{EMPLOYEES_URL}/{employee_id}", headers=HEADERS_B)
    assert r.status_code == 404


@pytest.mark.asyncio
async def test_list_employees_page_size_over_limit(client):
    r = await client.get(f"{EMPLOYEES_URL}?page_size=101", headers=HEADERS_A)
    assert r.status_code == 422


@pytest.mark.asyncio
async def test_search_employees(client):
    await client.post(EMPLOYEES_URL, json={"name": "Fernanda Ribeiro"}, headers=HEADERS_A)

    r = await client.get(f"{EMPLOYEES_URL}/search?q=Fernanda", headers=HEADERS_A)
    assert r.status_code == 200
    results = r.json()
    assert any(e["name"] == "Fernanda Ribeiro" for e in results)


@pytest.mark.asyncio
async def test_employee_external_ids(client):
    r = await client.post(EMPLOYEES_URL, json={"name": "Roberto Dias"}, headers=HEADERS_A)
    employee_id = r.json()["id"]

    r = await client.post(
        f"{EMPLOYEES_URL}/{employee_id}/external-ids",
        json={"system": "totvs", "external_id": "00123"},
        headers=HEADERS_A,
    )
    assert r.status_code == 201
    external_id_record = r.json()
    assert external_id_record["system"] == "totvs"
    assert external_id_record["external_id"] == "00123"

    r = await client.get(f"{EMPLOYEES_URL}/{employee_id}", headers=HEADERS_A)
    assert any(e["system"] == "totvs" for e in r.json()["external_ids"])

    r = await client.delete(
        f"{EMPLOYEES_URL}/{employee_id}/external-ids/{external_id_record['id']}",
        headers=HEADERS_A,
    )
    assert r.status_code == 204


@pytest.mark.asyncio
async def test_create_external_id_invalid_payload(client):
    r = await client.post(EMPLOYEES_URL, json={"name": "Sonia Prado"}, headers=HEADERS_A)
    employee_id = r.json()["id"]

    r = await client.post(
        f"{EMPLOYEES_URL}/{employee_id}/external-ids",
        json={"system": "totvs"},
        headers=HEADERS_A,
    )
    assert r.status_code == 422


@pytest.mark.asyncio
async def test_delete_external_id_scoped_to_owning_employee(client):
    r = await client.post(EMPLOYEES_URL, json={"name": "Marcos Villa"}, headers=HEADERS_A)
    employee_a_id = r.json()["id"]
    r = await client.post(EMPLOYEES_URL, json={"name": "Paula Nunes"}, headers=HEADERS_A)
    employee_b_id = r.json()["id"]

    r = await client.post(
        f"{EMPLOYEES_URL}/{employee_a_id}/external-ids",
        json={"system": "totvs", "external_id": "99999"},
        headers=HEADERS_A,
    )
    external_id_id = r.json()["id"]

    r = await client.delete(
        f"{EMPLOYEES_URL}/{employee_b_id}/external-ids/{external_id_id}",
        headers=HEADERS_A,
    )
    assert r.status_code == 404

    r = await client.get(f"{EMPLOYEES_URL}/{employee_a_id}", headers=HEADERS_A)
    assert any(e["id"] == external_id_id for e in r.json()["external_ids"])


@pytest.mark.asyncio
async def test_employee_optional_user_link(client):
    r = await client.post(
        EMPLOYEES_URL,
        json={"name": "Sem login no sistema", "user_id": None},
        headers=HEADERS_A,
    )
    assert r.status_code == 201
    assert r.json()["user_id"] is None
