from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select as _select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import require_session
from app.core.permissions import require_permission
from app.domain.auth.repository import AuthenticatedUser
from app.domain.contracts.schemas import (
    ApprovalDecision,
    ContractAmendmentCreate,
    ContractAmendmentOut,
    ContractApprovalStepOut,
    ContractCreate,
    ContractListResponse,
    ContractOut,
    ContractStatusUpdate,
    ContractSummary,
    ContractUpdate,
    SupplierContactCreate,
    SupplierContactOut,
    SupplierContactUpdate,
    SupplierCreate,
    SupplierListResponse,
    SupplierOption,
    SupplierOut,
    SupplierSummary,
    SupplierUpdate,
)
from app.domain.contracts.service import (
    _days_until_expiry,
    _expiry_alert,
    create_amendment,
    create_contract,
    create_supplier,
    create_supplier_contact,
    decide_approval,
    delete_contract,
    delete_supplier,
    delete_supplier_contact,
    get_contract,
    get_supplier,
    list_contracts,
    list_supplier_options,
    list_suppliers,
    update_contract,
    update_contract_status,
    update_supplier,
    update_supplier_contact,
)
from app.models import User

router = APIRouter(prefix="/contracts", tags=["contracts"])


# ---------------------------------------------------------------------------
# Suppliers
# ---------------------------------------------------------------------------


@router.get("/suppliers", response_model=SupplierListResponse)
async def list_suppliers_endpoint(
    user: Annotated[AuthenticatedUser, require_permission("contract.view")],
    session: Annotated[AsyncSession, Depends(require_session)],
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=100)] = 20,
    search: str | None = None,
    active_only: bool = False,
) -> SupplierListResponse:
    rows, total = await list_suppliers(
        session, user.company_id, page, page_size, search, active_only
    )
    return SupplierListResponse(
        items=[
            SupplierSummary(
                id=r.supplier.id,
                name=r.supplier.name,
                document=r.supplier.document,
                category=r.supplier.category,
                email=r.supplier.email,
                phone=r.supplier.phone,
                active=r.supplier.active,
                contact_count=r.contact_count,
                contract_count=r.contract_count,
                updated_at=r.supplier.updated_at,
            )
            for r in rows
        ],
        total=total,
        page=page,
        page_size=page_size,
    )


@router.get("/suppliers/options", response_model=list[SupplierOption])
async def list_supplier_options_endpoint(
    user: Annotated[AuthenticatedUser, require_permission("contract.view")],
    session: Annotated[AsyncSession, Depends(require_session)],
) -> list[SupplierOption]:
    items = await list_supplier_options(session, user.company_id)
    return [SupplierOption(id=s.id, name=s.name, document=s.document) for s in items]


@router.get("/suppliers/{supplier_id}", response_model=SupplierOut)
async def get_supplier_endpoint(
    supplier_id: int,
    user: Annotated[AuthenticatedUser, require_permission("contract.view")],
    session: Annotated[AsyncSession, Depends(require_session)],
) -> SupplierOut:
    result = await get_supplier(session, user.company_id, supplier_id)
    if not result:
        raise HTTPException(status_code=404, detail={"code": "not_found"})
    supplier, contacts = result
    return SupplierOut(
        id=supplier.id,
        name=supplier.name,
        document=supplier.document,
        document_type=supplier.document_type,
        category=supplier.category,
        email=supplier.email,
        phone=supplier.phone,
        website=supplier.website,
        address_street=supplier.address_street,
        address_number=supplier.address_number,
        address_complement=supplier.address_complement,
        address_city=supplier.address_city,
        address_state=supplier.address_state,
        address_zip=supplier.address_zip,
        active=supplier.active,
        notes=supplier.notes,
        contacts=[
            SupplierContactOut(
                id=c.id,
                supplier_id=c.supplier_id,
                name=c.name,
                role=c.role,
                email=c.email,
                phone=c.phone,
                whatsapp=c.whatsapp,
                is_primary=c.is_primary,
                notes=c.notes,
                created_at=c.created_at,
            )
            for c in contacts
        ],
        created_at=supplier.created_at,
        updated_at=supplier.updated_at,
    )


@router.post("/suppliers", response_model=SupplierOut, status_code=201)
async def create_supplier_endpoint(
    body: SupplierCreate,
    user: Annotated[AuthenticatedUser, require_permission("contract.create")],
    session: Annotated[AsyncSession, Depends(require_session)],
) -> SupplierOut:
    supplier = await create_supplier(
        session, user.company_id, user.id, body.model_dump(exclude_none=True)
    )
    return SupplierOut(
        id=supplier.id,
        name=supplier.name,
        document=supplier.document,
        document_type=supplier.document_type,
        category=supplier.category,
        email=supplier.email,
        phone=supplier.phone,
        website=supplier.website,
        address_street=supplier.address_street,
        address_number=supplier.address_number,
        address_complement=supplier.address_complement,
        address_city=supplier.address_city,
        address_state=supplier.address_state,
        address_zip=supplier.address_zip,
        active=supplier.active,
        notes=supplier.notes,
        contacts=[],
        created_at=supplier.created_at,
        updated_at=supplier.updated_at,
    )


@router.patch("/suppliers/{supplier_id}", response_model=SupplierOut)
async def update_supplier_endpoint(
    supplier_id: int,
    body: SupplierUpdate,
    user: Annotated[AuthenticatedUser, require_permission("contract.edit")],
    session: Annotated[AsyncSession, Depends(require_session)],
) -> SupplierOut:
    supplier = await update_supplier(
        session,
        user.company_id,
        user.id,
        supplier_id,
        body.model_dump(exclude_none=True),
    )
    if not supplier:
        raise HTTPException(status_code=404, detail={"code": "not_found"})
    result = await get_supplier(session, user.company_id, supplier_id)
    if not result:
        raise HTTPException(status_code=404, detail={"code": "not_found"})
    s, contacts = result
    return SupplierOut(
        id=s.id, name=s.name, document=s.document, document_type=s.document_type,
        category=s.category, email=s.email, phone=s.phone, website=s.website,
        address_street=s.address_street, address_number=s.address_number,
        address_complement=s.address_complement, address_city=s.address_city,
        address_state=s.address_state, address_zip=s.address_zip,
        active=s.active, notes=s.notes,
        contacts=[
            SupplierContactOut(
                id=c.id, supplier_id=c.supplier_id, name=c.name, role=c.role,
                email=c.email, phone=c.phone, whatsapp=c.whatsapp,
                is_primary=c.is_primary, notes=c.notes, created_at=c.created_at,
            )
            for c in contacts
        ],
        created_at=s.created_at, updated_at=s.updated_at,
    )


@router.delete("/suppliers/{supplier_id}", status_code=204)
async def delete_supplier_endpoint(
    supplier_id: int,
    user: Annotated[AuthenticatedUser, require_permission("contract.delete")],
    session: Annotated[AsyncSession, Depends(require_session)],
) -> None:
    deleted = await delete_supplier(session, user.company_id, user.id, supplier_id)
    if not deleted:
        raise HTTPException(status_code=404, detail={"code": "not_found"})


@router.post(
    "/suppliers/{supplier_id}/contacts", response_model=SupplierContactOut, status_code=201
)
async def create_contact_endpoint(
    supplier_id: int,
    body: SupplierContactCreate,
    user: Annotated[AuthenticatedUser, require_permission("contract.edit")],
    session: Annotated[AsyncSession, Depends(require_session)],
) -> SupplierContactOut:
    contact = await create_supplier_contact(
        session, user.company_id, user.id, supplier_id, body.model_dump(exclude_none=True)
    )
    if not contact:
        raise HTTPException(status_code=404, detail={"code": "not_found"})
    return SupplierContactOut(
        id=contact.id, supplier_id=contact.supplier_id, name=contact.name,
        role=contact.role, email=contact.email, phone=contact.phone,
        whatsapp=contact.whatsapp, is_primary=contact.is_primary,
        notes=contact.notes, created_at=contact.created_at,
    )


@router.patch("/contacts/{contact_id}", response_model=SupplierContactOut)
async def update_contact_endpoint(
    contact_id: int,
    body: SupplierContactUpdate,
    user: Annotated[AuthenticatedUser, require_permission("contract.edit")],
    session: Annotated[AsyncSession, Depends(require_session)],
) -> SupplierContactOut:
    contact = await update_supplier_contact(
        session, user.company_id, user.id, contact_id, body.model_dump(exclude_none=True)
    )
    if not contact:
        raise HTTPException(status_code=404, detail={"code": "not_found"})
    return SupplierContactOut(
        id=contact.id, supplier_id=contact.supplier_id, name=contact.name,
        role=contact.role, email=contact.email, phone=contact.phone,
        whatsapp=contact.whatsapp, is_primary=contact.is_primary,
        notes=contact.notes, created_at=contact.created_at,
    )


@router.delete("/contacts/{contact_id}", status_code=204)
async def delete_contact_endpoint(
    contact_id: int,
    user: Annotated[AuthenticatedUser, require_permission("contract.edit")],
    session: Annotated[AsyncSession, Depends(require_session)],
) -> None:
    deleted = await delete_supplier_contact(session, user.company_id, user.id, contact_id)
    if not deleted:
        raise HTTPException(status_code=404, detail={"code": "not_found"})


# ---------------------------------------------------------------------------
# Contracts
# ---------------------------------------------------------------------------


@router.get("", response_model=ContractListResponse)
async def list_contracts_endpoint(
    user: Annotated[AuthenticatedUser, require_permission("contract.view")],
    session: Annotated[AsyncSession, Depends(require_session)],
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=100)] = 20,
    search: str | None = None,
    status: str | None = None,
    contract_type: str | None = None,
    supplier_id: int | None = None,
    expiring_in_days: int | None = None,
) -> ContractListResponse:
    rows, total = await list_contracts(
        session, user.company_id, page, page_size,
        search, status, contract_type, supplier_id, expiring_in_days,
    )
    return ContractListResponse(
        items=[
            ContractSummary(
                id=r.contract.id,
                number=r.contract.number,
                title=r.contract.title,
                contract_type=r.contract.contract_type,
                supplier_name=r.supplier_name,
                responsible_name=r.responsible_name,
                status=r.contract.status,
                start_date=r.contract.start_date,
                end_date=r.contract.end_date,
                total_value=r.contract.total_value,
                monthly_value=r.contract.monthly_value,
                alert_days=r.contract.alert_days,
                days_until_expiry=_days_until_expiry(r.contract.end_date),
                expiry_alert=_expiry_alert(r.contract.end_date, r.contract.alert_days),
                updated_at=r.contract.updated_at,
            )
            for r in rows
        ],
        total=total,
        page=page,
        page_size=page_size,
    )


@router.get("/{contract_id}", response_model=ContractOut)
async def get_contract_endpoint(
    contract_id: int,
    user: Annotated[AuthenticatedUser, require_permission("contract.view")],
    session: Annotated[AsyncSession, Depends(require_session)],
) -> ContractOut:
    result = await get_contract(session, user.company_id, contract_id)
    if not result:
        raise HTTPException(status_code=404, detail={"code": "not_found"})
    contract, supplier_name, responsible_name, amendments, steps = result

    amendment_outs = []
    for a in amendments:
        uname = None
        if a.created_by_user_id:
            uname = await session.scalar(_select(User.name).where(User.id == a.created_by_user_id))
        amendment_outs.append(ContractAmendmentOut(
            id=a.id, contract_id=a.contract_id, amendment_type=a.amendment_type,
            description=a.description, new_end_date=a.new_end_date,
            new_value=a.new_value, signed_at=a.signed_at,
            created_by_user_id=a.created_by_user_id, created_by_name=uname,
            created_at=a.created_at,
        ))

    return ContractOut(
        id=contract.id, number=contract.number, title=contract.title,
        contract_type=contract.contract_type, supplier_id=contract.supplier_id,
        supplier_name=supplier_name, responsible_user_id=contract.responsible_user_id,
        responsible_name=responsible_name, created_by_user_id=contract.created_by_user_id,
        status=contract.status, description=contract.description,
        conditions=contract.conditions, notes=contract.notes,
        signed_at=contract.signed_at, start_date=contract.start_date,
        end_date=contract.end_date, alert_days=contract.alert_days,
        auto_renew=contract.auto_renew, indexer=contract.indexer,
        total_value=contract.total_value, monthly_value=contract.monthly_value,
        currency=contract.currency, payment_frequency=contract.payment_frequency,
        payment_day=contract.payment_day, cost_center=contract.cost_center,
        budget_category=contract.budget_category,
        amendments=amendment_outs,
        approval_steps=[
            ContractApprovalStepOut(
                id=s.id, step_order=s.step_order, approver_user_id=s.approver_user_id,
                approver_name=uname, status=s.status, comment=s.comment,
                decided_at=s.decided_at,
            )
            for s, uname in steps
        ],
        created_at=contract.created_at, updated_at=contract.updated_at,
    )


@router.post("", response_model=ContractOut, status_code=201)
async def create_contract_endpoint(
    body: ContractCreate,
    user: Annotated[AuthenticatedUser, require_permission("contract.create")],
    session: Annotated[AsyncSession, Depends(require_session)],
) -> ContractOut:
    data = body.model_dump(exclude={"approver_user_ids"}, exclude_none=True)
    contract = await create_contract(
        session, user.company_id, user.id, data, body.approver_user_ids
    )
    result = await get_contract(session, user.company_id, contract.id)
    if not result:
        raise HTTPException(status_code=500, detail={"code": "internal_error"})
    contract, supplier_name, responsible_name, amendments, steps = result
    return ContractOut(
        id=contract.id, number=contract.number, title=contract.title,
        contract_type=contract.contract_type, supplier_id=contract.supplier_id,
        supplier_name=supplier_name, responsible_user_id=contract.responsible_user_id,
        responsible_name=responsible_name, created_by_user_id=contract.created_by_user_id,
        status=contract.status, description=contract.description,
        conditions=contract.conditions, notes=contract.notes,
        signed_at=contract.signed_at, start_date=contract.start_date,
        end_date=contract.end_date, alert_days=contract.alert_days,
        auto_renew=contract.auto_renew, indexer=contract.indexer,
        total_value=contract.total_value, monthly_value=contract.monthly_value,
        currency=contract.currency, payment_frequency=contract.payment_frequency,
        payment_day=contract.payment_day, cost_center=contract.cost_center,
        budget_category=contract.budget_category,
        amendments=[], approval_steps=[
            ContractApprovalStepOut(
                id=s.id, step_order=s.step_order, approver_user_id=s.approver_user_id,
                approver_name=uname, status=s.status, comment=s.comment,
                decided_at=s.decided_at,
            )
            for s, uname in steps
        ],
        created_at=contract.created_at, updated_at=contract.updated_at,
    )


@router.patch("/{contract_id}", response_model=ContractOut)
async def update_contract_endpoint(
    contract_id: int,
    body: ContractUpdate,
    user: Annotated[AuthenticatedUser, require_permission("contract.edit")],
    session: Annotated[AsyncSession, Depends(require_session)],
) -> ContractOut:
    updated = await update_contract(
        session, user.company_id, user.id, contract_id,
        body.model_dump(exclude_none=True),
    )
    if not updated:
        raise HTTPException(status_code=404, detail={"code": "not_found"})
    result = await get_contract(session, user.company_id, contract_id)
    if not result:
        raise HTTPException(status_code=404, detail={"code": "not_found"})
    contract, supplier_name, responsible_name, amendments, steps = result
    return ContractOut(
        id=contract.id, number=contract.number, title=contract.title,
        contract_type=contract.contract_type, supplier_id=contract.supplier_id,
        supplier_name=supplier_name, responsible_user_id=contract.responsible_user_id,
        responsible_name=responsible_name, created_by_user_id=contract.created_by_user_id,
        status=contract.status, description=contract.description,
        conditions=contract.conditions, notes=contract.notes,
        signed_at=contract.signed_at, start_date=contract.start_date,
        end_date=contract.end_date, alert_days=contract.alert_days,
        auto_renew=contract.auto_renew, indexer=contract.indexer,
        total_value=contract.total_value, monthly_value=contract.monthly_value,
        currency=contract.currency, payment_frequency=contract.payment_frequency,
        payment_day=contract.payment_day, cost_center=contract.cost_center,
        budget_category=contract.budget_category,
        amendments=[
            ContractAmendmentOut(
                id=a.id, contract_id=a.contract_id, amendment_type=a.amendment_type,
                description=a.description, new_end_date=a.new_end_date,
                new_value=a.new_value, signed_at=a.signed_at,
                created_by_user_id=a.created_by_user_id, created_by_name=None,
                created_at=a.created_at,
            )
            for a in amendments
        ],
        approval_steps=[
            ContractApprovalStepOut(
                id=s.id, step_order=s.step_order, approver_user_id=s.approver_user_id,
                approver_name=uname, status=s.status, comment=s.comment,
                decided_at=s.decided_at,
            )
            for s, uname in steps
        ],
        created_at=contract.created_at, updated_at=contract.updated_at,
    )


@router.patch("/{contract_id}/status", response_model=ContractOut)
async def update_status_endpoint(
    contract_id: int,
    body: ContractStatusUpdate,
    user: Annotated[AuthenticatedUser, require_permission("contract.edit")],
    session: Annotated[AsyncSession, Depends(require_session)],
) -> ContractOut:
    updated = await update_contract_status(
        session, user.company_id, user.id, contract_id, body.status, body.comment
    )
    if not updated:
        raise HTTPException(status_code=404, detail={"code": "not_found"})
    result = await get_contract(session, user.company_id, contract_id)
    if not result:
        raise HTTPException(status_code=404, detail={"code": "not_found"})
    contract, supplier_name, responsible_name, amendments, steps = result
    return ContractOut(
        id=contract.id, number=contract.number, title=contract.title,
        contract_type=contract.contract_type, supplier_id=contract.supplier_id,
        supplier_name=supplier_name, responsible_user_id=contract.responsible_user_id,
        responsible_name=responsible_name, created_by_user_id=contract.created_by_user_id,
        status=contract.status, description=contract.description,
        conditions=contract.conditions, notes=contract.notes,
        signed_at=contract.signed_at, start_date=contract.start_date,
        end_date=contract.end_date, alert_days=contract.alert_days,
        auto_renew=contract.auto_renew, indexer=contract.indexer,
        total_value=contract.total_value, monthly_value=contract.monthly_value,
        currency=contract.currency, payment_frequency=contract.payment_frequency,
        payment_day=contract.payment_day, cost_center=contract.cost_center,
        budget_category=contract.budget_category,
        amendments=[
            ContractAmendmentOut(
                id=a.id, contract_id=a.contract_id, amendment_type=a.amendment_type,
                description=a.description, new_end_date=a.new_end_date,
                new_value=a.new_value, signed_at=a.signed_at,
                created_by_user_id=a.created_by_user_id, created_by_name=None,
                created_at=a.created_at,
            )
            for a in amendments
        ],
        approval_steps=[
            ContractApprovalStepOut(
                id=s.id, step_order=s.step_order, approver_user_id=s.approver_user_id,
                approver_name=uname, status=s.status, comment=s.comment,
                decided_at=s.decided_at,
            )
            for s, uname in steps
        ],
        created_at=contract.created_at, updated_at=contract.updated_at,
    )


@router.delete("/{contract_id}", status_code=204)
async def delete_contract_endpoint(
    contract_id: int,
    user: Annotated[AuthenticatedUser, require_permission("contract.delete")],
    session: Annotated[AsyncSession, Depends(require_session)],
) -> None:
    deleted = await delete_contract(session, user.company_id, user.id, contract_id)
    if not deleted:
        raise HTTPException(status_code=404, detail={"code": "not_found"})


@router.post("/{contract_id}/amendments", response_model=ContractAmendmentOut, status_code=201)
async def create_amendment_endpoint(
    contract_id: int,
    body: ContractAmendmentCreate,
    user: Annotated[AuthenticatedUser, require_permission("contract.edit")],
    session: Annotated[AsyncSession, Depends(require_session)],
) -> ContractAmendmentOut:
    amendment = await create_amendment(
        session, user.company_id, user.id, contract_id, body.model_dump(exclude_none=True)
    )
    if not amendment:
        raise HTTPException(status_code=404, detail={"code": "not_found"})
    return ContractAmendmentOut(
        id=amendment.id, contract_id=amendment.contract_id,
        amendment_type=amendment.amendment_type, description=amendment.description,
        new_end_date=amendment.new_end_date, new_value=amendment.new_value,
        signed_at=amendment.signed_at, created_by_user_id=amendment.created_by_user_id,
        created_by_name=None, created_at=amendment.created_at,
    )


@router.post("/{contract_id}/approve", response_model=ContractOut)
async def approve_contract_endpoint(
    contract_id: int,
    body: ApprovalDecision,
    user: Annotated[AuthenticatedUser, require_permission("contract.approve")],
    session: Annotated[AsyncSession, Depends(require_session)],
) -> ContractOut:
    updated = await decide_approval(
        session, user.company_id, user.id, contract_id, body.approved, body.comment
    )
    if not updated:
        raise HTTPException(
            status_code=422,
            detail={
                "code": "cannot_approve",
                "message": "Contrato não aguarda aprovação ou você não é aprovador.",
            },
        )
    result = await get_contract(session, user.company_id, contract_id)
    if not result:
        raise HTTPException(status_code=404, detail={"code": "not_found"})
    contract, supplier_name, responsible_name, amendments, steps = result
    return ContractOut(
        id=contract.id, number=contract.number, title=contract.title,
        contract_type=contract.contract_type, supplier_id=contract.supplier_id,
        supplier_name=supplier_name, responsible_user_id=contract.responsible_user_id,
        responsible_name=responsible_name, created_by_user_id=contract.created_by_user_id,
        status=contract.status, description=contract.description,
        conditions=contract.conditions, notes=contract.notes,
        signed_at=contract.signed_at, start_date=contract.start_date,
        end_date=contract.end_date, alert_days=contract.alert_days,
        auto_renew=contract.auto_renew, indexer=contract.indexer,
        total_value=contract.total_value, monthly_value=contract.monthly_value,
        currency=contract.currency, payment_frequency=contract.payment_frequency,
        payment_day=contract.payment_day, cost_center=contract.cost_center,
        budget_category=contract.budget_category,
        amendments=[
            ContractAmendmentOut(
                id=a.id, contract_id=a.contract_id, amendment_type=a.amendment_type,
                description=a.description, new_end_date=a.new_end_date,
                new_value=a.new_value, signed_at=a.signed_at,
                created_by_user_id=a.created_by_user_id, created_by_name=None,
                created_at=a.created_at,
            )
            for a in amendments
        ],
        approval_steps=[
            ContractApprovalStepOut(
                id=s.id, step_order=s.step_order, approver_user_id=s.approver_user_id,
                approver_name=uname, status=s.status, comment=s.comment,
                decided_at=s.decided_at,
            )
            for s, uname in steps
        ],
        created_at=contract.created_at, updated_at=contract.updated_at,
    )
