"""Central de suporte (chamados): criação, listagem pelo tenant, resposta do
admin da plataforma e isolamento cross-tenant/cross-usuário.

Ver docs/oportunidades-legado-operacao.md#6-central-de-suporte-chamados.
"""

import pytest

from app.core.security import create_platform_token
from tests.conftest import JWT_SECRET, TENANT_A, TENANT_B, auth_header

PREFIX = "/api/v1"
SUPPORT_URL = f"{PREFIX}/support"

HEADERS_A1 = auth_header(TENANT_A, 1)
HEADERS_B2 = auth_header(TENANT_B, 2)


@pytest.mark.asyncio
async def test_create_and_list_own_support_request(client):
    r = await client.post(
        f"{SUPPORT_URL}/request",
        json={
            "subject": "Não consigo exportar relatório",
            "priority": "ALTA",
            "contact_name": "User A",
            "contact_whatsapp": "11999990000",
            "message": "O botão de exportar não responde.",
        },
        headers=HEADERS_A1,
    )
    assert r.status_code == 201
    body = r.json()
    assert body["status"] == "pending"
    request_id = body["id"]

    r = await client.get(f"{SUPPORT_URL}/requests", headers=HEADERS_A1)
    assert r.status_code == 200
    items = r.json()
    mine = next((i for i in items if i["id"] == request_id), None)
    assert mine is not None
    assert mine["subject"] == "Não consigo exportar relatório"
    assert mine["priority"] == "ALTA"
    assert mine["status"] == "pending"
    assert mine["response_message"] is None


@pytest.mark.asyncio
async def test_default_priority_is_media(client):
    r = await client.post(
        f"{SUPPORT_URL}/request",
        json={
            "subject": "Dúvida sobre permissões",
            "contact_name": "User A",
            "contact_whatsapp": "11999990000",
        },
        headers=HEADERS_A1,
    )
    assert r.status_code == 201

    r = await client.get(f"{SUPPORT_URL}/requests", headers=HEADERS_A1)
    mine = next(i for i in r.json() if i["subject"] == "Dúvida sobre permissões")
    assert mine["priority"] == "MEDIA"


@pytest.mark.asyncio
async def test_cross_tenant_isolation(client):
    r = await client.post(
        f"{SUPPORT_URL}/request",
        json={
            "subject": "Chamado exclusivo do tenant A",
            "contact_name": "User A",
            "contact_whatsapp": "11999990000",
        },
        headers=HEADERS_A1,
    )
    assert r.status_code == 201

    r = await client.get(f"{SUPPORT_URL}/requests", headers=HEADERS_B2)
    assert r.status_code == 200
    assert all(i["subject"] != "Chamado exclusivo do tenant A" for i in r.json())


@pytest.mark.asyncio
async def test_cross_user_isolation_same_tenant(client, session):
    from sqlalchemy import select

    from app.models import User

    other_user = await session.scalar(select(User).where(User.email == "a2@test.com"))
    if other_user is None:
        other_user = User(
            company_id=TENANT_A,
            name="User A2",
            email="a2@test.com",
            password="$2b$12$LJ3m4ys3Lf5UXOAZ3dDkheNPZ8XNfMsZFHmH7.KGZv6JqRiW8gzAi",
            role_id=1,
            active=True,
        )
        session.add(other_user)
        await session.commit()
        await session.refresh(other_user)
    other_user_id = other_user.id

    r = await client.post(
        f"{SUPPORT_URL}/request",
        json={
            "subject": "Chamado exclusivo do usuário 1",
            "contact_name": "User A",
            "contact_whatsapp": "11999990000",
        },
        headers=HEADERS_A1,
    )
    assert r.status_code == 201

    headers_other_user = auth_header(TENANT_A, other_user_id)
    r = await client.get(f"{SUPPORT_URL}/requests", headers=headers_other_user)
    assert r.status_code == 200
    assert all(i["subject"] != "Chamado exclusivo do usuário 1" for i in r.json())


async def _get_or_create_platform_admin(session, email="admin1@test.com", name="Admin"):
    from sqlalchemy import select

    from app.models import PlatformUser

    admin = await session.scalar(select(PlatformUser).where(PlatformUser.email == email))
    if admin is None:
        admin = PlatformUser(email=email, name=name, password_hash="x", role="admin")
        session.add(admin)
        await session.flush()
    return admin


@pytest.mark.asyncio
async def test_admin_response_updates_status_and_notifies_tenant(session):
    """Testa `update_support_request_status` diretamente (sem HTTP): não há
    fixture de autenticação de plataforma no conftest ainda, então o fluxo do
    admin é coberto no nível de service, que é onde a lógica nova mora."""
    from sqlalchemy import select

    from app.domain.platform.service import update_support_request_status
    from app.models import Notification, SupportRequest

    admin = await _get_or_create_platform_admin(session)

    req = SupportRequest(
        company_id=TENANT_A,
        user_id=1,
        subject="Erro ao salvar cadastro",
        priority="ALTA",
        contact_name="User A",
        contact_whatsapp="11999990000",
        message="Dá erro 500 ao salvar.",
    )
    session.add(req)
    await session.flush()
    request_id = req.id

    updated = await update_support_request_status(
        session,
        request_id,
        status="resolved",
        actor_id=admin.id,
        actor_name=admin.name,
        response_message="Corrigido no deploy de hoje, pode tentar de novo.",
    )

    assert updated is not None
    assert updated.status == "resolved"
    assert updated.response_message == "Corrigido no deploy de hoje, pode tentar de novo."
    assert updated.responded_by == admin.id

    notif = await session.scalar(
        select(Notification).where(
            Notification.entity_type == "support_request",
            Notification.entity_id == request_id,
        )
    )
    assert notif is not None
    assert notif.user_id == 1
    assert notif.company_id == TENANT_A


@pytest.mark.asyncio
async def test_admin_response_without_message_does_not_notify(session):
    from sqlalchemy import select

    from app.domain.platform.service import update_support_request_status
    from app.models import Notification, SupportRequest

    admin = await _get_or_create_platform_admin(session)

    req = SupportRequest(
        company_id=TENANT_A,
        user_id=1,
        subject="Só mudando status, sem resposta",
        contact_name="User A",
        contact_whatsapp="11999990000",
    )
    session.add(req)
    await session.flush()
    request_id = req.id

    await update_support_request_status(
        session, request_id, status="contacted", actor_id=admin.id, actor_name=admin.name
    )

    notif = await session.scalar(
        select(Notification).where(
            Notification.entity_type == "support_request",
            Notification.entity_id == request_id,
        )
    )
    assert notif is None


@pytest.mark.asyncio
async def test_admin_response_creates_timeline_entries(session):
    """Cada resposta do admin vira uma linha de timeline (event_type=comment),
    e cada mudança de status vira outra (event_type=update) — mesmo sem
    resposta junto. Ambas atribuídas ao admin via `actor_name` (PlatformUser
    não tem linha em `users`, então `user_id` fica None — ver
    app/core/audit.py)."""
    from sqlalchemy import select

    from app.domain.platform.service import update_support_request_status
    from app.domain.timeline.service import get_timeline
    from app.models import SupportRequest

    admin = await _get_or_create_platform_admin(session, email="admin2@test.com", name="Bruna")

    req = SupportRequest(
        company_id=TENANT_A,
        user_id=1,
        subject="Timeline do chamado",
        contact_name="User A",
        contact_whatsapp="11999990000",
    )
    session.add(req)
    await session.flush()
    request_id = req.id

    await update_support_request_status(
        session,
        request_id,
        status="contacted",
        actor_id=admin.id,
        actor_name=admin.name,
        response_message="Já estamos vendo isso.",
    )
    await update_support_request_status(
        session, request_id, status="resolved", actor_id=admin.id, actor_name=admin.name
    )

    timeline = await get_timeline(session, TENANT_A, "support_request", request_id)
    assert len(timeline) == 3  # pending->contacted (update+comment) + contacted->resolved (update)

    status_events = [e for e in timeline if e["event_type"] == "update"]
    comment_events = [e for e in timeline if e["event_type"] == "comment"]
    assert len(status_events) == 2
    assert len(comment_events) == 1
    assert comment_events[0]["message"] == "Já estamos vendo isso."
    assert comment_events[0]["user"] == "Suporte · Bruna"
    assert status_events[0]["changes"] == {"status": {"from": "pending", "to": "contacted"}}
    assert status_events[1]["changes"] == {"status": {"from": "contacted", "to": "resolved"}}

    # Verificado direto no banco: user_id fica None, actor_name carrega o nome.
    from app.models import AuditEvent

    events = (
        await session.execute(
            select(AuditEvent).where(
                AuditEvent.entity_type == "support_request", AuditEvent.entity_id == request_id
            )
        )
    ).scalars().all()
    assert all(e.user_id is None and e.actor_name == "Suporte · Bruna" for e in events)


@pytest.mark.asyncio
async def test_same_status_does_not_duplicate_timeline_entry(session):
    from app.domain.platform.service import update_support_request_status
    from app.domain.timeline.service import get_timeline
    from app.models import SupportRequest

    admin = await _get_or_create_platform_admin(session)
    req = SupportRequest(
        company_id=TENANT_A,
        user_id=1,
        subject="Status repetido",
        contact_name="User A",
        contact_whatsapp="11999990000",
        status="contacted",
    )
    session.add(req)
    await session.flush()
    request_id = req.id

    await update_support_request_status(
        session, request_id, status="contacted", actor_id=admin.id, actor_name=admin.name
    )

    timeline = await get_timeline(session, TENANT_A, "support_request", request_id)
    assert timeline == []


@pytest.mark.asyncio
async def test_tenant_reads_own_ticket_timeline_via_generic_endpoint(client):
    r = await client.post(
        f"{SUPPORT_URL}/request",
        json={
            "subject": "Chamado com timeline",
            "contact_name": "User A",
            "contact_whatsapp": "11999990000",
            "message": "Mensagem inicial.",
        },
        headers=HEADERS_A1,
    )
    request_id = r.json()["id"]

    r = await client.post(
        f"{PREFIX}/timeline/support_request/{request_id}/comment",
        json={"message": "Alguma novidade?"},
        headers=HEADERS_A1,
    )
    assert r.status_code == 201

    r = await client.get(f"{PREFIX}/timeline/support_request/{request_id}", headers=HEADERS_A1)
    assert r.status_code == 200
    items = r.json()["items"]
    assert any(i["message"] == "Alguma novidade?" and i["user"] == "User A" for i in items)


@pytest.mark.asyncio
async def test_other_user_same_tenant_cannot_read_or_comment_on_ticket(client, session):
    from sqlalchemy import select

    from app.models import User

    other_user = await session.scalar(select(User).where(User.email == "a2@test.com"))
    if other_user is None:
        other_user = User(
            company_id=TENANT_A,
            name="User A2",
            email="a2@test.com",
            password="$2b$12$LJ3m4ys3Lf5UXOAZ3dDkheNPZ8XNfMsZFHmH7.KGZv6JqRiW8gzAi",
            role_id=1,
            active=True,
        )
        session.add(other_user)
        await session.commit()
        await session.refresh(other_user)
    other_user_id = other_user.id

    r = await client.post(
        f"{SUPPORT_URL}/request",
        json={
            "subject": "Chamado privado do usuário 1",
            "contact_name": "User A",
            "contact_whatsapp": "11999990000",
        },
        headers=HEADERS_A1,
    )
    request_id = r.json()["id"]

    headers_other_user = auth_header(TENANT_A, other_user_id)
    r = await client.get(
        f"{PREFIX}/timeline/support_request/{request_id}", headers=headers_other_user
    )
    assert r.status_code == 404

    r = await client.post(
        f"{PREFIX}/timeline/support_request/{request_id}/comment",
        json={"message": "Tentando ler chamado alheio"},
        headers=headers_other_user,
    )
    assert r.status_code == 404


@pytest.mark.asyncio
async def test_cross_tenant_cannot_read_ticket_timeline(client):
    r = await client.post(
        f"{SUPPORT_URL}/request",
        json={
            "subject": "Chamado privado do tenant A",
            "contact_name": "User A",
            "contact_whatsapp": "11999990000",
        },
        headers=HEADERS_A1,
    )
    request_id = r.json()["id"]

    r = await client.get(f"{PREFIX}/timeline/support_request/{request_id}", headers=HEADERS_B2)
    assert r.status_code == 404


@pytest.mark.asyncio
async def test_platform_reads_full_ticket_timeline(client, session):
    from app.domain.platform.service import update_support_request_status
    from app.models import SupportRequest

    admin = await _get_or_create_platform_admin(session, email="admin3@test.com", name="Carlos")

    req = SupportRequest(
        company_id=TENANT_A,
        user_id=1,
        subject="Chamado visto pelo painel",
        contact_name="User A",
        contact_whatsapp="11999990000",
    )
    session.add(req)
    await session.flush()
    request_id = req.id

    await update_support_request_status(
        session,
        request_id,
        status="contacted",
        actor_id=admin.id,
        actor_name=admin.name,
        response_message="Recebido, vamos verificar.",
    )
    await session.commit()

    platform_token = create_platform_token(
        subject=admin.id, role="admin", secret=JWT_SECRET, minutes=60
    )
    r = await client.get(
        f"{PREFIX}/platform/support-requests/{request_id}/timeline",
        headers={"Authorization": f"Bearer {platform_token}"},
    )
    assert r.status_code == 200
    items = r.json()
    assert any(
        i["event_type"] == "comment" and i["message"] == "Recebido, vamos verificar."
        for i in items
    )
    assert any(i["user"] == "Suporte · Carlos" for i in items)
