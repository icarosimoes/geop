from datetime import date, datetime, timedelta
from typing import NamedTuple

from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.audit import compute_diff, record_event
from app.models import (
    AuditEvent,
    Contract,
    ContractAmendment,
    ContractApprovalStep,
    CostCenter,
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
    suppliers = (
        (
            await session.execute(
                q.order_by(Supplier.name.asc()).offset((page - 1) * page_size).limit(page_size)
            )
        )
        .scalars()
        .all()
    )

    if not suppliers:
        return [], 0

    supplier_ids = [s.id for s in suppliers]

    contact_counts_rows = (
        await session.execute(
            select(SupplierContact.supplier_id, func.count().label("cnt"))
            .where(
                SupplierContact.supplier_id.in_(supplier_ids),
                SupplierContact.deleted_at.is_(None),
            )
            .group_by(SupplierContact.supplier_id)
        )
    ).all()
    contact_counts = {r.supplier_id: r.cnt for r in contact_counts_rows}

    contract_counts_rows = (
        await session.execute(
            select(Contract.supplier_id, func.count().label("cnt"))
            .where(
                Contract.supplier_id.in_(supplier_ids),
                Contract.company_id == company_id,
                Contract.deleted_at.is_(None),
            )
            .group_by(Contract.supplier_id)
        )
    ).all()
    contract_counts = {r.supplier_id: r.cnt for r in contract_counts_rows}

    result = [
        SupplierRow(s, contact_counts.get(s.id, 0), contract_counts.get(s.id, 0)) for s in suppliers
    ]
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
        (
            await session.execute(
                select(SupplierContact)
                .where(
                    SupplierContact.supplier_id == supplier_id,
                    SupplierContact.deleted_at.is_(None),
                )
                .order_by(SupplierContact.is_primary.desc(), SupplierContact.name.asc())
            )
        )
        .scalars()
        .all()
    )
    return supplier, list(contacts)


async def create_supplier(
    session: AsyncSession, company_id: int, user_id: int, data: dict
) -> Supplier:
    supplier = Supplier(company_id=company_id, **data)
    session.add(supplier)
    await session.flush()
    await record_event(
        session,
        company_id=company_id,
        user_id=user_id,
        entity_type="supplier",
        entity_id=supplier.id,
        event_type="created",
    )
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
        await record_event(
            session,
            company_id=company_id,
            user_id=user_id,
            entity_type="supplier",
            entity_id=supplier.id,
            event_type="updated",
            diff=diff,
        )
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
    supplier.deleted_at = datetime.now()
    await record_event(
        session,
        company_id=company_id,
        user_id=user_id,
        entity_type="supplier",
        entity_id=supplier.id,
        event_type="deleted",
    )
    await session.commit()
    return True


async def list_supplier_options(session: AsyncSession, company_id: int) -> list[Supplier]:
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
        )
        .scalars()
        .all()
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
        primaries = (
            (
                await session.execute(
                    select(SupplierContact).where(
                        SupplierContact.supplier_id == supplier_id,
                        SupplierContact.is_primary.is_(True),
                        SupplierContact.deleted_at.is_(None),
                    )
                )
            )
            .scalars()
            .all()
        )
        for p in primaries:
            p.is_primary = False
    contact = SupplierContact(company_id=company_id, supplier_id=supplier_id, **data)
    session.add(contact)
    await session.flush()
    await record_event(
        session,
        company_id=company_id,
        user_id=user_id,
        entity_type="supplier_contact",
        entity_id=contact.id,
        event_type="created",
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
            (
                await session.execute(
                    select(SupplierContact).where(
                        SupplierContact.supplier_id == contact.supplier_id,
                        SupplierContact.is_primary.is_(True),
                        SupplierContact.deleted_at.is_(None),
                        SupplierContact.id != contact_id,
                    )
                )
            )
            .scalars()
            .all()
        )
        for p in primaries:
            p.is_primary = False
    for k, v in data.items():
        setattr(contact, k, v)
    await record_event(
        session,
        company_id=company_id,
        user_id=user_id,
        entity_type="supplier_contact",
        entity_id=contact.id,
        event_type="updated",
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
    contact.deleted_at = datetime.now()
    await session.commit()
    return True


# ---------------------------------------------------------------------------
# Cost Centers
# ---------------------------------------------------------------------------


class CostCenterRow(NamedTuple):
    cost_center: CostCenter
    parent_name: str | None
    contract_count: int


async def list_cost_centers(
    session: AsyncSession,
    company_id: int,
    page: int,
    page_size: int,
    search: str | None,
    active_only: bool = False,
) -> tuple[list[CostCenterRow], int]:
    q = select(CostCenter).where(
        CostCenter.company_id == company_id,
        CostCenter.deleted_at.is_(None),
    )
    if search:
        term = f"%{search}%"
        q = q.where(or_(CostCenter.name.ilike(term), CostCenter.code.ilike(term)))
    if active_only:
        q = q.where(CostCenter.active.is_(True))

    total = await session.scalar(select(func.count()).select_from(q.subquery()))
    cost_centers = (
        (
            await session.execute(
                q.order_by(CostCenter.name.asc()).offset((page - 1) * page_size).limit(page_size)
            )
        )
        .scalars()
        .all()
    )

    if not cost_centers:
        return [], 0

    cost_center_ids = [c.id for c in cost_centers]
    parent_ids = [c.parent_id for c in cost_centers if c.parent_id]

    parent_names: dict[int, str] = {}
    if parent_ids:
        rows = (
            await session.execute(
                select(CostCenter.id, CostCenter.name).where(CostCenter.id.in_(parent_ids))
            )
        ).all()
        parent_names = {r.id: r.name for r in rows}

    contract_counts_rows = (
        await session.execute(
            select(Contract.cost_center_id, func.count().label("cnt"))
            .where(
                Contract.cost_center_id.in_(cost_center_ids),
                Contract.company_id == company_id,
                Contract.deleted_at.is_(None),
            )
            .group_by(Contract.cost_center_id)
        )
    ).all()
    contract_counts = {r.cost_center_id: r.cnt for r in contract_counts_rows}

    result = [
        CostCenterRow(
            c,
            parent_names.get(c.parent_id) if c.parent_id else None,
            contract_counts.get(c.id, 0),
        )
        for c in cost_centers
    ]
    return result, total or 0


async def get_cost_center(
    session: AsyncSession, company_id: int, cost_center_id: int
) -> tuple[CostCenter, str | None] | None:
    cost_center = await session.scalar(
        select(CostCenter).where(
            CostCenter.id == cost_center_id,
            CostCenter.company_id == company_id,
            CostCenter.deleted_at.is_(None),
        )
    )
    if not cost_center:
        return None
    parent_name = (
        await session.scalar(select(CostCenter.name).where(CostCenter.id == cost_center.parent_id))
        if cost_center.parent_id
        else None
    )
    return cost_center, parent_name


async def create_cost_center(
    session: AsyncSession, company_id: int, user_id: int, data: dict
) -> CostCenter:
    cost_center = CostCenter(company_id=company_id, **data)
    session.add(cost_center)
    await session.flush()
    await record_event(
        session,
        company_id=company_id,
        user_id=user_id,
        entity_type="cost_center",
        entity_id=cost_center.id,
        event_type="created",
    )
    await session.commit()
    await session.refresh(cost_center)
    return cost_center


async def update_cost_center(
    session: AsyncSession, company_id: int, user_id: int, cost_center_id: int, data: dict
) -> CostCenter | None:
    cost_center = await session.scalar(
        select(CostCenter).where(
            CostCenter.id == cost_center_id,
            CostCenter.company_id == company_id,
            CostCenter.deleted_at.is_(None),
        )
    )
    if not cost_center:
        return None
    if data.get("parent_id") == cost_center_id:
        data = {**data, "parent_id": None}
    old = {k: getattr(cost_center, k) for k in data}
    for k, v in data.items():
        setattr(cost_center, k, v)
    diff = compute_diff(old, data)
    if diff:
        await record_event(
            session,
            company_id=company_id,
            user_id=user_id,
            entity_type="cost_center",
            entity_id=cost_center.id,
            event_type="updated",
            diff=diff,
        )
    await session.commit()
    await session.refresh(cost_center)
    return cost_center


async def delete_cost_center(
    session: AsyncSession, company_id: int, user_id: int, cost_center_id: int
) -> bool:
    cost_center = await session.scalar(
        select(CostCenter).where(
            CostCenter.id == cost_center_id,
            CostCenter.company_id == company_id,
            CostCenter.deleted_at.is_(None),
        )
    )
    if not cost_center:
        return False
    cost_center.deleted_at = datetime.now()
    await record_event(
        session,
        company_id=company_id,
        user_id=user_id,
        entity_type="cost_center",
        entity_id=cost_center.id,
        event_type="deleted",
    )
    await session.commit()
    return True


async def list_cost_center_options(session: AsyncSession, company_id: int) -> list[CostCenter]:
    return list(
        (
            await session.execute(
                select(CostCenter)
                .where(
                    CostCenter.company_id == company_id,
                    CostCenter.active.is_(True),
                    CostCenter.deleted_at.is_(None),
                )
                .order_by(CostCenter.name.asc())
                .limit(200)
            )
        )
        .scalars()
        .all()
    )


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


async def _generate_contract_number(session: AsyncSession, company_id: int) -> str:
    year = date.today().year
    prefix = f"CTR-{year}-"
    count = (
        await session.scalar(
            select(func.count()).where(
                Contract.company_id == company_id,
                Contract.number.like(f"{prefix}%"),
                Contract.deleted_at.is_(None),
            )
        )
        or 0
    )
    return f"{prefix}{count + 1:04d}"


class ContractRow(NamedTuple):
    contract: Contract
    supplier_name: str | None
    responsible_name: str | None
    cost_center_name: str | None


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
        limit = today + timedelta(days=expiring_in_days)
        q = q.where(
            Contract.end_date.isnot(None),
            Contract.end_date >= today,
            Contract.end_date <= limit,
            Contract.status.in_(["ativo", "em_renovacao"]),
        )

    total = await session.scalar(select(func.count()).select_from(q.subquery()))
    contracts = (
        (
            await session.execute(
                q.order_by(Contract.end_date.asc().nullslast(), Contract.updated_at.desc())
                .offset((page - 1) * page_size)
                .limit(page_size)
            )
        )
        .scalars()
        .all()
    )

    if not contracts:
        return [], total or 0

    supplier_ids = [c.supplier_id for c in contracts if c.supplier_id]
    responsible_ids = [c.responsible_user_id for c in contracts if c.responsible_user_id]

    supplier_names: dict[int, str] = {}
    if supplier_ids:
        rows = (
            await session.execute(
                select(Supplier.id, Supplier.name).where(Supplier.id.in_(supplier_ids))
            )
        ).all()
        supplier_names = {r.id: r.name for r in rows}

    responsible_names: dict[int, str] = {}
    if responsible_ids:
        rows = (
            await session.execute(select(User.id, User.name).where(User.id.in_(responsible_ids)))
        ).all()
        responsible_names = {r.id: r.name for r in rows}

    cost_center_ids = [c.cost_center_id for c in contracts if c.cost_center_id]
    cost_center_names: dict[int, str] = {}
    if cost_center_ids:
        rows = (
            await session.execute(
                select(CostCenter.id, CostCenter.name).where(CostCenter.id.in_(cost_center_ids))
            )
        ).all()
        cost_center_names = {r.id: r.name for r in rows}

    result = [
        ContractRow(
            c,
            supplier_names.get(c.supplier_id) if c.supplier_id else None,
            responsible_names.get(c.responsible_user_id) if c.responsible_user_id else None,
            cost_center_names.get(c.cost_center_id) if c.cost_center_id else None,
        )
        for c in contracts
    ]
    return result, total or 0


async def get_contract(
    session: AsyncSession, company_id: int, contract_id: int
) -> (
    tuple[  # noqa: E501
        Contract,
        str | None,
        str | None,
        str | None,
        list[ContractAmendment],
        list[tuple[ContractApprovalStep, str | None]],  # noqa: E501
    ]
    | None
):
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
    cost_center_name = (
        await session.scalar(
            select(CostCenter.name).where(CostCenter.id == contract.cost_center_id)
        )
        if contract.cost_center_id
        else None
    )
    amendments = list(
        (
            await session.execute(
                select(ContractAmendment)
                .where(ContractAmendment.contract_id == contract_id)
                .order_by(ContractAmendment.created_at.desc())
            )
        )
        .scalars()
        .all()
    )
    raw_steps = list(
        (
            await session.execute(
                select(ContractApprovalStep)
                .where(ContractApprovalStep.contract_id == contract_id)
                .order_by(ContractApprovalStep.step_order.asc())
            )
        )
        .scalars()
        .all()
    )

    approver_ids = [s.approver_user_id for s in raw_steps]
    approver_names: dict[int, str] = {}
    if approver_ids:
        rows = (
            await session.execute(select(User.id, User.name).where(User.id.in_(approver_ids)))
        ).all()
        approver_names = {r.id: r.name for r in rows}

    steps = [(s, approver_names.get(s.approver_user_id)) for s in raw_steps]
    return contract, supplier_name, responsible_name, cost_center_name, amendments, steps


async def create_contract(
    session: AsyncSession,
    company_id: int,
    user_id: int,
    data: dict,
    approver_user_ids: list[int],
) -> Contract:
    if not data.get("number"):
        data["number"] = await _generate_contract_number(session, company_id)

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

    await record_event(
        session,
        company_id=company_id,
        user_id=user_id,
        entity_type="contract",
        entity_id=contract.id,
        event_type="created",
    )
    await session.commit()
    await session.refresh(contract)
    return contract


async def update_contract(
    session: AsyncSession,
    company_id: int,
    user_id: int,
    contract_id: int,
    data: dict,
    approver_user_ids: list[int] | None = None,
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

    fields = {k: v for k, v in data.items() if k != "approver_user_ids"}
    old = {k: getattr(contract, k) for k in fields}
    for k, v in fields.items():
        setattr(contract, k, v)
    diff = compute_diff(old, fields)
    if diff:
        await record_event(
            session,
            company_id=company_id,
            user_id=user_id,
            entity_type="contract",
            entity_id=contract.id,
            event_type="updated",
            diff=diff,
        )

    if approver_user_ids is not None and contract.status == "rascunho":
        existing = (
            (
                await session.execute(
                    select(ContractApprovalStep).where(
                        ContractApprovalStep.contract_id == contract_id,
                    )
                )
            )
            .scalars()
            .all()
        )
        for step in existing:
            await session.delete(step)
        await session.flush()
        for i, uid in enumerate(approver_user_ids, start=1):
            session.add(
                ContractApprovalStep(
                    company_id=company_id,
                    contract_id=contract_id,
                    step_order=i,
                    approver_user_id=uid,
                )
            )

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
        company_id=company_id,
        user_id=user_id,
        entity_type="contract",
        entity_id=contract.id,
        event_type="status_changed",
        diff={"from": old_status, "to": new_status, "comment": comment},
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
    contract.deleted_at = datetime.now()
    await record_event(
        session,
        company_id=company_id,
        user_id=user_id,
        entity_type="contract",
        entity_id=contract.id,
        event_type="deleted",
    )
    await session.commit()
    return True


async def submit_contract(
    session: AsyncSession,
    company_id: int,
    user_id: int,
    contract_id: int,
    approver_user_ids: list[int] | None,
) -> Contract | None:
    """Envia contrato para aprovação; aceito apenas quando status é rascunho."""
    contract = await session.scalar(
        select(Contract).where(
            Contract.id == contract_id,
            Contract.company_id == company_id,
            Contract.deleted_at.is_(None),
        )
    )
    if not contract or contract.status != "rascunho":
        return None

    existing_steps = (
        (
            await session.execute(
                select(ContractApprovalStep).where(
                    ContractApprovalStep.contract_id == contract_id,
                )
            )
        )
        .scalars()
        .all()
    )
    for step in existing_steps:
        await session.delete(step)
    await session.flush()

    ids_to_use = approver_user_ids if approver_user_ids is not None else []
    for i, uid in enumerate(ids_to_use, start=1):
        session.add(
            ContractApprovalStep(
                company_id=company_id,
                contract_id=contract_id,
                step_order=i,
                approver_user_id=uid,
            )
        )

    if ids_to_use:
        contract.status = "aguardando_aprovacao"
    else:
        contract.status = "ativo"

    await record_event(
        session,
        company_id=company_id,
        user_id=user_id,
        entity_type="contract",
        entity_id=contract_id,
        event_type="submitted",
        diff={"new_status": contract.status},
    )
    await session.commit()
    await session.refresh(contract)
    return contract


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

    if data.get("new_end_date"):
        contract.end_date = data["new_end_date"]
    if data.get("new_value") is not None:
        contract.total_value = data["new_value"]

    await session.flush()
    await record_event(
        session,
        company_id=company_id,
        user_id=user_id,
        entity_type="contract",
        entity_id=contract_id,
        event_type="amendment_added",
        diff={"type": data["amendment_type"]},
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
    step.decided_at = datetime.now()

    if not approved:
        contract.status = "rascunho"
        await record_event(
            session,
            company_id=company_id,
            user_id=user_id,
            entity_type="contract",
            entity_id=contract_id,
            event_type="rejected",
            diff={"comment": comment},
        )
    else:
        await session.flush()
        pending = await session.scalar(
            select(func.count()).where(
                ContractApprovalStep.contract_id == contract_id,
                ContractApprovalStep.status == "pendente",
            )
        )
        if (pending or 0) == 0:
            contract.status = "ativo"
            await record_event(
                session,
                company_id=company_id,
                user_id=user_id,
                entity_type="contract",
                entity_id=contract_id,
                event_type="approved",
            )
        else:
            await record_event(
                session,
                company_id=company_id,
                user_id=user_id,
                entity_type="contract",
                entity_id=contract_id,
                event_type="step_approved",
                diff={"step_order": step.step_order},
            )

    await session.commit()
    await session.refresh(contract)
    return contract


# ---------------------------------------------------------------------------
# History
# ---------------------------------------------------------------------------


class HistoryRow(NamedTuple):
    event: AuditEvent
    user_name: str | None


async def list_contract_history(
    session: AsyncSession,
    company_id: int,
    contract_id: int,
) -> list[HistoryRow]:
    contract = await session.scalar(
        select(Contract).where(
            Contract.id == contract_id,
            Contract.company_id == company_id,
            Contract.deleted_at.is_(None),
        )
    )
    if not contract:
        return []

    events = list(
        (
            await session.execute(
                select(AuditEvent)
                .where(
                    AuditEvent.company_id == company_id,
                    AuditEvent.entity_type == "contract",
                    AuditEvent.entity_id == contract_id,
                )
                .order_by(AuditEvent.created_at.desc())
            )
        )
        .scalars()
        .all()
    )

    user_ids = list({e.user_id for e in events if e.user_id is not None})
    user_names: dict[int, str] = {}
    if user_ids:
        rows = (
            await session.execute(select(User.id, User.name).where(User.id.in_(user_ids)))
        ).all()
        user_names = {r.id: r.name for r in rows}

    return [
        HistoryRow(e, user_names.get(e.user_id) if e.user_id is not None else e.actor_name)
        for e in events
    ]


# ---------------------------------------------------------------------------
# Expiry alerts job
# ---------------------------------------------------------------------------


async def run_expiry_alerts(session: AsyncSession) -> int:
    """
    Varre todos os tenants em busca de contratos próximos do vencimento
    e cria notificações para o responsável. Também transita para em_renovacao
    contratos vencidos com auto_renew=True.
    Retorna o número de notificações criadas.
    """
    from app.domain.notifications.service import create_notification

    today = date.today()
    notified = 0

    active_contracts = list(
        (
            await session.execute(
                select(Contract).where(
                    Contract.deleted_at.is_(None),
                    Contract.status.in_(["ativo", "em_renovacao"]),
                    Contract.end_date.isnot(None),
                    Contract.responsible_user_id.isnot(None),
                )
            )
        )
        .scalars()
        .all()
    )

    for contract in active_contracts:
        days = (contract.end_date - today).days  # type: ignore[operator]

        if contract.auto_renew and days < 0 and contract.status == "ativo":
            contract.status = "em_renovacao"
            await record_event(
                session,
                company_id=contract.company_id,
                user_id=0,
                entity_type="contract",
                entity_id=contract.id,
                event_type="status_changed",
                diff={"from": "ativo", "to": "em_renovacao", "comment": "auto_renew"},
            )
            continue

        if 0 <= days <= contract.alert_days:
            if days == 0:
                body = "O contrato vence hoje."
            elif days == 1:
                body = "O contrato vence amanhã."
            else:
                body = f"O contrato vence em {days} dias ({contract.end_date})."

            await create_notification(
                session,
                company_id=contract.company_id,
                user_id=contract.responsible_user_id,  # type: ignore[arg-type]
                title=f"Contrato próximo do vencimento: {contract.title}",
                body=body,
                category="warning",
                entity_type="contract",
                entity_id=contract.id,
            )
            notified += 1

    await session.commit()
    return notified
