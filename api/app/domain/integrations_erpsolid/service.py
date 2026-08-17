from datetime import datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Contract, CostCenter, Employee, EmployeePayslip, Supplier

ContractRow = tuple[Contract, Supplier | None, CostCenter | None]
PayslipRow = tuple[EmployeePayslip, Employee]


async def list_contracts_for_erpsolid(
    session: AsyncSession,
    company_id: int,
    since: datetime | None = None,
) -> list[ContractRow]:
    """Contract + Supplier/CostCenter embutidos (sem round-trip extra pro erpsolid
    montar um Payable). Contract não tem `relationship()` pra Supplier/CostCenter
    nesse codebase — segue o mesmo padrão de join manual do resto do domínio
    `contracts` (ver `contracts/service.py::get_contract`)."""
    query = select(Contract).where(Contract.company_id == company_id, Contract.deleted_at.is_(None))
    if since is not None:
        query = query.where(Contract.updated_at >= since)
    contracts = list((await session.execute(query.order_by(Contract.id))).scalars().all())
    if not contracts:
        return []

    supplier_ids = {c.supplier_id for c in contracts if c.supplier_id}
    cost_center_ids = {c.cost_center_id for c in contracts if c.cost_center_id}

    suppliers: dict[int, Supplier] = {}
    if supplier_ids:
        supplier_rows = (
            await session.execute(select(Supplier).where(Supplier.id.in_(supplier_ids)))
        ).scalars()
        suppliers = {s.id: s for s in supplier_rows}

    cost_centers: dict[int, CostCenter] = {}
    if cost_center_ids:
        cost_center_rows = (
            await session.execute(select(CostCenter).where(CostCenter.id.in_(cost_center_ids)))
        ).scalars()
        cost_centers = {cc.id: cc for cc in cost_center_rows}

    return [
        (
            c,
            suppliers.get(c.supplier_id) if c.supplier_id else None,
            cost_centers.get(c.cost_center_id) if c.cost_center_id else None,
        )
        for c in contracts
    ]


async def list_employee_payslips_for_erpsolid(
    session: AsyncSession,
    company_id: int,
    since: datetime | None = None,
) -> list[PayslipRow]:
    # EmployeePayslip não tem `updated_at` (só `created_at`/`deleted_at`) — diferente
    # de Contract, que usa TimestampMixin. Como o valor é gravado uma vez pelo sync
    # e não é editado depois, filtrar por `created_at` cobre o caso de incremental.
    query = select(EmployeePayslip).where(
        EmployeePayslip.company_id == company_id, EmployeePayslip.deleted_at.is_(None)
    )
    if since is not None:
        query = query.where(EmployeePayslip.created_at >= since)
    payslips = list((await session.execute(query.order_by(EmployeePayslip.id))).scalars().all())
    if not payslips:
        return []

    employee_ids = {p.employee_id for p in payslips}
    rows = (await session.execute(select(Employee).where(Employee.id.in_(employee_ids)))).scalars()
    employees = {e.id: e for e in rows}

    return [(p, employees[p.employee_id]) for p in payslips if p.employee_id in employees]
