from datetime import datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Contract, CostCenter, Employee, EmployeeExternalId, EmployeePayslip, Supplier
from app.services.external_import import upsert_by_external_id

ContractRow = tuple[Contract, Supplier | None, CostCenter | None]
PayslipRow = tuple[EmployeePayslip, Employee]

# Fonte dos cadastros espelhados vindos do erpsolid (Fornecedores/Centros de
# custo/Funcionários) — "erpsolid manda": nunca editado manualmente na tela do
# GEOP, só re-sincronizado. Mesmo `import_source="geop"` que o erpsolid usa pro
# sentido contrário, só que aqui.
ERPSOLID_IMPORT_SOURCE = "erpsolid"


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


async def upsert_suppliers_from_erpsolid(
    session: AsyncSession, company_id: int, items: list[dict]
) -> int:
    rows = [{**item, "import_source": ERPSOLID_IMPORT_SOURCE} for item in items]
    id_map = await upsert_by_external_id(
        session, Supplier, company_id, ERPSOLID_IMPORT_SOURCE, rows
    )
    return len(id_map)


async def upsert_cost_centers_from_erpsolid(
    session: AsyncSession, company_id: int, items: list[dict]
) -> int:
    rows = [{**item, "import_source": ERPSOLID_IMPORT_SOURCE} for item in items]
    id_map = await upsert_by_external_id(
        session, CostCenter, company_id, ERPSOLID_IMPORT_SOURCE, rows
    )
    return len(id_map)


async def upsert_employees_from_erpsolid(
    session: AsyncSession, company_id: int, items: list[dict]
) -> int:
    """Usa `EmployeeExternalId` (system="erpsolid") pra achar o Employee local já
    vinculado, em vez do padrão de coluna `import_source`/`external_id` direta
    usado em Supplier/CostCenter acima — é a tabela de vínculo que este domínio já
    usa pra qualquer sistema externo (`app/domain/employees/service.py`), não faz
    sentido duplicar como coluna só pra esta integração."""
    external_ids = [item["external_id"] for item in items]
    existing: dict[str, int] = {}
    if external_ids:
        result = await session.execute(
            select(EmployeeExternalId.external_id, EmployeeExternalId.employee_id).where(
                EmployeeExternalId.company_id == company_id,
                EmployeeExternalId.system == ERPSOLID_IMPORT_SOURCE,
                EmployeeExternalId.external_id.in_(external_ids),
            )
        )
        existing = {ext_id: employee_id for ext_id, employee_id in result.all()}

    count = 0
    for item in items:
        row = dict(item)
        external_id = row.pop("external_id")
        # ErpsolidEmployeePush.email -> Employee.personal_email (o schema de push usa
        # o nome genérico "email"; o model local já usa "personal_email" pra separar
        # do e-mail de User, ver docstring de `Employee`).
        row["personal_email"] = row.pop("email", None)
        employee_id = existing.get(external_id)
        if employee_id is not None:
            employee = await session.get(Employee, employee_id)
            if employee is not None:
                for key, value in row.items():
                    setattr(employee, key, value)
                count += 1
                continue
        employee = Employee(company_id=company_id, **row)
        session.add(employee)
        await session.flush()
        session.add(
            EmployeeExternalId(
                company_id=company_id,
                employee_id=employee.id,
                system=ERPSOLID_IMPORT_SOURCE,
                external_id=external_id,
            )
        )
        count += 1
    return count
