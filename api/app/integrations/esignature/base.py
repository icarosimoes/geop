"""Interface de provedor de assinatura eletrônica ICP-Brasil (certificado
digital, incluindo certificado em nuvem — Certisign, Soluti, Serasa, Safeweb,
Valid, BRy). O GEOP não se credencia diretamente junto às Autoridades
Certificadoras; delega pra um provedor já credenciado (hoje: Clicksign, ver
`clicksign.py`) que expõe isso como uma API REST única. Essa interface isola
o resto do sistema do formato específico de cada provedor — plugar outro
(D4Sign, BRy Signer, ...) no futuro é só uma nova implementação aqui."""

from dataclasses import dataclass
from typing import Any, Protocol


@dataclass
class EnvelopeResult:
    """Resultado de criar um envelope de assinatura pro provedor."""

    external_id: str
    sign_url: str


@dataclass
class SignatureEvent:
    """Evento normalizado a partir do payload de webhook do provedor."""

    external_id: str
    status: str  # "signed" | "refused" | "pending" | "canceled" (normalizado)
    certificate_info: dict[str, Any] | None = None
    signed_pdf_url: str | None = None


class ESignatureProvider(Protocol):
    """Cada função abaixo recebe `api_key` explicitamente (sem estado de
    cliente), mesmo padrão de `app/integrations/brevo.py` — a credencial vem
    do `CompanySetting` do tenant a cada chamada, nunca fica em memória entre
    requests."""

    async def create_envelope(
        self,
        *,
        api_key: str,
        pdf_bytes: bytes,
        filename: str,
        signer_name: str,
        signer_email: str,
        signer_document: str | None,
        callback_url: str,
    ) -> EnvelopeResult: ...

    def parse_webhook(self, payload: dict[str, Any]) -> SignatureEvent: ...

    async def download_signed_document(self, *, api_key: str, external_id: str) -> bytes: ...
