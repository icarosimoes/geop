"""
Negative-path tests: validation failures, edge cases, and error conditions
across all main domains.
"""

from datetime import UTC, datetime, timedelta

import jwt
import pytest
from httpx import AsyncClient

from tests.conftest import JWT_SECRET, TENANT_A, auth_header, make_token

API = "/api/v1"


# ---------------------------------------------------------------------------
# Auth
# ---------------------------------------------------------------------------


class TestAuthNegative:
    @pytest.mark.asyncio
    async def test_login_empty_email(self, client: AsyncClient):
        r = await client.post(f"{API}/auth/login", json={"email": "", "password": "x"})
        assert r.status_code == 422

    @pytest.mark.asyncio
    async def test_login_empty_password(self, client: AsyncClient):
        r = await client.post(f"{API}/auth/login", json={"email": "a@b.com", "password": ""})
        assert r.status_code == 422

    @pytest.mark.asyncio
    async def test_login_missing_at_in_email(self, client: AsyncClient):
        r = await client.post(f"{API}/auth/login", json={"email": "nope", "password": "test1234"})
        assert r.status_code == 422

    @pytest.mark.asyncio
    async def test_login_nonexistent_email(self, client: AsyncClient):
        r = await client.post(
            f"{API}/auth/login",
            json={"email": "ghost@nowhere.com", "password": "Str0ngPwd!"},
        )
        assert r.status_code == 401

    @pytest.mark.asyncio
    async def test_login_wrong_password(self, client: AsyncClient):
        r = await client.post(
            f"{API}/auth/login",
            json={"email": "a@test.com", "password": "WrongPass123"},
        )
        assert r.status_code == 401

    @pytest.mark.asyncio
    async def test_refresh_invalid_token(self, client: AsyncClient):
        r = await client.post(f"{API}/auth/refresh", json={"refresh_token": "not.a.valid.token"})
        assert r.status_code == 401

    @pytest.mark.asyncio
    async def test_refresh_with_access_token(self, client: AsyncClient):
        """Using an access token where a refresh token is expected must fail."""
        access_token = make_token(TENANT_A, user_id=1)
        r = await client.post(f"{API}/auth/refresh", json={"refresh_token": access_token})
        assert r.status_code == 401

    @pytest.mark.asyncio
    async def test_refresh_with_expired_token(self, client: AsyncClient):
        expired = jwt.encode(
            {
                "sub": "1",
                "company_id": TENANT_A,
                "type": "refresh",
                "iat": datetime.now(UTC) - timedelta(days=10),
                "exp": datetime.now(UTC) - timedelta(days=3),
            },
            JWT_SECRET,
            algorithm="HS256",
        )
        r = await client.post(f"{API}/auth/refresh", json={"refresh_token": expired})
        assert r.status_code == 401

    @pytest.mark.asyncio
    async def test_me_without_token(self, client: AsyncClient):
        r = await client.get(f"{API}/auth/me")
        assert r.status_code == 401

    @pytest.mark.asyncio
    async def test_me_with_invalid_token(self, client: AsyncClient):
        r = await client.get(
            f"{API}/auth/me", headers={"Authorization": "Bearer garbage.token.here"}
        )
        assert r.status_code == 401

    @pytest.mark.asyncio
    async def test_set_password_expired_invite_token(self, client: AsyncClient):
        expired = jwt.encode(
            {
                "sub": "1",
                "company_id": TENANT_A,
                "type": "invite",
                "iat": datetime.now(UTC) - timedelta(hours=72),
                "exp": datetime.now(UTC) - timedelta(hours=24),
            },
            JWT_SECRET,
            algorithm="HS256",
        )
        r = await client.post(
            f"{API}/auth/set-password",
            json={"token": expired, "password": "NewStr0ng!"},
        )
        assert r.status_code == 401

    @pytest.mark.asyncio
    async def test_set_password_weak_password(self, client: AsyncClient):
        """Weak password should be rejected even with a valid invite token."""
        from app.core.security import create_invite_token

        token = create_invite_token(user_id=1, company_id=TENANT_A, secret=JWT_SECRET, hours=48)
        r = await client.post(
            f"{API}/auth/set-password",
            json={"token": token, "password": "short"},
        )
        assert r.status_code == 422

    @pytest.mark.asyncio
    async def test_set_password_access_token_wrong_type(self, client: AsyncClient):
        """Using an access token in set-password should fail (wrong type)."""
        access = make_token(TENANT_A, user_id=1)
        r = await client.post(
            f"{API}/auth/set-password",
            json={"token": access, "password": "Str0ngPwd!"},
        )
        assert r.status_code == 401


# ---------------------------------------------------------------------------
# Fiscal Requests
# ---------------------------------------------------------------------------


class TestFiscalRequestsNegative:
    @pytest.mark.asyncio
    async def test_create_missing_required_fields(self, client: AsyncClient):
        r = await client.post(f"{API}/fiscal-requests", json={}, headers=auth_header(TENANT_A))
        assert r.status_code == 422

    @pytest.mark.asyncio
    async def test_create_invalid_cpf_in_payload(self, client: AsyncClient):
        r = await client.post(
            f"{API}/fiscal-requests",
            json={
                "request_type": "nfe",
                "title": "Test",
                "requester": "John",
                "payload": {"taxpayerDoc": "00000000000"},
            },
            headers=auth_header(TENANT_A),
        )
        assert r.status_code == 422

    @pytest.mark.asyncio
    async def test_create_invalid_cnpj_in_payload(self, client: AsyncClient):
        r = await client.post(
            f"{API}/fiscal-requests",
            json={
                "request_type": "nfe",
                "title": "Test",
                "requester": "John",
                "payload": {"taxpayerDoc": "11111111111111"},
            },
            headers=auth_header(TENANT_A),
        )
        assert r.status_code == 422

    @pytest.mark.asyncio
    async def test_create_invalid_doc_length(self, client: AsyncClient):
        r = await client.post(
            f"{API}/fiscal-requests",
            json={
                "request_type": "nfe",
                "title": "Test",
                "requester": "John",
                "payload": {"taxpayerDoc": "12345"},
            },
            headers=auth_header(TENANT_A),
        )
        assert r.status_code == 422

    @pytest.mark.asyncio
    async def test_create_invalid_email_in_payload(self, client: AsyncClient):
        r = await client.post(
            f"{API}/fiscal-requests",
            json={
                "request_type": "nfe",
                "title": "Test",
                "requester": "John",
                "payload": {"taxpayerEmail": "not-an-email"},
            },
            headers=auth_header(TENANT_A),
        )
        assert r.status_code == 422

    @pytest.mark.asyncio
    async def test_update_nonexistent(self, client: AsyncClient):
        r = await client.patch(
            f"{API}/fiscal-requests/999999",
            json={"title": "nope"},
            headers=auth_header(TENANT_A),
        )
        assert r.status_code == 404

    @pytest.mark.asyncio
    async def test_delete_nonexistent(self, client: AsyncClient):
        r = await client.delete(f"{API}/fiscal-requests/999999", headers=auth_header(TENANT_A))
        assert r.status_code == 404

    @pytest.mark.asyncio
    async def test_list_page_zero(self, client: AsyncClient):
        r = await client.get(f"{API}/fiscal-requests?page=0", headers=auth_header(TENANT_A))
        assert r.status_code == 422

    @pytest.mark.asyncio
    async def test_list_page_size_too_large(self, client: AsyncClient):
        r = await client.get(f"{API}/fiscal-requests?page_size=101", headers=auth_header(TENANT_A))
        assert r.status_code == 422

    @pytest.mark.asyncio
    async def test_create_without_auth(self, client: AsyncClient):
        r = await client.post(
            f"{API}/fiscal-requests",
            json={"request_type": "nfe", "title": "t", "requester": "x"},
        )
        assert r.status_code == 401

    @pytest.mark.asyncio
    async def test_create_wrong_permission(self, client: AsyncClient):
        token = make_token(TENANT_A, user_id=1, permissions=["fiscal_request.view"])
        r = await client.post(
            f"{API}/fiscal-requests",
            json={"request_type": "nfe", "title": "t", "requester": "x"},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert r.status_code == 403


# ---------------------------------------------------------------------------
# Users
# ---------------------------------------------------------------------------


class TestUsersNegative:
    @pytest.mark.asyncio
    async def test_create_weak_password_no_digits(self, client: AsyncClient):
        r = await client.post(
            f"{API}/users",
            json={
                "name": "Test",
                "email": "new@test.com",
                "password": "abcdefgh",
            },
            headers=auth_header(TENANT_A),
        )
        assert r.status_code == 422

    @pytest.mark.asyncio
    async def test_create_weak_password_too_short(self, client: AsyncClient):
        r = await client.post(
            f"{API}/users",
            json={
                "name": "Test",
                "email": "new@test.com",
                "password": "Ab1",
            },
            headers=auth_header(TENANT_A),
        )
        assert r.status_code == 422

    @pytest.mark.asyncio
    async def test_create_weak_password_no_letters(self, client: AsyncClient):
        r = await client.post(
            f"{API}/users",
            json={
                "name": "Test",
                "email": "new@test.com",
                "password": "12345678",
            },
            headers=auth_header(TENANT_A),
        )
        assert r.status_code == 422

    @pytest.mark.asyncio
    async def test_create_duplicate_email(self, client: AsyncClient):
        """a@test.com is seeded in conftest; creating again must 409."""
        r = await client.post(
            f"{API}/users",
            json={
                "name": "Dup",
                "email": "a@test.com",
                "password": "Str0ngPwd!",
            },
            headers=auth_header(TENANT_A),
        )
        assert r.status_code == 409

    @pytest.mark.asyncio
    async def test_update_nonexistent(self, client: AsyncClient):
        r = await client.patch(
            f"{API}/users/999999",
            json={"name": "ghost"},
            headers=auth_header(TENANT_A),
        )
        assert r.status_code == 404

    @pytest.mark.asyncio
    async def test_delete_self(self, client: AsyncClient):
        """User cannot delete themselves."""
        r = await client.delete(f"{API}/users/1", headers=auth_header(TENANT_A, user_id=1))
        assert r.status_code == 400
        assert r.json()["detail"]["code"] == "cannot_delete_self"

    @pytest.mark.asyncio
    async def test_delete_nonexistent(self, client: AsyncClient):
        r = await client.delete(f"{API}/users/999999", headers=auth_header(TENANT_A))
        assert r.status_code == 404

    @pytest.mark.asyncio
    async def test_profile_update_no_changes(self, client: AsyncClient):
        r = await client.patch(f"{API}/users/me", json={}, headers=auth_header(TENANT_A))
        assert r.status_code == 422
        assert r.json()["detail"]["code"] == "no_fields"

    @pytest.mark.asyncio
    async def test_profile_update_weak_password(self, client: AsyncClient):
        r = await client.patch(
            f"{API}/users/me",
            json={"password": "123"},
            headers=auth_header(TENANT_A),
        )
        assert r.status_code == 422

    @pytest.mark.asyncio
    async def test_create_without_auth(self, client: AsyncClient):
        r = await client.post(
            f"{API}/users",
            json={"name": "x", "email": "x@x.com", "password": "Str0ngPwd1"},
        )
        assert r.status_code == 401

    @pytest.mark.asyncio
    async def test_create_wrong_permission(self, client: AsyncClient):
        token = make_token(TENANT_A, user_id=1, permissions=["user.view"])
        r = await client.post(
            f"{API}/users",
            json={"name": "x", "email": "perm@x.com", "password": "Str0ngPwd1"},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert r.status_code == 403

    @pytest.mark.asyncio
    async def test_delete_wrong_permission(self, client: AsyncClient):
        token = make_token(TENANT_A, user_id=1, permissions=["user.view"])
        r = await client.delete(
            f"{API}/users/2",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert r.status_code == 403


# ---------------------------------------------------------------------------
# Attachments
# ---------------------------------------------------------------------------


class TestAttachmentsNegative:
    @pytest.mark.asyncio
    async def test_download_nonexistent(self, client: AsyncClient):
        r = await client.get(f"{API}/attachments/999999/download", headers=auth_header(TENANT_A))
        assert r.status_code == 404

    @pytest.mark.asyncio
    async def test_delete_nonexistent(self, client: AsyncClient):
        r = await client.delete(f"{API}/attachments/999999", headers=auth_header(TENANT_A))
        assert r.status_code == 404

    @pytest.mark.asyncio
    async def test_upload_missing_entity_id(self, client: AsyncClient):
        """entity_id is required; omitting it should 422."""
        r = await client.post(
            f"{API}/attachments?entity_type=work_order",
            files={"file": ("test.txt", b"hello", "text/plain")},
            headers=auth_header(TENANT_A),
        )
        assert r.status_code == 422

    @pytest.mark.asyncio
    async def test_upload_entity_id_zero(self, client: AsyncClient):
        """entity_id must be ge=1."""
        r = await client.post(
            f"{API}/attachments?entity_type=work_order&entity_id=0",
            files={"file": ("test.txt", b"hello", "text/plain")},
            headers=auth_header(TENANT_A),
        )
        assert r.status_code == 422

    @pytest.mark.asyncio
    async def test_upload_missing_entity_type(self, client: AsyncClient):
        """entity_type is required; omitting it should 422."""
        r = await client.post(
            f"{API}/attachments?entity_id=1",
            files={"file": ("test.txt", b"hello", "text/plain")},
            headers=auth_header(TENANT_A),
        )
        assert r.status_code == 422

    @pytest.mark.asyncio
    async def test_upload_without_auth(self, client: AsyncClient):
        r = await client.post(
            f"{API}/attachments?entity_type=work_order&entity_id=1",
            files={"file": ("test.txt", b"hello", "text/plain")},
        )
        assert r.status_code == 401

    @pytest.mark.asyncio
    async def test_download_without_auth(self, client: AsyncClient):
        r = await client.get(f"{API}/attachments/1/download")
        assert r.status_code == 401

    @pytest.mark.asyncio
    async def test_delete_without_auth(self, client: AsyncClient):
        r = await client.delete(f"{API}/attachments/1")
        assert r.status_code == 401


# ---------------------------------------------------------------------------
# Work Orders
# ---------------------------------------------------------------------------


class TestWorkOrdersNegative:
    @pytest.mark.asyncio
    async def test_create_missing_title(self, client: AsyncClient):
        r = await client.post(f"{API}/work-orders", json={}, headers=auth_header(TENANT_A))
        assert r.status_code == 422

    @pytest.mark.asyncio
    async def test_get_nonexistent(self, client: AsyncClient):
        r = await client.get(f"{API}/work-orders/999999", headers=auth_header(TENANT_A))
        assert r.status_code == 404

    @pytest.mark.asyncio
    async def test_update_nonexistent(self, client: AsyncClient):
        r = await client.patch(
            f"{API}/work-orders/999999",
            json={"title": "nope"},
            headers=auth_header(TENANT_A),
        )
        assert r.status_code == 404

    @pytest.mark.asyncio
    async def test_update_no_fields(self, client: AsyncClient):
        r = await client.patch(
            f"{API}/work-orders/1",
            json={},
            headers=auth_header(TENANT_A),
        )
        assert r.status_code == 422

    @pytest.mark.asyncio
    async def test_delete_nonexistent(self, client: AsyncClient):
        r = await client.delete(f"{API}/work-orders/999999", headers=auth_header(TENANT_A))
        assert r.status_code == 404

    @pytest.mark.asyncio
    async def test_transition_nonexistent(self, client: AsyncClient):
        r = await client.post(
            f"{API}/work-orders/999999/transition/em_andamento",
            headers=auth_header(TENANT_A),
        )
        assert r.status_code == 404

    @pytest.mark.asyncio
    async def test_transition_invalid_target_status(self, client: AsyncClient):
        """Transitioning to a status that doesn't exist should fail."""
        r = await client.post(
            f"{API}/work-orders/999999/transition/inexistente",
            headers=auth_header(TENANT_A),
        )
        # Either 404 (not found) or 422 (invalid transition) is acceptable
        assert r.status_code in (404, 422)

    @pytest.mark.asyncio
    async def test_clone_nonexistent(self, client: AsyncClient):
        r = await client.post(f"{API}/work-orders/999999/clone", headers=auth_header(TENANT_A))
        assert r.status_code == 404

    @pytest.mark.asyncio
    async def test_list_page_zero(self, client: AsyncClient):
        r = await client.get(f"{API}/work-orders?page=0", headers=auth_header(TENANT_A))
        assert r.status_code == 422

    @pytest.mark.asyncio
    async def test_list_page_negative(self, client: AsyncClient):
        r = await client.get(f"{API}/work-orders?page=-1", headers=auth_header(TENANT_A))
        assert r.status_code == 422

    @pytest.mark.asyncio
    async def test_list_page_size_too_large(self, client: AsyncClient):
        r = await client.get(f"{API}/work-orders?page_size=101", headers=auth_header(TENANT_A))
        assert r.status_code == 422

    @pytest.mark.asyncio
    async def test_list_page_size_zero(self, client: AsyncClient):
        r = await client.get(f"{API}/work-orders?page_size=0", headers=auth_header(TENANT_A))
        assert r.status_code == 422

    @pytest.mark.asyncio
    async def test_create_without_auth(self, client: AsyncClient):
        r = await client.post(f"{API}/work-orders", json={"title": "no auth"})
        assert r.status_code == 401

    @pytest.mark.asyncio
    async def test_create_wrong_permission(self, client: AsyncClient):
        token = make_token(TENANT_A, user_id=1, permissions=["work_order.view"])
        r = await client.post(
            f"{API}/work-orders",
            json={"title": "forbidden"},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert r.status_code == 403

    @pytest.mark.asyncio
    async def test_delete_wrong_permission(self, client: AsyncClient):
        token = make_token(TENANT_A, user_id=1, permissions=["work_order.view"])
        r = await client.delete(
            f"{API}/work-orders/1",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert r.status_code == 403

    @pytest.mark.asyncio
    async def test_transition_wrong_permission(self, client: AsyncClient):
        token = make_token(TENANT_A, user_id=1, permissions=["work_order.view"])
        r = await client.post(
            f"{API}/work-orders/1/transition/em_andamento",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert r.status_code == 403


# ---------------------------------------------------------------------------
# General patterns: invalid JSON, malformed requests
# ---------------------------------------------------------------------------


class TestGeneralNegative:
    @pytest.mark.asyncio
    async def test_invalid_json_body(self, client: AsyncClient):
        r = await client.post(
            f"{API}/auth/login",
            content=b"{broken json",
            headers={"Content-Type": "application/json"},
        )
        assert r.status_code == 422

    @pytest.mark.asyncio
    async def test_expired_access_token(self, client: AsyncClient):
        expired = jwt.encode(
            {
                "sub": "1",
                "company_id": TENANT_A,
                "role_id": 1,
                "permissions": ["*"],
                "type": "access",
                "iat": datetime.now(UTC) - timedelta(hours=2),
                "exp": datetime.now(UTC) - timedelta(hours=1),
            },
            JWT_SECRET,
            algorithm="HS256",
        )
        r = await client.get(
            f"{API}/work-orders",
            headers={"Authorization": f"Bearer {expired}"},
        )
        assert r.status_code == 401

    @pytest.mark.asyncio
    async def test_bearer_with_empty_token(self, client: AsyncClient):
        r = await client.get(
            f"{API}/work-orders",
            headers={"Authorization": "Bearer "},
        )
        assert r.status_code in (401, 403, 422)

    @pytest.mark.asyncio
    async def test_wrong_auth_scheme(self, client: AsyncClient):
        r = await client.get(
            f"{API}/work-orders",
            headers={"Authorization": "Basic dXNlcjpwYXNz"},
        )
        assert r.status_code == 401

    @pytest.mark.asyncio
    async def test_token_signed_with_wrong_secret(self, client: AsyncClient):
        bad_token = jwt.encode(
            {
                "sub": "1",
                "company_id": TENANT_A,
                "role_id": 1,
                "permissions": ["*"],
                "type": "access",
                "iat": datetime.now(UTC),
                "exp": datetime.now(UTC) + timedelta(hours=1),
            },
            "completely-different-secret-that-is-long-enough",
            algorithm="HS256",
        )
        r = await client.get(
            f"{API}/work-orders",
            headers={"Authorization": f"Bearer {bad_token}"},
        )
        assert r.status_code == 401
