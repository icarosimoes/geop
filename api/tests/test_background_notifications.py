"""Testes para o fluxo de notificações em background."""

import asyncio
from unittest.mock import AsyncMock, patch

import pytest

from app.integrations.notifications import (
    PendingDelivery,
    _EmailTask,
    _WhatsAppTask,
    deliver_notifications,
    prepare_notifications,
)
from tests.conftest import TENANT_A, auth_header


@pytest.mark.asyncio
async def test_prepare_notifications_returns_none_without_recipients(session):
    result = await prepare_notifications(
        session,
        company_id=TENANT_A,
        actor_name="User A",
        actor_email="a@test.com",
        event="create",
        title="Teste",
        module="Testes",
    )
    assert result is None


@pytest.mark.asyncio
async def test_deliver_notifications_sends_emails():
    pending = PendingDelivery(
        emails=[
            _EmailTask(
                notification_id=None,
                params={
                    "api_key": "fake-key",
                    "from_address": "test@test.com",
                    "from_name": "Test",
                    "to_email": "dest@test.com",
                    "to_name": "Dest",
                    "subject": "Test",
                    "html": "<p>test</p>",
                    "reply_to": "reply@test.com",
                },
            )
        ],
        whatsapp=[],
        brevo_config={},
        evolution_config={},
    )
    with patch(
        "app.integrations.notifications.send_email",
        new_callable=AsyncMock,
        return_value={"messageId": "123"},
    ) as mock_send:
        await deliver_notifications(pending)
        mock_send.assert_called_once()


@pytest.mark.asyncio
async def test_deliver_notifications_sends_whatsapp():
    pending = PendingDelivery(
        emails=[],
        whatsapp=[_WhatsAppTask(phone="5511999999999", text="Olá")],
        brevo_config={},
        evolution_config={
            "api_key": "fake",
            "api_url": "http://fake",
            "instance": "test",
        },
    )
    with patch(
        "app.integrations.evolution.send_text",
        new_callable=AsyncMock,
        return_value={"status": "ok"},
    ) as mock_send:
        await deliver_notifications(pending)
        mock_send.assert_called_once()


@pytest.mark.asyncio
async def test_deliver_notifications_handles_email_failure():
    pending = PendingDelivery(
        emails=[
            _EmailTask(
                notification_id=None,
                params={
                    "api_key": "k",
                    "from_address": "a@b.com",
                    "from_name": "T",
                    "to_email": "c@d.com",
                    "to_name": "D",
                    "subject": "S",
                    "html": "<p></p>",
                    "reply_to": None,
                },
            )
        ],
        whatsapp=[],
        brevo_config={},
        evolution_config={},
    )
    with patch(
        "app.integrations.notifications.send_email",
        new_callable=AsyncMock,
        side_effect=Exception("Brevo down"),
    ):
        await deliver_notifications(pending)


@pytest.mark.asyncio
async def test_prepare_notifications_falls_back_to_platform_brevo(session):
    """Sem Brevo configurado no tenant, usa a config global da plataforma."""
    from app.models import PlatformSetting, User

    session.add(
        User(
            id=101,
            company_id=TENANT_A,
            name="Recipient",
            email="recipient@test.com",
            password="x",
            role_id=1,
            active=True,
        )
    )
    session.add(
        PlatformSetting(
            key="email",
            value={
                "brevo_api_key": "platform-level-key",
                "email_from_address": "plataforma@registro.app",
                "email_from_name": "Plataforma Registro",
            },
        )
    )
    await session.commit()

    result = await prepare_notifications(
        session,
        company_id=TENANT_A,
        actor_name="User A",
        actor_email="a@test.com",
        event="create",
        title="Teste",
        module="Testes",
        owner_user_id=101,
    )

    assert result is not None
    assert len(result.emails) == 1
    params = result.emails[0].params
    assert params["api_key"] == "platform-level-key"
    assert params["from_address"] == "plataforma@registro.app"
    assert params["from_name"] == "Plataforma Registro"


@pytest.mark.asyncio
async def test_notify_record_event_fires_background_task(client):
    """POST que cria registro retorna imediatamente; entrega é async."""
    with patch(
        "app.integrations.notifications.deliver_notifications",
        new_callable=AsyncMock,
    ):
        r = await client.post(
            "/api/v1/bulletin",
            headers=auth_header(TENANT_A),
            json={"title": "Aviso bg test", "content": "Conteúdo"},
        )
        assert r.status_code == 201
        await asyncio.sleep(0.1)
