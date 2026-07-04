from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import require_session
from app.core.permissions import require_permission
from app.domain.auth.repository import AuthenticatedUser
from app.domain.employees.schemas import (
    EmployeeCreate,
    EmployeeDetailedSummary,
    EmployeeExternalIdCreate,
    EmployeeExternalIdSummary,
    EmployeeListResponse,
    EmployeeOption,
    EmployeeSummary,
    EmployeeUpdate,
)
from app.domain.employees.service import (
    create_employee,
    create_employee_external_id,
    delete_employee,
    delete_employee_external_id,
    get_employee,
    get_employee_external_ids,
    list_employees,
    search_employees,
    update_employee,
)

router = APIRouter(prefix="/employees", tags=["employees"])


def _to_summary(employee) -> EmployeeSummary:
    return EmployeeSummary(
        id=employee.id,
        name=employee.name,
        cpf=employee.cpf,
        personal_email=employee.personal_email,
        phone=employee.phone,
        status=employee.status,
        user_id=employee.user_id,
        avatar_url=employee.avatar_url,
        created_at=employee.created_at,
        updated_at=employee.updated_at,
    )


def _to_detailed_summary(employee, external_ids=None) -> EmployeeDetailedSummary:
    return EmployeeDetailedSummary(
        id=employee.id,
        name=employee.name,
        cpf=employee.cpf,
        personal_email=employee.personal_email,
        phone=employee.phone,
        status=employee.status,
        user_id=employee.user_id,
        avatar_url=employee.avatar_url,
        rg=employee.rg,
        birth_date=employee.birth_date,
        address_street=employee.address_street,
        address_number=employee.address_number,
        address_complement=employee.address_complement,
        address_neighborhood=employee.address_neighborhood,
        address_city=employee.address_city,
        address_state=employee.address_state,
        address_zip=employee.address_zip,
        created_at=employee.created_at,
        updated_at=employee.updated_at,
        external_ids=[
            EmployeeExternalIdSummary(
                id=eid.id,
                employee_id=eid.employee_id,
                system=eid.system,
                external_id=eid.external_id,
            )
            for eid in (external_ids or [])
        ],
    )


@router.get("", response_model=EmployeeListResponse)
async def list_employees_endpoint(
    user: Annotated[AuthenticatedUser, require_permission("employee.view")],
    session: Annotated[AsyncSession, Depends(require_session)],
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=100)] = 20,
    status: str | None = None,
) -> EmployeeListResponse:
    items, total = await list_employees(
        session, user.company_id, page, page_size, status=status
    )
    return EmployeeListResponse(
        items=[_to_summary(item) for item in items],
        total=total,
        page=page,
        page_size=page_size,
    )


@router.get("/search", response_model=list[EmployeeOption])
async def search_employees_endpoint(
    user: Annotated[AuthenticatedUser, require_permission("employee.view")],
    session: Annotated[AsyncSession, Depends(require_session)],
    q: str = "",
) -> list[EmployeeOption]:
    results = await search_employees(session, user.company_id, q)
    return [EmployeeOption(**r) for r in results]


@router.get("/{employee_id}", response_model=EmployeeDetailedSummary)
async def get_employee_endpoint(
    employee_id: int,
    user: Annotated[AuthenticatedUser, require_permission("employee.view")],
    session: Annotated[AsyncSession, Depends(require_session)],
) -> EmployeeDetailedSummary:
    record = await get_employee(session, user.company_id, employee_id)
    if record is None:
        raise HTTPException(status_code=404, detail={"code": "not_found"})
    external_ids = await get_employee_external_ids(session, user.company_id, employee_id)
    return _to_detailed_summary(record, external_ids)


@router.post("", response_model=EmployeeSummary, status_code=201)
async def create_employee_endpoint(
    body: EmployeeCreate,
    user: Annotated[AuthenticatedUser, require_permission("employee.manage")],
    session: Annotated[AsyncSession, Depends(require_session)],
) -> EmployeeSummary:
    record = await create_employee(
        session,
        user.company_id,
        user.id,
        name=body.name,
        cpf=body.cpf,
        rg=body.rg,
        birth_date=body.birth_date,
        phone=body.phone,
        personal_email=body.personal_email,
        address_street=body.address_street,
        address_number=body.address_number,
        address_complement=body.address_complement,
        address_neighborhood=body.address_neighborhood,
        address_city=body.address_city,
        address_state=body.address_state,
        address_zip=body.address_zip,
        status=body.status,
        user_id=body.user_id,
    )
    return _to_summary(record)


@router.patch("/{employee_id}", response_model=EmployeeSummary)
async def update_employee_endpoint(
    employee_id: int,
    body: EmployeeUpdate,
    user: Annotated[AuthenticatedUser, require_permission("employee.manage")],
    session: Annotated[AsyncSession, Depends(require_session)],
) -> EmployeeSummary:
    updates = body.model_dump(exclude_none=True)
    record = await update_employee(session, user.company_id, user.id, employee_id, updates)
    if record is None:
        raise HTTPException(status_code=404, detail={"code": "not_found"})
    return _to_summary(record)


@router.delete("/{employee_id}", status_code=204)
async def delete_employee_endpoint(
    employee_id: int,
    user: Annotated[AuthenticatedUser, require_permission("employee.manage")],
    session: Annotated[AsyncSession, Depends(require_session)],
) -> None:
    deleted = await delete_employee(session, user.company_id, user.id, employee_id)
    if not deleted:
        raise HTTPException(status_code=404, detail={"code": "not_found"})


@router.post(
    "/{employee_id}/external-ids", response_model=EmployeeExternalIdSummary, status_code=201
)
async def create_external_id_endpoint(
    employee_id: int,
    body: EmployeeExternalIdCreate,
    user: Annotated[AuthenticatedUser, require_permission("employee.manage")],
    session: Annotated[AsyncSession, Depends(require_session)],
) -> EmployeeExternalIdSummary:
    employee = await get_employee(session, user.company_id, employee_id)
    if employee is None:
        raise HTTPException(status_code=404, detail={"code": "not_found"})

    record = await create_employee_external_id(
        session,
        user.company_id,
        user.id,
        employee_id,
        system=body.system,
        external_id=body.external_id,
    )
    return EmployeeExternalIdSummary(
        id=record.id,
        employee_id=record.employee_id,
        system=record.system,
        external_id=record.external_id,
    )


@router.delete("/{employee_id}/external-ids/{external_id_id}", status_code=204)
async def delete_external_id_endpoint(
    employee_id: int,
    external_id_id: int,
    user: Annotated[AuthenticatedUser, require_permission("employee.manage")],
    session: Annotated[AsyncSession, Depends(require_session)],
) -> None:
    employee = await get_employee(session, user.company_id, employee_id)
    if employee is None:
        raise HTTPException(status_code=404, detail={"code": "not_found"})

    deleted = await delete_employee_external_id(
        session, user.company_id, user.id, employee_id, external_id_id
    )
    if not deleted:
        raise HTTPException(status_code=404, detail={"code": "not_found"})
