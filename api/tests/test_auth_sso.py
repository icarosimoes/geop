"""Testes do handoff de SSO erpsolid -> GEOP (`POST /auth/sso/exchange`)."""

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import create_erpsolid_sso_token, create_impersonation_token
from app.models import User
from tests.conftest import ERPSOLID_SSO_SHARED_SECRET, TENANT_A

URL = "/api/v1/auth/sso/exchange"


def sso_token(
    *,
    company_id: int = TENANT_A,
    email: str = "novo.usuario@erp.com.br",
    name: str = "Novo Usuário",
    secret: str = ERPSOLID_SSO_SHARED_SECRET,
    role: str | None = None,
    seconds: int = 60,
) -> str:
    return create_erpsolid_sso_token(
        company_id=company_id, email=email, name=name, secret=secret, role=role, seconds=seconds
    )


class TestSsoExchange:
    @pytest.mark.asyncio
    async def test_exchange_auto_provisions_new_user(self, client, session: AsyncSession):
        token = sso_token(email="primeiro.acesso@erp.com.br", name="Primeiro Acesso")
        r = await client.post(URL, json={"token": token})
        assert r.status_code == 200
        data = r.json()
        assert "access_token" in data
        assert "refresh_token" in data
        assert data["user"]["email"] == "primeiro.acesso@erp.com.br"
        assert data["user"]["company_id"] == TENANT_A

        record = await session.scalar(
            select(User).where(
                User.company_id == TENANT_A, User.email == "primeiro.acesso@erp.com.br"
            )
        )
        assert record is not None
        assert record.active is True
        assert record.email_verified_at is not None

    @pytest.mark.asyncio
    async def test_exchange_reuses_existing_user(self, client, session: AsyncSession):
        # a@test.com já existe no seed (id=1, TENANT_A)
        token = sso_token(email="a@test.com", name="User A")
        r = await client.post(URL, json={"token": token})
        assert r.status_code == 200
        assert r.json()["user"]["id"] == 1

    @pytest.mark.asyncio
    async def test_exchange_expired_token_returns_400(self, client):
        token = sso_token(email="expirado@erp.com.br", seconds=-1)
        r = await client.post(URL, json={"token": token})
        assert r.status_code == 400
        assert r.json()["detail"]["code"] == "invalid_sso_token"

    @pytest.mark.asyncio
    async def test_exchange_tampered_secret_returns_400(self, client):
        token = sso_token(
            email="tampered@erp.com.br", secret="secret-errado-com-pelo-menos-32-caracteres"
        )
        r = await client.post(URL, json={"token": token})
        assert r.status_code == 400
        assert r.json()["detail"]["code"] == "invalid_sso_token"

    @pytest.mark.asyncio
    async def test_exchange_wrong_token_type_returns_400(self, client):
        # Token de outro propósito (impersonation), mesmo assinado com o segredo certo
        # por acidente de configuração — não deve ser aceito pelo exchange de SSO.
        token = create_impersonation_token(
            subject=1, company_id=TENANT_A, secret=ERPSOLID_SSO_SHARED_SECRET
        )
        r = await client.post(URL, json={"token": token})
        assert r.status_code == 400
        assert r.json()["detail"]["code"] == "invalid_sso_token"

    @pytest.mark.asyncio
    async def test_exchange_unknown_company_returns_400(self, client):
        token = sso_token(company_id=999999, email="fantasma@erp.com.br")
        r = await client.post(URL, json={"token": token})
        assert r.status_code == 400
        assert r.json()["detail"]["code"] == "company_not_found"

    @pytest.mark.asyncio
    async def test_exchange_inactive_user_returns_401(self, client, session: AsyncSession):
        from app.models import Role

        role_id = await session.scalar(select(Role.id).where(Role.company_id == TENANT_A).limit(1))
        inactive = User(
            company_id=TENANT_A,
            role_id=role_id,
            name="Desativado",
            email="desativado@erp.com.br",
            password="$2b$12$LJ3m4ys3Lf5UXOAZ3dDkheNPZ8XNfMsZFHmH7.KGZv6JqRiW8gzAi",
            active=False,
        )
        session.add(inactive)
        await session.commit()

        token = sso_token(email="desativado@erp.com.br")
        r = await client.post(URL, json={"token": token})
        assert r.status_code == 401
        assert r.json()["detail"]["code"] == "inactive_user"


class TestSsoAdminPromotion:
    """Erpsolid tratado como backoffice do GEOP: quem é admin do tenant lá chega
    como admin aqui também, tanto no primeiro acesso quanto em logins seguintes."""

    @pytest.mark.asyncio
    async def test_new_user_with_admin_role_gets_admin_role_in_geop(
        self, client, session: AsyncSession
    ):
        token = sso_token(email="admin.novo@erp.com.br", name="Admin Novo", role="admin")
        r = await client.post(URL, json={"token": token})
        assert r.status_code == 200

        from app.models import Role

        record = await session.scalar(
            select(User).where(User.company_id == TENANT_A, User.email == "admin.novo@erp.com.br")
        )
        assert record is not None
        role_code = await session.scalar(select(Role.code).where(Role.id == record.role_id))
        assert role_code == "admin"

    @pytest.mark.asyncio
    async def test_new_user_without_admin_role_keeps_default_colaborador(
        self, client, session: AsyncSession
    ):
        token = sso_token(email="colaborador.novo@erp.com.br", name="Colaborador Novo")
        r = await client.post(URL, json={"token": token})
        assert r.status_code == 200

        from app.models import Role

        record = await session.scalar(
            select(User).where(
                User.company_id == TENANT_A, User.email == "colaborador.novo@erp.com.br"
            )
        )
        assert record is not None
        role_code = await session.scalar(select(Role.code).where(Role.id == record.role_id))
        assert role_code == "colaborador"

    @pytest.mark.asyncio
    async def test_existing_colaborador_is_upgraded_when_erpsolid_says_admin(
        self, client, session: AsyncSession
    ):
        from app.models import Role

        colaborador_role_id = await session.scalar(
            select(Role.id).where(Role.company_id == TENANT_A, Role.code == "colaborador")
        )
        if colaborador_role_id is None:
            role = Role(company_id=TENANT_A, code="colaborador", name="Colaborador")
            session.add(role)
            await session.flush()
            colaborador_role_id = role.id

        existing = User(
            company_id=TENANT_A,
            role_id=colaborador_role_id,
            name="Já Provisionado",
            email="ja.provisionado@erp.com.br",
            password="$2b$12$LJ3m4ys3Lf5UXOAZ3dDkheNPZ8XNfMsZFHmH7.KGZv6JqRiW8gzAi",
            active=True,
        )
        session.add(existing)
        await session.commit()

        token = sso_token(email="ja.provisionado@erp.com.br", role="admin")
        r = await client.post(URL, json={"token": token})
        assert r.status_code == 200

        await session.refresh(existing)
        role_code = await session.scalar(select(Role.code).where(Role.id == existing.role_id))
        assert role_code == "admin"

    @pytest.mark.asyncio
    async def test_existing_admin_is_not_downgraded_without_admin_claim(
        self, client, session: AsyncSession
    ):
        # a@test.com (id=1) já é admin no seed — sem claim "role", não deve mexer.
        token = sso_token(email="a@test.com")
        r = await client.post(URL, json={"token": token})
        assert r.status_code == 200
        assert r.json()["user"]["id"] == 1
