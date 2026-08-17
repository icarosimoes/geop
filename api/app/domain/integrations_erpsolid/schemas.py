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
