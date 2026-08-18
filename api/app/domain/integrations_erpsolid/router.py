import hmac
from datetime import datetime
from typing import Annotated

from fastapi import APIRouter, Depends, Header, HTTPException, Query, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings, get_settings
from app.core.dependencies import require_session
from app.core.rate_limit import limiter
from app.domain.integrations_erpsolid.schemas import (
    ErpsolidContractOut,
    ErpsolidCostCenterOut,
    ErpsolidCostCenterPush,
    ErpsolidEmployeeOut,
    ErpsolidEmployeePayslipOut,
    ErpsolidEmployeePush,
    ErpsolidSupplierOut,
    ErpsolidSupplierPush,
    ProvisionTenantRequest,
    ProvisionTenantResponse,
    RegistriesPushResponse,
)
from app.domain.integrations_erpsolid.service import (
    list_contracts_for_erpsolid,
    list_employee_payslips_for_erpsolid,
    upsert_cost_centers_from_erpsolid,
    upsert_employees_from_erpsolid,
    upsert_suppliers_from_erpsolid,
)
from app.domain.platform.service import provision_tenant_with_admin

router = APIRouter(prefix="/integrations/erpsolid", tags=["integrations-erpsolid"])


def _require_integration_key(integration_key: str | None, settings: Settings) -> None:
    # hmac.compare_digest em vez do `!=` — mesmo padrão já usado no webhook do Asaas.
    if not settings.erpsolid_integration_key or not hmac.compare_digest(
        integration_key or "", settings.erpsolid_integration_key
    ):
        raise HTTPException(status_code=401, detail={"code": "invalid_integration_key"})


@router.post("/provision-tenant", response_model=ProvisionTenantResponse, status_code=201)
@limiter.limit("10/minute")
async def provision_tenant(
    request: Request,
    body: ProvisionTenantRequest,
    session: Annotated[AsyncSession, Depends(require_session)],
    settings: Annotated[Settings, Depends(get_settings)],
    integration_key: Annotated[str | None, Header(alias="X-Erpsolid-Key")] = None,
) -> ProvisionTenantResponse:
    _require_integration_key(integration_key, settings)
    try:
        company = await provision_tenant_with_admin(
            session,
            name=body.name,
            document=body.document,
            email=body.email,
            trial_days=body.trial_days,
        )
    except ValueError as exc:
        code = str(exc)
        status_code = 409 if code == "company_already_exists" else 503
        raise HTTPException(status_code=status_code, detail={"code": code}) from exc
    return ProvisionTenantResponse(geop_company_id=company.id)


@router.get("/contracts", response_model=list[ErpsolidContractOut])
async def list_contracts(
    session: Annotated[AsyncSession, Depends(require_session)],
    settings: Annotated[Settings, Depends(get_settings)],
    company_id: Annotated[int, Query()],
    since: Annotated[datetime | None, Query()] = None,
    integration_key: Annotated[str | None, Header(alias="X-Erpsolid-Key")] = None,
) -> list[ErpsolidContractOut]:
    _require_integration_key(integration_key, settings)
    rows = await list_contracts_for_erpsolid(session, company_id, since)
    return [
        ErpsolidContractOut(
            id=contract.id,
            number=contract.number,
            title=contract.title,
            contract_type=contract.contract_type,
            status=contract.status,
            description=contract.description,
            total_value=contract.total_value,
            monthly_value=contract.monthly_value,
            currency=contract.currency,
            payment_frequency=contract.payment_frequency,
            payment_day=contract.payment_day,
            start_date=contract.start_date,
            end_date=contract.end_date,
            budget_category=contract.budget_category,
            supplier=(
                ErpsolidSupplierOut(id=supplier.id, name=supplier.name, document=supplier.document)
                if supplier
                else None
            ),
            cost_center=(
                ErpsolidCostCenterOut(id=cc.id, name=cc.name, code=cc.code) if cc else None
            ),
            created_at=contract.created_at,
            updated_at=contract.updated_at,
        )
        for contract, supplier, cc in rows
    ]


@router.get("/employee-payslips", response_model=list[ErpsolidEmployeePayslipOut])
async def list_employee_payslips(
    session: Annotated[AsyncSession, Depends(require_session)],
    settings: Annotated[Settings, Depends(get_settings)],
    company_id: Annotated[int, Query()],
    since: Annotated[datetime | None, Query()] = None,
    integration_key: Annotated[str | None, Header(alias="X-Erpsolid-Key")] = None,
) -> list[ErpsolidEmployeePayslipOut]:
    _require_integration_key(integration_key, settings)
    rows = await list_employee_payslips_for_erpsolid(session, company_id, since)
    return [
        ErpsolidEmployeePayslipOut(
            id=payslip.id,
            reference_month=payslip.reference_month,
            gross_amount=payslip.gross_amount,
            net_amount=payslip.net_amount,
            inss_amount=payslip.inss_amount,
            irrf_amount=payslip.irrf_amount,
            fgts_amount=payslip.fgts_amount,
            employee=ErpsolidEmployeeOut(
                id=employee.id,
                name=employee.name,
                cpf=employee.cpf,
                registration_number=employee.registration_number,
            ),
            created_at=payslip.created_at,
        )
        for payslip, employee in rows
    ]


# ---------------------------------------------------------------------------
# push de cadastros erpsolid -> GEOP (embutido no mesmo `POST /geop/sync` que já
# existe do lado erpsolid — ver `services/geop/registries_push.py` de lá)
# ---------------------------------------------------------------------------


@router.post("/suppliers", response_model=RegistriesPushResponse)
async def push_suppliers(
    session: Annotated[AsyncSession, Depends(require_session)],
    settings: Annotated[Settings, Depends(get_settings)],
    company_id: Annotated[int, Query()],
    items: list[ErpsolidSupplierPush],
    integration_key: Annotated[str | None, Header(alias="X-Erpsolid-Key")] = None,
) -> RegistriesPushResponse:
    _require_integration_key(integration_key, settings)
    upserted = await upsert_suppliers_from_erpsolid(
        session, company_id, [item.model_dump() for item in items]
    )
    await session.commit()
    return RegistriesPushResponse(upserted=upserted)


@router.post("/cost-centers", response_model=RegistriesPushResponse)
async def push_cost_centers(
    session: Annotated[AsyncSession, Depends(require_session)],
    settings: Annotated[Settings, Depends(get_settings)],
    company_id: Annotated[int, Query()],
    items: list[ErpsolidCostCenterPush],
    integration_key: Annotated[str | None, Header(alias="X-Erpsolid-Key")] = None,
) -> RegistriesPushResponse:
    _require_integration_key(integration_key, settings)
    upserted = await upsert_cost_centers_from_erpsolid(
        session, company_id, [item.model_dump() for item in items]
    )
    await session.commit()
    return RegistriesPushResponse(upserted=upserted)


@router.post("/employees", response_model=RegistriesPushResponse)
async def push_employees(
    session: Annotated[AsyncSession, Depends(require_session)],
    settings: Annotated[Settings, Depends(get_settings)],
    company_id: Annotated[int, Query()],
    items: list[ErpsolidEmployeePush],
    integration_key: Annotated[str | None, Header(alias="X-Erpsolid-Key")] = None,
) -> RegistriesPushResponse:
    _require_integration_key(integration_key, settings)
    upserted = await upsert_employees_from_erpsolid(
        session, company_id, [item.model_dump() for item in items]
    )
    await session.commit()
    return RegistriesPushResponse(upserted=upserted)
