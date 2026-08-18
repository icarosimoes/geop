from datetime import date, datetime
from decimal import Decimal

from pydantic import BaseModel, Field

# ---------------------------------------------------------------------------
# provision-tenant
# ---------------------------------------------------------------------------


class ProvisionTenantRequest(BaseModel):
    name: str = Field(..., min_length=1, max_length=160)
    document: str | None = Field(None, max_length=20)
    email: str = Field(..., max_length=255)
    trial_days: int = 365


class ProvisionTenantResponse(BaseModel):
    geop_company_id: int


# ---------------------------------------------------------------------------
# contracts
# ---------------------------------------------------------------------------


class ErpsolidSupplierOut(BaseModel):
    id: int
    name: str
    document: str | None


class ErpsolidCostCenterOut(BaseModel):
    id: int
    name: str
    code: str | None


class ErpsolidContractOut(BaseModel):
    id: int
    number: str | None
    title: str
    contract_type: str
    status: str
    description: str | None
    total_value: Decimal | None
    monthly_value: Decimal | None
    currency: str
    payment_frequency: str | None
    payment_day: int | None
    start_date: date | None
    end_date: date | None
    budget_category: str | None
    supplier: ErpsolidSupplierOut | None
    cost_center: ErpsolidCostCenterOut | None
    created_at: datetime
    updated_at: datetime


# ---------------------------------------------------------------------------
# employee-payslips
# ---------------------------------------------------------------------------


class ErpsolidEmployeeOut(BaseModel):
    id: int
    name: str
    cpf: str | None
    registration_number: str | None


class ErpsolidEmployeePayslipOut(BaseModel):
    id: int
    reference_month: date
    gross_amount: Decimal | None
    net_amount: Decimal | None
    inss_amount: Decimal | None
    irrf_amount: Decimal | None
    fgts_amount: Decimal | None
    employee: ErpsolidEmployeeOut
    created_at: datetime


# ---------------------------------------------------------------------------
# push de cadastros erpsolid -> GEOP (erpsolid manda: espelho read-only aqui,
# nunca editado na tela do GEOP — ver `docs/planos/geop-integracao.md`)
# ---------------------------------------------------------------------------


class ErpsolidSupplierPush(BaseModel):
    external_id: str
    name: str
    document: str | None = None
    document_type: str | None = None
    category: str | None = None
    email: str | None = None
    phone: str | None = None
    address_street: str | None = None
    address_number: str | None = None
    address_complement: str | None = None
    address_neighborhood: str | None = None
    address_city: str | None = None
    address_state: str | None = None
    address_zip: str | None = None
    active: bool = True
    notes: str | None = None


class ErpsolidCostCenterPush(BaseModel):
    external_id: str
    name: str
    code: str | None = None
    active: bool = True


class ErpsolidEmployeePush(BaseModel):
    external_id: str
    name: str
    cpf: str | None = None
    rg: str | None = None
    birth_date: date | None = None
    phone: str | None = None
    email: str | None = None
    job_title: str | None = None
    hire_date: date | None = None
    termination_date: date | None = None
    status: str = "active"  # active | inactive | terminated


class RegistriesPushResponse(BaseModel):
    upserted: int
