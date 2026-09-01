"""Testes do pipeline comercial: Cliente -> Orçamento -> Aceite (link público) ->
Venda -> Faturamento -> Cobrança, e isolamento cross-tenant."""

from unittest.mock import AsyncMock, patch

import pytest

from app.core.rate_limit import limiter
from app.core.security import create_quote_acceptance_token
from tests.conftest import JWT_SECRET, TENANT_A, TENANT_B, auth_header

PREFIX = "/api/v1/commercial"
PUBLIC_PREFIX = "/api/v1/public/quotes"


@pytest.fixture(autouse=True)
def _reset_public_quotes_rate_limit():
    """/public/quotes/* tem rate limit (10-30/minute); sem reset, os vários
    testes deste arquivo somados (+ o teste dedicado de 429 abaixo) estourariam
    o limite dentro da mesma janela — mesmo padrão de test_timeclock_mobile.py."""
    limiter.reset()
    yield
    limiter.reset()


def _customer_body(name="Cliente Teste", **kw):
    return {"name": name, "document": "12345678000199", "email": "cliente@teste.com", **kw}


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
                "item_type": "produto",
                "description": "Item A",
                "quantity": 2,
                "unit_price": "100.00",
            },
            {
                "item_type": "servico",
                "description": "Instalação",
                "quantity": 1,
                "unit_price": "50.00",
                "discount_percent": "10",
            },
        ],
        **kw,
    }


async def _create_quote(client, customer_id: int, company_id=TENANT_A, **kw) -> dict:
    r = await client.post(
        f"{PREFIX}/quotes", json=_quote_body(customer_id, **kw), headers=auth_header(company_id)
    )
    assert r.status_code == 201, r.text
    return r.json()


def _public_token(quote_id: int, company_id: int = TENANT_A) -> str:
    return create_quote_acceptance_token(
        quote_id=quote_id, company_id=company_id, secret=JWT_SECRET
    )


@pytest.mark.asyncio
async def test_create_quote_computes_totals(client):
    customer_id = await _create_customer(client)
    quote = await _create_quote(client, customer_id)

    # 2*100 + (50 - 10%) = 200 + 45 = 245
    assert quote["subtotal"] == "245.00"
    assert quote["total"] == "245.00"
    assert quote["status"] == "rascunho"
    assert len(quote["items"]) == 2


@pytest.mark.asyncio
async def test_send_requires_items(client):
    customer_id = await _create_customer(client)
    r = await client.post(
        f"{PREFIX}/quotes",
        json={**_quote_body(customer_id), "items": []},
        headers=auth_header(TENANT_A),
    )
    quote_id = r.json()["id"]

    r = await client.post(f"{PREFIX}/quotes/{quote_id}/send", headers=auth_header(TENANT_A))
    assert r.status_code == 422
    assert r.json()["detail"]["code"] == "invalid_state"


@pytest.mark.asyncio
async def test_edit_blocked_after_send(client):
    customer_id = await _create_customer(client)
    quote = await _create_quote(client, customer_id)
    quote_id = quote["id"]

    r = await client.post(f"{PREFIX}/quotes/{quote_id}/send", headers=auth_header(TENANT_A))
    assert r.status_code == 200
    acceptance_url = r.json()["acceptance_url"]
    assert "/orcamento/" in acceptance_url

    r = await client.patch(
        f"{PREFIX}/quotes/{quote_id}", json={"title": "Novo título"}, headers=auth_header(TENANT_A)
    )
    assert r.status_code == 422
    assert r.json()["detail"]["code"] == "invalid_state"


@pytest.mark.asyncio
async def test_public_accept_creates_sale_and_full_pipeline(client):
    customer_id = await _create_customer(client)
    quote = await _create_quote(client, customer_id)
    quote_id = quote["id"]

    r = await client.post(f"{PREFIX}/quotes/{quote_id}/send", headers=auth_header(TENANT_A))
    assert r.status_code == 200

    token = _public_token(quote_id)

    # visualização pública, sem header de auth nenhum
    r = await client.get(f"{PUBLIC_PREFIX}/{token}")
    assert r.status_code == 200
    assert r.json()["status"] == "enviado"
    assert r.json()["total"] == "245.00"

    r = await client.post(f"{PUBLIC_PREFIX}/{token}/accept", json={})
    assert r.status_code == 200
    assert r.json()["status"] == "aceito"

    # decidir de novo (já decidido) é rejeitado
    r = await client.post(f"{PUBLIC_PREFIX}/{token}/accept", json={})
    assert r.status_code == 422

    # venda foi criada automaticamente
    r = await client.get(f"{PREFIX}/sales", headers=auth_header(TENANT_A))
    assert r.status_code == 200
    sales = r.json()["items"]
    sale = next(s for s in sales if s["customer_id"] == customer_id)
    assert sale["total_value"] == "245.00"
    assert sale["status"] == "confirmada"

    sale_id = sale["id"]

    # faturamento
    r = await client.post(
        f"{PREFIX}/sales/{sale_id}/invoices",
        json={"amount": "245.00"},
        headers=auth_header(TENANT_A),
    )
    assert r.status_code == 201, r.text
    invoice = r.json()
    assert invoice["status"] == "faturada"

    # cobrança parcial
    r = await client.post(
        f"{PREFIX}/invoices/{invoice['id']}/payments",
        json={"amount": "100.00", "paid_at": "2026-01-10", "method": "pix"},
        headers=auth_header(TENANT_A),
    )
    assert r.status_code == 201, r.text

    r = await client.patch(
        f"{PREFIX}/invoices/{invoice['id']}", json={}, headers=auth_header(TENANT_A)
    )
    assert r.status_code == 200
    assert r.json()["status"] == "faturada"  # ainda não quitada
    assert r.json()["paid_total"] == "100.00"

    # quita o restante
    r = await client.post(
        f"{PREFIX}/invoices/{invoice['id']}/payments",
        json={"amount": "145.00", "paid_at": "2026-01-15", "method": "pix"},
        headers=auth_header(TENANT_A),
    )
    assert r.status_code == 201

    r = await client.patch(
        f"{PREFIX}/invoices/{invoice['id']}", json={}, headers=auth_header(TENANT_A)
    )
    assert r.json()["status"] == "paga"

    # funil reflete orçado/aprovado/faturado/recebido
    r = await client.get(f"{PREFIX}/funnel", headers=auth_header(TENANT_A))
    assert r.status_code == 200
    funnel = r.json()
    assert funnel["approved_count"] >= 1
    assert float(funnel["invoiced_total"]) >= 245.00
    assert float(funnel["received_total"]) >= 245.00


@pytest.mark.asyncio
async def test_public_token_scoped_to_its_own_tenant(client):
    """Um token de aceite emitido pra TENANT_A não pode ser usado pra ler/decidir
    um orçamento de TENANT_B, mesmo trocando o quote_id — o RLS filtra pelo
    company_id assinado no token, não pelo id sozinho."""
    customer_b = await _create_customer(client, company_id=TENANT_B, name="Cliente B")
    quote_b = await _create_quote(client, customer_b, company_id=TENANT_B)
    r = await client.post(f"{PREFIX}/quotes/{quote_b['id']}/send", headers=auth_header(TENANT_B))
    assert r.status_code == 200

    # token forjado pra TENANT_A, mas com o quote_id que só existe em TENANT_B
    forged_token = _public_token(quote_b["id"], company_id=TENANT_A)
    r = await client.get(f"{PUBLIC_PREFIX}/{forged_token}")
    assert r.status_code == 404


@pytest.mark.asyncio
async def test_cross_tenant_cannot_see_other_customer(client):
    customer_id = await _create_customer(client, company_id=TENANT_A)
    r = await client.get(f"{PREFIX}/customers/{customer_id}", headers=auth_header(TENANT_B))
    assert r.status_code == 404


@pytest.mark.asyncio
async def test_quote_pdf(client):
    customer_id = await _create_customer(client)
    quote = await _create_quote(client, customer_id)

    r = await client.get(f"{PREFIX}/quotes/{quote['id']}/pdf", headers=auth_header(TENANT_A))
    assert r.status_code == 200
    assert r.headers["content-type"] == "application/pdf"
    assert r.content[:4] == b"%PDF"


@pytest.mark.asyncio
async def test_sale_pdf_and_public_quote_pdf(client):
    customer_id = await _create_customer(client)
    quote = await _create_quote(client, customer_id)
    quote_id = quote["id"]

    r = await client.post(f"{PREFIX}/quotes/{quote_id}/send", headers=auth_header(TENANT_A))
    assert r.status_code == 200

    token = _public_token(quote_id)
    r = await client.get(f"{PUBLIC_PREFIX}/{token}/pdf")
    assert r.status_code == 200
    assert r.content[:4] == b"%PDF"

    r = await client.post(f"{PUBLIC_PREFIX}/{token}/accept", json={})
    assert r.status_code == 200

    sales = await client.get(f"{PREFIX}/sales", headers=auth_header(TENANT_A))
    sale = next(s for s in sales.json()["items"] if s["customer_id"] == customer_id)

    r = await client.get(f"{PREFIX}/sales/{sale['id']}/pdf", headers=auth_header(TENANT_A))
    assert r.status_code == 200
    assert r.headers["content-type"] == "application/pdf"
    assert r.content[:4] == b"%PDF"


async def _set_tenant_brevo_config(session, value: dict) -> None:
    """Upsert em `company_settings` (chave `brevo`) pra TENANT_A — via `select`
    primeiro porque o teste roda contra o Postgres compartilhado de dev e a
    linha, uma vez commitada, sobrevive entre testes (não há rollback depois
    de um `commit()` explícito). Ver `_clear_tenant_brevo_config` — quem chama
    esta função é responsável por limpar no final do teste."""
    from sqlalchemy import select

    from app.models import CompanySetting

    row = await session.scalar(
        select(CompanySetting).where(
            CompanySetting.company_id == TENANT_A, CompanySetting.key == "brevo"
        )
    )
    if row:
        row.value = value
    else:
        session.add(CompanySetting(company_id=TENANT_A, key="brevo", value=value))
    await session.commit()


async def _clear_tenant_brevo_config(session) -> None:
    from sqlalchemy import delete

    from app.models import CompanySetting

    await session.execute(
        delete(CompanySetting).where(
            CompanySetting.company_id == TENANT_A, CompanySetting.key == "brevo"
        )
    )
    await session.commit()


@pytest.mark.asyncio
async def test_send_quote_emails_customer_when_brevo_configured(client, session):
    """`send_quote` dispara um email pro cliente com o link de aceite quando há
    config de Brevo (por tenant, aqui) e o cliente tem email cadastrado."""
    await _set_tenant_brevo_config(
        session,
        {
            "api_key": "tenant-level-key",
            "from_address": "vendas@tenant.com",
            "from_name": "Tenant Vendas",
        },
    )
    try:
        customer_id = await _create_customer(client)
        quote = await _create_quote(client, customer_id)
        quote_id = quote["id"]

        with patch("app.integrations.brevo.send_email", new_callable=AsyncMock) as mock_send:
            r = await client.post(f"{PREFIX}/quotes/{quote_id}/send", headers=auth_header(TENANT_A))
            assert r.status_code == 200

        mock_send.assert_awaited_once()
        kwargs = mock_send.call_args.kwargs
        assert kwargs["api_key"] == "tenant-level-key"
        assert kwargs["from_address"] == "vendas@tenant.com"
        assert kwargs["to_email"] == "cliente@teste.com"
        assert "/orcamento/" in kwargs["html"]
    finally:
        await _clear_tenant_brevo_config(session)


@pytest.mark.asyncio
async def test_send_quote_email_failure_does_not_break_send(client, session):
    """Um Brevo fora do ar não pode reverter o envio do orçamento — best effort."""
    await _set_tenant_brevo_config(session, {"api_key": "tenant-level-key"})
    try:
        customer_id = await _create_customer(client)
        quote = await _create_quote(client, customer_id)
        quote_id = quote["id"]

        with patch(
            "app.integrations.brevo.send_email",
            new_callable=AsyncMock,
            side_effect=Exception("Brevo down"),
        ):
            r = await client.post(f"{PREFIX}/quotes/{quote_id}/send", headers=auth_header(TENANT_A))

        assert r.status_code == 200
        assert r.json()["quote"]["status"] == "enviado"
    finally:
        await _clear_tenant_brevo_config(session)


@pytest.mark.asyncio
async def test_public_accept_rate_limited(client):
    """`POST /public/quotes/{token}/accept` é limitado a 10/minuto por IP — a
    11a chamada na mesma janela deve devolver 429, mesmo repetindo o mesmo
    token (que já cai em 422 invalid_state depois da 1a aceitação)."""
    customer_id = await _create_customer(client)
    quote = await _create_quote(client, customer_id)
    quote_id = quote["id"]
    r = await client.post(f"{PREFIX}/quotes/{quote_id}/send", headers=auth_header(TENANT_A))
    assert r.status_code == 200
    token = _public_token(quote_id)

    statuses = [
        (await client.post(f"{PUBLIC_PREFIX}/{token}/accept", json={})).status_code
        for _ in range(11)
    ]

    assert statuses[0] == 200
    assert statuses[1:10] == [422] * 9
    assert statuses[10] == 429
