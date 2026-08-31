"""Serviço do cliente de e-mail: IMAP/POP3, cache de mensagens, alertas WhatsApp."""

import base64
import email
import email.header
import imaplib
import poplib
import re
from datetime import UTC, datetime, timedelta
from email.utils import parseaddr, parsedate_to_datetime

import structlog
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.domain.email_client.schemas import (
    EmailAccountCreate,
    EmailAccountUpdate,
    EmailAlertRuleCreate,
    EmailAlertRuleUpdate,
    SyncResult,
    WhatsAppTarget,
)
from app.models.email_client import EmailAccount, EmailAlertRule, EmailMessage

logger = structlog.get_logger()

# Chave simples de ofuscação — para produção substitua por Fernet/KMS.
_MARKER = "geop_b64:"


def _encrypt(plain: str) -> str:
    return _MARKER + base64.b64encode(plain.encode()).decode()


def _decrypt(stored: str) -> str:
    if stored.startswith(_MARKER):
        return base64.b64decode(stored[len(_MARKER) :]).decode()
    return stored  # fallback para senhas antigas não marcadas


# ── Contas ──


async def list_accounts(session: AsyncSession, *, company_id: int) -> list[EmailAccount]:
    result = await session.execute(
        select(EmailAccount).where(
            EmailAccount.company_id == company_id,
            EmailAccount.deleted_at.is_(None),
        )
    )
    return list(result.scalars().all())


async def get_account(
    session: AsyncSession, *, company_id: int, account_id: int
) -> EmailAccount | None:
    return (
        await session.execute(
            select(EmailAccount).where(
                EmailAccount.company_id == company_id,
                EmailAccount.id == account_id,
                EmailAccount.deleted_at.is_(None),
            )
        )
    ).scalar_one_or_none()


async def create_account(
    session: AsyncSession, *, company_id: int, data: EmailAccountCreate
) -> EmailAccount:
    account = EmailAccount(
        company_id=company_id,
        name=data.name,
        provider=data.provider,
        protocol=data.protocol,
        imap_host=data.imap_host,
        imap_port=data.imap_port,
        imap_ssl=data.imap_ssl,
        username=data.username,
        password_enc=_encrypt(data.password),
    )
    session.add(account)
    await session.flush()
    return account


async def update_account(
    session: AsyncSession,
    *,
    account: EmailAccount,
    data: EmailAccountUpdate,
) -> EmailAccount:
    for field, value in data.model_dump(exclude_none=True).items():
        if field == "password":
            account.password_enc = _encrypt(value)
        else:
            setattr(account, field, value)
    return account


async def delete_account(session: AsyncSession, *, account: EmailAccount) -> None:
    account.deleted_at = datetime.now(UTC)


async def upsert_oauth_account(
    session: AsyncSession,
    *,
    company_id: int,
    google_email: str,
    account_name: str,
    tokens: dict,
) -> tuple[EmailAccount, bool]:
    """Cria a EmailAccount da conta Google autorizada ou, se já existir uma conta
    ativa com o mesmo e-mail neste tenant (ex.: uma conta cadastrada por senha que
    parou de autenticar), atualiza essa mesma linha para OAuth em vez de duplicar —
    esse é o caminho de "reconectar" uma conta quebrada. Retorna (account, created)."""
    existing = (
        await session.execute(
            select(EmailAccount).where(
                EmailAccount.company_id == company_id,
                EmailAccount.username == google_email,
                EmailAccount.deleted_at.is_(None),
            )
        )
    ).scalar_one_or_none()

    # oauth_token_expires_at é TIMESTAMP WITHOUT TIME ZONE — naive UTC, mesma
    # convenção já documentada para outros campos de data desta API (asyncpg
    # rejeita datetime com tzinfo numa coluna sem timezone).
    expires_at = (datetime.now(UTC) + timedelta(seconds=tokens.get("expires_in", 3600))).replace(
        tzinfo=None
    )
    access_token_enc = _encrypt(tokens["access_token"])
    # O Google só reemite refresh_token no primeiro consent (prompt=consent garante
    # isso na autorização inicial); numa reautorização ele pode vir ausente — nesse
    # caso mantém o refresh_token que já tínhamos.
    refresh_token = tokens.get("refresh_token")

    if existing:
        existing.auth_type = "oauth"
        existing.provider = "gmail"
        existing.protocol = "imap"
        existing.imap_host = "imap.gmail.com"
        existing.imap_port = 993
        existing.imap_ssl = True
        existing.password_enc = None
        existing.oauth_access_token_enc = access_token_enc
        if refresh_token:
            existing.oauth_refresh_token_enc = _encrypt(refresh_token)
        existing.oauth_token_expires_at = expires_at
        existing.active = True
        return existing, False

    if not refresh_token:
        raise ValueError("Google não retornou refresh_token nesta autorização")

    account = EmailAccount(
        company_id=company_id,
        name=account_name,
        provider="gmail",
        protocol="imap",
        auth_type="oauth",
        imap_host="imap.gmail.com",
        imap_port=993,
        imap_ssl=True,
        username=google_email,
        password_enc=None,
        oauth_access_token_enc=access_token_enc,
        oauth_refresh_token_enc=_encrypt(refresh_token),
        oauth_token_expires_at=expires_at,
    )
    session.add(account)
    await session.flush()
    return account, True


# ── Mensagens ──


async def list_messages(
    session: AsyncSession,
    *,
    company_id: int,
    account_id: int | None = None,
    page: int = 1,
    page_size: int = 50,
    only_unread: bool = False,
) -> tuple[list[EmailMessage], int]:
    q = select(EmailMessage).where(EmailMessage.company_id == company_id)
    if account_id:
        q = q.where(EmailMessage.account_id == account_id)
    if only_unread:
        q = q.where(EmailMessage.is_read.is_(False))
    total = (await session.execute(select(func.count()).select_from(q.subquery()))).scalar_one()
    items = (
        (
            await session.execute(
                q.order_by(EmailMessage.received_at.desc().nullslast())
                .offset((page - 1) * page_size)
                .limit(page_size)
            )
        )
        .scalars()
        .all()
    )
    return list(items), total


async def get_message(
    session: AsyncSession, *, company_id: int, message_id: int
) -> EmailMessage | None:
    return (
        await session.execute(
            select(EmailMessage).where(
                EmailMessage.company_id == company_id,
                EmailMessage.id == message_id,
            )
        )
    ).scalar_one_or_none()


async def mark_read(session: AsyncSession, *, message: EmailMessage, is_read: bool) -> None:
    message.is_read = is_read


# ── Regras de alerta ──


async def list_alert_rules(session: AsyncSession, *, company_id: int) -> list[EmailAlertRule]:
    result = await session.execute(
        select(EmailAlertRule)
        .where(
            EmailAlertRule.company_id == company_id,
            EmailAlertRule.deleted_at.is_(None),
        )
        .order_by(EmailAlertRule.id)
    )
    return list(result.scalars().all())


async def get_alert_rule(
    session: AsyncSession, *, company_id: int, rule_id: int
) -> EmailAlertRule | None:
    return (
        await session.execute(
            select(EmailAlertRule).where(
                EmailAlertRule.company_id == company_id,
                EmailAlertRule.id == rule_id,
                EmailAlertRule.deleted_at.is_(None),
            )
        )
    ).scalar_one_or_none()


async def create_alert_rule(
    session: AsyncSession, *, company_id: int, data: EmailAlertRuleCreate
) -> EmailAlertRule:
    rule = EmailAlertRule(
        company_id=company_id,
        name=data.name,
        filter_type=data.filter_type,
        filter_value=data.filter_value,
        whatsapp_targets=[t.model_dump() for t in data.whatsapp_targets],
        account_ids=data.account_ids,
    )
    session.add(rule)
    await session.flush()
    return rule


async def update_alert_rule(
    session: AsyncSession,
    *,
    rule: EmailAlertRule,
    data: EmailAlertRuleUpdate,
) -> EmailAlertRule:
    payload = data.model_dump(exclude_none=True)
    if "whatsapp_targets" in payload:
        payload["whatsapp_targets"] = [
            t.model_dump() if isinstance(t, WhatsAppTarget) else t
            for t in payload["whatsapp_targets"]
        ]
    for field, value in payload.items():
        setattr(rule, field, value)
    return rule


async def delete_alert_rule(session: AsyncSession, *, rule: EmailAlertRule) -> None:
    rule.deleted_at = datetime.now(UTC)


# ── IMAP helpers ──


def _decode_header(raw: str | bytes | None) -> str:
    if raw is None:
        return ""
    if isinstance(raw, bytes):
        raw = raw.decode(errors="replace")
    parts = email.header.decode_header(raw)
    decoded = []
    for part, charset in parts:
        if isinstance(part, bytes):
            decoded.append(part.decode(charset or "utf-8", errors="replace"))
        else:
            decoded.append(str(part))
    return " ".join(decoded)


def _extract_body(msg: email.message.Message) -> tuple[str | None, str | None]:
    text_plain = None
    text_html = None
    if msg.is_multipart():
        for part in msg.walk():
            ct = part.get_content_type()
            if ct == "text/plain" and text_plain is None:
                payload = part.get_payload(decode=True)
                if isinstance(payload, bytes):
                    charset = part.get_content_charset() or "utf-8"
                    text_plain = payload.decode(charset, errors="replace")
            elif ct == "text/html" and text_html is None:
                payload = part.get_payload(decode=True)
                if isinstance(payload, bytes):
                    charset = part.get_content_charset() or "utf-8"
                    text_html = payload.decode(charset, errors="replace")
    else:
        payload = msg.get_payload(decode=True)
        if isinstance(payload, bytes):
            charset = msg.get_content_charset() or "utf-8"
            content = payload.decode(charset, errors="replace")
            if msg.get_content_type() == "text/html":
                text_html = content
            else:
                text_plain = content
    return text_plain, text_html


def _rule_matches(rule: EmailAlertRule, msg: EmailMessage) -> bool:
    """Verifica se uma mensagem corresponde ao filtro da regra."""
    pattern = rule.filter_value.lower()
    if rule.filter_type == "subject":
        return pattern in (msg.subject or "").lower()
    elif rule.filter_type == "sender":
        return pattern in msg.from_addr.lower()
    elif rule.filter_type == "domain":
        # extrai domínio do remetente
        match = re.search(r"@([\w.\-]+)", msg.from_addr)
        if not match:
            return False
        domain = match.group(1).lower()
        return domain == pattern.lstrip("@").lower()
    return False


def _format_alert(msg: EmailMessage, account_name: str) -> str:
    subject = msg.subject or "(sem assunto)"
    from_display = msg.from_name or msg.from_addr
    received = ""
    if msg.received_at:
        received = msg.received_at.strftime("%d/%m/%Y %H:%M")
    preview = (msg.body_text or "")[:400].strip()
    return (
        f"📧 *Novo e-mail — {account_name}*\n"
        f"*De:* {from_display} <{msg.from_addr}>\n"
        f"*Assunto:* {subject}\n"
        f"*Recebido:* {received}\n\n"
        f"{preview}" + ("\n[...]" if len(msg.body_text or "") > 400 else "")
    )


# ── Sincronização IMAP / POP3 ──


async def _ensure_google_token_fresh(session: AsyncSession, account: EmailAccount) -> str:
    """Retorna um access_token válido para a conta OAuth, renovando via refresh_token
    se estiver expirado (ou perto de expirar). Chamado antes do fetch, que roda em
    thread separada e não pode fazer a chamada HTTP async pro Google."""
    from app.integrations import google_oauth

    # naive UTC: oauth_token_expires_at é TIMESTAMP WITHOUT TIME ZONE (ver
    # upsert_oauth_account) — comparar/gravar com datetime aware quebraria aqui.
    now = datetime.now(UTC).replace(tzinfo=None)
    margin = timedelta(seconds=60)
    if (
        account.oauth_access_token_enc
        and account.oauth_token_expires_at
        and account.oauth_token_expires_at - margin > now
    ):
        return _decrypt(account.oauth_access_token_enc)

    if not account.oauth_refresh_token_enc:
        raise ValueError("Conta Google sem refresh_token — reconecte a conta")

    settings = get_settings()
    tokens = await google_oauth.refresh_access_token(
        refresh_token=_decrypt(account.oauth_refresh_token_enc),
        client_id=settings.google_oauth_client_id,
        client_secret=settings.google_oauth_client_secret,
    )
    access_token: str = tokens["access_token"]
    account.oauth_access_token_enc = _encrypt(access_token)
    account.oauth_token_expires_at = now + timedelta(seconds=tokens.get("expires_in", 3600))
    await session.commit()
    return access_token


async def sync_account(
    session: AsyncSession,
    *,
    account: EmailAccount,
    rules: list[EmailAlertRule],
    evolution_config: dict | None,
    max_messages: int = 50,
) -> SyncResult:
    """
    Conecta via IMAP ou POP3, busca mensagens novas, armazena e dispara alertas.
    Executado em thread separada para não bloquear o event loop.
    """
    import asyncio

    new_count = 0
    alerts_sent = 0
    error_msg: str | None = None

    try:
        protocol = getattr(account, "protocol", "imap") or "imap"
        password: str | None = None
        access_token: str | None = None
        if account.auth_type == "oauth":
            access_token = await _ensure_google_token_fresh(session, account)
            fetch_fn = _imap_fetch  # OAuth só é suportado via IMAP nesta fase
        else:
            password = _decrypt(account.password_enc or "")
            fetch_fn = _pop3_fetch if protocol == "pop3" else _imap_fetch
        result = await asyncio.get_event_loop().run_in_executor(
            None,
            lambda: fetch_fn(account, max_messages, password=password, access_token=access_token),
        )
        raw_messages, fetch_error = result
        if fetch_error:
            error_msg = fetch_error
            return SyncResult(
                account_id=account.id,
                new_messages=0,
                alerts_sent=0,
                error=error_msg,
            )

        for raw in raw_messages:
            uid = raw["uid"]
            # Verifica se já existe
            existing = (
                await session.execute(
                    select(EmailMessage).where(
                        EmailMessage.account_id == account.id,
                        EmailMessage.uid == uid,
                    )
                )
            ).scalar_one_or_none()
            if existing:
                continue

            msg_obj = EmailMessage(
                company_id=account.company_id,
                account_id=account.id,
                uid=uid,
                folder=raw.get("folder", "INBOX"),
                from_addr=raw["from_addr"],
                from_name=raw.get("from_name"),
                to_addr=raw.get("to_addr"),
                subject=raw.get("subject"),
                body_text=raw.get("body_text"),
                body_html=raw.get("body_html"),
                received_at=raw.get("received_at"),
                is_read=False,
                alerted_rule_ids=[],
            )
            session.add(msg_obj)
            await session.flush()
            new_count += 1

            # Checar regras ativas que incluem esta conta
            applicable_rules = [
                r for r in rules if r.active and (not r.account_ids or account.id in r.account_ids)
            ]
            for rule in applicable_rules:
                if rule.id in (msg_obj.alerted_rule_ids or []):
                    continue
                if _rule_matches(rule, msg_obj):
                    sent_ok = await _send_whatsapp_alerts(
                        msg_obj,
                        rule,
                        account.name,
                        evolution_config,
                    )
                    if sent_ok:
                        alerted = list(msg_obj.alerted_rule_ids or [])
                        alerted.append(rule.id)
                        msg_obj.alerted_rule_ids = alerted
                        alerts_sent += 1

        account.last_synced_at = datetime.now(UTC)

    except Exception as exc:
        logger.error("email_sync_error", account_id=account.id, error=str(exc))
        error_msg = str(exc)

    return SyncResult(
        account_id=account.id,
        new_messages=new_count,
        alerts_sent=alerts_sent,
        error=error_msg,
    )


def _imap_fetch(
    account: EmailAccount,
    max_messages: int,
    *,
    password: str | None = None,
    access_token: str | None = None,
) -> tuple[list[dict], str | None]:
    """Executa fetch IMAP em thread síncrona. Autentica por senha (LOGIN) ou, se
    `access_token` for passado, por OAuth2 (XOAUTH2 — usado pelas contas Google)."""
    try:
        conn: imaplib.IMAP4
        if account.imap_ssl:
            conn = imaplib.IMAP4_SSL(account.imap_host, account.imap_port)
        else:
            conn = imaplib.IMAP4(account.imap_host, account.imap_port)

        if access_token:
            auth_string = f"user={account.username}\x01auth=Bearer {access_token}\x01\x01"
            conn.authenticate("XOAUTH2", lambda _: auth_string.encode())
        else:
            conn.login(account.username, password or "")
        conn.select("INBOX")

        # UID SEARCH/FETCH (não SEARCH/FETCH por número de sequência): o número de
        # sequência muda a cada alteração da caixa (mensagem apagada, nova mensagem
        # chegando), o que quebraria a deduplicação por "uid" em sync_account —
        # mensagens já sincronizadas voltariam a aparecer como novas, ou mensagens
        # novas seriam puladas por coincidir com um número já visto antes.
        # `None` no lugar do charset é o padrão do próprio imaplib (mesmo formato de
        # search()); a stub de tipos não modela esse argumento como opcional.
        status, data = conn.uid("search", None, "ALL")  # type: ignore[arg-type]
        if status != "OK":
            conn.logout()
            return [], "IMAP search falhou"

        uids = data[0].split()
        # Busca os mais recentes
        uids = uids[-max_messages:]

        messages = []
        for uid_bytes in reversed(uids):
            uid = uid_bytes.decode()
            status, msg_data = conn.uid("fetch", uid_bytes, "(RFC822)")
            if status != "OK" or not msg_data or not msg_data[0]:
                continue
            raw_email = msg_data[0][1]
            if not isinstance(raw_email, bytes):
                continue
            parsed = email.message_from_bytes(raw_email)

            from_raw = parsed.get("From", "")
            from_name_raw, from_addr = parseaddr(from_raw)
            from_name = _decode_header(from_name_raw) or None

            subject = _decode_header(parsed.get("Subject"))
            to_addr = parsed.get("To")
            body_text, body_html = _extract_body(parsed)

            received_at = None
            date_str = parsed.get("Date")
            if date_str:
                try:
                    received_at = parsedate_to_datetime(date_str)
                    if received_at.tzinfo:
                        received_at = received_at.astimezone(UTC).replace(tzinfo=None)
                except Exception:
                    pass

            messages.append(
                {
                    "uid": uid,
                    "folder": "INBOX",
                    "from_addr": from_addr or from_raw,
                    "from_name": from_name,
                    "to_addr": to_addr,
                    "subject": subject or None,
                    "body_text": body_text,
                    "body_html": body_html,
                    "received_at": received_at,
                }
            )

        conn.logout()
        return messages, None

    except imaplib.IMAP4.error as exc:
        return [], f"IMAP error: {exc}"
    except Exception as exc:
        return [], str(exc)


def _pop3_fetch(
    account: EmailAccount,
    max_messages: int,
    *,
    password: str | None = None,
    access_token: str | None = None,
) -> tuple[list[dict], str | None]:
    """Executa fetch POP3 em thread síncrona, usando UIDL para deduplicação.
    OAuth2 (`access_token`) não é suportado neste protocolo nesta fase — contas
    Google sempre usam IMAP (ver upsert_oauth_account)."""
    if access_token:
        return [], "OAuth2 não é suportado via POP3"
    try:
        conn: poplib.POP3
        if account.imap_ssl:
            conn = poplib.POP3_SSL(account.imap_host, account.imap_port)
        else:
            conn = poplib.POP3(account.imap_host, account.imap_port)

        conn.user(account.username)
        conn.pass_(password or "")

        # UIDL mapeia número → uid único persistente
        uidl_resp = conn.uidl()
        # uidl_resp é lista de bytes b"num uid"
        uid_map: list[tuple[int, str]] = []
        for line in uidl_resp[1]:
            parts = line.decode(errors="replace").split()
            if len(parts) >= 2:
                uid_map.append((int(parts[0]), parts[1]))

        # Pega os mais recentes
        uid_map = uid_map[-max_messages:]

        messages = []
        for msg_num, uid in reversed(uid_map):
            try:
                resp, lines, _octets = conn.retr(msg_num)
                raw_email = b"\r\n".join(lines)
                parsed = email.message_from_bytes(raw_email)

                from_raw = parsed.get("From", "")
                from_name_raw, from_addr = parseaddr(from_raw)
                from_name = _decode_header(from_name_raw) or None

                subject = _decode_header(parsed.get("Subject"))
                to_addr = parsed.get("To")
                body_text, body_html = _extract_body(parsed)

                received_at = None
                date_str = parsed.get("Date")
                if date_str:
                    try:
                        received_at = parsedate_to_datetime(date_str)
                        if received_at.tzinfo:
                            received_at = received_at.astimezone(UTC).replace(tzinfo=None)
                    except Exception:
                        pass

                messages.append(
                    {
                        "uid": uid,
                        "folder": "INBOX",
                        "from_addr": from_addr or from_raw,
                        "from_name": from_name,
                        "to_addr": to_addr,
                        "subject": subject or None,
                        "body_text": body_text,
                        "body_html": body_html,
                        "received_at": received_at,
                    }
                )
            except Exception:
                continue

        conn.quit()
        return messages, None

    except poplib.error_proto as exc:
        return [], f"POP3 error: {exc}"
    except Exception as exc:
        return [], str(exc)


async def _send_whatsapp_alerts(
    msg: EmailMessage,
    rule: EmailAlertRule,
    account_name: str,
    evolution_config: dict | None,
) -> bool:
    if not evolution_config or not evolution_config.get("api_key"):
        logger.warning("whatsapp_not_configured", rule_id=rule.id)
        return False

    from app.integrations.evolution import send_text

    text = _format_alert(msg, account_name)
    all_ok = True
    for target in rule.whatsapp_targets:
        number: str | None = target.get("number") if isinstance(target, dict) else target.number
        if not number:
            continue
        result = await send_text(
            api_url=evolution_config["api_url"],
            api_key=evolution_config["api_key"],
            instance=evolution_config["instance"],
            to=number,
            text=text,
        )
        if result is None:
            logger.warning("whatsapp_alert_failed", rule_id=rule.id, number=number)
            all_ok = False
    return all_ok


async def test_connection(
    *,
    host: str,
    port: int,
    ssl: bool,
    username: str,
    password: str,
    protocol: str = "imap",
) -> dict:
    """Testa conexão IMAP ou POP3 sem persistir nada."""
    import asyncio

    def _test() -> dict:
        try:
            if protocol == "pop3":
                pop: poplib.POP3 = poplib.POP3_SSL(host, port) if ssl else poplib.POP3(host, port)
                pop.user(username)
                pop.pass_(password)
                pop.quit()
            else:
                imap: imaplib.IMAP4 = (
                    imaplib.IMAP4_SSL(host, port) if ssl else imaplib.IMAP4(host, port)
                )
                imap.login(username, password)
                imap.logout()
            return {"ok": True}
        except (imaplib.IMAP4.error, poplib.error_proto) as exc:
            return {"ok": False, "error": str(exc)}
        except Exception as exc:
            return {"ok": False, "error": str(exc)}

    return await asyncio.get_event_loop().run_in_executor(None, _test)


# Alias para compatibilidade retroativa
async def test_imap_connection(
    *, host: str, port: int, ssl: bool, username: str, password: str
) -> dict:
    return await test_connection(
        host=host, port=port, ssl=ssl, username=username, password=password
    )
