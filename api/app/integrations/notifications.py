"""Dispara notificações por email (Brevo), WhatsApp (Evolution) e in-app."""

from __future__ import annotations

import asyncio
import dataclasses
from datetime import datetime

import structlog
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.settings.router import get_company_setting, get_module_recipients
from app.integrations.brevo import send_email
from app.models import Notification, NotificationPreference, User

logger = structlog.get_logger()

ENTITY_TO_MODULE: dict[str, str] = {
    "work_order": "work_orders",
    "meeting": "meetings",
    "shift_report": "shift_reports",
    "procedure": "procedures",
    "module_record": "modules",
}


@dataclasses.dataclass
class _EmailTask:
    notification_id: int | None
    params: dict


@dataclasses.dataclass
class _WhatsAppTask:
    phone: str
    text: str


@dataclasses.dataclass
class PendingDelivery:
    company_id: int
    emails: list[_EmailTask]
    whatsapp: list[_WhatsAppTask]
    brevo_config: dict
    evolution_config: dict


async def _resolve_users(session: AsyncSession, user_ids: list[int]) -> list[dict]:
    if not user_ids:
        return []
    rows = (
        await session.execute(
            select(User.id, User.name, User.email, User.phone).where(
                User.id.in_(user_ids), User.active.is_(True)
            )
        )
    ).all()
    return [{"id": r.id, "name": r.name, "email": r.email, "phone": r.phone} for r in rows]


async def _load_preferences(
    session: AsyncSession,
    company_id: int,
    user_ids: list[int],
    module: str,
) -> dict[int, dict[str, bool]]:
    if not user_ids or not module:
        return {}
    rows = (
        await session.scalars(
            select(NotificationPreference).where(
                NotificationPreference.company_id == company_id,
                NotificationPreference.user_id.in_(user_ids),
                NotificationPreference.module == module,
            )
        )
    ).all()
    prefs: dict[int, dict[str, bool]] = {}
    for r in rows:
        prefs[r.user_id] = {"in_app": r.in_app, "email": r.email}
    return prefs


def _build_html(action: str, title: str, module: str, actor: str, detail: str | None = None) -> str:
    detail_block = f"<p style='color:#555'>{detail}</p>" if detail else ""
    return f"""
    <div style="font-family:sans-serif;max-width:600px;margin:0 auto">
      <div style="background:#1e3a5f;padding:20px;border-radius:8px 8px 0 0">
        <h2 style="color:white;margin:0">GEOP</h2>
      </div>
      <div style="padding:20px;border:1px solid #e5e7eb;border-top:none;border-radius:0 0 8px 8px">
        <p style="color:#1e3a5f;font-weight:700;margin:0 0 8px">{action}</p>
        <h3 style="margin:0 0 12px">{title}</h3>
        <p style="color:#555;margin:0 0 4px"><strong>Módulo:</strong> {module}</p>
        <p style="color:#555;margin:0 0 4px"><strong>Por:</strong> {actor}</p>
        {detail_block}
        <hr style="border:none;border-top:1px solid #e5e7eb;margin:16px 0"/>
        <p style="font-size:12px;color:#999">
          Você recebeu este email porque é responsável ou notificado.
        </p>
      </div>
    </div>
    """


async def create_notification(
    session: AsyncSession,
    *,
    company_id: int,
    user_id: int,
    title: str,
    body: str | None = None,
    category: str = "info",
    entity_type: str | None = None,
    entity_id: int | None = None,
) -> Notification:
    record = Notification(
        company_id=company_id,
        user_id=user_id,
        title=title,
        body=body,
        category=category,
        entity_type=entity_type,
        entity_id=entity_id,
    )
    session.add(record)
    return record


async def prepare_notifications(
    session: AsyncSession,
    *,
    company_id: int,
    actor_name: str,
    actor_email: str,
    event: str,
    title: str,
    module: str,
    owner_user_id: int | None = None,
    created_by_user_id: int | None = None,
    notify_user_ids: list[int] | None = None,
    detail: str | None = None,
    entity_type: str | None = None,
    entity_id: int | None = None,
) -> PendingDelivery | None:
    """Cria registros de notificação in-app e retorna dados para entrega async."""
    action_labels = {
        "create": "Novo registro criado",
        "update": "Registro atualizado",
        "comment": "Novo comentário",
    }
    action_label = action_labels.get(event, event)

    recipient_ids: set[int] = set()
    if owner_user_id:
        recipient_ids.add(owner_user_id)
    if notify_user_ids:
        recipient_ids.update(notify_user_ids)
    if event in ("update", "comment") and created_by_user_id:
        recipient_ids.add(created_by_user_id)

    pref_module = ENTITY_TO_MODULE.get(entity_type or "", "")
    if pref_module:
        module_recipient_ids = await get_module_recipients(session, company_id, pref_module)
        recipient_ids.update(module_recipient_ids)

    recipients = await _resolve_users(session, list(recipient_ids))
    if not recipients:
        return None

    prefs = await _load_preferences(session, company_id, [r["id"] for r in recipients], pref_module)

    notification_body = f"{actor_name} · {module}"
    if detail:
        notification_body += f"\n{detail}"

    created_notifications: list[tuple[Notification, dict]] = []
    for r in recipients:
        if r["email"] == actor_email:
            continue
        user_pref = prefs.get(r["id"], {"in_app": True, "email": True})
        if user_pref["in_app"]:
            notif = await create_notification(
                session,
                company_id=company_id,
                user_id=r["id"],
                title=f"{action_label}: {title}",
                body=notification_body,
                category=event,
                entity_type=entity_type,
                entity_id=entity_id,
            )
            created_notifications.append((notif, r))
    await session.flush()

    brevo = await get_company_setting(session, company_id, "brevo")
    evolution = await get_company_setting(session, company_id, "evolution")

    api_key = brevo.get("api_key")
    from_address = brevo.get("from_address")
    from_name = brevo.get("from_name")
    if not api_key:
        from app.core.config import get_settings
        from app.domain.platform.service import get_effective_email_config

        (
            platform_api_key,
            platform_from_address,
            platform_from_name,
        ) = await get_effective_email_config(session, get_settings())
        api_key = platform_api_key
        from_address = from_address or platform_from_address
        from_name = from_name or platform_from_name

    email_tasks: list[_EmailTask] = []
    if api_key:
        from_address = from_address or "noreply@registro.app"
        from_name = from_name or "GEOP"
        html = _build_html(action_label, title, module, actor_name, detail)
        subject = f"[GEOP] {action_label}: {title}"

        for r in recipients:
            if r["email"] == actor_email:
                continue
            user_pref = prefs.get(r["id"], {"in_app": True, "email": True})
            if not user_pref["email"]:
                continue
            notif_record = next(
                (n for n, ri in created_notifications if ri["id"] == r["id"]),
                None,
            )
            email_tasks.append(
                _EmailTask(
                    notification_id=notif_record.id if notif_record else None,
                    params={
                        "api_key": api_key,
                        "from_address": from_address,
                        "from_name": from_name,
                        "to_email": r["email"],
                        "to_name": r["name"],
                        "subject": subject,
                        "html": html,
                        "reply_to": actor_email,
                    },
                )
            )

    whatsapp_tasks: list[_WhatsAppTask] = []
    evo_key = evolution.get("api_key")
    if evo_key:
        whatsapp_text = f"*{action_label}*\n{title}\n\nMódulo: {module}\nPor: {actor_name}"
        if detail:
            whatsapp_text += f"\n{detail}"
        for r in recipients:
            if r["email"] == actor_email:
                continue
            user_pref = prefs.get(r["id"], {"in_app": True, "email": True})
            if not user_pref.get("whatsapp", True):
                continue
            phone = r.get("phone")
            if not phone:
                continue
            whatsapp_tasks.append(_WhatsAppTask(phone=phone, text=whatsapp_text))

    await session.commit()

    if not email_tasks and not whatsapp_tasks:
        return None

    return PendingDelivery(
        company_id=company_id,
        emails=email_tasks,
        whatsapp=whatsapp_tasks,
        brevo_config=dict(brevo),
        evolution_config=dict(evolution),
    )


async def deliver_notifications(pending: PendingDelivery) -> None:
    """Envia emails e WhatsApp. Roda em background após a resposta HTTP."""
    from app.core.database import SessionLocal

    notification_ids_sent: list[int] = []

    if pending.emails:
        results = await asyncio.gather(
            *[send_email(**e.params) for e in pending.emails],
            return_exceptions=True,
        )
        for task, result in zip(pending.emails, results, strict=True):
            if task.notification_id and not isinstance(result, BaseException):
                notification_ids_sent.append(task.notification_id)

    if pending.whatsapp:
        evo_key = pending.evolution_config.get("api_key")
        if evo_key:
            from app.integrations.evolution import send_text

            for wt in pending.whatsapp:
                try:
                    await send_text(
                        api_url=pending.evolution_config["api_url"],
                        api_key=evo_key,
                        instance=pending.evolution_config["instance"],
                        to=wt.phone,
                        text=wt.text,
                    )
                except Exception:
                    logger.warning("whatsapp_send_failed", phone=wt.phone)

    if notification_ids_sent and SessionLocal:
        from app.core.rls import set_tenant_context

        try:
            async with SessionLocal() as session:
                # Sessão nova, aberta em background (fora do request original) —
                # sem isso, `notifications` (RLS) rejeita o SELECT/UPDATE abaixo
                # sob a role restrita (ver docs/auditoria-2026-07-03.md#c1).
                await set_tenant_context(session, pending.company_id)
                now = datetime.now()
                for nid in notification_ids_sent:
                    notif = await session.get(Notification, nid)
                    if notif:
                        notif.email_sent_at = now
                await session.commit()
        except Exception:
            logger.warning("email_sent_at_update_failed")


async def notify_record_event(
    session: AsyncSession,
    *,
    company_id: int,
    actor_name: str,
    actor_email: str,
    event: str,
    title: str,
    module: str,
    owner_user_id: int | None = None,
    created_by_user_id: int | None = None,
    notify_user_ids: list[int] | None = None,
    detail: str | None = None,
    entity_type: str | None = None,
    entity_id: int | None = None,
) -> None:
    """Wrapper: prepara notificações e dispara entrega em background."""
    pending = await prepare_notifications(
        session,
        company_id=company_id,
        actor_name=actor_name,
        actor_email=actor_email,
        event=event,
        title=title,
        module=module,
        owner_user_id=owner_user_id,
        created_by_user_id=created_by_user_id,
        notify_user_ids=notify_user_ids,
        detail=detail,
        entity_type=entity_type,
        entity_id=entity_id,
    )
    if pending:
        asyncio.create_task(deliver_notifications(pending))
