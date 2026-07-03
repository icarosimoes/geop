"""Endpoint que recebe as batidas enviadas pelo relógio (push).

O formato exato do payload de push do Control iD (ADMS/iDSecure) ainda não
foi confirmado contra um equipamento real. O parsing fica isolado em
`_parse_events`/`_parse_timestamp` para ser fácil de ajustar assim que
tivermos uma captura real — o contrato aceito hoje é deliberadamente
tolerante (aceita nomes de campo alternativos e timestamp em ISO8601 ou
epoch), e o `raw_payload` de cada evento é sempre persistido para permitir
reprocessar depois que o parser for corrigido.
"""

from datetime import datetime
from typing import Annotated, Any

import structlog
from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import require_session
from app.core.rate_limit import limiter
from app.domain.timeclock.service import get_device_by_token, ingest_punch

logger = structlog.get_logger()

router = APIRouter(prefix="/integrations/control-id", tags=["timeclock-webhook"])


def _parse_timestamp(value: Any) -> datetime | None:
    if value is None:
        return None
    if isinstance(value, (int, float)):
        return datetime.fromtimestamp(value)
    if isinstance(value, str):
        try:
            return datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError:
            return None
    return None


def _parse_events(body: Any) -> list[dict]:
    if isinstance(body, dict) and "events" in body:
        raw_events = body["events"]
    elif isinstance(body, list):
        raw_events = body
    else:
        raw_events = [body]

    events = []
    for raw in raw_events:
        if not isinstance(raw, dict):
            continue
        external_id = str(
            raw.get("external_id") or raw.get("user_id") or raw.get("pis") or ""
        ).strip()
        punched_at = _parse_timestamp(
            raw.get("punched_at") or raw.get("time") or raw.get("timestamp")
        )
        if not external_id or punched_at is None:
            continue
        punch_type_raw = str(raw.get("type") or raw.get("direction") or raw.get("inout") or "")
        punch_type = None
        if punch_type_raw.lower() in ("in", "entrada", "0", "1"):
            punch_type = "in"
        elif punch_type_raw.lower() in ("out", "saida", "saída", "2", "3"):
            punch_type = "out"
        events.append(
            {
                "external_id": external_id,
                "punched_at": punched_at,
                "punch_type": punch_type,
                "external_event_id": str(raw.get("event_id") or raw.get("id") or "") or None,
                "raw_payload": raw,
            }
        )
    return events


@router.post("/{webhook_token}/punches")
@limiter.limit("120/minute")
async def control_id_webhook(
    webhook_token: str,
    request: Request,
    session: Annotated[AsyncSession, Depends(require_session)],
) -> dict:
    device = await get_device_by_token(session, webhook_token)
    if device is None:
        raise HTTPException(status_code=401, detail={"code": "invalid_webhook_token"})

    body = await request.json()
    events = _parse_events(body)
    logger.info("control_id_webhook_received", device_id=device.id, event_count=len(events))

    created = 0
    for event in events:
        await ingest_punch(
            session,
            company_id=device.company_id,
            device=device,
            external_id=event["external_id"],
            punched_at=event["punched_at"],
            punch_type=event["punch_type"],
            external_event_id=event["external_event_id"],
            raw_payload=event["raw_payload"],
        )
        created += 1

    return {"received": len(events), "processed": created}
