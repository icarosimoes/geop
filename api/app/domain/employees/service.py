from datetime import datetime
from typing import NamedTuple

from pydantic import ValidationError
from sqlalchemy import and_, func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.audit import compute_diff, record_event
from app.core.config import get_settings
from app.core.storage import build_object_key, upload_file, validate_file
from app.domain.employees.schemas import EmployeeCreate
from app.models import Employee, EmployeeExternalId, Sector

IMPORT_FIELDS = (
    "name",
    "cpf",
    "rg",
    "birth_date",
    "phone",
    "personal_email",
    "address_street",
    "address_number",
    "address_complement",
    "address_neighborhood",
    "address_city",
    "address_state",
    "address_zip",
    "status",
    "job_title",
    "hire_date",
    "termination_date",
    "registration_number",
    "salary",
)


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


async def get_sector_name(session: AsyncSession, sector_id: int | None) -> str | None:
    if not sector_id:
        return None
    return await session.scalar(
        select(Sector.name).where(Sector.id == sector_id, Sector.deleted_at.is_(None))
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
    job_title: str | None = None,
    hire_date: str | None = None,
    termination_date: str | None = None,
    registration_number: str | None = None,
    salary: float | None = None,
    sector_id: int | None = None,
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
        job_title=job_title,
        hire_date=hire_date,
        termination_date=termination_date,
        registration_number=registration_number,
        salary=salary,
        sector_id=sector_id,
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


async def upload_avatar(
    session: AsyncSession,
    company_id: int,
    actor_id: int,
    employee_id: int,
    *,
    data: bytes,
    filename: str,
    content_type: str,
) -> Employee | None:
    record = await get_employee(session, company_id, employee_id)
    if record is None:
        return None

    error = validate_file(filename, content_type, len(data), data)
    if error:
        raise ValueError(error)

    if content_type not in {"image/jpeg", "image/png", "image/webp"}:
        raise ValueError("Avatar deve ser JPEG, PNG ou WebP")

    settings = get_settings()
    key = build_object_key(company_id, "employee-avatar", employee_id, filename)
    upload_file(data, key, content_type)

    old_url = record.avatar_url
    record.avatar_url = f"{settings.s3_public_url}/{settings.s3_bucket}/{key}"

    await record_event(
        session,
        company_id=company_id,
        user_id=actor_id,
        entity_type="employee",
        entity_id=record.id,
        event_type="update",
        diff={"avatar_url": {"from": old_url or "", "to": record.avatar_url}},
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


async def import_employees(
    session: AsyncSession,
    company_id: int,
    actor_id: int,
    rows: list[dict[str, str]],
) -> tuple[int, int, list[dict]]:
    """Cria funcionários a partir de linhas de CSV já parseadas.

    Cada linha é validada com o mesmo schema `EmployeeCreate` usado pelo
    endpoint de criação individual (CPF, datas e CEP passam pelas mesmas
    regras). Uma linha inválida não interrompe as demais.
    """
    created = 0
    failed = 0
    results: list[dict] = []

    for index, raw_row in enumerate(rows, start=1):
        row = {
            field: raw_row[field].strip()
            for field in IMPORT_FIELDS
            if raw_row.get(field, "").strip()
        }
        name = row.get("name")
        try:
            payload = EmployeeCreate(**row)
        except ValidationError as exc:
            failed += 1
            message = "; ".join(err["msg"] for err in exc.errors())
            results.append({"row": index, "ok": False, "name": name, "error": message})
            continue

        try:
            record = await create_employee(
                session,
                company_id,
                actor_id,
                **payload.model_dump(),
            )
        except ValueError as exc:
            failed += 1
            results.append({"row": index, "ok": False, "name": name, "error": str(exc)})
            continue

        created += 1
        results.append({"row": index, "ok": True, "name": record.name, "id": record.id})

    return created, failed, results
