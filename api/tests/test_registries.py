"""Testes de cadastros (registries), incluindo geofencing de Local."""

import pytest

from tests.conftest import TENANT_A, auth_header

PREFIX = "/api/v1"


@pytest.mark.asyncio
async def test_create_and_update_location_with_geofence(client):
    create = await client.post(
        f"{PREFIX}/registries",
        json={"name": "Recepção", "category": "Local"},
        headers=auth_header(TENANT_A),
    )
    assert create.status_code == 201
    location_id = create.json()["id"]
    assert create.json()["latitude"] is None
    assert create.json()["geofence_radius_m"] is None

    update = await client.patch(
        f"{PREFIX}/registries/{location_id}?category=Local",
        json={"latitude": -23.55052, "longitude": -46.633308, "geofence_radius_m": 150},
        headers=auth_header(TENANT_A),
    )
    assert update.status_code == 200
    body = update.json()
    assert body["latitude"] == pytest.approx(-23.55052)
    assert body["longitude"] == pytest.approx(-46.633308)
    assert body["geofence_radius_m"] == 150

    listing = await client.get(
        f"{PREFIX}/registries?category=Local",
        headers=auth_header(TENANT_A),
    )
    assert listing.status_code == 200
    item = next(i for i in listing.json()["items"] if i["id"] == location_id)
    assert item["geofence_radius_m"] == 150


@pytest.mark.asyncio
async def test_sector_update_ignores_geofence_fields(client):
    create = await client.post(
        f"{PREFIX}/registries",
        json={"name": "Governança", "category": "Setor"},
        headers=auth_header(TENANT_A),
    )
    assert create.status_code == 201
    sector_id = create.json()["id"]
    assert "latitude" not in create.json() or create.json()["latitude"] is None

    update = await client.patch(
        f"{PREFIX}/registries/{sector_id}?category=Setor",
        json={"name": "Governança 2", "latitude": -23.5, "geofence_radius_m": 200},
        headers=auth_header(TENANT_A),
    )
    assert update.status_code == 200
    body = update.json()
    assert body["name"] == "Governança 2"
    assert body["latitude"] is None
    assert body["geofence_radius_m"] is None
