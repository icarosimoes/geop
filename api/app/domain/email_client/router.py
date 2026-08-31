"""Router do cliente de e-mail e alertas WhatsApp."""

from typing import Annotated

import jwt
import structlog
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import RedirectResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.audit import record_event
from app.core.config import Settings, get_settings
from app.core.dependencies import require_session
from app.core.permissions import require_permission
from app.core.rls import set_tenant_context
from app.core.security import create_email_oauth_state_token, decode_email_oauth_state_token
from app.domain.auth.repository import AuthenticatedUser
from app.domain.email_client import schemas, service
from app.domain.settings.router import get_company_setting
from app.integrations import google_oauth
from app.integrations.google_oauth import GoogleOAuthError

logger = structlog.get_logger()

router = APIRouter(prefix="/email-client", tags=["email-client"])


# ── Contas ──


@router.get("/accounts", response_model=list[schemas.EmailAccountRead])
async def list_accounts(
    user: Annotated[AuthenticatedUser, require_permission("settings.view")],
    session: Annotated[AsyncSession, Depends(require_session)],
) -> list[schemas.EmailAccountRead]:
    accounts = await service.list_accounts(session, company_id=user.company_id)
    return [schemas.EmailAccountRead.model_validate(a) for a in accounts]


@router.post("/accounts", response_model=schemas.EmailAccountRead, status_code=201)
async def create_account(
    body: schemas.EmailAccountCreate,
    user: Annotated[AuthenticatedUser, require_permission("settings.edit")],
    session: Annotated[AsyncSession, Depends(require_session)],
) -> schemas.EmailAccountRead:
    account = await service.create_account(session, company_id=user.company_id, data=body)
    await record_event(
        session,
        company_id=user.company_id,
        user_id=user.id,
        event_type="create",
        entity_type="email_account",
        entity_id=account.id,
    )
    await session.commit()
    return schemas.EmailAccountRead.model_validate(account)


@router.patch("/accounts/{account_id}", response_model=schemas.EmailAccountRead)
async def update_account(
    account_id: int,
    body: schemas.EmailAccountUpdate,
    user: Annotated[AuthenticatedUser, require_permission("settings.edit")],
    session: Annotated[AsyncSession, Depends(require_session)],
) -> schemas.EmailAccountRead:
    account = await service.get_account(session, company_id=user.company_id, account_id=account_id)
    if not account:
        raise HTTPException(status_code=404, detail={"code": "not_found"})
    account = await service.update_account(session, account=account, data=body)
    await record_event(
        session,
        company_id=user.company_id,
        user_id=user.id,
        event_type="update",
        entity_type="email_account",
        entity_id=account.id,
        diff={"updated": True},
    )
    await session.commit()
    return schemas.EmailAccountRead.model_validate(account)


@router.delete("/accounts/{account_id}", status_code=204)
async def delete_account(
    account_id: int,
    user: Annotated[AuthenticatedUser, require_permission("settings.edit")],
    session: Annotated[AsyncSession, Depends(require_session)],
) -> None:
    account = await service.get_account(session, company_id=user.company_id, account_id=account_id)
    if not account:
        raise HTTPException(status_code=404, detail={"code": "not_found"})
    await service.delete_account(session, account=account)
    await session.commit()


@router.post("/accounts/{account_id}/test-connection")
async def test_account_connection(
    account_id: int,
    user: Annotated[AuthenticatedUser, require_permission("settings.view")],
    session: Annotated[AsyncSession, Depends(require_session)],
) -> dict:
    account = await service.get_account(session, company_id=user.company_id, account_id=account_id)
    if not account:
        raise HTTPException(status_code=404, detail={"code": "not_found"})
    if account.auth_type == "oauth":
        # Testar conexão de uma conta OAuth é só garantir que o token continua
        # válido/renovável — a sincronização de verdade já faz esse teste na prática.
        try:
            await service._ensure_google_token_fresh(session, account)
            await session.commit()
            return {"ok": True}
        except Exception as exc:
            return {"ok": False, "error": str(exc)}
    password = service._decrypt(account.password_enc or "")
    result = await service.test_connection(
        host=account.imap_host,
        port=account.imap_port,
        ssl=account.imap_ssl,
        username=account.username,
        password=password,
        protocol=getattr(account, "protocol", "imap") or "imap",
    )
    return result


# ── OAuth2 (Google) ──


@router.post("/oauth/start", response_model=schemas.OAuthStartResponse)
async def oauth_start(
    body: schemas.OAuthStartRequest,
    user: Annotated[AuthenticatedUser, require_permission("settings.edit")],
    settings: Annotated[Settings, Depends(get_settings)],
) -> schemas.OAuthStartResponse:
    if not settings.google_oauth_client_id or not settings.google_oauth_redirect_uri:
        raise HTTPException(status_code=400, detail={"code": "oauth_not_configured"})

    state = create_email_oauth_state_token(
        company_id=user.company_id,
        user_id=user.id,
        account_name=body.name,
        secret=settings.jwt_secret,
    )
    authorize_url = google_oauth.build_authorize_url(
        client_id=settings.google_oauth_client_id,
        redirect_uri=settings.google_oauth_redirect_uri,
        state=state,
    )
    return schemas.OAuthStartResponse(authorize_url=authorize_url)


@router.get("/oauth/callback", include_in_schema=False)
async def oauth_callback(
    session: Annotated[AsyncSession, Depends(require_session)],
    settings: Annotated[Settings, Depends(get_settings)],
    code: str | None = None,
    state: str | None = None,
    error: str | None = None,
) -> RedirectResponse:
    """Callback do consentimento do Google. Endpoint público (chega direto do
    redirect do browser, sem cookie de sessão) — autenticado só pelo `state`
    assinado, mesmo padrão de /auth/sso/exchange."""
    web_url = settings.registro_web_url

    if error:
        return RedirectResponse(f"{web_url}/email?oauth=error&reason=denied")
    if not code or not state:
        return RedirectResponse(f"{web_url}/email?oauth=error&reason=invalid_request")

    try:
        claims = decode_email_oauth_state_token(state, settings.jwt_secret)
    except jwt.InvalidTokenError:
        return RedirectResponse(f"{web_url}/email?oauth=error&reason=invalid_state")

    # Endpoint público: chega direto do redirect do Google, sem passar por
    # current_user (que normalmente seta isso a partir do JWT de sessão) — sem
    # isso, o RLS bloquearia silenciosamente o select/insert do EmailAccount.
    await set_tenant_context(session, int(claims["company_id"]))

    try:
        tokens = await google_oauth.exchange_code(
            code=code,
            client_id=settings.google_oauth_client_id,
            client_secret=settings.google_oauth_client_secret,
            redirect_uri=settings.google_oauth_redirect_uri,
        )
        userinfo = await google_oauth.fetch_userinfo(tokens["access_token"])
        google_email = userinfo["email"]
    except (GoogleOAuthError, KeyError) as exc:
        logger.error("email_oauth_callback_error", error=str(exc))
        return RedirectResponse(f"{web_url}/email?oauth=error&reason=exchange_failed")

    try:
        account, created = await service.upsert_oauth_account(
            session,
            company_id=claims["company_id"],
            google_email=google_email,
            account_name=claims["account_name"],
            tokens=tokens,
        )
    except ValueError as exc:
        logger.error("email_oauth_callback_error", error=str(exc))
        return RedirectResponse(f"{web_url}/email?oauth=error&reason=no_refresh_token")

    await record_event(
        session,
        company_id=claims["company_id"],
        user_id=claims["user_id"],
        event_type="create" if created else "update",
        entity_type="email_account",
        entity_id=account.id,
    )
    await session.commit()
    return RedirectResponse(f"{web_url}/email?oauth=connected")


# ── Mensagens ──


@router.get("/messages", response_model=schemas.MessagePage)
async def list_messages(
    user: Annotated[AuthenticatedUser, require_permission("settings.view")],
    session: Annotated[AsyncSession, Depends(require_session)],
    account_id: int | None = None,
    page: int = 1,
    page_size: int = 50,
    only_unread: bool = False,
) -> schemas.MessagePage:
    items, total = await service.list_messages(
        session,
        company_id=user.company_id,
        account_id=account_id,
        page=page,
        page_size=page_size,
        only_unread=only_unread,
    )
    return schemas.MessagePage(
        items=[schemas.EmailMessageList.model_validate(m) for m in items],
        total=total,
        page=page,
        page_size=page_size,
    )


@router.get("/messages/{message_id}", response_model=schemas.EmailMessageRead)
async def get_message(
    message_id: int,
    user: Annotated[AuthenticatedUser, require_permission("settings.view")],
    session: Annotated[AsyncSession, Depends(require_session)],
) -> schemas.EmailMessageRead:
    msg = await service.get_message(session, company_id=user.company_id, message_id=message_id)
    if not msg:
        raise HTTPException(status_code=404, detail={"code": "not_found"})
    # Marca como lido automaticamente ao abrir
    await service.mark_read(session, message=msg, is_read=True)
    await session.commit()
    return schemas.EmailMessageRead.model_validate(msg)


@router.patch("/messages/{message_id}/read")
async def mark_message_read(
    message_id: int,
    user: Annotated[AuthenticatedUser, require_permission("settings.view")],
    session: Annotated[AsyncSession, Depends(require_session)],
    is_read: bool = True,
) -> dict:
    msg = await service.get_message(session, company_id=user.company_id, message_id=message_id)
    if not msg:
        raise HTTPException(status_code=404, detail={"code": "not_found"})
    await service.mark_read(session, message=msg, is_read=is_read)
    await session.commit()
    return {"ok": True}


# ── Regras de alerta ──


@router.get("/alert-rules", response_model=list[schemas.EmailAlertRuleRead])
async def list_alert_rules(
    user: Annotated[AuthenticatedUser, require_permission("settings.view")],
    session: Annotated[AsyncSession, Depends(require_session)],
) -> list[schemas.EmailAlertRuleRead]:
    rules = await service.list_alert_rules(session, company_id=user.company_id)
    return [schemas.EmailAlertRuleRead.model_validate(r) for r in rules]


@router.post("/alert-rules", response_model=schemas.EmailAlertRuleRead, status_code=201)
async def create_alert_rule(
    body: schemas.EmailAlertRuleCreate,
    user: Annotated[AuthenticatedUser, require_permission("settings.edit")],
    session: Annotated[AsyncSession, Depends(require_session)],
) -> schemas.EmailAlertRuleRead:
    rule = await service.create_alert_rule(session, company_id=user.company_id, data=body)
    await record_event(
        session,
        company_id=user.company_id,
        user_id=user.id,
        event_type="create",
        entity_type="email_alert_rule",
        entity_id=rule.id,
    )
    await session.commit()
    return schemas.EmailAlertRuleRead.model_validate(rule)


@router.patch("/alert-rules/{rule_id}", response_model=schemas.EmailAlertRuleRead)
async def update_alert_rule(
    rule_id: int,
    body: schemas.EmailAlertRuleUpdate,
    user: Annotated[AuthenticatedUser, require_permission("settings.edit")],
    session: Annotated[AsyncSession, Depends(require_session)],
) -> schemas.EmailAlertRuleRead:
    rule = await service.get_alert_rule(session, company_id=user.company_id, rule_id=rule_id)
    if not rule:
        raise HTTPException(status_code=404, detail={"code": "not_found"})
    rule = await service.update_alert_rule(session, rule=rule, data=body)
    await session.commit()
    return schemas.EmailAlertRuleRead.model_validate(rule)


@router.delete("/alert-rules/{rule_id}", status_code=204)
async def delete_alert_rule(
    rule_id: int,
    user: Annotated[AuthenticatedUser, require_permission("settings.edit")],
    session: Annotated[AsyncSession, Depends(require_session)],
) -> None:
    rule = await service.get_alert_rule(session, company_id=user.company_id, rule_id=rule_id)
    if not rule:
        raise HTTPException(status_code=404, detail={"code": "not_found"})
    await service.delete_alert_rule(session, rule=rule)
    await session.commit()


# ── Sincronização manual ──


@router.post("/sync", response_model=list[schemas.SyncResult])
async def sync_all(
    user: Annotated[AuthenticatedUser, require_permission("settings.edit")],
    session: Annotated[AsyncSession, Depends(require_session)],
) -> list[schemas.SyncResult]:
    """Dispara sincronização IMAP manual para todas as contas ativas."""
    accounts = await service.list_accounts(session, company_id=user.company_id)
    active_accounts = [a for a in accounts if a.active]
    if not active_accounts:
        return []

    rules = await service.list_alert_rules(session, company_id=user.company_id)
    evolution_cfg = await get_company_setting(session, user.company_id, "evolution")

    results = []
    for account in active_accounts:
        result = await service.sync_account(
            session,
            account=account,
            rules=rules,
            evolution_config=evolution_cfg or None,
        )
        results.append(result)

    await session.commit()
    return results


@router.post("/sync/{account_id}", response_model=schemas.SyncResult)
async def sync_one(
    account_id: int,
    user: Annotated[AuthenticatedUser, require_permission("settings.edit")],
    session: Annotated[AsyncSession, Depends(require_session)],
) -> schemas.SyncResult:
    """Sincroniza uma conta específica."""
    account = await service.get_account(session, company_id=user.company_id, account_id=account_id)
    if not account:
        raise HTTPException(status_code=404, detail={"code": "not_found"})

    rules = await service.list_alert_rules(session, company_id=user.company_id)
    evolution_cfg = await get_company_setting(session, user.company_id, "evolution")

    result = await service.sync_account(
        session,
        account=account,
        rules=rules,
        evolution_config=evolution_cfg or None,
    )
    await session.commit()
    return result
