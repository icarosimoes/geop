from datetime import datetime
from typing import NamedTuple

from sqlalchemy import and_, func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.audit import compute_diff, record_event
from app.models import Employee, EmployeeExternalId


class EmployeeRow(NamedTuple):
    employee: Employee
    user_name: str | None


async def list_employees(
    session: AsyncSession,
    company_id: int,
    page: int,
    page_size: int,
    status: str | None = None,
) -> tuple[list[Employee], int]:
    filters = [Employee.company_id == company_id, Employee.deleted_at.is_(None)]
    if status:
        filters.append(Employee.status == status)

    total = await session.scalar(
        select(func.count(Employee.id)).where(and_(*filters))
    )

    rows = (
        await session.execute(
            select(Employee)
            .where(and_(*filters))
            .order_by(Employee.name)
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
    ).scalars()

    return list(rows), total or 0


async def get_employee(
    session: AsyncSession, company_id: int, employee_id: int
) -> Employee | None:
    return await session.scalar(
        select(Employee).where(
            Employee.id == employee_id,
            Employee.company_id == company_id,
            Employee.deleted_at.is_(None),
        )
    )


async def create_employee(
    session: AsyncSession,
    company_id: int,
    actor_id: int,
    *,
    name: str,
    cpf: str | None = None,
    rg: str | None = None,
    birth_date: str | None = None,
    phone: str | None = None,
    personal_email: str | None = None,
    address_street: str | None = None,
    address_number: str | None = None,
    address_complement: str | None = None,
    address_neighborhood: str | None = None,
    address_city: str | None = None,
    address_state: str | None = None,
    address_zip: str | None = None,
    status: str = "active",
    user_id: int | None = None,
) -> Employee:
    record = Employee(
        company_id=company_id,
        name=name,
        cpf=cpf,
        rg=rg,
        birth_date=birth_date,
        phone=phone,
        personal_email=personal_email,
        address_street=address_street,
        address_number=address_number,
        address_complement=address_complement,
        address_neighborhood=address_neighborhood,
        address_city=address_city,
        address_state=address_state,
        address_zip=address_zip,
        status=status,
        user_id=user_id,
    )
    session.add(record)
    try:
        await session.flush()
    except IntegrityError as exc:
        await session.rollback()
        raise ValueError("CPF já cadastrado para outro funcionário nesta empresa.") from exc
    await record_event(
        session,
        company_id=company_id,
        user_id=actor_id,
        entity_type="employee",
        entity_id=record.id,
        event_type="create",
    )
    await session.commit()
    await session.refresh(record)
    return record


async def update_employee(
    session: AsyncSession, company_id: int, actor_id: int, employee_id: int, updates: dict
) -> Employee | None:
    record = await get_employee(session, company_id, employee_id)
    if record is None:
        return None

    before = {k: str(getattr(record, k)) for k in updates}
    for field, value in updates.items():
        setattr(record, field, value)

    diff = compute_diff(before, {k: str(v) for k, v in updates.items()})
    if diff:
        await record_event(
            session,
            company_id=company_id,
            user_id=actor_id,
            entity_type="employee",
            entity_id=record.id,
            event_type="update",
            diff=diff,
        )
    try:
        await session.commit()
    except IntegrityError as exc:
        await session.rollback()
        raise ValueError("CPF já cadastrado para outro funcionário nesta empresa.") from exc
    await session.refresh(record)
    return record


async def delete_employee(
    session: AsyncSession, company_id: int, actor_id: int, employee_id: int
) -> bool:
    record = await get_employee(session, company_id, employee_id)
    if record is None:
        return False

    record.deleted_at = datetime.now()
    await record_event(
        session,
        company_id=company_id,
        user_id=actor_id,
        entity_type="employee",
        entity_id=record.id,
        event_type="delete",
    )
    await session.commit()
    return True


async def search_employees(
    session: AsyncSession, company_id: int, query: str = ""
) -> list[dict]:
    """Search employees by name (for autocomplete/selects)."""
    filters = [
        Employee.company_id == company_id,
        Employee.deleted_at.is_(None),
        Employee.status == "active",
    ]
    if query:
        filters.append(Employee.name.ilike(f"%{query}%"))

    rows = (
        await session.execute(
            select(Employee)
            .where(*filters)
            .order_by(Employee.name)
            .limit(20)
        )
    ).scalars()

    return [{"id": r.id, "name": r.name} for r in rows]


async def get_employee_external_ids(
    session: AsyncSession, company_id: int, employee_id: int
) -> list[EmployeeExternalId]:
    """Get all external IDs for an employee."""
    rows = (
        await session.execute(
            select(EmployeeExternalId).where(
                EmployeeExternalId.company_id == company_id,
                EmployeeExternalId.employee_id == employee_id,
            )
        )
    ).scalars()
    return list(rows)


async def create_employee_external_id(
    session: AsyncSession,
    company_id: int,
    actor_id: int,
    employee_id: int,
    *,
    system: str,
    external_id: str,
) -> EmployeeExternalId:
    """Create an external ID link for an employee."""
    record = EmployeeExternalId(
        company_id=company_id,
        employee_id=employee_id,
        system=system,
        external_id=external_id,
    )
    session.add(record)
    try:
        await session.flush()
    except IntegrityError as exc:
        await session.rollback()
        raise ValueError("Este external_id já está vinculado a outro funcionário.") from exc
    await record_event(
        session,
        company_id=company_id,
        user_id=actor_id,
        entity_type="employee_external_id",
        entity_id=record.id,
        event_type="create",
    )
    await session.commit()
    await session.refresh(record)
    return record


async def delete_employee_external_id(
    session: AsyncSession, company_id: int, actor_id: int, employee_id: int, external_id_id: int
) -> bool:
    """Delete an external ID link, scoped to the owning employee."""
    record = await session.scalar(
        select(EmployeeExternalId).where(
            EmployeeExternalId.id == external_id_id,
            EmployeeExternalId.employee_id == employee_id,
            EmployeeExternalId.company_id == company_id,
        )
    )
    if record is None:
        return False
    await session.delete(record)
    await record_event(
        session,
        company_id=company_id,
        user_id=actor_id,
        entity_type="employee_external_id",
        entity_id=external_id_id,
        event_type="delete",
    )
    await session.commit()
    return True
