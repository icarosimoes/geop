import os

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import text as sa_text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

from app.core.security import create_access_token
from app.models.base import Base

JWT_SECRET = "test-secret-with-at-least-32-characters-here"
ERPSOLID_INTEGRATION_KEY = "erpsolid-test-integration-key"
ERPSOLID_SSO_SHARED_SECRET = "erpsolid-test-sso-shared-secret-32-chars-min"
TENANT_A = 1
TENANT_B = 2

_TEST_DB_URL = os.environ.get("TEST_DATABASE_URL") or os.environ.get("DATABASE_URL")
USE_POSTGRES = bool(_TEST_DB_URL and "postgresql" in _TEST_DB_URL)


@pytest.fixture(scope="session")
def test_engine():
    if USE_POSTGRES:
        return create_async_engine(_TEST_DB_URL, echo=False)
    return create_async_engine(
        "sqlite+aiosqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )


@pytest.fixture(scope="session")
def test_session_factory(test_engine):
    return async_sessionmaker(test_engine, expire_on_commit=False)


@pytest.fixture(scope="session", autouse=True)
async def create_tables(test_engine):
    if USE_POSTGRES:
        return
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


@pytest.fixture(scope="session", autouse=True)
async def seed_data(test_session_factory, create_tables):
    from app.models import Company, Employee, Role, User

    async with test_session_factory() as s:
        existing = await s.get(Company, TENANT_A)
        if existing:
            return

        s.add(
            Company(
                id=TENANT_A,
                name="Hotel A",
                slug="hotel-a",
                status="active",
                timezone="America/Sao_Paulo",
            )
        )
        s.add(
            Company(
                id=TENANT_B,
                name="Hotel B",
                slug="hotel-b",
                status="active",
                timezone="America/New_York",
            )
        )
        await s.flush()

        s.add(Role(id=1, company_id=TENANT_A, code="admin", name="Admin"))
        s.add(Role(id=2, company_id=TENANT_B, code="admin", name="Admin"))
        await s.flush()

        pw = "$2b$12$LJ3m4ys3Lf5UXOAZ3dDkheNPZ8XNfMsZFHmH7.KGZv6JqRiW8gzAi"
        s.add(
            User(
                id=1,
                company_id=TENANT_A,
                name="User A",
                email="a@test.com",
                password=pw,
                role_id=1,
                active=True,
            )
        )
        s.add(
            User(
                id=2,
                company_id=TENANT_B,
                name="User B",
                email="b@test.com",
                password=pw,
                role_id=2,
                active=True,
            )
        )
        await s.flush()

        s.add(
            Employee(
                id=1,
                company_id=TENANT_A,
                name="User A",
                personal_email="a@test.com",
                user_id=1,
                status="active",
            )
        )
        s.add(
            Employee(
                id=2,
                company_id=TENANT_B,
                name="User B",
                personal_email="b@test.com",
                user_id=2,
                status="active",
            )
        )
        await s.commit()

        if USE_POSTGRES:
            async with test_session_factory() as seq_s:
                for tbl in ("companies", "roles", "users", "employees"):
                    await seq_s.execute(
                        sa_text(
                            f"SELECT setval(pg_get_serial_sequence('{tbl}', 'id'), "
                            f"COALESCE((SELECT MAX(id) FROM {tbl}), 1))"
                        )
                    )
                await seq_s.commit()


@pytest.fixture()
async def session(test_session_factory):
    async with test_session_factory() as s:
        yield s
        await s.rollback()


@pytest.fixture()
def app(test_session_factory):
    from app.core.auth import current_user
    from app.core.config import Settings, get_settings
    from app.core.dependencies import require_platform_session, require_session
    from app.core.security import decode_access_token
    from app.main import app as fastapi_app

    test_settings = Settings(
        jwt_secret=JWT_SECRET,
        database_url=_TEST_DB_URL or "sqlite+aiosqlite:///:memory:",
        erpsolid_integration_key=ERPSOLID_INTEGRATION_KEY,
        erpsolid_sso_shared_secret=ERPSOLID_SSO_SHARED_SECRET,
    )

    async def _test_session():
        async with test_session_factory() as session:
            try:
                yield session
            finally:
                # SET LOCAL is transaction-scoped; rolling back also keeps a
                # failed request from poisoning the connection pool.
                await session.rollback()

    from typing import Annotated

    from fastapi import Depends
    from fastapi.security import OAuth2PasswordBearer

    _oauth2 = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/login")

    async def _current_user_test(
        token: Annotated[str, Depends(_oauth2)],
        session: Annotated[AsyncSession, Depends(require_session)],
    ):
        from fastapi import HTTPException

        from app.domain.auth.repository import AuthenticatedUser

        try:
            claims = decode_access_token(token, test_settings.jwt_secret)
        except Exception as exc:
            raise HTTPException(status_code=401, detail={"code": "invalid_token"}) from exc

        cid = int(claims["company_id"])
        if USE_POSTGRES:
            from sqlalchemy import text

            await session.execute(
                text("SELECT set_config('app.current_company_id', :cid, true)"),
                {"cid": str(cid)},
            )

        return AuthenticatedUser(
            id=int(claims["sub"]),
            name=f"User {claims['sub']}",
            email=f"user{claims['sub']}@test.com",
            phone=None,
            password_hash="",
            company_id=cid,
            company_name="Test Hotel",
            role_id=int(claims.get("role_id", 1)),
            role_name="admin",
            permissions=claims.get("permissions", ["*"]),
        )

    fastapi_app.dependency_overrides[get_settings] = lambda: test_settings
    fastapi_app.dependency_overrides[require_session] = _test_session
    # Testes usam a mesma conexão pras rotas /platform/* — a distinção
    # registro_app/registro_platform (BYPASSRLS) só existe fora dos testes; ver
    # app/core/database.py e docs/infra/role-restrita-postgres.md.
    fastapi_app.dependency_overrides[require_platform_session] = _test_session
    fastapi_app.dependency_overrides[current_user] = _current_user_test

    yield fastapi_app

    fastapi_app.dependency_overrides.clear()


@pytest.fixture()
async def client(app):
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c


def make_token(
    company_id: int,
    user_id: int = 1,
    permissions: list[str] | None = None,
) -> str:
    return create_access_token(
        subject=user_id,
        company_id=company_id,
        role_id=1,
        permissions=permissions if permissions is not None else ["*"],
        secret=JWT_SECRET,
        minutes=60,
    )


def auth_header(company_id: int, user_id: int = 1) -> dict[str, str]:
    return {"Authorization": f"Bearer {make_token(company_id, user_id)}"}
