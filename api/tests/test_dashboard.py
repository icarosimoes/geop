"""Testes do dashboard via API."""

import pytest

from tests.conftest import TENANT_A, USE_POSTGRES, auth_header

pytestmark = pytest.mark.skipif(
    not USE_POSTGRES, reason="Dashboard uses raw SQL requiring PostgreSQL"
)

HEADERS_A = auth_header(TENANT_A, 1)
DASH_URL = "/api/v1/dashboard/metrics"


@pytest.mark.asyncio
async def test_get_metrics(client):
    r = await client.get(DASH_URL, headers=HEADERS_A)
    assert r.status_code == 200
    data = r.json()
    assert "open_occurrences" in data
    assert "my_occurrences" in data
    assert "open_fiscal" in data
    assert "completed_month" in data
    assert "active_users" in data
    assert "active_sectors" in data
    assert "recent" in data
    assert isinstance(data["recent"], list)


@pytest.mark.asyncio
async def test_get_metrics_kpis_structure(client):
    r = await client.get(DASH_URL, headers=HEADERS_A)
    assert r.status_code == 200
    kpis = r.json()["kpis"]
    assert "work_orders" in kpis
    assert "fiscal_requests" in kpis
    assert "trend" in kpis
    assert isinstance(kpis["trend"], list)

    # Work order KPIs
    wo = kpis["work_orders"]
    assert "total" in wo
    assert "by_status" in wo
    assert "by_priority" in wo
    assert "overdue" in wo

    # Fiscal request KPIs
    fr = kpis["fiscal_requests"]
    assert "by_status" in fr
    assert "by_type" in fr
    assert "overdue" in fr


@pytest.mark.asyncio
async def test_get_metrics_numeric_values(client):
    r = await client.get(DASH_URL, headers=HEADERS_A)
    data = r.json()
    assert isinstance(data["open_occurrences"], int)
    assert isinstance(data["my_occurrences"], int)
    assert isinstance(data["active_users"], int)
    assert data["open_occurrences"] >= 0
    assert data["active_users"] >= 0


@pytest.mark.asyncio
async def test_metrics_requires_auth(client):
    r = await client.get(DASH_URL)
    assert r.status_code in (401, 403)
