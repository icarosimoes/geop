"""Regressão: excluir conta/regra do email_client (e sincronizar) dava 500 em
produção — `deleted_at`/`last_synced_at` gravavam datetime com tzinfo numa
coluna TIMESTAMP WITHOUT TIME ZONE, e o asyncpg rejeita isso no commit
(mesma causa do incidente documentado do erpsolid). Erro só aparece com um
INSERT/UPDATE de verdade contra o Postgres — testes unitários com mock não
pegam, por isso são testes via client HTTP real.
"""

from unittest.mock import MagicMock, patch

import pytest
from sqlalchemy import select

from app.domain.email_client import service
from app.models.email_client import EmailAccount
from tests.conftest import TENANT_A, auth_header

PREFIX = "/api/v1/email-client"


async def _create_account(client, headers) -> int:
    r = await client.post(
        f"{PREFIX}/accounts",
        json={
            "name": "Conta teste",
            "provider": "imap",
            "protocol": "imap",
            "imap_host": "imap.exemplo.com",
            "imap_port": 993,
            "imap_ssl": True,
            "username": "conta@exemplo.com",
            "password": "senha123",
        },
        headers=headers,
    )
    assert r.status_code == 201
    return r.json()["id"]


@pytest.mark.asyncio
async def test_delete_account_does_not_500(client):
    headers = auth_header(TENANT_A)
    account_id = await _create_account(client, headers)

    r = await client.delete(f"{PREFIX}/accounts/{account_id}", headers=headers)
    assert r.status_code == 204

    # Excluída (soft delete) não deve mais aparecer na listagem.
    r = await client.get(f"{PREFIX}/accounts", headers=headers)
    assert all(a["id"] != account_id for a in r.json())


@pytest.mark.asyncio
async def test_delete_alert_rule_does_not_500(client):
    headers = auth_header(TENANT_A)
    r = await client.post(
        f"{PREFIX}/alert-rules",
        json={
            "name": "Regra teste",
            "filter_type": "subject",
            "filter_value": "urgente",
            "whatsapp_targets": [],
            "account_ids": [],
        },
        headers=headers,
    )
    assert r.status_code == 201
    rule_id = r.json()["id"]

    r = await client.delete(f"{PREFIX}/alert-rules/{rule_id}", headers=headers)
    assert r.status_code == 204


@pytest.mark.asyncio
async def test_sync_account_sets_naive_last_synced_at(session):
    """sync_account grava last_synced_at e o router faz session.commit() logo
    em seguida — se o valor viesse com tzinfo, o commit contra o Postgres real
    falharia com TypeError (encoding do asyncpg), reproduzindo o 500 visto em
    produção em POST /email-client/sync."""
    account = EmailAccount(
        company_id=TENANT_A,
        name="Conta teste",
        provider="imap",
        protocol="imap",
        imap_host="imap.exemplo.com",
        imap_port=993,
        imap_ssl=True,
        username="conta@exemplo.com",
        password_enc="geop_b64:c2VuaGE=",
    )
    session.add(account)
    await session.flush()

    fake_conn = MagicMock()
    fake_conn.login.return_value = ("OK", [b"login ok"])
    fake_conn.select.return_value = ("OK", [b"1"])
    fake_conn.uid.return_value = ("OK", [b""])  # nenhuma mensagem

    account_id = account.id  # capturado antes do expire_all abaixo

    with patch("imaplib.IMAP4_SSL", return_value=fake_conn):
        result = await service.sync_account(
            session, account=account, rules=[], evolution_config=None
        )
    assert result.error is None

    # Reproduz exatamente o que o router faz depois de sync_account: commit
    # de verdade contra o Postgres. Antes do fix, isso é onde o TypeError do
    # asyncpg estourava.
    await session.commit()

    session.expire_all()
    refreshed = (
        await session.execute(select(EmailAccount).where(EmailAccount.id == account_id))
    ).scalar_one()
    assert refreshed.last_synced_at is not None
    assert refreshed.last_synced_at.tzinfo is None
