"""Testes de cobertura para o domínio de anexos (attachments)."""

from unittest.mock import patch

import pytest

from tests.conftest import TENANT_A, TENANT_B, auth_header


@pytest.fixture()
def mock_storage():
    with (
        patch("app.domain.attachments.service.upload_file", return_value="fake/key.pdf"),
        patch("app.domain.attachments.service.delete_file"),
        patch(
            "app.domain.attachments.router.download_file",
            return_value=(b"content", "application/pdf"),
        ),
    ):
        yield


@pytest.mark.asyncio
async def test_upload_attachment(client, session, mock_storage):
    resp = await client.post(
        "/api/v1/attachments",
        params={"entity_type": "work_order", "entity_id": 1},
        files={"file": ("doc.pdf", b"%PDF-1.4 content", "application/pdf")},
        headers=auth_header(TENANT_A),
    )
    assert resp.status_code == 201
    data = resp.json()
    assert data["filename"] == "doc.pdf"
    assert data["entity_type"] == "work_order"
    assert data["entity_id"] == 1
    assert data["size_bytes"] > 0


@pytest.mark.asyncio
async def test_upload_invalid_entity_type(client, session, mock_storage):
    resp = await client.post(
        "/api/v1/attachments",
        params={"entity_type": "invalid_entity", "entity_id": 1},
        files={"file": ("doc.pdf", b"%PDF-1.4 content", "application/pdf")},
        headers=auth_header(TENANT_A),
    )
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_upload_invalid_content_type(client, session, mock_storage):
    resp = await client.post(
        "/api/v1/attachments",
        params={"entity_type": "work_order", "entity_id": 1},
        files={"file": ("virus.exe", b"MZ content", "application/x-msdownload")},
        headers=auth_header(TENANT_A),
    )
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_list_attachments(client, session, mock_storage):
    await client.post(
        "/api/v1/attachments",
        params={"entity_type": "work_order", "entity_id": 99},
        files={"file": ("a.pdf", b"%PDF-1.4", "application/pdf")},
        headers=auth_header(TENANT_A),
    )
    resp = await client.get(
        "/api/v1/attachments",
        params={"entity_type": "work_order", "entity_id": 99},
        headers=auth_header(TENANT_A),
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] >= 1
    assert len(data["items"]) >= 1


@pytest.mark.asyncio
async def test_list_attachments_cross_tenant(client, session, mock_storage):
    await client.post(
        "/api/v1/attachments",
        params={"entity_type": "work_order", "entity_id": 200},
        files={"file": ("b.pdf", b"%PDF-1.4", "application/pdf")},
        headers=auth_header(TENANT_A),
    )
    resp = await client.get(
        "/api/v1/attachments",
        params={"entity_type": "work_order", "entity_id": 200},
        headers=auth_header(TENANT_B, user_id=2),
    )
    assert resp.status_code == 200
    assert resp.json()["total"] == 0


@pytest.mark.asyncio
async def test_delete_attachment(client, session, mock_storage):
    upload_resp = await client.post(
        "/api/v1/attachments",
        params={"entity_type": "work_order", "entity_id": 300},
        files={"file": ("c.pdf", b"%PDF-1.4", "application/pdf")},
        headers=auth_header(TENANT_A),
    )
    assert upload_resp.status_code == 201
    att_id = upload_resp.json()["id"]

    del_resp = await client.delete(
        f"/api/v1/attachments/{att_id}",
        headers=auth_header(TENANT_A),
    )
    assert del_resp.status_code == 204


@pytest.mark.asyncio
async def test_delete_attachment_cross_tenant(client, session, mock_storage):
    upload_resp = await client.post(
        "/api/v1/attachments",
        params={"entity_type": "work_order", "entity_id": 301},
        files={"file": ("d.pdf", b"%PDF-1.4", "application/pdf")},
        headers=auth_header(TENANT_A),
    )
    att_id = upload_resp.json()["id"]

    del_resp = await client.delete(
        f"/api/v1/attachments/{att_id}",
        headers=auth_header(TENANT_B, user_id=2),
    )
    assert del_resp.status_code == 404


@pytest.mark.asyncio
async def test_delete_nonexistent_attachment(client, session, mock_storage):
    resp = await client.delete(
        "/api/v1/attachments/99999",
        headers=auth_header(TENANT_A),
    )
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_max_attachments_limit(client, session, mock_storage):
    for i in range(20):
        resp = await client.post(
            "/api/v1/attachments",
            params={"entity_type": "work_order", "entity_id": 500},
            files={"file": (f"f{i}.pdf", b"%PDF-1.4", "application/pdf")},
            headers=auth_header(TENANT_A),
        )
        assert resp.status_code == 201

    resp = await client.post(
        "/api/v1/attachments",
        params={"entity_type": "work_order", "entity_id": 500},
        files={"file": ("extra.pdf", b"%PDF-1.4", "application/pdf")},
        headers=auth_header(TENANT_A),
    )
    assert resp.status_code == 422
