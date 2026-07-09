from datetime import UTC, date, datetime
from typing import NamedTuple

from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.audit import compute_diff, record_event
from app.models import (
    Contract,
    ContractAmendment,
    ContractApprovalStep,
    Supplier,
    SupplierContact,
    User,
)

# ---------------------------------------------------------------------------
# Suppliers
# ---------------------------------------------------------------------------


class SupplierRow(NamedTuple):
    supplier: Supplier
    contact_count: int
    contract_count: int


async def list_suppliers(
    session: AsyncSession,
    company_id: int,
    page: int,
    page_size: int,
    search: str | None,
    active_only: bool = False,
) -> tuple[list[SupplierRow], int]:
    q = select(Supplier).where(
        Supplier.company_id == company_id,
        Supplier.deleted_at.is_(None),
    )
    if search:
        term = f"%{search}%"
        q = q.where(
            or_(
                Supplier.name.ilike(term),
                Supplier.document.ilike(term),
                Supplier.category.ilike(term),
            )
        )
    if active_only:
        q = q.where(Supplier.active.is_(True))

    total = await session.scalar(select(func.count()).select_from(q.subquery()))
    rows = (
        await session.execute(
            q.order_by(Supplier.name.asc())
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
    ).scalars().all()

    result = []
    for s in rows:
        cc = await session.scalar(
            select(func.count()).where(
                SupplierContact.supplier_id == s.id,
                SupplierContact.deleted_at.is_(None),
            )
        ) or 0
        ct = await session.scalar(
            select(func.count()).where(
                Contract.supplier_id == s.id,
                Contract.company_id == company_id,
                Contract.deleted_at.is_(None),
            )
        ) or 0
        result.append(SupplierRow(s, cc, ct))
    return result, total or 0


async def get_supplier(
    session: AsyncSession, company_id: int, supplier_id: int
) -> tuple[Supplier, list[SupplierContact]] | None:
    supplier = await session.scalar(
        select(Supplier).where(
            Supplier.id == supplier_id,
            Supplier.company_id == company_id,
            Supplier.deleted_at.is_(None),
        )
    )
    if not supplier:
        return None
    contacts = (
        await session.execute(
            select(SupplierContact)
            .where(
                SupplierContact.supplier_id == supplier_id,
                SupplierContact.deleted_at.is_(None),
            )
            .order_by(SupplierContact.is_primary.desc(), SupplierContact.name.asc())
        )
    ).scalars().all()
    return supplier, list(contacts)


async def create_supplier(
    session: AsyncSession, company_id: int, user_id: int, data: dict
) -> Supplier:
    supplier = Supplier(company_id=company_id, **data)
    session.add(supplier)
    await session.flush()
    await record_event(session, company_id, user_id, "supplier", supplier.id, "created", {})
    await session.commit()
    await session.refresh(supplier)
    return supplier


async def update_supplier(
    session: AsyncSession, company_id: int, user_id: int, supplier_id: int, data: dict
) -> Supplier | None:
    supplier = await session.scalar(
        select(Supplier).where(
            Supplier.id == supplier_id,
            Supplier.company_id == company_id,
            Supplier.deleted_at.is_(None),
        )
    )
    if not supplier:
        return None
    old = {k: getattr(supplier, k) for k in data}
    for k, v in data.items():
        setattr(supplier, k, v)
    diff = compute_diff(old, data)
    if diff:
        await record_event(session, company_id, user_id, "supplier", supplier.id, "updated", diff)
    await session.commit()
    await session.refresh(supplier)
    return supplier


async def delete_supplier(
    session: AsyncSession, company_id: int, user_id: int, supplier_id: int
) -> bool:
    supplier = await session.scalar(
        select(Supplier).where(
            Supplier.id == supplier_id,
            Supplier.company_id == company_id,
            Supplier.deleted_at.is_(None),
        )
    )
    if not supplier:
        return False
    supplier.deleted_at = datetime.now(UTC)
    await record_event(session, company_id, user_id, "supplier", supplier.id, "deleted", {})
    await session.commit()
    return True


async def list_supplier_options(
    session: AsyncSession, company_id: int
) -> list[Supplier]:
    return list(
        (
            await session.execute(
                select(Supplier)
                .where(
                    Supplier.company_id == company_id,
                    Supplier.active.is_(True),
                    Supplier.deleted_at.is_(None),
                )
                .order_by(Supplier.name.asc())
                .limit(200)
            )
        ).scalars().all()
    )


# ---------------------------------------------------------------------------
# Supplier Contacts
# ---------------------------------------------------------------------------


async def create_supplier_contact(
    session: AsyncSession,
    company_id: int,
    user_id: int,
    supplier_id: int,
    data: dict,
) -> SupplierContact | None:
    supplier = await session.scalar(
        select(Supplier).where(
            Supplier.id == supplier_id,
            Supplier.company_id == company_id,
            Supplier.deleted_at.is_(None),
        )
    )
    if not supplier:
        return None
    if data.get("is_primary"):
        await session.execute(
            select(SupplierContact)
            .where(
                SupplierContact.supplier_id == supplier_id,
                SupplierContact.is_primary.is_(True),
                SupplierContact.deleted_at.is_(None),
            )
        )
        primaries = (
            await session.execute(
                select(SupplierContact).where(
                    SupplierContact.supplier_id == supplier_id,
                    SupplierContact.is_primary.is_(True),
                    SupplierContact.deleted_at.is_(None),
                )
            )
        ).scalars().all()
        for p in primaries:
            p.is_primary = False
    contact = SupplierContact(company_id=company_id, supplier_id=supplier_id, **data)
    session.add(contact)
    await session.flush()
    await record_event(
        session, company_id, user_id, "supplier_contact", contact.id, "created", {}
    )
    await session.commit()
    await session.refresh(contact)
    return contact


async def update_supplier_contact(
    session: AsyncSession,
    company_id: int,
    user_id: int,
    contact_id: int,
    data: dict,
) -> SupplierContact | None:
    contact = await session.scalar(
        select(SupplierContact).where(
            SupplierContact.id == contact_id,
            SupplierContact.company_id == company_id,
            SupplierContact.deleted_at.is_(None),
        )
    )
    if not contact:
        return None
    if data.get("is_primary"):
        primaries = (
            await session.execute(
                select(SupplierContact).where(
                    SupplierContact.supplier_id == contact.supplier_id,
                    SupplierContact.is_primary.is_(True),
                    SupplierContact.deleted_at.is_(None),
                    SupplierContact.id != contact_id,
                )
            )
        ).scalars().all()
        for p in primaries:
            p.is_primary = False
    for k, v in data.items():
        setattr(contact, k, v)
    await record_event(
        session, company_id, user_id, "supplier_contact", contact.id, "updated", {}
    )
    await session.commit()
    await session.refresh(contact)
    return contact


async def delete_supplier_contact(
    session: AsyncSession, company_id: int, user_id: int, contact_id: int
) -> bool:
    contact = await session.scalar(
        select(SupplierContact).where(
            SupplierContact.id == contact_id,
            SupplierContact.company_id == company_id,
            SupplierContact.deleted_at.is_(None),
        )
    )
    if not contact:
        return False
    contact.deleted_at = datetime.now(UTC)
    await session.commit()
    return True


# ---------------------------------------------------------------------------
# Contracts
# ---------------------------------------------------------------------------


def _days_until_expiry(end_date: date | None) -> int | None:
    if not end_date:
        return None
    return (end_date - date.today()).days


def _expiry_alert(end_date: date | None, alert_days: int) -> bool:
    days = _days_until_expiry(end_date)
    if days is None:
        return False
    return days <= alert_days


class ContractRow(NamedTuple):
    contract: Contract
    supplier_name: str | None
    responsible_name: str | None


async def list_contracts(
    session: AsyncSession,
    company_id: int,
    page: int,
    page_size: int,
    search: str | None = None,
    status: str | None = None,
    contract_type: str | None = None,
    supplier_id: int | None = None,
    expiring_in_days: int | None = None,
) -> tuple[list[ContractRow], int]:
    q = select(Contract).where(
        Contract.company_id == company_id,
        Contract.deleted_at.is_(None),
    )
    if search:
        term = f"%{search}%"
        q = q.where(or_(Contract.title.ilike(term), Contract.number.ilike(term)))
    if status:
        q = q.where(Contract.status == status)
    if contract_type:
        q = q.where(Contract.contract_type == contract_type)
    if supplier_id:
        q = q.where(Contract.supplier_id == supplier_id)
    if expiring_in_days is not None:
        today = date.today()
        limit = date.fromordinal(today.toordinal() + expiring_in_days)
        q = q.where(Contract.end_date.isnot(None), Contract.end_date <= limit)

    total = await session.scalar(select(func.count()).select_from(q.subquery()))
    rows = (
        await session.execute(
            q.order_by(Contract.end_date.asc().nullslast(), Contract.updated_at.desc())
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
    ).scalars().all()

    result = []
    for c in rows:
        supplier_name = (
            await session.scalar(
                select(Supplier.name).where(Supplier.id == c.supplier_id)
            )
            if c.supplier_id
            else None
        )
        responsible_name = (
            await session.scalar(
                select(User.name).where(User.id == c.responsible_user_id)
            )
            if c.responsible_user_id
            else None
        )
        result.append(ContractRow(c, supplier_name, responsible_name))
    return result, total or 0


async def get_contract(
    session: AsyncSession, company_id: int, contract_id: int
) -> tuple[  # noqa: E501
    Contract, str | None, str | None, list[ContractAmendment], list[tuple[ContractApprovalStep, str | None]]  # noqa: E501
] | None:
    contract = await session.scalar(
        select(Contract).where(
            Contract.id == contract_id,
            Contract.company_id == company_id,
            Contract.deleted_at.is_(None),
        )
    )
    if not contract:
        return None

    supplier_name = (
        await session.scalar(select(Supplier.name).where(Supplier.id == contract.supplier_id))
        if contract.supplier_id
        else None
    )
    responsible_name = (
        await session.scalar(select(User.name).where(User.id == contract.responsible_user_id))
        if contract.responsible_user_id
        else None
    )
    amendments = list(
        (
            await session.execute(
                select(ContractAmendment)
                .where(ContractAmendment.contract_id == contract_id)
                .order_by(ContractAmendment.created_at.desc())
            )
        ).scalars().all()
    )
    raw_steps = list(
        (
            await session.execute(
                select(ContractApprovalStep)
                .where(ContractApprovalStep.contract_id == contract_id)
                .order_by(ContractApprovalStep.step_order.asc())
            )
        ).scalars().all()
    )
    steps = []
    for step in raw_steps:
        uname = await session.scalar(select(User.name).where(User.id == step.approver_user_id))
        steps.append((step, uname))
    return contract, supplier_name, responsible_name, amendments, steps


async def create_contract(
    session: AsyncSession,
    company_id: int,
    user_id: int,
    data: dict,
    approver_user_ids: list[int],
) -> Contract:
    contract = Contract(company_id=company_id, created_by_user_id=user_id, **data)
    session.add(contract)
    await session.flush()

    for i, uid in enumerate(approver_user_ids, start=1):
        step = ContractApprovalStep(
            company_id=company_id,
            contract_id=contract.id,
            step_order=i,
            approver_user_id=uid,
        )
        session.add(step)

    await record_event(session, company_id, user_id, "contract", contract.id, "created", {})
    await session.commit()
    await session.refresh(contract)
    return contract


async def update_contract(
    session: AsyncSession,
    company_id: int,
    user_id: int,
    contract_id: int,
    data: dict,
) -> Contract | None:
    contract = await session.scalar(
        select(Contract).where(
            Contract.id == contract_id,
            Contract.company_id == company_id,
            Contract.deleted_at.is_(None),
        )
    )
    if not contract:
        return None
    old = {k: getattr(contract, k) for k in data}
    for k, v in data.items():
        setattr(contract, k, v)
    diff = compute_diff(old, data)
    if diff:
        await record_event(session, company_id, user_id, "contract", contract.id, "updated", diff)
    await session.commit()
    await session.refresh(contract)
    return contract


async def update_contract_status(
    session: AsyncSession,
    company_id: int,
    user_id: int,
    contract_id: int,
    new_status: str,
    comment: str | None,
) -> Contract | None:
    contract = await session.scalar(
        select(Contract).where(
            Contract.id == contract_id,
            Contract.company_id == company_id,
            Contract.deleted_at.is_(None),
        )
    )
    if not contract:
        return None
    old_status = contract.status
    contract.status = new_status
    await record_event(
        session,
        company_id,
        user_id,
        "contract",
        contract.id,
        "status_changed",
        {"from": old_status, "to": new_status, "comment": comment},
    )
    await session.commit()
    await session.refresh(contract)
    return contract


async def delete_contract(
    session: AsyncSession, company_id: int, user_id: int, contract_id: int
) -> bool:
    contract = await session.scalar(
        select(Contract).where(
            Contract.id == contract_id,
            Contract.company_id == company_id,
            Contract.deleted_at.is_(None),
        )
    )
    if not contract:
        return False
    contract.deleted_at = datetime.now(UTC)
    await record_event(session, company_id, user_id, "contract", contract.id, "deleted", {})
    await session.commit()
    return True


# ---------------------------------------------------------------------------
# Amendments
# ---------------------------------------------------------------------------


async def create_amendment(
    session: AsyncSession,
    company_id: int,
    user_id: int,
    contract_id: int,
    data: dict,
) -> ContractAmendment | None:
    contract = await session.scalar(
        select(Contract).where(
            Contract.id == contract_id,
            Contract.company_id == company_id,
            Contract.deleted_at.is_(None),
        )
    )
    if not contract:
        return None

    amendment = ContractAmendment(
        company_id=company_id,
        contract_id=contract_id,
        created_by_user_id=user_id,
        **data,
    )
    session.add(amendment)

    # Apply amendment effects to contract
    if data.get("new_end_date"):
        contract.end_date = data["new_end_date"]
    if data.get("new_value") is not None:
        contract.total_value = data["new_value"]

    await session.flush()
    await record_event(
        session, company_id, user_id, "contract", contract_id, "amendment_added",
        {"type": data["amendment_type"]},
    )
    await session.commit()
    await session.refresh(amendment)
    return amendment


# ---------------------------------------------------------------------------
# Approvals
# ---------------------------------------------------------------------------


async def decide_approval(
    session: AsyncSession,
    company_id: int,
    user_id: int,
    contract_id: int,
    approved: bool,
    comment: str | None,
) -> Contract | None:
    contract = await session.scalar(
        select(Contract).where(
            Contract.id == contract_id,
            Contract.company_id == company_id,
            Contract.deleted_at.is_(None),
        )
    )
    if not contract or contract.status != "aguardando_aprovacao":
        return None

    step = await session.scalar(
        select(ContractApprovalStep).where(
            ContractApprovalStep.contract_id == contract_id,
            ContractApprovalStep.approver_user_id == user_id,
            ContractApprovalStep.status == "pendente",
        )
    )
    if not step:
        return None

    step.status = "aprovado" if approved else "rejeitado"
    step.comment = comment
    step.decided_at = datetime.now(UTC)

    if not approved:
        contract.status = "rascunho"
        await record_event(
            session, company_id, user_id, "contract", contract_id, "rejected",
            {"comment": comment},
        )
    else:
        pending = await session.scalar(
            select(func.count()).where(
                ContractApprovalStep.contract_id == contract_id,
                ContractApprovalStep.status == "pendente",
            )
        )
        if (pending or 0) == 0:
            contract.status = "ativo"
            await record_event(
                session, company_id, user_id, "contract", contract_id, "approved", {}
            )
        else:
            await record_event(
                session, company_id, user_id, "contract", contract_id,
                "step_approved", {"step_order": step.step_order},
            )

    await session.commit()
    await session.refresh(contract)
    return contract
