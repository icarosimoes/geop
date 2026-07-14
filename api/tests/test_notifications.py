"""Testes de notificações via API."""

import pytest

from app.models import Notification
from tests.conftest import TENANT_A, TENANT_B, auth_header

HEADERS_A = auth_header(TENANT_A, 1)
HEADERS_B = auth_header(TENANT_B, 2)
NOTIF_URL = "/api/v1/notifications"


async def _seed_notification(session, user_id=1, company_id=TENANT_A, title="Test notif"):
    n = Notification(
        company_id=company_id,
        user_id=user_id,
        title=title,
        body="Corpo da notificação",
        category="info",
        entity_type="work_order",
        entity_id=1,
    )
    session.add(n)
    await session.commit()
    await session.refresh(n)
    return n


# ── List ──


@pytest.mark.asyncio
async def test_list_notifications(client, session):
    await _seed_notification(session)
    r = await client.get(NOTIF_URL, headers=HEADERS_A)
    assert r.status_code == 200
    data = r.json()
    assert "items" in data
    assert "total" in data
    assert "unread" in data
    assert data["page"] == 1


@pytest.mark.asyncio
async def test_list_notifications_pagination(client, session):
    for i in range(3):
        await _seed_notification(session, title=f"Notif {i}")
    r = await client.get(f"{NOTIF_URL}?page=1&page_size=2", headers=HEADERS_A)
    assert r.status_code == 200
    data = r.json()
    assert len(data["items"]) <= 2


@pytest.mark.asyncio
async def test_list_notifications_unread_only(client, session):
    await _seed_notification(session, title="Unread filter")
    r = await client.get(f"{NOTIF_URL}?unread_only=true", headers=HEADERS_A)
    assert r.status_code == 200
    data = r.json()
    for item in data["items"]:
        assert item["read_at"] is None


# ── Mark as read ──


@pytest.mark.asyncio
async def test_mark_as_read(client, session):
    n = await _seed_notification(session, title="Mark read")
    r = await client.patch(f"{NOTIF_URL}/{n.id}/read", headers=HEADERS_A)
    assert r.status_code == 200
    data = r.json()
    assert data["read_at"] is not None


@pytest.mark.asyncio
async def test_mark_as_read_idempotent(client, session):
    n = await _seed_notification(session, title="Idempotent read")
    await client.patch(f"{NOTIF_URL}/{n.id}/read", headers=HEADERS_A)
    r = await client.patch(f"{NOTIF_URL}/{n.id}/read", headers=HEADERS_A)
    assert r.status_code == 200
    assert r.json()["read_at"] is not None


@pytest.mark.asyncio
async def test_mark_as_read_nonexistent_returns_404(client):
    r = await client.patch(f"{NOTIF_URL}/99999/read", headers=HEADERS_A)
    assert r.status_code == 404


# ── Mark all as read ──


@pytest.mark.asyncio
async def test_mark_all_as_read(client, session):
    await _seed_notification(session, title="All read 1")
    await _seed_notification(session, title="All read 2")

    r = await client.post(f"{NOTIF_URL}/read-all", headers=HEADERS_A)
    assert r.status_code == 204

    r2 = await client.get(f"{NOTIF_URL}?unread_only=true", headers=HEADERS_A)
    assert r2.json()["total"] == 0


# ── Cross-tenant isolation ──


@pytest.mark.asyncio
async def test_cross_tenant_cannot_read_notification(client, session):
    n = await _seed_notification(session, user_id=1, company_id=TENANT_A, title="Private")
    r = await client.patch(f"{NOTIF_URL}/{n.id}/read", headers=HEADERS_B)
    assert r.status_code == 404


@pytest.mark.asyncio
async def test_cross_tenant_list_isolation(client, session):
    await _seed_notification(session, user_id=1, company_id=TENANT_A, title="TenantAOnly")
    r = await client.get(NOTIF_URL, headers=HEADERS_B)
    assert r.status_code == 200
    items = r.json()["items"]
    assert not any(i["title"] == "TenantAOnly" for i in items)


# ── Preferences ──


@pytest.mark.asyncio
async def test_list_preferences(client):
    r = await client.get(f"{NOTIF_URL}/preferences", headers=HEADERS_A)
    assert r.status_code == 200
    data = r.json()
    assert isinstance(data, list)
    assert len(data) > 0
    for pref in data:
        assert "module" in pref
        assert "in_app" in pref
        assert "email" in pref


@pytest.mark.asyncio
async def test_update_preference(client):
    r = await client.put(
        f"{NOTIF_URL}/preferences/work_orders",
        json={"in_app": True, "email": False},
        headers=HEADERS_A,
    )
    assert r.status_code == 200
    data = r.json()
    assert data["module"] == "work_orders"
    assert data["in_app"] is True
    assert data["email"] is False


@pytest.mark.asyncio
async def test_update_preference_invalid_module(client):
    r = await client.put(
        f"{NOTIF_URL}/preferences/invalid_module",
        json={"in_app": True, "email": True},
        headers=HEADERS_A,
    )
    assert r.status_code == 400


# ── Auth required ──


@pytest.mark.asyncio
async def test_list_requires_auth(client):
    r = await client.get(NOTIF_URL)
    assert r.status_code in (401, 403)
