"""Testes da assinatura eletrônica do orçamento: método `simples` (OTP por
e-mail) e isolamento do webhook ICP-Brasil (Clicksign). Ver
app/domain/commercial/service.py — seção "Assinatura eletrônica"."""

import re
from datetime import timedelta
from unittest.mock import AsyncMock, patch

import pytest

from app.core.rate_limit import limiter
from app.core.security import create_esignature_webhook_token, create_quote_acceptance_token
from tests.conftest import JWT_SECRET, TENANT_A, TENANT_B, auth_header

PREFIX = "/api/v1/commercial"
PUBLIC_PREFIX = "/api/v1/public/quotes"
WEBHOOK_PREFIX = "/api/v1/public/quotes/webhooks"

CODE_RE = re.compile(r"letter-spacing:4px'>(\d{6})<")


@pytest.fixture(autouse=True)
def _reset_rate_limit():
    limiter.reset()
    yield
    limiter.reset()


@pytest.fixture(autouse=True)
def mock_storage():
    """A assinatura confirmada guarda o PDF final como `Attachment` (MinIO/S3)
    — mesmo mock de `tests/test_attachments.py::mock_storage`, autouse aqui
    porque quase todo teste deste arquivo passa pelo fluxo de confirmação."""
    with patch("app.domain.attachments.service.upload_file", return_value="fake/key.pdf"):
        yield


def _customer_body(name="Cliente Teste", email="cliente@teste.com", **kw):
    body = {"name": name, "document": "12345678000199", **kw}
    if email is not None:
        body["email"] = email
    return body


async def _create_customer(client, company_id=TENANT_A, **kw) -> int:
    r = await client.post(
        f"{PREFIX}/customers", json=_customer_body(**kw), headers=auth_header(company_id)
    )
    assert r.status_code == 201, r.text
    return r.json()["id"]


def _quote_body(customer_id: int, **kw):
    return {
        "customer_id": customer_id,
        "title": "Orçamento de teste",
        "items": [
            {
                "item_type": "servico",
                "description": "Serviço A",
                "quantity": 1,
                "unit_price": "100.00",
            }
        ],
        **kw,
    }


async def _create_and_send_quote(client, customer_id: int, company_id=TENANT_A) -> int:
    r = await client.post(
        f"{PREFIX}/quotes", json=_quote_body(customer_id), headers=auth_header(company_id)
    )
    assert r.status_code == 201, r.text
    quote_id = r.json()["id"]
    r = await client.post(f"{PREFIX}/quotes/{quote_id}/send", headers=auth_header(company_id))
    assert r.status_code == 200, r.text
    return quote_id


def _public_token(quote_id: int, company_id: int = TENANT_A) -> str:
    return create_quote_acceptance_token(
        quote_id=quote_id, company_id=company_id, secret=JWT_SECRET
    )


async def _set_tenant_brevo_config(session, company_id, value: dict) -> None:
    """`company_settings` está sob RLS — diferente do helper equivalente em
    test_commercial.py (que confia em algum teste anterior já ter "aquecido"
    a GUC nessa conexão pooled), aqui seta o tenant explicitamente antes da
    query, pra não depender da ordem de execução do arquivo/suite (ver
    app/core/rls.py::set_tenant_context)."""
    from sqlalchemy import select

    from app.core.rls import set_tenant_context
    from app.models import CompanySetting

    await set_tenant_context(session, company_id)
    row = await session.scalar(
        select(CompanySetting).where(
            CompanySetting.company_id == company_id, CompanySetting.key == "brevo"
        )
    )
    if row:
        row.value = value
    else:
        session.add(CompanySetting(company_id=company_id, key="brevo", value=value))
    await session.commit()


async def _clear_tenant_brevo_config(session, company_id) -> None:
    from sqlalchemy import delete

    from app.core.rls import set_tenant_context
    from app.models import CompanySetting

    await set_tenant_context(session, company_id)
    await session.execute(
        delete(CompanySetting).where(
            CompanySetting.company_id == company_id, CompanySetting.key == "brevo"
        )
    )
    await session.commit()


@pytest.mark.asyncio
async def test_otp_signature_happy_path_creates_sale(client, session):
    await _set_tenant_brevo_config(session, TENANT_A, {"api_key": "tenant-key"})
    try:
        customer_id = await _create_customer(client)
        quote_id = await _create_and_send_quote(client, customer_id)
        token = _public_token(quote_id)

        with patch("app.integrations.brevo.send_email", new_callable=AsyncMock) as mock_send:
            mock_send.return_value = {"messageId": "abc"}
            r = await client.post(
                f"{PUBLIC_PREFIX}/{token}/signature/otp",
                json={"signer_name": "Fulano de Tal", "signer_document": "12345678900"},
            )
        assert r.status_code == 200, r.text
        assert r.json()["status"] == "otp_enviado"

        html = mock_send.call_args.kwargs["html"]
        match = CODE_RE.search(html)
        assert match, html
        code = match.group(1)

        r = await client.post(f"{PUBLIC_PREFIX}/{token}/signature/otp/confirm", json={"code": code})
        assert r.status_code == 200, r.text
        assert r.json()["status"] == "aceito"

        # venda foi criada, igual o aceite simples
        r = await client.get(f"{PREFIX}/sales", headers=auth_header(TENANT_A))
        sale = next(s for s in r.json()["items"] if s["customer_id"] == customer_id)
        assert sale["status"] == "confirmada"

        # detalhe do orçamento reflete o método/estado da assinatura
        r = await client.get(f"{PREFIX}/quotes/{quote_id}", headers=auth_header(TENANT_A))
        assert r.json()["signature_method"] == "simples"
        assert r.json()["signature_status"] == "assinado"
    finally:
        await _clear_tenant_brevo_config(session, TENANT_A)


@pytest.mark.asyncio
async def test_otp_wrong_code_locks_after_max_attempts(client, session):
    await _set_tenant_brevo_config(session, TENANT_A, {"api_key": "tenant-key"})
    try:
        customer_id = await _create_customer(client)
        quote_id = await _create_and_send_quote(client, customer_id)
        token = _public_token(quote_id)

        with patch("app.integrations.brevo.send_email", new_callable=AsyncMock) as mock_send:
            mock_send.return_value = {"messageId": "abc"}
            r = await client.post(
                f"{PUBLIC_PREFIX}/{token}/signature/otp",
                json={"signer_name": "Fulano de Tal", "signer_document": "12345678900"},
            )
        assert r.status_code == 200
        html = mock_send.call_args.kwargs["html"]
        real_code = CODE_RE.search(html).group(1)
        wrong_code = "000000" if real_code != "000000" else "111111"

        # 5 tentativas erradas
        for _ in range(5):
            r = await client.post(
                f"{PUBLIC_PREFIX}/{token}/signature/otp/confirm", json={"code": wrong_code}
            )
            assert r.status_code == 422
            assert r.json()["detail"]["code"] == "otp_invalid"

        # a 6ª, mesmo com o código certo, já está bloqueada
        r = await client.post(
            f"{PUBLIC_PREFIX}/{token}/signature/otp/confirm", json={"code": real_code}
        )
        assert r.status_code == 422
        assert r.json()["detail"]["code"] == "otp_locked"
    finally:
        await _clear_tenant_brevo_config(session, TENANT_A)


@pytest.mark.asyncio
async def test_otp_expired_code_rejected(client, session):
    await _set_tenant_brevo_config(session, TENANT_A, {"api_key": "tenant-key"})
    try:
        customer_id = await _create_customer(client)
        quote_id = await _create_and_send_quote(client, customer_id)
        token = _public_token(quote_id)

        with patch("app.integrations.brevo.send_email", new_callable=AsyncMock) as mock_send:
            mock_send.return_value = {"messageId": "abc"}
            r = await client.post(
                f"{PUBLIC_PREFIX}/{token}/signature/otp",
                json={"signer_name": "Fulano de Tal", "signer_document": "12345678900"},
            )
        assert r.status_code == 200
        code = CODE_RE.search(mock_send.call_args.kwargs["html"]).group(1)

        with patch("app.domain.commercial.service.OTP_EXPIRY", timedelta(seconds=-1)):
            r = await client.post(
                f"{PUBLIC_PREFIX}/{token}/signature/otp/confirm", json={"code": code}
            )
        assert r.status_code == 422
        assert r.json()["detail"]["code"] == "otp_expired"
    finally:
        await _clear_tenant_brevo_config(session, TENANT_A)


@pytest.mark.asyncio
async def test_otp_request_fails_without_customer_email(client):
    customer_id = await _create_customer(client, email=None)
    quote_id = await _create_and_send_quote(client, customer_id)
    token = _public_token(quote_id)

    r = await client.post(
        f"{PUBLIC_PREFIX}/{token}/signature/otp",
        json={"signer_name": "Fulano de Tal", "signer_document": "12345678900"},
    )
    assert r.status_code == 422
    assert r.json()["detail"]["code"] == "no_customer_email"


@pytest.mark.asyncio
async def test_otp_request_without_brevo_configured_fails_cleanly(client):
    """Sem Brevo (por tenant) e com a chave de plataforma inválida/ausente, o
    pedido de código falha com 422 em vez de aparentar sucesso — diferente do
    aceite simples por clique, aqui a entrega do e-mail é essencial pro fluxo.
    `send_email` é mockado pra falhar (em vez de deixar de existir) porque o
    Postgres de dev local usado por este teste pode já ter uma config de
    e-mail de plataforma seedada (`platform_settings`), o que faria a chamada
    real ao Brevo acontecer — indesejável num teste."""
    customer_id = await _create_customer(client)
    quote_id = await _create_and_send_quote(client, customer_id)
    token = _public_token(quote_id)

    with patch(
        "app.integrations.brevo.send_email",
        new_callable=AsyncMock,
        return_value={"error": True, "status": 401},
    ):
        r = await client.post(
            f"{PUBLIC_PREFIX}/{token}/signature/otp",
            json={"signer_name": "Fulano de Tal", "signer_document": "12345678900"},
        )
    assert r.status_code == 422
    assert r.json()["detail"]["code"] in ("email_not_configured", "email_send_failed")


@pytest.mark.asyncio
async def test_otp_resend_within_cooldown_is_blocked(client, session):
    await _set_tenant_brevo_config(session, TENANT_A, {"api_key": "tenant-key"})
    try:
        customer_id = await _create_customer(client)
        quote_id = await _create_and_send_quote(client, customer_id)
        token = _public_token(quote_id)
        body = {"signer_name": "Fulano de Tal", "signer_document": "12345678900"}

        with patch("app.integrations.brevo.send_email", new_callable=AsyncMock) as mock_send:
            mock_send.return_value = {"messageId": "abc"}
            r1 = await client.post(f"{PUBLIC_PREFIX}/{token}/signature/otp", json=body)
            r2 = await client.post(f"{PUBLIC_PREFIX}/{token}/signature/otp", json=body)

        assert r1.status_code == 200
        assert r2.status_code == 422
        assert r2.json()["detail"]["code"] == "otp_cooldown"
    finally:
        await _clear_tenant_brevo_config(session, TENANT_A)


@pytest.mark.asyncio
async def test_start_icp_signature_requires_provider_configured(client):
    customer_id = await _create_customer(client)
    quote_id = await _create_and_send_quote(client, customer_id)

    r = await client.post(
        f"{PREFIX}/quotes/{quote_id}/signature/icp", headers=auth_header(TENANT_A)
    )
    assert r.status_code == 422
    assert r.json()["detail"]["code"] == "not_configured"


@pytest.mark.asyncio
async def test_clicksign_webhook_unknown_envelope_is_ignored(client):
    token = create_esignature_webhook_token(company_id=TENANT_A, secret=JWT_SECRET)
    r = await client.post(
        f"{WEBHOOK_PREFIX}/clicksign/{token}",
        json={"event": {"name": "auto_close", "data": {"envelope": {"id": "does-not-exist"}}}},
    )
    assert r.status_code == 200
    assert r.json()["status"] == "ignored"


@pytest.mark.asyncio
async def test_clicksign_webhook_invalid_token_rejected(client):
    r = await client.post(
        f"{WEBHOOK_PREFIX}/clicksign/not-a-valid-token",
        json={"event": {"name": "auto_close", "data": {}}},
    )
    assert r.status_code == 401


@pytest.mark.asyncio
async def test_clicksign_webhook_token_scoped_to_its_own_tenant(client, session):
    """Um webhook_token emitido pra TENANT_B não enxerga uma QuoteSignature
    criada sob TENANT_A — mesmo isolamento por RLS do restante do domínio."""
    from app.core.rls import set_tenant_context
    from app.models import QuoteSignature

    customer_id = await _create_customer(client, company_id=TENANT_A)
    quote_id = await _create_and_send_quote(client, customer_id, company_id=TENANT_A)

    await set_tenant_context(session, TENANT_A)
    session.add(
        QuoteSignature(
            company_id=TENANT_A,
            quote_id=quote_id,
            method="icp_brasil",
            status="pendente",
            provider="clicksign",
            provider_envelope_id="env-cross-tenant-test",
        )
    )
    await session.commit()

    forged_token = create_esignature_webhook_token(company_id=TENANT_B, secret=JWT_SECRET)
    r = await client.post(
        f"{WEBHOOK_PREFIX}/clicksign/{forged_token}",
        json={
            "event": {
                "name": "auto_close",
                "data": {"envelope": {"id": "env-cross-tenant-test"}},
            }
        },
    )
    assert r.status_code == 200
    assert r.json()["status"] == "ignored"
