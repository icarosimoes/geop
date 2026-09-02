"""Implementação de `ESignatureProvider` pra Clicksign (API v3, JSON:API).

⚠️ IMPORTANTE: os nomes de endpoint/campos abaixo seguem o formato documentado
publicamente da API v3 da Clicksign no momento em que este módulo foi escrito.
Antes de ativar em produção pra um tenant real, confirme contra a documentação
atual em https://developers.clicksign.com — provedores externos mudam API sem
aviso prévio ao GEOP. Os pontos mais sensíveis a mudança de formato estão
isolados nas funções privadas `_create_envelope_payload`/`_add_signer_payload`/
`_parse_webhook_event`, então um ajuste fica restrito a este arquivo.

Fluxo: criar envelope -> subir o PDF como documento -> adicionar o cliente
como signatário exigindo autenticação por certificado ICP-Brasil (que cobre
certificado em nuvem — a Clicksign redireciona o signatário pro fluxo de
autenticação do provedor de certificado que ele escolher) -> ativar o
envelope -> devolver o link de assinatura (`sign_url`) do signatário."""

import base64
from typing import Any

import httpx
import structlog

from app.integrations.esignature.base import EnvelopeResult, SignatureEvent

logger = structlog.get_logger()

BASE_URL = "https://api.clicksign.com/api/v3"


def _headers(api_key: str) -> dict[str, str]:
    return {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/vnd.api+json",
        "Accept": "application/vnd.api+json",
    }


async def create_envelope(
    *,
    api_key: str,
    pdf_bytes: bytes,
    filename: str,
    signer_name: str,
    signer_email: str,
    signer_document: str | None,
    callback_url: str,
) -> EnvelopeResult:
    async with httpx.AsyncClient(
        timeout=30, base_url=BASE_URL, headers=_headers(api_key)
    ) as client:
        envelope = await client.post(
            "/envelopes",
            json={
                "data": {
                    "type": "envelopes",
                    "attributes": {
                        "name": filename,
                        "locale": "pt-BR",
                        "auto_close": True,
                    },
                }
            },
        )
        envelope.raise_for_status()
        envelope_id = envelope.json()["data"]["id"]

        document = await client.post(
            f"/envelopes/{envelope_id}/documents",
            json={
                "data": {
                    "type": "documents",
                    "attributes": {
                        "filename": filename,
                        "content_base64": (
                            f"data:application/pdf;base64,{base64.b64encode(pdf_bytes).decode()}"
                        ),
                    },
                }
            },
        )
        document.raise_for_status()

        signer = await client.post(
            f"/envelopes/{envelope_id}/signers",
            json={
                "data": {
                    "type": "signers",
                    "attributes": {
                        "name": signer_name,
                        "email": signer_email,
                        "has_documentation": bool(signer_document),
                        "documentation": signer_document,
                        "auths": ["icp_brasil"],
                        "communicate_events": {"document_signed": "email"},
                    },
                }
            },
        )
        signer.raise_for_status()
        signer_data = signer.json()["data"]
        signer_id = signer_data["id"]
        sign_url = signer_data.get("attributes", {}).get("sign_url", "")

        await client.patch(
            f"/envelopes/{envelope_id}",
            json={
                "data": {
                    "id": envelope_id,
                    "type": "envelopes",
                    "attributes": {"status": "running"},
                }
            },
        )

    logger.info(
        "clicksign_envelope_created",
        envelope_id=envelope_id,
        signer_id=signer_id,
    )
    return EnvelopeResult(external_id=envelope_id, sign_url=sign_url)


def parse_webhook(payload: dict[str, Any]) -> SignatureEvent:
    event = payload.get("event", {})
    event_name = event.get("name", "")
    envelope = event.get("data", {}).get("envelope", event.get("data", {}))
    envelope_id = envelope.get("id", "")

    status_map = {
        "auto_close": "signed",
        "sign": "signed",
        "refusal": "refused",
        "deadline": "expired",
    }
    status = status_map.get(event_name, "pending")

    return SignatureEvent(
        external_id=str(envelope_id),
        status=status,
        certificate_info=event.get("data", {}).get("signer", {}) or None,
        signed_pdf_url=envelope.get("download_url"),
    )


async def download_signed_document(*, api_key: str, external_id: str) -> bytes:
    async with httpx.AsyncClient(
        timeout=30, base_url=BASE_URL, headers=_headers(api_key)
    ) as client:
        r = await client.get(f"/envelopes/{external_id}/documents")
        r.raise_for_status()
        documents = r.json().get("data", [])
        download_url = ""
        if documents:
            download_url = documents[0].get("attributes", {}).get("download_url", "")
        if not download_url:
            raise ValueError("clicksign: documento assinado sem download_url")
        file_resp = await client.get(download_url)
        file_resp.raise_for_status()
        return file_resp.content
