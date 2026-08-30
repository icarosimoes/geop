"""Testes do fetch IMAP/POP3 do email_client — foco em deduplicação por UID estável."""

from unittest.mock import MagicMock, patch

from app.domain.email_client.service import _imap_fetch
from app.models.email_client import EmailAccount

RAW_EMAIL = (
    b"From: Remetente <remetente@exemplo.com>\r\n"
    b"To: destino@exemplo.com\r\n"
    b"Subject: Assunto de teste\r\n"
    b"Date: Mon, 24 Aug 2026 10:00:00 +0000\r\n"
    b"Content-Type: text/plain\r\n"
    b"\r\n"
    b"Corpo da mensagem.\r\n"
)


def _account() -> EmailAccount:
    return EmailAccount(
        id=1,
        company_id=1,
        name="Conta teste",
        provider="imap",
        protocol="imap",
        imap_host="imap.exemplo.com",
        imap_port=993,
        imap_ssl=True,
        username="user@exemplo.com",
        password_enc="geop_b64:c2VuaGE=",
    )


def test_imap_fetch_uses_uid_commands_not_sequence_numbers():
    """
    Regressão: _imap_fetch usava conn.search()/conn.fetch() (número de sequência,
    que muda a cada alteração da caixa) em vez de conn.uid("search"/"fetch", ...)
    (UID persistente). Como sync_account deduplica mensagens pelo campo "uid",
    usar número de sequência fazia mensagens novas serem puladas (ou reprocessadas)
    sempre que a caixa mudava entre duas sincronizações.
    """
    fake_conn = MagicMock()
    fake_conn.login.return_value = ("OK", [b"login ok"])
    fake_conn.select.return_value = ("OK", [b"1"])
    fake_conn.uid.side_effect = [
        ("OK", [b"101 102"]),  # uid("search", ...)
        ("OK", [(b"102 (RFC822 {123}", RAW_EMAIL), b")"]),  # uid("fetch", "102", ...)
        ("OK", [(b"101 (RFC822 {123}", RAW_EMAIL), b")"]),  # uid("fetch", "101", ...)
    ]

    with patch("imaplib.IMAP4_SSL", return_value=fake_conn):
        messages, error = _imap_fetch(_account(), "senha", max_messages=50)

    assert error is None
    assert not fake_conn.search.called, "não deve usar SEARCH por número de sequência"
    assert not fake_conn.fetch.called, "não deve usar FETCH por número de sequência"
    assert fake_conn.uid.call_args_list[0].args[0] == "search"
    assert all(c.args[0] == "fetch" for c in fake_conn.uid.call_args_list[1:])

    assert len(messages) == 2
    uids = {m["uid"] for m in messages}
    assert uids == {"101", "102"}, (
        "uid armazenado deve ser o UID persistente, não o número de sequência"
    )
    assert messages[0]["from_addr"] == "remetente@exemplo.com"
    assert messages[0]["subject"] == "Assunto de teste"


def test_imap_fetch_reports_search_failure():
    fake_conn = MagicMock()
    fake_conn.login.return_value = ("OK", [b"login ok"])
    fake_conn.select.return_value = ("OK", [b"1"])
    fake_conn.uid.return_value = ("NO", [b"search failed"])

    with patch("imaplib.IMAP4_SSL", return_value=fake_conn):
        messages, error = _imap_fetch(_account(), "senha", max_messages=50)

    assert messages == []
    assert error == "IMAP search falhou"
