"""Testes do cadastro de funcionários (Employee, separado de User)."""

from unittest.mock import patch

import pytest

from tests.conftest import TENANT_A, TENANT_B, auth_header

HEADERS_A = auth_header(TENANT_A, 1)
HEADERS_B = auth_header(TENANT_B, 2)
EMPLOYEES_URL = "/api/v1/employees"


@pytest.fixture()
def mock_employee_storage():
    with patch(
        "app.domain.employees.service.upload_file", return_value="fake/employee-avatar.jpg"
    ):
        yield


@pytest.mark.asyncio
async def test_create_and_get_employee(client):
    r = await client.post(
        EMPLOYEES_URL,
        json={"name": "Maria Souza", "cpf": "11122233396", "phone": "11988887777"},
        headers=HEADERS_A,
    )
    assert r.status_code == 201
    employee = r.json()
    assert employee["name"] == "Maria Souza"
    assert employee["cpf"] == "11122233396"
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
        json={"name": "Carlos Lima", "cpf": "58215069800"},
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
        json={"name": "Pedro Alves", "cpf": "53493219199"},
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
        json={"name": "Ana Costa", "cpf": "99988877714"},
        headers=HEADERS_A,
    )
    assert r.status_code == 201

    r = await client.post(
        EMPLOYEES_URL,
        json={"name": "Ana Costa Duplicada", "cpf": "99988877714"},
        headers=HEADERS_A,
    )
    assert r.status_code in (400, 409, 422)


@pytest.mark.asyncio
async def test_cpf_can_repeat_across_companies(client):
    r = await client.post(
        EMPLOYEES_URL,
        json={"name": "Funcionário Tenant A", "cpf": "55566677720"},
        headers=HEADERS_A,
    )
    assert r.status_code == 201

    r = await client.post(
        EMPLOYEES_URL,
        json={"name": "Funcionário Tenant B", "cpf": "55566677720"},
        headers=HEADERS_B,
    )
    assert r.status_code == 201


@pytest.mark.asyncio
async def test_tenant_isolation_employees(client):
    r = await client.post(
        EMPLOYEES_URL,
        json={"name": "Só do Tenant A", "cpf": "70061734004"},
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
    await client.post(
        EMPLOYEES_URL,
        json={"name": "Fernanda Ribeiro", "cpf": "77498428296"},
        headers=HEADERS_A,
    )

    r = await client.get(f"{EMPLOYEES_URL}/search?q=Fernanda", headers=HEADERS_A)
    assert r.status_code == 200
    results = r.json()
    assert any(e["name"] == "Fernanda Ribeiro" for e in results)


@pytest.mark.asyncio
async def test_employee_external_ids(client):
    r = await client.post(
        EMPLOYEES_URL,
        json={"name": "Roberto Dias", "cpf": "45752473403"},
        headers=HEADERS_A,
    )
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
    r = await client.post(
        EMPLOYEES_URL,
        json={"name": "Sonia Prado", "cpf": "77210037179"},
        headers=HEADERS_A,
    )
    employee_id = r.json()["id"]

    r = await client.post(
        f"{EMPLOYEES_URL}/{employee_id}/external-ids",
        json={"system": "totvs"},
        headers=HEADERS_A,
    )
    assert r.status_code == 422


@pytest.mark.asyncio
async def test_delete_external_id_scoped_to_owning_employee(client):
    r = await client.post(
        EMPLOYEES_URL,
        json={"name": "Marcos Villa", "cpf": "42195663502"},
        headers=HEADERS_A,
    )
    employee_a_id = r.json()["id"]
    r = await client.post(
        EMPLOYEES_URL,
        json={"name": "Paula Nunes", "cpf": "49354497136"},
        headers=HEADERS_A,
    )
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
async def test_create_employee_invalid_cpf_checksum(client):
    r = await client.post(
        EMPLOYEES_URL,
        json={"name": "CPF Inválido", "cpf": "11122233344"},
        headers=HEADERS_A,
    )
    assert r.status_code == 422


@pytest.mark.asyncio
async def test_create_employee_invalid_birth_date_format(client):
    r = await client.post(
        EMPLOYEES_URL,
        json={"name": "Data Inválida", "cpf": "28789261100", "birth_date": "01/01/1990"},
        headers=HEADERS_A,
    )
    assert r.status_code == 422


@pytest.mark.asyncio
async def test_create_employee_invalid_address_zip(client):
    r = await client.post(
        EMPLOYEES_URL,
        json={"name": "CEP Inválido", "cpf": "24098335514", "address_zip": "123"},
        headers=HEADERS_A,
    )
    assert r.status_code == 422


@pytest.mark.asyncio
async def test_create_employee_normalizes_address_zip(client):
    r = await client.post(
        EMPLOYEES_URL,
        json={"name": "CEP Válido", "cpf": "11847383947", "address_zip": "01310100"},
        headers=HEADERS_A,
    )
    assert r.status_code == 201
    employee_id = r.json()["id"]

    r = await client.get(f"{EMPLOYEES_URL}/{employee_id}", headers=HEADERS_A)
    assert r.json()["address_zip"] == "01310-100"


@pytest.mark.asyncio
async def test_create_employee_invalid_status(client):
    r = await client.post(
        EMPLOYEES_URL,
        json={"name": "Status Inválido", "cpf": "46339793614", "status": "on_vacation"},
        headers=HEADERS_A,
    )
    assert r.status_code == 422


@pytest.mark.asyncio
async def test_employee_optional_user_link(client):
    r = await client.post(
        EMPLOYEES_URL,
        json={"name": "Sem login no sistema", "cpf": "49493173500", "user_id": None},
        headers=HEADERS_A,
    )
    assert r.status_code == 201
    assert r.json()["user_id"] is None


@pytest.mark.asyncio
async def test_create_employee_requires_cpf(client):
    r = await client.post(
        EMPLOYEES_URL,
        json={"name": "Sem CPF"},
        headers=HEADERS_A,
    )
    assert r.status_code == 422


@pytest.mark.asyncio
async def test_create_employee_with_contract_fields(client):
    r = await client.post(
        EMPLOYEES_URL,
        json={
            "name": "Funcionário Contratado",
            "cpf": "60650705130",
            "job_title": "Recepcionista",
            "hire_date": "2026-01-10",
            "registration_number": "MAT-0001",
        },
        headers=HEADERS_A,
    )
    assert r.status_code == 201
    employee_id = r.json()["id"]

    r = await client.get(f"{EMPLOYEES_URL}/{employee_id}", headers=HEADERS_A)
    body = r.json()
    assert body["job_title"] == "Recepcionista"
    assert body["hire_date"] == "2026-01-10"
    assert body["registration_number"] == "MAT-0001"


@pytest.mark.asyncio
async def test_create_employee_invalid_hire_date(client):
    r = await client.post(
        EMPLOYEES_URL,
        json={"name": "Data Ruim", "cpf": "10307981410", "hire_date": "10/01/2026"},
        headers=HEADERS_A,
    )
    assert r.status_code == 422


@pytest.mark.asyncio
async def test_update_employee_termination_date(client):
    r = await client.post(
        EMPLOYEES_URL,
        json={"name": "Vai Desligar", "cpf": "26012998279"},
        headers=HEADERS_A,
    )
    employee_id = r.json()["id"]

    r = await client.patch(
        f"{EMPLOYEES_URL}/{employee_id}",
        json={"status": "terminated", "termination_date": "2026-07-04"},
        headers=HEADERS_A,
    )
    assert r.status_code == 200

    r = await client.get(f"{EMPLOYEES_URL}/{employee_id}", headers=HEADERS_A)
    assert r.json()["termination_date"] == "2026-07-04"
    assert r.json()["status"] == "terminated"


@pytest.mark.asyncio
async def test_employee_sector_link(client):
    r = await client.post(
        "/api/v1/registries",
        json={"name": "Governança", "category": "Setor"},
        headers=HEADERS_A,
    )
    assert r.status_code == 201
    sector_id = r.json()["id"]

    r = await client.post(
        EMPLOYEES_URL,
        json={"name": "Camareira", "cpf": "69435358705", "sector_id": sector_id},
        headers=HEADERS_A,
    )
    assert r.status_code == 201
    employee_id = r.json()["id"]

    r = await client.get(f"{EMPLOYEES_URL}/{employee_id}", headers=HEADERS_A)
    body = r.json()
    assert body["sector_id"] == sector_id
    assert body["sector_name"] == "Governança"


@pytest.mark.asyncio
async def test_upload_employee_avatar(client, mock_employee_storage):
    r = await client.post(
        EMPLOYEES_URL,
        json={"name": "Com Avatar", "cpf": "72926858205"},
        headers=HEADERS_A,
    )
    employee_id = r.json()["id"]

    r = await client.post(
        f"{EMPLOYEES_URL}/{employee_id}/avatar",
        files={"file": ("foto.jpg", b"fake-image-bytes", "image/jpeg")},
        headers=HEADERS_A,
    )
    assert r.status_code == 200
    assert r.json()["avatar_url"]


@pytest.mark.asyncio
async def test_upload_employee_avatar_rejects_invalid_content_type(client, mock_employee_storage):
    r = await client.post(
        EMPLOYEES_URL,
        json={"name": "Avatar Ruim", "cpf": "88381020905"},
        headers=HEADERS_A,
    )
    employee_id = r.json()["id"]

    r = await client.post(
        f"{EMPLOYEES_URL}/{employee_id}/avatar",
        files={"file": ("doc.pdf", b"%PDF-1.4", "application/pdf")},
        headers=HEADERS_A,
    )
    assert r.status_code == 400


@pytest.mark.asyncio
async def test_employee_status_change_appears_in_timeline(client):
    r = await client.post(
        EMPLOYEES_URL,
        json={"name": "Histórico Status", "cpf": "53767411768"},
        headers=HEADERS_A,
    )
    employee_id = r.json()["id"]

    r = await client.patch(
        f"{EMPLOYEES_URL}/{employee_id}",
        json={"status": "inactive"},
        headers=HEADERS_A,
    )
    assert r.status_code == 200

    r = await client.get(f"/api/v1/timeline/employee/{employee_id}", headers=HEADERS_A)
    assert r.status_code == 200
    events = r.json()["items"]
    assert any(e["event_type"] == "update" for e in events)
    assert any(e["event_type"] == "create" for e in events)


@pytest.mark.asyncio
async def test_employee_timeline_cross_tenant_not_found(client):
    r = await client.post(
        EMPLOYEES_URL,
        json={"name": "Isolado", "cpf": "27645833114"},
        headers=HEADERS_A,
    )
    employee_id = r.json()["id"]

    r = await client.get(f"/api/v1/timeline/employee/{employee_id}", headers=HEADERS_B)
    assert r.status_code == 404


@pytest.mark.asyncio
async def test_import_employees_csv(client):
    csv_content = (
        "name,cpf,job_title\n"
        "Importado Um,23449111035,Camareira\n"
        "Importado Dois,16140541000,Recepcionista\n"
    )
    r = await client.post(
        f"{EMPLOYEES_URL}/import",
        files={"file": ("funcionarios.csv", csv_content.encode("utf-8"), "text/csv")},
        headers=HEADERS_A,
    )
    assert r.status_code == 200
    body = r.json()
    assert body["total"] == 2
    assert body["created"] == 2
    assert body["failed"] == 0
    assert all(row["ok"] for row in body["results"])

    r = await client.get(f"{EMPLOYEES_URL}?page_size=100", headers=HEADERS_A)
    names = [e["name"] for e in r.json()["items"]]
    assert "Importado Um" in names
    assert "Importado Dois" in names


@pytest.mark.asyncio
async def test_import_employees_csv_partial_failure(client):
    csv_content = (
        "name,cpf\n"
        "Linha Boa,42235698212\n"
        "Linha CPF Ruim,11111111111\n"
        "Linha Sem CPF,\n"
    )
    r = await client.post(
        f"{EMPLOYEES_URL}/import",
        files={"file": ("funcionarios.csv", csv_content.encode("utf-8"), "text/csv")},
        headers=HEADERS_A,
    )
    assert r.status_code == 200
    body = r.json()
    assert body["total"] == 3
    assert body["created"] == 1
    assert body["failed"] == 2
    assert body["results"][0]["ok"] is True
    assert body["results"][1]["ok"] is False
    assert body["results"][2]["ok"] is False


@pytest.mark.asyncio
async def test_import_employees_csv_duplicate_cpf_in_batch(client):
    csv_content = (
        "name,cpf\n"
        "Duplicado Um,94243628548\n"
        "Duplicado Dois,94243628548\n"
    )
    r = await client.post(
        f"{EMPLOYEES_URL}/import",
        files={"file": ("funcionarios.csv", csv_content.encode("utf-8"), "text/csv")},
        headers=HEADERS_A,
    )
    assert r.status_code == 200
    body = r.json()
    assert body["created"] == 1
    assert body["failed"] == 1


@pytest.mark.asyncio
async def test_import_employees_rejects_non_csv(client):
    r = await client.post(
        f"{EMPLOYEES_URL}/import",
        files={"file": ("funcionarios.xlsx", b"fake", "application/octet-stream")},
        headers=HEADERS_A,
    )
    assert r.status_code == 400
