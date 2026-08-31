"""Integração OAuth2 com o Google — usada pelo email_client para autenticar
contas Gmail via IMAP (XOAUTH2) em vez de usuário+senha.
"""

from urllib.parse import urlencode

import httpx
import structlog

logger = structlog.get_logger()

AUTHORIZE_URL = "https://accounts.google.com/o/oauth2/v2/auth"
TOKEN_URL = "https://oauth2.googleapis.com/token"
USERINFO_URL = "https://www.googleapis.com/oauth2/v2/userinfo"

# https://mail.google.com/ é o scope que autoriza XOAUTH2 no IMAP (full access ao
# Gmail). "email" vem junto só pra identificar a conta autorizada via
# fetch_userinfo() — sem ele, o endpoint oauth2/v2/userinfo rejeita o access_token
# com 401 "missing required authentication credential" (token sem escopo de
# identidade não é aceito ali, mesmo sendo um token válido pro Gmail).
SCOPE = "https://mail.google.com/ email"


class GoogleOAuthError(Exception):
    """Falha na troca/renovação de token com o Google — carrega o motivo pro
    router decidir o redirect de erro apropriado."""


def build_authorize_url(*, client_id: str, redirect_uri: str, state: str) -> str:
    params = {
        "client_id": client_id,
        "redirect_uri": redirect_uri,
        "response_type": "code",
        "scope": SCOPE,
        "access_type": "offline",
        # Força o Google a sempre devolver refresh_token, mesmo se o usuário já
        # tiver autorizado este app antes (por padrão só vem no primeiro consent).
        "prompt": "consent",
        "state": state,
    }
    return f"{AUTHORIZE_URL}?{urlencode(params)}"


async def exchange_code(
    *, code: str, client_id: str, client_secret: str, redirect_uri: str
) -> dict:
    """Troca o authorization code pelo primeiro par access_token/refresh_token."""
    payload = {
        "code": code,
        "client_id": client_id,
        "client_secret": client_secret,
        "redirect_uri": redirect_uri,
        "grant_type": "authorization_code",
    }
    return await _post_token(payload)


async def refresh_access_token(*, refresh_token: str, client_id: str, client_secret: str) -> dict:
    """Renova o access_token expirado. O Google não reemite refresh_token aqui —
    o chamador deve manter o refresh_token original."""
    payload = {
        "refresh_token": refresh_token,
        "client_id": client_id,
        "client_secret": client_secret,
        "grant_type": "refresh_token",
    }
    return await _post_token(payload)


async def _post_token(payload: dict) -> dict:
    try:
        async with httpx.AsyncClient(timeout=15) as client:
            resp = await client.post(TOKEN_URL, data=payload)
            resp.raise_for_status()
            data: dict = resp.json()
            return data
    except httpx.HTTPStatusError as exc:
        logger.error(
            "google_oauth_token_error",
            status=exc.response.status_code,
            body=exc.response.text,
        )
        raise GoogleOAuthError(f"Falha ao trocar token com o Google: {exc.response.text}") from exc
    except httpx.RequestError as exc:
        logger.error("google_oauth_request_error", error=str(exc))
        raise GoogleOAuthError(f"Erro de conexão com o Google: {exc}") from exc


async def fetch_userinfo(access_token: str) -> dict:
    """Busca o e-mail da conta Google autorizada, pra identificar/gravar a
    EmailAccount correspondente."""
    try:
        async with httpx.AsyncClient(timeout=15) as client:
            resp = await client.get(
                USERINFO_URL,
                headers={"Authorization": f"Bearer {access_token}"},
            )
            resp.raise_for_status()
            data: dict = resp.json()
            return data
    except httpx.HTTPStatusError as exc:
        logger.error(
            "google_oauth_userinfo_error",
            status=exc.response.status_code,
            body=exc.response.text,
        )
        raise GoogleOAuthError("Falha ao buscar informações da conta Google") from exc
    except httpx.RequestError as exc:
        logger.error("google_oauth_request_error", error=str(exc))
        raise GoogleOAuthError(f"Erro de conexão com o Google: {exc}") from exc
