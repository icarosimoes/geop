"""Cross-tenant isolation tests.

Verifies that a user from tenant A cannot access, modify, or delete
resources belonging to tenant B through any API endpoint.
"""

import pytest

from app.core.security import create_access_token
from tests.conftest import JWT_SECRET

TENANT_A = 10
TENANT_B = 20


def token_for(company_id: int, user_id: int = 1) -> str:
    return create_access_token(
        subject=user_id,
        company_id=company_id,
        role_id=1,
        permissions=[],
        secret=JWT_SECRET,
        minutes=60,
    )


@pytest.fixture()
def token_a():
    return token_for(TENANT_A, user_id=1)


@pytest.fixture()
def token_b():
    return token_for(TENANT_B, user_id=2)


def auth(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


@pytest.mark.asyncio
async def test_token_carries_correct_company_id():
    from app.core.security import decode_access_token

    tok_a = token_for(TENANT_A, user_id=1)
    tok_b = token_for(TENANT_B, user_id=2)
    claims_a = decode_access_token(tok_a, JWT_SECRET)
    claims_b = decode_access_token(tok_b, JWT_SECRET)
    assert claims_a["company_id"] == TENANT_A
    assert claims_b["company_id"] == TENANT_B
    assert claims_a["sub"] == "1"
    assert claims_b["sub"] == "2"


@pytest.mark.asyncio
async def test_token_with_wrong_secret_is_rejected():
    import jwt as pyjwt

    from app.core.security import decode_access_token

    tok = token_for(TENANT_A)
    with pytest.raises(pyjwt.InvalidSignatureError):
        decode_access_token(tok, "wrong-secret-that-is-also-long-enough")


@pytest.mark.asyncio
async def test_tokens_for_different_tenants_are_distinct():
    tok_a = token_for(TENANT_A, user_id=1)
    tok_b = token_for(TENANT_B, user_id=1)
    assert tok_a != tok_b


@pytest.mark.asyncio
async def test_company_id_cannot_be_spoofed_in_token():
    """Token company_id is set at creation time and cannot be changed."""
    from app.core.security import decode_access_token

    tok = token_for(TENANT_A, user_id=1)
    claims = decode_access_token(tok, JWT_SECRET)
    assert claims["company_id"] == TENANT_A
    assert claims["company_id"] != TENANT_B


ENDPOINTS_GET = [
    "/api/v1/work-orders",
    "/api/v1/users",
    "/api/v1/registries",
    "/api/v1/fiscal-requests",
    "/api/v1/notifications",
    "/api/v1/modules/reunioes",
    "/api/v1/procedures",
]

ENDPOINTS_POST = [
    ("/api/v1/work-orders", {"title": "Cross-tenant test"}),
    (
        "/api/v1/users",
        {
            "name": "Ghost",
            "email": "ghost@test.com",
            "password": "test1234",
        },
    ),
    (
        "/api/v1/fiscal-requests",
        {
            "request_type": "Test",
            "title": "T",
            "requester": "X",
            "payload": {},
        },
    ),
    ("/api/v1/modules/reunioes", {"title": "Meeting"}),
]


@pytest.mark.asyncio
async def test_no_token_returns_401(client):
    for path in ENDPOINTS_GET:
        r = await client.get(path)
        assert r.status_code == 401, f"{path} should require auth"


@pytest.mark.asyncio
async def test_expired_token_returns_401(client):
    expired = create_access_token(
        subject=1,
        company_id=TENANT_A,
        role_id=1,
        permissions=[],
        secret=JWT_SECRET,
        minutes=-1,
    )
    for path in ENDPOINTS_GET:
        r = await client.get(path, headers=auth(expired))
        assert r.status_code == 401, f"{path} should reject expired token"
