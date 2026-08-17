"""Testes da integração server-to-server com o Solid ERP (`/integrations/erpsolid/*`)."""

from datetime import date

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import (
    Attachment,
    Company,
    Contract,
    CostCenter,
    Employee,
    EmployeePayslip,
    Plan,
    PlatformUser,
    Supplier,
    User,
)
from tests.conftest import ERPSOLID_INTEGRATION_KEY, TENANT_A

BASE = "/api/v1/integrations/erpsolid"


def erpsolid_headers(key: str | None = ERPSOLID_INTEGRATION_KEY) -> dict[str, str]:
    headers: dict[str, str] = {}
    if key is not None:
        headers["X-Erpsolid-Key"] = key
    return headers


@pytest.fixture()
async def plan(session: AsyncSession) -> Plan:
    existing = await session.scalar(select(Plan).where(Plan.code == "professional"))
    if existing:
        return existing
    record = Plan(
        code="professional",
        name="Professional",
        price_cents=0,
        features={},
        limits={},
    )
    session.add(record)
    await session.commit()
    await session.refresh(record)
    return record


@pytest.fixture()
async def platform_user(session: AsyncSession) -> PlatformUser:
    existing = await session.scalar(select(PlatformUser).limit(1))
    if existing:
        return existing
    record = PlatformUser(
        email="ops@geop.internal",
        name="Ops",
        password_hash="$2b$12$LJ3m4ys3Lf5UXOAZ3dDkheNPZ8XNfMsZFHmH7.KGZv6JqRiW8gzAi",
        role="admin",
    )
    session.add(record)
    await session.commit()
    await session.refresh(record)
    return record


# ---------------------------------------------------------------------------
# Autenticação — X-Erpsolid-Key
# ---------------------------------------------------------------------------


class TestIntegrationAuth:
    @pytest.mark.asyncio
    async def test_missing_key_provision_returns_401(self, client):
        r = await client.post(
            f"{BASE}/provision-tenant",
            json={"name": "Hotel X", "document": "12345678000199", "email": "a@x.com"},
        )
        assert r.status_code == 401
        assert r.json()["detail"]["code"] == "invalid_integration_key"

    @pytest.mark.asyncio
    async def test_wrong_key_provision_returns_401(self, client):
        r = await client.post(
            f"{BASE}/provision-tenant",
            json={"name": "Hotel X", "document": "12345678000199", "email": "a@x.com"},
            headers=erpsolid_headers("wrong-key"),
        )
        assert r.status_code == 401

    @pytest.mark.asyncio
    async def test_missing_key_contracts_returns_401(self, client):
        r = await client.get(f"{BASE}/contracts", params={"company_id": TENANT_A})
        assert r.status_code == 401

    @pytest.mark.asyncio
    async def test_key_contracts_returns_200(self, client):
        r = await client.get(
            f"{BASE}/contracts",
            params={"company_id": TENANT_A},
            headers=erpsolid_headers(),
        )
        assert r.status_code == 200
        assert isinstance(r.json(), list)

    @pytest.mark.asyncio
    async def test_missing_key_payslips_returns_401(self, client):
        r = await client.get(f"{BASE}/employee-payslips", params={"company_id": TENANT_A})
        assert r.status_code == 401

    @pytest.mark.asyncio
    async def test_key_payslips_returns_200(self, client):
        r = await client.get(
            f"{BASE}/employee-payslips",
            params={"company_id": TENANT_A},
            headers=erpsolid_headers(),
        )
        assert r.status_code == 200
        assert isinstance(r.json(), list)


# ---------------------------------------------------------------------------
# POST /provision-tenant
# ---------------------------------------------------------------------------


class TestProvisionTenant:
    @pytest.mark.asyncio
    async def test_provision_creates_company_and_admin(
        self, client, session: AsyncSession, plan, platform_user
    ):
        r = await client.post(
            f"{BASE}/provision-tenant",
            json={
                "name": "Hotel Provisionado",
                "document": "99988877000166",
                "email": "admin@hotelprovisionado.com.br",
                "trial_days": 30,
            },
            headers=erpsolid_headers(),
        )
        assert r.status_code == 201
        company_id = r.json()["geop_company_id"]
        assert isinstance(company_id, int)

        company = await session.scalar(select(Company).where(Company.id == company_id))
        assert company is not None
        assert company.name == "Hotel Provisionado"
        assert company.document == "99988877000166"

        admin = await session.scalar(
            select(User).where(
                User.company_id == company_id,
                User.email == "admin@hotelprovisionado.com.br",
            )
        )
        assert admin is not None
        assert admin.active is True
        assert admin.role_id is not None

    @pytest.mark.asyncio
    async def test_provision_duplicate_document_returns_409(
        self, client, session: AsyncSession, plan, platform_user
    ):
        body = {
            "name": "Hotel Duplicado",
            "document": "11122233000144",
            "email": "a@dup.com",
        }
        r1 = await client.post(f"{BASE}/provision-tenant", json=body, headers=erpsolid_headers())
        assert r1.status_code == 201

        r2 = await client.post(f"{BASE}/provision-tenant", json=body, headers=erpsolid_headers())
        assert r2.status_code == 409
        assert r2.json()["detail"]["code"] == "company_already_exists"


# ---------------------------------------------------------------------------
# GET /contracts
# ---------------------------------------------------------------------------


@pytest.fixture()
async def contract_with_relations(session: AsyncSession) -> Contract:
    supplier = Supplier(company_id=TENANT_A, name="Fornecedor Teste", document="12345678000100")
    session.add(supplier)
    cost_center = CostCenter(company_id=TENANT_A, name="Manutenção", code="CC-01")
    session.add(cost_center)
    await session.flush()

    contract = Contract(
        company_id=TENANT_A,
        title="Contrato de Limpeza",
        contract_type="servico",
        supplier_id=supplier.id,
        cost_center_id=cost_center.id,
        status="ativo",
        monthly_value="1500.00",
        currency="BRL",
    )
    session.add(contract)
    await session.commit()
    await session.refresh(contract)
    return contract


class TestListContracts:
    @pytest.mark.asyncio
    async def test_list_contracts_includes_supplier_and_cost_center(
        self, client, contract_with_relations
    ):
        r = await client.get(
            f"{BASE}/contracts",
            params={"company_id": TENANT_A},
            headers=erpsolid_headers(),
        )
        assert r.status_code == 200
        items = r.json()
        item = next(i for i in items if i["id"] == contract_with_relations.id)
        assert item["title"] == "Contrato de Limpeza"
        assert item["supplier"]["name"] == "Fornecedor Teste"
        assert item["cost_center"]["code"] == "CC-01"

    @pytest.mark.asyncio
    async def test_list_contracts_scoped_by_company(self, client, contract_with_relations):
        r = await client.get(
            f"{BASE}/contracts",
            params={"company_id": 999999},
            headers=erpsolid_headers(),
        )
        assert r.status_code == 200
        assert r.json() == []


# ---------------------------------------------------------------------------
# GET /employee-payslips
# ---------------------------------------------------------------------------


@pytest.fixture()
async def payslip_with_amounts(session: AsyncSession) -> EmployeePayslip:
    employee = await session.scalar(
        select(Employee).where(Employee.company_id == TENANT_A, Employee.id == 1)
    )
    attachment = Attachment(
        company_id=TENANT_A,
        entity_type="employee_payslip",
        entity_id=0,
        filename="holerite.pdf",
        content_type="application/pdf",
        size_bytes=10,
        storage_key="test/holerite-erpsolid.pdf",
        uploaded_by_user_id=employee.user_id,
    )
    session.add(attachment)
    await session.flush()

    payslip = EmployeePayslip(
        company_id=TENANT_A,
        employee_id=employee.id,
        reference_month=date(2026, 7, 1),
        attachment_id=attachment.id,
        gross_amount="5000.00",
        net_amount="4200.00",
        inss_amount="500.00",
        irrf_amount="300.00",
        fgts_amount="400.00",
    )
    session.add(payslip)
    await session.commit()
    await session.refresh(payslip)
    return payslip


class TestListEmployeePayslips:
    @pytest.mark.asyncio
    async def test_list_payslips_includes_amounts_and_employee(self, client, payslip_with_amounts):
        r = await client.get(
            f"{BASE}/employee-payslips",
            params={"company_id": TENANT_A},
            headers=erpsolid_headers(),
        )
        assert r.status_code == 200
        items = r.json()
        item = next(i for i in items if i["id"] == payslip_with_amounts.id)
        assert item["gross_amount"] == "5000.00"
        assert item["net_amount"] == "4200.00"
        assert item["employee"]["id"] == payslip_with_amounts.employee_id
