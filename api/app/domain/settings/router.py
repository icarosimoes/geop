from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm.attributes import flag_modified

from app.core.audit import record_event
from app.core.dependencies import require_session
from app.core.permissions import require_permission
from app.domain.auth.repository import AuthenticatedUser
from app.models import Company, CompanySetting

router = APIRouter(prefix="/settings", tags=["settings"])


async def _get_setting(session: AsyncSession, company_id: int, key: str) -> CompanySetting | None:
    return (
        await session.execute(
            select(CompanySetting).where(
                CompanySetting.company_id == company_id,
                CompanySetting.key == key,
            )
        )
    ).scalar_one_or_none()


async def get_company_setting(session: AsyncSession, company_id: int, key: str) -> dict:
    row = await _get_setting(session, company_id, key)
    return row.value if row else {}


# ── Evolution API ──


class EvolutionConfig(BaseModel):
    api_url: str
    api_key: str
    instance: str


class EvolutionRead(BaseModel):
    has_credentials: bool
    api_url: str | None = None
    instance: str | None = None


@router.get("/evolution", response_model=EvolutionRead)
async def get_evolution(
    user: Annotated[AuthenticatedUser, require_permission("settings.view")],
    session: Annotated[AsyncSession, Depends(require_session)],
) -> EvolutionRead:
    row = await _get_setting(session, user.company_id, "evolution")
    value = row.value if row else {}
    if not value.get("api_key"):
        return EvolutionRead(has_credentials=False)
    return EvolutionRead(
        has_credentials=True,
        api_url=value.get("api_url"),
        instance=value.get("instance"),
    )


@router.post("/evolution", response_model=EvolutionRead)
async def save_evolution(
    body: EvolutionConfig,
    user: Annotated[AuthenticatedUser, require_permission("settings.edit")],
    session: Annotated[AsyncSession, Depends(require_session)],
) -> EvolutionRead:
    row = await _get_setting(session, user.company_id, "evolution")
    new_value = {"api_url": body.api_url, "api_key": body.api_key, "instance": body.instance}
    if row:
        row.value = new_value
        flag_modified(row, "value")
    else:
        session.add(CompanySetting(company_id=user.company_id, key="evolution", value=new_value))
    await session.commit()
    return EvolutionRead(has_credentials=True, api_url=body.api_url, instance=body.instance)


class EvolutionTestSend(BaseModel):
    to: str
    text: str


class EvolutionStatus(BaseModel):
    connected: bool
    state: str | None = None
    detail: str | None = None


@router.get("/evolution/status", response_model=EvolutionStatus)
async def evolution_status(
    user: Annotated[AuthenticatedUser, require_permission("settings.view")],
    session: Annotated[AsyncSession, Depends(require_session)],
) -> EvolutionStatus:
    row = await _get_setting(session, user.company_id, "evolution")
    value = row.value if row else {}
    if not value.get("api_key"):
        return EvolutionStatus(connected=False, detail="Credenciais não configuradas")
    from app.integrations.evolution import check_connection

    result = await check_connection(
        api_url=value["api_url"],
        api_key=value["api_key"],
        instance=value["instance"],
    )
    state = result.get("state") or result.get("instance", {}).get("state", "unknown")
    return EvolutionStatus(connected=(state == "open"), state=state)


@router.post("/evolution/test")
async def evolution_test_send(
    body: EvolutionTestSend,
    user: Annotated[AuthenticatedUser, require_permission("settings.edit")],
    session: Annotated[AsyncSession, Depends(require_session)],
) -> dict:
    row = await _get_setting(session, user.company_id, "evolution")
    value = row.value if row else {}
    if not value.get("api_key"):
        raise HTTPException(status_code=422, detail={"code": "not_configured"})
    from app.integrations.evolution import send_text

    result = await send_text(
        api_url=value["api_url"],
        api_key=value["api_key"],
        instance=value["instance"],
        to=body.to,
        text=body.text,
    )
    if result is None:
        raise HTTPException(status_code=502, detail={"code": "send_failed"})
    return {"status": "sent", "response": result}


# ── Brevo (E-mail transacional) ──


class BrevoConfig(BaseModel):
    api_key: str
    from_address: str
    from_name: str


class BrevoRead(BaseModel):
    has_credentials: bool
    from_address: str | None = None
    from_name: str | None = None


@router.get("/brevo", response_model=BrevoRead)
async def get_brevo(
    user: Annotated[AuthenticatedUser, require_permission("settings.view")],
    session: Annotated[AsyncSession, Depends(require_session)],
) -> BrevoRead:
    row = await _get_setting(session, user.company_id, "brevo")
    value = row.value if row else {}
    if not value.get("api_key"):
        return BrevoRead(has_credentials=False)
    return BrevoRead(
        has_credentials=True,
        from_address=value.get("from_address"),
        from_name=value.get("from_name"),
    )


@router.post("/brevo", response_model=BrevoRead)
async def save_brevo(
    body: BrevoConfig,
    user: Annotated[AuthenticatedUser, require_permission("settings.edit")],
    session: Annotated[AsyncSession, Depends(require_session)],
) -> BrevoRead:
    row = await _get_setting(session, user.company_id, "brevo")
    new_value = {
        "api_key": body.api_key,
        "from_address": body.from_address,
        "from_name": body.from_name,
    }
    if row:
        row.value = new_value
        flag_modified(row, "value")
    else:
        session.add(CompanySetting(company_id=user.company_id, key="brevo", value=new_value))
    await session.commit()
    return BrevoRead(has_credentials=True, from_address=body.from_address, from_name=body.from_name)


# ── Destinatários de notificação por módulo ──

VALID_MODULES = [
    "occurrences",
    "fiscal_requests",
    "meetings",
    "shift_reports",
    "procedures",
    "inspections",
    "maintenance",
    "modules",
]


class ModuleRecipientsOut(BaseModel):
    module: str
    user_ids: list[int]


class ModuleRecipientsUpdate(BaseModel):
    user_ids: list[int]


async def get_module_recipients(
    session: AsyncSession,
    company_id: int,
    module: str,
) -> list[int]:
    data = await get_company_setting(session, company_id, "notification_recipients")
    return data.get(module, [])


@router.get("/notification-recipients", response_model=list[ModuleRecipientsOut])
async def list_all_recipients(
    user: Annotated[AuthenticatedUser, require_permission("settings.view")],
    session: Annotated[AsyncSession, Depends(require_session)],
) -> list[ModuleRecipientsOut]:
    data = await get_company_setting(session, user.company_id, "notification_recipients")
    return [ModuleRecipientsOut(module=mod, user_ids=data.get(mod, [])) for mod in VALID_MODULES]


@router.put(
    "/notification-recipients/{module}",
    response_model=ModuleRecipientsOut,
)
async def update_module_recipients(
    module: str,
    body: ModuleRecipientsUpdate,
    user: Annotated[AuthenticatedUser, require_permission("settings.edit")],
    session: Annotated[AsyncSession, Depends(require_session)],
) -> ModuleRecipientsOut:
    if module not in VALID_MODULES:
        raise HTTPException(status_code=400, detail={"code": "invalid_module"})
    row = await _get_setting(session, user.company_id, "notification_recipients")
    if row:
        value = dict(row.value)
        value[module] = body.user_ids
        row.value = value
        flag_modified(row, "value")
    else:
        session.add(
            CompanySetting(
                company_id=user.company_id,
                key="notification_recipients",
                value={module: body.user_ids},
            )
        )
    await session.commit()
    return ModuleRecipientsOut(module=module, user_ids=body.user_ids)


# ── Categorias de OS ──


class CategoryList(BaseModel):
    items: list[str]


class CategoryAdd(BaseModel):
    name: str


@router.get("/work-order-categories", response_model=CategoryList)
async def get_work_order_categories(
    user: Annotated[AuthenticatedUser, require_permission("settings.view")],
    session: Annotated[AsyncSession, Depends(require_session)],
) -> CategoryList:
    row = await _get_setting(session, user.company_id, "work_order_categories")
    items = row.value.get("items", []) if row else []
    return CategoryList(items=sorted(items))


@router.post("/work-order-categories", response_model=CategoryList)
async def add_work_order_category(
    body: CategoryAdd,
    user: Annotated[AuthenticatedUser, require_permission("settings.edit")],
    session: Annotated[AsyncSession, Depends(require_session)],
) -> CategoryList:
    name = body.name.strip()
    if not name:
        raise HTTPException(status_code=422, detail={"code": "empty_name"})
    row = await _get_setting(session, user.company_id, "work_order_categories")
    if row:
        items = list(row.value.get("items", []))
        if name not in items:
            items.append(name)
        row.value = {"items": items}
        flag_modified(row, "value")
    else:
        session.add(
            CompanySetting(
                company_id=user.company_id,
                key="work_order_categories",
                value={"items": [name]},
            )
        )
    await session.commit()
    return CategoryList(items=sorted(row.value["items"] if row else [name]))


@router.delete("/work-order-categories/{name}")
async def delete_work_order_category(
    name: str,
    user: Annotated[AuthenticatedUser, require_permission("settings.edit")],
    session: Annotated[AsyncSession, Depends(require_session)],
) -> CategoryList:
    row = await _get_setting(session, user.company_id, "work_order_categories")
    if not row:
        return CategoryList(items=[])
    items = [i for i in row.value.get("items", []) if i != name]
    row.value = {"items": items}
    flag_modified(row, "value")
    await session.commit()
    return CategoryList(items=sorted(items))


# ── Ponto e banco de horas ──


class TimeclockSettings(BaseModel):
    overtime_paid_in_cash: bool = False
    # Salário-base por cargo (job_title), usado como alternativa/fallback ao
    # salário individual do funcionário no cálculo do valor da hora extra —
    # ver `_resolve_salary` em mirror.py.
    cargo_salaries: dict[str, float] = {}


@router.get("/timeclock", response_model=TimeclockSettings)
async def get_timeclock_settings(
    user: Annotated[AuthenticatedUser, require_permission("settings.view")],
    session: Annotated[AsyncSession, Depends(require_session)],
) -> TimeclockSettings:
    value = await get_company_setting(session, user.company_id, "timeclock")
    return TimeclockSettings(
        overtime_paid_in_cash=value.get("overtime_paid_in_cash", False),
        cargo_salaries=value.get("cargo_salaries", {}),
    )


@router.post("/timeclock", response_model=TimeclockSettings)
async def save_timeclock_settings(
    body: TimeclockSettings,
    user: Annotated[AuthenticatedUser, require_permission("settings.edit")],
    session: Annotated[AsyncSession, Depends(require_session)],
) -> TimeclockSettings:
    row = await _get_setting(session, user.company_id, "timeclock")
    new_value = {
        "overtime_paid_in_cash": body.overtime_paid_in_cash,
        "cargo_salaries": body.cargo_salaries,
    }
    if row:
        row.value = new_value
        flag_modified(row, "value")
    else:
        session.add(CompanySetting(company_id=user.company_id, key="timeclock", value=new_value))
    await session.commit()
    return body


# ── Dados do Estabelecimento ──


class CompanyRead(BaseModel):
    id: int
    name: str
    slug: str
    email: str | None = None
    document: str | None = None
    timezone: str
    status: str


class CompanyUpdate(BaseModel):
    name: str | None = None
    email: str | None = None
    document: str | None = None
    timezone: str | None = None


@router.get("/company", response_model=CompanyRead)
async def get_company(
    user: Annotated[AuthenticatedUser, require_permission("settings.view")],
    session: Annotated[AsyncSession, Depends(require_session)],
) -> CompanyRead:
    company = await session.get(Company, user.company_id)
    if company is None:
        raise HTTPException(status_code=404, detail={"code": "company_not_found"})
    return CompanyRead(
        id=company.id,
        name=company.name,
        slug=company.slug,
        email=company.email,
        document=company.document,
        timezone=company.timezone,
        status=company.status,
    )


@router.patch("/company", response_model=CompanyRead)
async def update_company(
    body: CompanyUpdate,
    user: Annotated[AuthenticatedUser, require_permission("settings.edit")],
    session: Annotated[AsyncSession, Depends(require_session)],
) -> CompanyRead:
    company = await session.get(Company, user.company_id)
    if company is None:
        raise HTTPException(status_code=404, detail={"code": "company_not_found"})

    diff = {}
    if body.name is not None and body.name != company.name:
        diff["name"] = {"from": company.name, "to": body.name}
        company.name = body.name
    if body.email is not None and body.email != company.email:
        diff["email"] = {"from": company.email, "to": body.email}
        company.email = body.email
    if body.document is not None and body.document != company.document:
        diff["document"] = {"from": company.document, "to": body.document}
        company.document = body.document
    if body.timezone is not None and body.timezone != company.timezone:
        diff["timezone"] = {"from": company.timezone, "to": body.timezone}
        company.timezone = body.timezone

    if diff:
        await record_event(
            session,
            company_id=user.company_id,
            user_id=user.id,
            entity_type="company",
            entity_id=company.id,
            event_type="update",
            diff=diff,
        )

    await session.commit()
    await session.refresh(company)
    return CompanyRead(
        id=company.id,
        name=company.name,
        slug=company.slug,
        email=company.email,
        document=company.document,
        timezone=company.timezone,
        status=company.status,
    )
