"""Testes de permissão: valida que endpoints retornam 403 sem a permissão correta."""

import pytest

from tests.conftest import TENANT_A, make_token

PREFIX = "/api/v1"


def auth_with(permissions: list[str], company_id: int = TENANT_A) -> dict[str, str]:
    return {"Authorization": f"Bearer {make_token(company_id, 1, permissions)}"}


def auth_none(company_id: int = TENANT_A) -> dict[str, str]:
    return auth_with([], company_id)


# ---------------------------------------------------------------------------
# Work Orders
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_work_orders_list_forbidden_without_permission(client):
    r = await client.get(f"{PREFIX}/work-orders", headers=auth_none())
    assert r.status_code == 403
    assert r.json()["detail"]["required"] == "work_order.view"


@pytest.mark.asyncio
async def test_work_orders_list_forbidden_with_wrong_permission(client):
    r = await client.get(f"{PREFIX}/work-orders", headers=auth_with(["bulletin.view"]))
    assert r.status_code == 403


@pytest.mark.asyncio
async def test_work_orders_list_allowed_with_permission(client):
    r = await client.get(f"{PREFIX}/work-orders", headers=auth_with(["work_order.view"]))
    assert r.status_code == 200


@pytest.mark.asyncio
async def test_work_orders_create_forbidden_without_permission(client):
    r = await client.post(f"{PREFIX}/work-orders", headers=auth_none(), json={})
    assert r.status_code == 403
    assert r.json()["detail"]["required"] == "work_order.create"


@pytest.mark.asyncio
async def test_work_orders_create_allowed_with_permission(client):
    r = await client.post(
        f"{PREFIX}/work-orders",
        headers=auth_with(["work_order.create"]),
        json={"title": "Teste permissão", "category": "general"},
    )
    assert r.status_code in (201, 422)


# ---------------------------------------------------------------------------
# Bulletin
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_bulletin_list_forbidden_without_permission(client):
    r = await client.get(f"{PREFIX}/bulletin", headers=auth_none())
    assert r.status_code == 403
    assert r.json()["detail"]["required"] == "bulletin.view"


@pytest.mark.asyncio
async def test_bulletin_list_forbidden_with_wrong_permission(client):
    r = await client.get(f"{PREFIX}/bulletin", headers=auth_with(["work_order.view"]))
    assert r.status_code == 403


@pytest.mark.asyncio
async def test_bulletin_list_allowed_with_permission(client):
    r = await client.get(f"{PREFIX}/bulletin", headers=auth_with(["bulletin.view"]))
    assert r.status_code == 200


@pytest.mark.asyncio
async def test_bulletin_create_forbidden_without_permission(client):
    r = await client.post(f"{PREFIX}/bulletin", headers=auth_none(), json={})
    assert r.status_code == 403
    assert r.json()["detail"]["required"] == "bulletin.create"


@pytest.mark.asyncio
async def test_bulletin_create_allowed_with_permission(client):
    r = await client.post(
        f"{PREFIX}/bulletin",
        headers=auth_with(["bulletin.create"]),
        json={"title": "Aviso teste", "content": "Conteúdo"},
    )
    assert r.status_code in (201, 422)


# ---------------------------------------------------------------------------
# Maintenance
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_maintenance_list_forbidden_without_permission(client):
    r = await client.get(f"{PREFIX}/maintenance", headers=auth_none())
    assert r.status_code == 403
    assert r.json()["detail"]["required"] == "maintenance.view"


@pytest.mark.asyncio
async def test_maintenance_list_forbidden_with_wrong_permission(client):
    r = await client.get(f"{PREFIX}/maintenance", headers=auth_with(["checklist.view"]))
    assert r.status_code == 403


@pytest.mark.asyncio
async def test_maintenance_list_allowed_with_permission(client):
    r = await client.get(f"{PREFIX}/maintenance", headers=auth_with(["maintenance.view"]))
    assert r.status_code == 200


@pytest.mark.asyncio
async def test_maintenance_create_forbidden_without_permission(client):
    r = await client.post(f"{PREFIX}/maintenance", headers=auth_none(), json={})
    assert r.status_code == 403
    assert r.json()["detail"]["required"] == "maintenance.create"


@pytest.mark.asyncio
async def test_maintenance_create_allowed_with_permission(client):
    r = await client.post(
        f"{PREFIX}/maintenance",
        headers=auth_with(["maintenance.create"]),
        json={"title": "Troca de lâmpada", "description": "Quarto 101"},
    )
    assert r.status_code in (201, 422)


# ---------------------------------------------------------------------------
# Checklists
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_checklists_templates_forbidden_without_permission(client):
    r = await client.get(f"{PREFIX}/checklists/templates", headers=auth_none())
    assert r.status_code == 403
    assert r.json()["detail"]["required"] == "checklist.view"


@pytest.mark.asyncio
async def test_checklists_templates_forbidden_with_wrong_permission(client):
    r = await client.get(
        f"{PREFIX}/checklists/templates",
        headers=auth_with(["maintenance.view"]),
    )
    assert r.status_code == 403


@pytest.mark.asyncio
async def test_checklists_templates_allowed_with_permission(client):
    r = await client.get(
        f"{PREFIX}/checklists/templates",
        headers=auth_with(["checklist.view"]),
    )
    assert r.status_code == 200


@pytest.mark.asyncio
async def test_checklists_create_forbidden_without_permission(client):
    r = await client.post(f"{PREFIX}/checklists/templates", headers=auth_none(), json={})
    assert r.status_code == 403
    assert r.json()["detail"]["required"] == "checklist.create"


@pytest.mark.asyncio
async def test_checklists_create_allowed_with_permission(client):
    r = await client.post(
        f"{PREFIX}/checklists/templates",
        headers=auth_with(["checklist.create"]),
        json={"name": "Checklist teste", "items": []},
    )
    assert r.status_code in (201, 422)
