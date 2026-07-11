"""Testes do domínio de contratos."""

import pytest

from tests.conftest import TENANT_A, TENANT_B, auth_header

HEADERS_A = auth_header(TENANT_A, 1)
HEADERS_B = auth_header(TENANT_B, 2)
CONTRACTS_URL = "/api/v1/contracts"
SUPPLIERS_URL = "/api/v1/contracts/suppliers"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


async def _create_supplier(client, headers=None):
    headers = headers or HEADERS_A
    r = await client.post(SUPPLIERS_URL, json={"name": "Fornecedor Teste"}, headers=headers)
    assert r.status_code == 201
    return r.json()


async def _create_contract(client, supplier_id=None, extra=None, headers=None):
    headers = headers or HEADERS_A
    body = {"title": "Contrato de Serviço", **(extra or {})}
    if supplier_id:
        body["supplier_id"] = supplier_id
    r = await client.post(CONTRACTS_URL, json=body, headers=headers)
    assert r.status_code == 201
    return r.json()


# ---------------------------------------------------------------------------
# Supplier CRUD
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_create_and_get_supplier(client):
    r = await client.post(
        SUPPLIERS_URL,
        json={"name": "ACME Ltda", "document": "12345678000100", "category": "TI"},
        headers=HEADERS_A,
    )
    assert r.status_code == 201
    s = r.json()
    assert s["name"] == "ACME Ltda"
    assert s["category"] == "TI"
    assert s["active"] is True

    r = await client.get(f"{SUPPLIERS_URL}/{s['id']}", headers=HEADERS_A)
    assert r.status_code == 200
    assert r.json()["name"] == "ACME Ltda"


@pytest.mark.asyncio
async def test_list_suppliers_paginated(client):
    await _create_supplier(client)
    r = await client.get(SUPPLIERS_URL, headers=HEADERS_A)
    assert r.status_code == 200
    body = r.json()
    assert "items" in body
    assert "total" in body
    assert body["page"] == 1
    assert body["page_size"] == 20


@pytest.mark.asyncio
async def test_update_supplier(client):
    s = await _create_supplier(client)
    r = await client.patch(
        f"{SUPPLIERS_URL}/{s['id']}",
        json={"phone": "11988887777", "active": False},
        headers=HEADERS_A,
    )
    assert r.status_code == 200
    assert r.json()["phone"] == "11988887777"
    assert r.json()["active"] is False


@pytest.mark.asyncio
async def test_delete_supplier_is_soft_delete(client):
    s = await _create_supplier(client)
    r = await client.delete(f"{SUPPLIERS_URL}/{s['id']}", headers=HEADERS_A)
    assert r.status_code == 204

    r = await client.get(f"{SUPPLIERS_URL}/{s['id']}", headers=HEADERS_A)
    assert r.status_code == 404


@pytest.mark.asyncio
async def test_supplier_cross_tenant_isolation(client):
    s = await _create_supplier(client, headers=HEADERS_A)
    r = await client.get(f"{SUPPLIERS_URL}/{s['id']}", headers=HEADERS_B)
    assert r.status_code == 404


# ---------------------------------------------------------------------------
# Supplier Contacts
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_create_contact(client):
    s = await _create_supplier(client)
    r = await client.post(
        f"{SUPPLIERS_URL}/{s['id']}/contacts",
        json={"name": "João Silva", "email": "joao@acme.com", "is_primary": True},
        headers=HEADERS_A,
    )
    assert r.status_code == 201
    c = r.json()
    assert c["name"] == "João Silva"
    assert c["is_primary"] is True


@pytest.mark.asyncio
async def test_only_one_primary_contact(client):
    s = await _create_supplier(client)
    await client.post(
        f"{SUPPLIERS_URL}/{s['id']}/contacts",
        json={"name": "Contato 1", "is_primary": True},
        headers=HEADERS_A,
    )
    await client.post(
        f"{SUPPLIERS_URL}/{s['id']}/contacts",
        json={"name": "Contato 2", "is_primary": True},
        headers=HEADERS_A,
    )
    r = await client.get(f"{SUPPLIERS_URL}/{s['id']}", headers=HEADERS_A)
    contacts = r.json()["contacts"]
    primaries = [c for c in contacts if c["is_primary"]]
    assert len(primaries) == 1
    assert primaries[0]["name"] == "Contato 2"


# ---------------------------------------------------------------------------
# Contract CRUD
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_create_contract_auto_number(client):
    c = await _create_contract(client)
    assert c["number"] is not None
    assert c["number"].startswith("CTR-")
    assert c["status"] == "rascunho"


@pytest.mark.asyncio
async def test_create_contract_custom_number(client):
    c = await _create_contract(client, extra={"number": "CTR-MANUAL-001"})
    assert c["number"] == "CTR-MANUAL-001"


@pytest.mark.asyncio
async def test_list_contracts_paginated(client):
    await _create_contract(client)
    r = await client.get(CONTRACTS_URL, headers=HEADERS_A)
    assert r.status_code == 200
    body = r.json()
    assert "items" in body and "total" in body
    assert body["page"] == 1


@pytest.mark.asyncio
async def test_update_contract(client):
    c = await _create_contract(client)
    r = await client.patch(
        f"{CONTRACTS_URL}/{c['id']}",
        json={"title": "Contrato Atualizado", "notes": "obs importante"},
        headers=HEADERS_A,
    )
    assert r.status_code == 200
    assert r.json()["title"] == "Contrato Atualizado"
    assert r.json()["notes"] == "obs importante"


@pytest.mark.asyncio
async def test_delete_contract_is_soft_delete(client):
    c = await _create_contract(client)
    r = await client.delete(f"{CONTRACTS_URL}/{c['id']}", headers=HEADERS_A)
    assert r.status_code == 204

    r = await client.get(f"{CONTRACTS_URL}/{c['id']}", headers=HEADERS_A)
    assert r.status_code == 404


@pytest.mark.asyncio
async def test_contract_cross_tenant_isolation(client):
    c = await _create_contract(client, headers=HEADERS_A)
    r = await client.get(f"{CONTRACTS_URL}/{c['id']}", headers=HEADERS_B)
    assert r.status_code == 404


# ---------------------------------------------------------------------------
# Date validation
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_create_contract_invalid_dates_start_after_end(client):
    r = await client.post(
        CONTRACTS_URL,
        json={"title": "Datas Inválidas", "start_date": "2026-12-31", "end_date": "2026-01-01"},
        headers=HEADERS_A,
    )
    assert r.status_code == 422


@pytest.mark.asyncio
async def test_create_contract_invalid_dates_signed_after_start(client):
    r = await client.post(
        CONTRACTS_URL,
        json={
            "title": "Assinatura Inválida",
            "signed_at": "2026-06-01",
            "start_date": "2026-01-01",
        },
        headers=HEADERS_A,
    )
    assert r.status_code == 422


@pytest.mark.asyncio
async def test_create_contract_valid_dates(client):
    r = await client.post(
        CONTRACTS_URL,
        json={
            "title": "Datas Válidas",
            "signed_at": "2026-01-01",
            "start_date": "2026-02-01",
            "end_date": "2027-02-01",
        },
        headers=HEADERS_A,
    )
    assert r.status_code == 201


# ---------------------------------------------------------------------------
# Status update
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_update_status_valid(client):
    c = await _create_contract(client)
    r = await client.patch(
        f"{CONTRACTS_URL}/{c['id']}/status",
        json={"status": "ativo"},
        headers=HEADERS_A,
    )
    assert r.status_code == 200
    assert r.json()["status"] == "ativo"


@pytest.mark.asyncio
async def test_update_status_invalid(client):
    c = await _create_contract(client)
    r = await client.patch(
        f"{CONTRACTS_URL}/{c['id']}/status",
        json={"status": "status_invalido"},
        headers=HEADERS_A,
    )
    assert r.status_code == 422


# ---------------------------------------------------------------------------
# Submit (enviar para aprovação)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_submit_without_approvers_goes_to_ativo(client):
    c = await _create_contract(client)
    r = await client.post(
        f"{CONTRACTS_URL}/{c['id']}/submit",
        json={},
        headers=HEADERS_A,
    )
    assert r.status_code == 200
    assert r.json()["status"] == "ativo"


@pytest.mark.asyncio
async def test_submit_with_approvers_goes_to_aguardando(client):
    c = await _create_contract(client)
    r = await client.post(
        f"{CONTRACTS_URL}/{c['id']}/submit",
        json={"approver_user_ids": [1]},
        headers=HEADERS_A,
    )
    assert r.status_code == 200
    assert r.json()["status"] == "aguardando_aprovacao"
    assert len(r.json()["approval_steps"]) == 1


@pytest.mark.asyncio
async def test_submit_only_from_rascunho(client):
    c = await _create_contract(client)
    await client.patch(
        f"{CONTRACTS_URL}/{c['id']}/status",
        json={"status": "ativo"},
        headers=HEADERS_A,
    )
    r = await client.post(
        f"{CONTRACTS_URL}/{c['id']}/submit",
        json={},
        headers=HEADERS_A,
    )
    assert r.status_code == 422


@pytest.mark.asyncio
async def test_submit_resets_previous_steps(client):
    c = await _create_contract(client, extra={"approver_user_ids": [1]})
    r = await client.post(
        f"{CONTRACTS_URL}/{c['id']}/submit",
        json={"approver_user_ids": [1]},
        headers=HEADERS_A,
    )
    assert r.status_code == 200
    steps = r.json()["approval_steps"]
    assert len(steps) == 1


# ---------------------------------------------------------------------------
# Approval flow
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_single_approver_flow(client):
    c = await _create_contract(client)
    await client.post(
        f"{CONTRACTS_URL}/{c['id']}/submit",
        json={"approver_user_ids": [1]},
        headers=HEADERS_A,
    )
    r = await client.post(
        f"{CONTRACTS_URL}/{c['id']}/approve",
        json={"approved": True},
        headers=HEADERS_A,
    )
    assert r.status_code == 200
    assert r.json()["status"] == "ativo"


@pytest.mark.asyncio
async def test_rejection_returns_to_rascunho(client):
    c = await _create_contract(client)
    await client.post(
        f"{CONTRACTS_URL}/{c['id']}/submit",
        json={"approver_user_ids": [1]},
        headers=HEADERS_A,
    )
    r = await client.post(
        f"{CONTRACTS_URL}/{c['id']}/approve",
        json={"approved": False, "comment": "Precisa de ajustes"},
        headers=HEADERS_A,
    )
    assert r.status_code == 200
    assert r.json()["status"] == "rascunho"


@pytest.mark.asyncio
async def test_approve_non_pending_contract_fails(client):
    c = await _create_contract(client)
    r = await client.post(
        f"{CONTRACTS_URL}/{c['id']}/approve",
        json={"approved": True},
        headers=HEADERS_A,
    )
    assert r.status_code == 422


# ---------------------------------------------------------------------------
# Amendments
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_create_amendment_updates_contract(client):
    c = await _create_contract(client, extra={"total_value": "1000.00", "end_date": "2027-01-01"})
    r = await client.post(
        f"{CONTRACTS_URL}/{c['id']}/amendments",
        json={
            "amendment_type": "valor",
            "description": "Reajuste contratual",
            "new_value": "1200.00",
            "new_end_date": "2027-06-01",
        },
        headers=HEADERS_A,
    )
    assert r.status_code == 201
    assert r.json()["amendment_type"] == "valor"

    r = await client.get(f"{CONTRACTS_URL}/{c['id']}", headers=HEADERS_A)
    body = r.json()
    assert float(body["total_value"]) == 1200.0
    assert body["end_date"] == "2027-06-01"
    assert len(body["amendments"]) == 1


@pytest.mark.asyncio
async def test_amendment_invalid_type(client):
    c = await _create_contract(client)
    r = await client.post(
        f"{CONTRACTS_URL}/{c['id']}/amendments",
        json={"amendment_type": "invalido", "description": "teste"},
        headers=HEADERS_A,
    )
    assert r.status_code == 422


# ---------------------------------------------------------------------------
# History
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_contract_history(client):
    c = await _create_contract(client)
    await client.patch(
        f"{CONTRACTS_URL}/{c['id']}/status",
        json={"status": "ativo"},
        headers=HEADERS_A,
    )
    r = await client.get(f"{CONTRACTS_URL}/{c['id']}/history", headers=HEADERS_A)
    assert r.status_code == 200
    body = r.json()
    assert "items" in body
    assert body["total"] >= 2
    event_types = [item["event_type"] for item in body["items"]]
    assert "created" in event_types
    assert "status_changed" in event_types


@pytest.mark.asyncio
async def test_contract_history_cross_tenant(client):
    c = await _create_contract(client, headers=HEADERS_A)
    r = await client.get(f"{CONTRACTS_URL}/{c['id']}/history", headers=HEADERS_B)
    assert r.status_code == 200
    assert r.json()["total"] == 0


# ---------------------------------------------------------------------------
# Expiring filter
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_expiring_in_days_excludes_encerrado(client):
    from datetime import date, timedelta

    future_date = (date.today() + timedelta(days=10)).isoformat()
    c = await _create_contract(client, extra={"end_date": future_date})
    await client.patch(
        f"{CONTRACTS_URL}/{c['id']}/status",
        json={"status": "encerrado"},
        headers=HEADERS_A,
    )
    r = await client.get(f"{CONTRACTS_URL}?expiring_in_days=30", headers=HEADERS_A)
    ids = [item["id"] for item in r.json()["items"]]
    assert c["id"] not in ids


@pytest.mark.asyncio
async def test_expiring_in_days_excludes_past(client):
    from datetime import date, timedelta

    past_date = (date.today() - timedelta(days=5)).isoformat()
    c = await _create_contract(client, extra={"end_date": past_date})
    await client.patch(
        f"{CONTRACTS_URL}/{c['id']}/status",
        json={"status": "ativo"},
        headers=HEADERS_A,
    )
    r = await client.get(f"{CONTRACTS_URL}?expiring_in_days=30", headers=HEADERS_A)
    ids = [item["id"] for item in r.json()["items"]]
    assert c["id"] not in ids


# ---------------------------------------------------------------------------
# Update approvers
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_update_approvers_in_rascunho(client):
    c = await _create_contract(client, extra={"approver_user_ids": [1]})
    assert len(c["approval_steps"]) == 1

    r = await client.patch(
        f"{CONTRACTS_URL}/{c['id']}",
        json={"approver_user_ids": []},
        headers=HEADERS_A,
    )
    assert r.status_code == 200
    assert len(r.json()["approval_steps"]) == 0


@pytest.mark.asyncio
async def test_update_approvers_not_in_active_contract(client):
    c = await _create_contract(client)
    await client.patch(
        f"{CONTRACTS_URL}/{c['id']}/status",
        json={"status": "ativo"},
        headers=HEADERS_A,
    )
    r = await client.patch(
        f"{CONTRACTS_URL}/{c['id']}",
        json={"approver_user_ids": [1]},
        headers=HEADERS_A,
    )
    assert r.status_code == 200
    assert len(r.json()["approval_steps"]) == 0
