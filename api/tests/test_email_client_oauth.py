"""Testes do fluxo OAuth2 do Google (email_client): state token, /oauth/start,
/oauth/callback e o upsert que reconecta uma conta quebrada em vez de duplicar.
"""

from datetime import UTC, datetime, timedelta

import jwt
import pytest
from sqlalchemy import select

from app.core.security import (
    create_email_oauth_state_token,
    create_erpsolid_sso_token,
    decode_email_oauth_state_token,
)
from app.domain.email_client.service import _decrypt, _encrypt, _ensure_google_token_fresh
from app.models.email_client import EmailAccount
from tests.conftest import JWT_SECRET, TENANT_A, auth_header

PREFIX = "/api/v1/email-client"


# ── state token ──


def test_email_oauth_state_token_roundtrip():
    token = create_email_oauth_state_token(
        company_id=1, user_id=2, account_name="G7Bahia", secret=JWT_SECRET
    )
    claims = decode_email_oauth_state_token(token, JWT_SECRET)
    assert claims["company_id"] == 1
    assert claims["user_id"] == 2
    assert claims["account_name"] == "G7Bahia"
    assert claims["type"] == "email_oauth_state"


def test_email_oauth_state_token_rejects_wrong_type():
    # Um token de outro fluxo (mesma lib, secret diferente do tipo esperado) não
    # pode ser confundido com um state do email_client.
    other = create_erpsolid_sso_token(company_id=1, email="a@b.com", name="A", secret=JWT_SECRET)
    with pytest.raises(jwt.InvalidTokenError):
        decode_email_oauth_state_token(other, JWT_SECRET)


def test_email_oauth_state_token_expired():
    token = create_email_oauth_state_token(
        company_id=1, user_id=2, account_name="G7Bahia", secret=JWT_SECRET, seconds=-1
    )
    with pytest.raises(jwt.ExpiredSignatureError):
        decode_email_oauth_state_token(token, JWT_SECRET)


# ── /oauth/start ──


def _configure_oauth(app):
    from app.core.config import Settings, get_settings

    app.dependency_overrides[get_settings] = lambda: Settings(
        jwt_secret=JWT_SECRET,
        google_oauth_client_id="test-client-id",
        google_oauth_client_secret="test-client-secret",
        google_oauth_redirect_uri="http://testserver/api/v1/email-client/oauth/callback",
    )


@pytest.mark.asyncio
async def test_oauth_start_not_configured_by_default(client):
    r = await client.post(
        f"{PREFIX}/oauth/start", json={"name": "G7Bahia"}, headers=auth_header(TENANT_A)
    )
    assert r.status_code == 400
    assert r.json()["detail"]["code"] == "oauth_not_configured"


@pytest.mark.asyncio
async def test_oauth_start_returns_authorize_url(app, client):
    _configure_oauth(app)
    r = await client.post(
        f"{PREFIX}/oauth/start", json={"name": "G7Bahia"}, headers=auth_header(TENANT_A)
    )
    assert r.status_code == 200
    url = r.json()["authorize_url"]
    assert url.startswith("https://accounts.google.com/o/oauth2/v2/auth?")
    assert "client_id=test-client-id" in url
    assert "scope=https%3A%2F%2Fmail.google.com%2F+email" in url
    assert "state=" in url


# ── /oauth/callback ──


@pytest.mark.asyncio
async def test_oauth_callback_denied(app, client):
    _configure_oauth(app)
    r = await client.get(
        f"{PREFIX}/oauth/callback", params={"error": "access_denied"}, follow_redirects=False
    )
    assert r.status_code in (302, 307)
    assert "oauth=error&reason=denied" in r.headers["location"]


@pytest.mark.asyncio
async def test_oauth_callback_missing_params(app, client):
    _configure_oauth(app)
    r = await client.get(f"{PREFIX}/oauth/callback", follow_redirects=False)
    assert "oauth=error&reason=invalid_request" in r.headers["location"]


@pytest.mark.asyncio
async def test_oauth_callback_invalid_state(app, client):
    _configure_oauth(app)
    r = await client.get(
        f"{PREFIX}/oauth/callback",
        params={"code": "abc", "state": "garbage"},
        follow_redirects=False,
    )
    assert "oauth=error&reason=invalid_state" in r.headers["location"]


@pytest.mark.asyncio
async def test_oauth_callback_success_creates_account(app, client, session, monkeypatch):
    _configure_oauth(app)

    async def fake_exchange_code(**kwargs):
        return {"access_token": "fake-access", "refresh_token": "fake-refresh", "expires_in": 3600}

    async def fake_fetch_userinfo(access_token):
        assert access_token == "fake-access"
        return {"email": "redacaog7bahia@gmail.com"}

    monkeypatch.setattr("app.integrations.google_oauth.exchange_code", fake_exchange_code)
    monkeypatch.setattr("app.integrations.google_oauth.fetch_userinfo", fake_fetch_userinfo)

    state = create_email_oauth_state_token(
        company_id=TENANT_A, user_id=1, account_name="G7Bahia", secret=JWT_SECRET
    )
    r = await client.get(
        f"{PREFIX}/oauth/callback",
        params={"code": "auth-code", "state": state},
        follow_redirects=False,
    )
    assert "oauth=connected" in r.headers["location"]

    account = (
        await session.execute(
            select(EmailAccount).where(EmailAccount.username == "redacaog7bahia@gmail.com")
        )
    ).scalar_one()
    assert account.auth_type == "oauth"
    assert account.provider == "gmail"
    assert account.imap_host == "imap.gmail.com"
    assert account.password_enc is None
    assert account.oauth_access_token_enc is not None


@pytest.mark.asyncio
async def test_oauth_callback_upserts_existing_password_account(app, client, session, monkeypatch):
    _configure_oauth(app)
    existing = EmailAccount(
        company_id=TENANT_A,
        name="G7Bahia (senha)",
        provider="imap",
        protocol="imap",
        auth_type="password",
        imap_host="imap.gmail.com",
        imap_port=993,
        imap_ssl=True,
        username="reconectar@gmail.com",
        password_enc="geop_b64:c2VuaGE=",
    )
    session.add(existing)
    await session.commit()
    existing_id = existing.id

    async def fake_exchange_code(**kwargs):
        return {"access_token": "fake-access", "refresh_token": "fake-refresh", "expires_in": 3600}

    async def fake_fetch_userinfo(access_token):
        return {"email": "reconectar@gmail.com"}

    monkeypatch.setattr("app.integrations.google_oauth.exchange_code", fake_exchange_code)
    monkeypatch.setattr("app.integrations.google_oauth.fetch_userinfo", fake_fetch_userinfo)

    state = create_email_oauth_state_token(
        company_id=TENANT_A, user_id=1, account_name="ignorado", secret=JWT_SECRET
    )
    r = await client.get(
        f"{PREFIX}/oauth/callback",
        params={"code": "auth-code", "state": state},
        follow_redirects=False,
    )
    assert "oauth=connected" in r.headers["location"]

    # O callback rodou numa session diferente (a que o dependency override de
    # require_session cria por request) — sem expirar, o identity map desta
    # session devolveria o objeto `existing` em cache, com os valores antigos.
    session.expire_all()
    accounts = (
        (
            await session.execute(
                select(EmailAccount).where(EmailAccount.username == "reconectar@gmail.com")
            )
        )
        .scalars()
        .all()
    )
    assert len(accounts) == 1, "reconectar não deve duplicar a conta"
    assert accounts[0].id == existing_id
    assert accounts[0].auth_type == "oauth"
    assert accounts[0].password_enc is None


@pytest.mark.asyncio
async def test_oauth_callback_exchange_failure(app, client, monkeypatch):
    _configure_oauth(app)

    async def fake_exchange_code(**kwargs):
        from app.integrations.google_oauth import GoogleOAuthError

        raise GoogleOAuthError("invalid_grant")

    monkeypatch.setattr("app.integrations.google_oauth.exchange_code", fake_exchange_code)

    state = create_email_oauth_state_token(
        company_id=TENANT_A, user_id=1, account_name="G7Bahia", secret=JWT_SECRET
    )
    r = await client.get(
        f"{PREFIX}/oauth/callback",
        params={"code": "bad-code", "state": state},
        follow_redirects=False,
    )
    assert "oauth=error&reason=exchange_failed" in r.headers["location"]


# ── renovação de token (_ensure_google_token_fresh) ──


def _oauth_account(**overrides) -> EmailAccount:
    # Sem `id` explícito: outros testes do módulo também gravam EmailAccount de
    # verdade (commit, não rollback) na mesma base — um id fixo colidiria com o
    # autoincrement e ainda dessincronizaria a sequence pras próximas inserções.
    defaults = dict(
        company_id=TENANT_A,
        name="Conta OAuth teste",
        provider="gmail",
        protocol="imap",
        auth_type="oauth",
        imap_host="imap.gmail.com",
        imap_port=993,
        imap_ssl=True,
        username="oauth-fresh-test@gmail.com",
        password_enc=None,
        oauth_refresh_token_enc=_encrypt("stored-refresh-token"),
    )
    defaults.update(overrides)
    return EmailAccount(**defaults)


def _now_naive() -> datetime:
    # oauth_token_expires_at é TIMESTAMP WITHOUT TIME ZONE — o Postgres sempre
    # devolve naive, então os fixtures/asserts do teste precisam ser naive
    # também (não passam por round-trip no DB nos dois primeiros testes).
    return datetime.now(UTC).replace(tzinfo=None)


@pytest.mark.asyncio
async def test_ensure_google_token_fresh_reuses_valid_token(session):
    account = _oauth_account(
        oauth_access_token_enc=_encrypt("still-valid-token"),
        oauth_token_expires_at=_now_naive() + timedelta(minutes=30),
    )
    token = await _ensure_google_token_fresh(session, account)
    assert token == "still-valid-token"


@pytest.mark.asyncio
async def test_ensure_google_token_fresh_refreshes_when_expired(session, monkeypatch):
    account = _oauth_account(
        oauth_access_token_enc=_encrypt("expired-token"),
        oauth_token_expires_at=_now_naive() - timedelta(minutes=5),
    )
    session.add(account)
    await session.flush()

    async def fake_refresh(*, refresh_token, client_id, client_secret):
        assert refresh_token == "stored-refresh-token"
        return {"access_token": "brand-new-token", "expires_in": 3600}

    monkeypatch.setattr("app.integrations.google_oauth.refresh_access_token", fake_refresh)

    token = await _ensure_google_token_fresh(session, account)
    assert token == "brand-new-token"
    assert _decrypt(account.oauth_access_token_enc) == "brand-new-token"
    assert account.oauth_token_expires_at > _now_naive()


@pytest.mark.asyncio
async def test_ensure_google_token_fresh_requires_refresh_token(session):
    account = _oauth_account(oauth_refresh_token_enc=None)
    with pytest.raises(ValueError):
        await _ensure_google_token_fresh(session, account)
