from datetime import date, datetime
from decimal import Decimal
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.models import AuditEvent


async def record_event(
    session: AsyncSession,
    *,
    company_id: int,
    user_id: int | None,
    entity_type: str,
    entity_id: int,
    event_type: str,
    diff: dict[str, Any] | None = None,
    actor_name: str | None = None,
) -> AuditEvent | None:
    """`user_id` é o caminho normal (ator é um `User` do tenant). Para atores sem
    linha em `users` (ex.: admin da plataforma, `PlatformUser`), passe
    `user_id=None` e `actor_name` com o nome pra exibição — ver
    `app/models/operations.py::AuditEvent`.

    Retorna o `AuditEvent` criado (ou `None` no no-op de diff vazio) já com
    `id`/`created_at` populados via `flush()` — sem precisar de uma query extra
    depois do commit pra reler o evento (o `app.current_company_id` do RLS é
    setado por transação; uma query após o commit da transação original cai
    fora do escopo do GUC — achado ao ligar a timeline de chamados de suporte,
    ver docs/registro-trabalho.md)."""
    if user_id is None and not actor_name:
        raise ValueError("record_event precisa de user_id ou actor_name")
    if event_type == "update" and not diff:
        return None
    event = AuditEvent(
        company_id=company_id,
        user_id=user_id,
        actor_name=actor_name,
        entity_type=entity_type,
        entity_id=entity_id,
        event_type=event_type,
        diff=_json_safe(diff) if diff is not None else None,
    )
    session.add(event)
    await session.flush()
    return event


def _json_safe(value: Any) -> Any:
    """`AuditEvent.diff` é uma coluna JSON (json.dumps puro, sem serializer
    custom no engine) — `date`/`datetime`/`Decimal` quebram a INSERT com
    `TypeError: Object of type date is not JSON serializable` assim que algum
    campo desse tipo aparece num diff (ex.: `Sale.delivered_at`). Sanitiza aqui,
    no único ponto de inserção (`record_event`), pra cobrir tanto os diffs
    montados por `compute_diff` quanto os montados à mão pelos domínios (ex.:
    `diff={"new_value": ...}` em `contracts/service.py::create_amendment`) —
    achado ao editar datas de entrega/instalação de uma `Sale`, ver
    app/domain/commercial/service.py::update_sale."""
    if isinstance(value, (date, datetime)):
        return value.isoformat()
    if isinstance(value, Decimal):
        return str(value)
    if isinstance(value, dict):
        return {k: _json_safe(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [_json_safe(v) for v in value]
    return value


def compute_diff(before: dict[str, Any], after: dict[str, Any]) -> dict[str, Any] | None:
    changes: dict[str, Any] = {}
    for key in after:
        old = before.get(key)
        new = after[key]
        if str(old) != str(new):
            changes[key] = {"from": old, "to": new}
    return changes or None
