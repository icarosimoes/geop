import re
import secrets
from datetime import UTC, datetime, timedelta
from typing import Any

import bcrypt
import httpx
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.audit import record_event
from app.core.config import Settings
from app.core.rls import set_tenant_context
from app.core.security import create_impersonation_token
from app.domain.timeclock.service import ensure_default_shifts
from app.integrations.asaas import AsaasClient, AsaasError
from app.models import (
    Company,
    Invoice,
    Permission,
    Plan,
    PlatformAuditLog,
    PlatformSetting,
    PlatformUser,
    Role,
    Subscription,
    SupportRequest,
    UsageRecord,
    User,
    WorkOrder,
)


async def _log_platform_audit(
    session: AsyncSession,
    *,
    actor_id: int,
    action: str,
    target_type: str,
    target_id: int | str | None = None,
    payload: dict[str, Any] | None = None,
    ip_address: str | None = None,
) -> None:
    session.add(
        PlatformAuditLog(
            platform_user_id=actor_id,
            action=action,
            target_type=target_type,
            target_id=str(target_id) if target_id is not None else None,
            payload=payload,
            ip_address=ip_address,
            created_at=datetime.now(UTC).replace(tzinfo=None),
        )
    )


async def create_impersonation_ticket(
    session: AsyncSession,
    *,
    company_id: int,
    actor: PlatformUser,
    settings: Settings,
    ip_address: str | None = None,
) -> str | None:
    # Redundante sob `registro_platform` (BYPASSRLS), mantido pelo mesmo motivo
    # do comentário em update_support_request_status.
    await set_tenant_context(session, company_id)
    user = await session.scalar(
        select(User)
        .where(User.company_id == company_id, User.active.is_(True), User.deleted_at.is_(None))
        .order_by(User.id)
        .limit(1)
    )
    if user is None:
        return None
    ticket = create_impersonation_token(
        subject=user.id, company_id=company_id, secret=settings.jwt_secret
    )
    await _log_platform_audit(
        session,
        actor_id=actor.id,
        action="tenant.impersonate",
        target_type="company",
        target_id=company_id,
        payload={"user_id": user.id, "user_email": user.email},
        ip_address=ip_address,
    )
    await session.commit()
    return ticket


# ---------------------------------------------------------------------------
# Tenants
# ---------------------------------------------------------------------------


async def create_tenant(
    session: AsyncSession,
    *,
    name: str,
    slug: str,
    email: str | None,
    document: str | None,
    trade_name: str | None = None,
    address_street: str | None = None,
    address_number: str | None = None,
    address_complement: str | None = None,
    address_neighborhood: str | None = None,
    address_city: str | None = None,
    address_state: str | None = None,
    address_zip: str | None = None,
    timezone: str,
    plan_id: int,
    trial_days: int = 14,
    actor_id: int,
) -> Company:
    plan = await session.scalar(select(Plan).where(Plan.id == plan_id))
    if plan is None:
        raise ValueError("plan_not_found")
    company = Company(
        name=name,
        slug=slug,
        email=email,
        document=document,
        trade_name=trade_name,
        address_street=address_street,
        address_number=address_number,
        address_complement=address_complement,
        address_neighborhood=address_neighborhood,
        address_city=address_city,
        address_state=address_state,
        address_zip=address_zip,
        timezone=timezone,
    )
    session.add(company)
    await session.flush()
    await ensure_default_shifts(session, company.id)
    subscription = Subscription(
        company_id=company.id,
        plan_id=plan.id,
        status="trial",
        trial_ends_at=(datetime.now(UTC) + timedelta(days=trial_days)).replace(tzinfo=None),
    )
    session.add(subscription)
    await _log_platform_audit(
        session,
        actor_id=actor_id,
        action="tenant.create",
        target_type="company",
        target_id=company.id,
        payload={"name": name, "slug": slug, "plan_id": plan_id, "trial_days": trial_days},
    )
    await session.commit()
    await session.refresh(company)
    return company


def _slugify(value: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", value.strip().lower()).strip("-")
    return slug or "empresa"


async def _unique_slug(session: AsyncSession, base: str) -> str:
    slug = _slugify(base)
    candidate = slug
    suffix = 1
    while await session.scalar(select(Company.id).where(Company.slug == candidate)):
        suffix += 1
        candidate = f"{slug}-{suffix}"
    return candidate


async def provision_tenant_with_admin(
    session: AsyncSession,
    *,
    name: str,
    document: str | None,
    email: str,
    trial_days: int = 365,
) -> Company:
    """Provisiona um tenant GEOP do zero (Company + Subscription + role admin +
    primeiro usuário) numa chamada só — usado pela integração server-to-server
    com o erpsolid (`POST /integrations/erpsolid/provision-tenant`), que precisa
    de um GEOP funcional pra um tenant que acabou de comprar o módulo, sem
    passar pelo fluxo manual do painel de plataforma.

    Combina `create_tenant()` com o bloco de bootstrap de role/admin usado em
    `scripts/seed_demo_hotel_exemplo.py:105-157`."""
    if document:
        existing = await session.scalar(
            select(Company.id).where(Company.document == document, Company.deleted_at.is_(None))
        )
        if existing is not None:
            raise ValueError("company_already_exists")

    plan_id = await session.scalar(select(Plan.id).where(Plan.code == "professional"))
    if plan_id is None:
        plan_id = await session.scalar(select(Plan.id).order_by(Plan.id).limit(1))
    if plan_id is None:
        raise ValueError("no_plan_available")

    platform_user_id = await session.scalar(
        select(PlatformUser.id).order_by(PlatformUser.id).limit(1)
    )
    if platform_user_id is None:
        raise ValueError("no_platform_user_available")

    slug = await _unique_slug(session, name)
    company = await create_tenant(
        session,
        name=name,
        slug=slug,
        email=email,
        document=document,
        timezone="America/Sao_Paulo",
        plan_id=plan_id,
        trial_days=trial_days,
        actor_id=platform_user_id,
    )

    # Bootstrap: role admin (permissão wildcard) + primeiro usuário, criados via
    # ORM direto e sem record_event — igual ao seed script, já que ainda não
    # existe nenhum User no tenant pra ser o "actor" do evento de auditoria.
    wildcard = await session.scalar(select(Permission).where(Permission.code == "*"))
    role = Role(company_id=company.id, code="admin", name="Administrador")
    role.permissions = [wildcard] if wildcard else []
    session.add(role)
    await session.flush()

    unusable_password = bcrypt.hashpw(secrets.token_urlsafe(32).encode(), bcrypt.gensalt()).decode()
    admin = User(
        company_id=company.id,
        role_id=role.id,
        name=name,
        email=email.lower(),
        password=unusable_password,
        active=True,
        email_verified_at=datetime.now(UTC).replace(tzinfo=None),
    )
    session.add(admin)
    await session.commit()
    await session.refresh(company)
    return company


async def get_tenant_detail(session: AsyncSession, tenant_id: int) -> dict[str, Any] | None:
    company = await session.scalar(
        select(Company).where(Company.id == tenant_id, Company.deleted_at.is_(None))
    )
    if company is None:
        return None
    users_count = (
        await session.scalar(
            select(func.count(User.id)).where(
                User.company_id == tenant_id,
                User.deleted_at.is_(None),
                User.active.is_(True),
            )
        )
        or 0
    )
    sub = await session.scalar(select(Subscription).where(Subscription.company_id == tenant_id))
    invoices: list[Invoice] = []
    if sub:
        invoices = list(
            (
                await session.execute(
                    select(Invoice)
                    .where(Invoice.subscription_id == sub.id)
                    .order_by(Invoice.due_date.desc())
                )
            )
            .scalars()
            .all()
        )
    return {
        "company": company,
        "users_count": users_count,
        "subscription": sub,
        "invoices": invoices,
    }


async def update_tenant(
    session: AsyncSession,
    tenant_id: int,
    *,
    updates: dict[str, Any],
    actor_id: int,
) -> Company | None:
    company = await session.scalar(
        select(Company).where(Company.id == tenant_id, Company.deleted_at.is_(None))
    )
    if company is None:
        return None
    changed: dict[str, Any] = {}
    for field, value in updates.items():
        old = getattr(company, field, None)
        if str(old) != str(value):
            changed[field] = {"from": str(old), "to": str(value)}
            setattr(company, field, value)
    if changed:
        await _log_platform_audit(
            session,
            actor_id=actor_id,
            action="tenant.update",
            target_type="company",
            target_id=tenant_id,
            payload=changed,
        )
    await session.commit()
    await session.refresh(company)
    return company


async def soft_delete_tenant(
    session: AsyncSession,
    tenant_id: int,
    *,
    actor_id: int,
) -> bool:
    company = await session.scalar(
        select(Company).where(Company.id == tenant_id, Company.deleted_at.is_(None))
    )
    if company is None:
        return False
    company.deleted_at = datetime.now(UTC).replace(tzinfo=None)
    company.status = "inactive"
    await _log_platform_audit(
        session,
        actor_id=actor_id,
        action="tenant.delete",
        target_type="company",
        target_id=tenant_id,
    )
    await session.commit()
    return True


# ---------------------------------------------------------------------------
# Plans
# ---------------------------------------------------------------------------


async def create_plan(
    session: AsyncSession,
    *,
    code: str,
    name: str,
    price_cents: int,
    currency: str,
    billing_period: str,
    features: dict[str, Any],
    limits: dict[str, Any],
    active: bool,
    public: bool,
    actor_id: int,
) -> Plan:
    plan = Plan(
        code=code,
        name=name,
        price_cents=price_cents,
        currency=currency,
        billing_period=billing_period,
        features=features,
        limits=limits,
        active=active,
        public=public,
    )
    session.add(plan)
    await session.flush()
    await _log_platform_audit(
        session,
        actor_id=actor_id,
        action="plan.create",
        target_type="plan",
        target_id=plan.id,
        payload={"code": code, "name": name, "price_cents": price_cents},
    )
    await session.commit()
    await session.refresh(plan)
    return plan


async def update_plan(
    session: AsyncSession,
    plan_id: int,
    *,
    updates: dict[str, Any],
    actor_id: int,
) -> Plan | None:
    plan = await session.scalar(select(Plan).where(Plan.id == plan_id))
    if plan is None:
        return None
    changed: dict[str, Any] = {}
    for field, value in updates.items():
        old = getattr(plan, field, None)
        if str(old) != str(value):
            changed[field] = {"from": str(old), "to": str(value)}
            setattr(plan, field, value)
    if changed:
        await _log_platform_audit(
            session,
            actor_id=actor_id,
            action="plan.update",
            target_type="plan",
            target_id=plan_id,
            payload=changed,
        )
    await session.commit()
    await session.refresh(plan)
    return plan


async def soft_delete_plan(
    session: AsyncSession,
    plan_id: int,
    *,
    actor_id: int,
) -> bool:
    plan = await session.scalar(select(Plan).where(Plan.id == plan_id))
    if plan is None:
        return False
    active_subs = await session.scalar(
        select(func.count(Subscription.id)).where(
            Subscription.plan_id == plan_id,
            Subscription.status.in_(["active", "trial"]),
        )
    )
    if active_subs:
        raise ValueError("plan_has_active_subscriptions")
    plan.active = False
    await _log_platform_audit(
        session,
        actor_id=actor_id,
        action="plan.delete",
        target_type="plan",
        target_id=plan_id,
    )
    await session.commit()
    return True


# ---------------------------------------------------------------------------
# Subscriptions
# ---------------------------------------------------------------------------


async def get_subscription_with_invoices(
    session: AsyncSession,
    subscription_id: int,
) -> dict[str, Any] | None:
    sub = await session.scalar(select(Subscription).where(Subscription.id == subscription_id))
    if sub is None:
        return None
    invoices = list(
        (
            await session.execute(
                select(Invoice)
                .where(Invoice.subscription_id == subscription_id)
                .order_by(Invoice.due_date.desc())
            )
        )
        .scalars()
        .all()
    )
    return {"subscription": sub, "invoices": invoices}


async def update_subscription(
    session: AsyncSession,
    subscription_id: int,
    *,
    updates: dict[str, Any],
    actor_id: int,
) -> Subscription | None:
    sub = await session.scalar(select(Subscription).where(Subscription.id == subscription_id))
    if sub is None:
        return None
    changed: dict[str, Any] = {}
    for field, value in updates.items():
        old = getattr(sub, field, None)
        if str(old) != str(value):
            changed[field] = {"from": str(old), "to": str(value)}
            setattr(sub, field, value)
    if changed:
        await _log_platform_audit(
            session,
            actor_id=actor_id,
            action="subscription.update",
            target_type="subscription",
            target_id=subscription_id,
            payload=changed,
        )
    await session.commit()
    await session.refresh(sub)
    return sub


# ---------------------------------------------------------------------------
# Asaas provisioning
# ---------------------------------------------------------------------------


def _asaas_client(settings: Settings) -> AsaasClient:
    return AsaasClient(api_key=settings.asaas_api_key, base_url=settings.asaas_api_url)


async def provision_asaas_customer(
    session: AsyncSession,
    company_id: int,
    settings: Settings,
    actor_id: int,
) -> str:
    company = await session.scalar(
        select(Company).where(Company.id == company_id, Company.deleted_at.is_(None))
    )
    if company is None:
        raise ValueError("company_not_found")
    if company.asaas_customer_id:
        return company.asaas_customer_id
    client = _asaas_client(settings)
    result = await client.create_customer(
        name=company.name,
        email=company.email or "",
        cpf_cnpj=company.document or "",
        external_reference=str(company.id),
    )
    company.asaas_customer_id = result["id"]
    await _log_platform_audit(
        session,
        actor_id=actor_id,
        action="asaas.customer_created",
        target_type="company",
        target_id=company.id,
        payload={"asaas_customer_id": result["id"]},
    )
    await session.commit()
    return result["id"]


async def provision_asaas_subscription(
    session: AsyncSession,
    subscription_id: int,
    settings: Settings,
    actor_id: int,
) -> str:
    sub = await session.scalar(select(Subscription).where(Subscription.id == subscription_id))
    if sub is None:
        raise ValueError("subscription_not_found")
    if sub.billing_provider_subscription_id:
        return sub.billing_provider_subscription_id
    company = await session.scalar(select(Company).where(Company.id == sub.company_id))
    if not company or not company.asaas_customer_id:
        raise ValueError("company_has_no_asaas_customer")
    plan = sub.plan
    client = _asaas_client(settings)
    result = await client.create_subscription(
        customer_id=company.asaas_customer_id,
        value=plan.price_cents / 100,
        cycle="MONTHLY" if plan.billing_period == "monthly" else "YEARLY",
        description=f"GEOP — {plan.name}",
        external_reference=str(sub.id),
    )
    sub.billing_provider_subscription_id = result["id"]
    sub.status = "active"
    sub.current_period_start = datetime.now(UTC).replace(tzinfo=None)
    await _log_platform_audit(
        session,
        actor_id=actor_id,
        action="asaas.subscription_created",
        target_type="subscription",
        target_id=sub.id,
        payload={"asaas_subscription_id": result["id"]},
    )
    await session.commit()
    await session.refresh(sub)
    return result["id"]


# ---------------------------------------------------------------------------
# Lifecycle: trial expiration, suspension, reactivation
# ---------------------------------------------------------------------------


async def process_trial_expirations(
    session: AsyncSession,
    actor_id: int | None = None,
) -> list[dict[str, Any]]:
    now = datetime.now(UTC).replace(tzinfo=None)
    expired = (
        (
            await session.execute(
                select(Subscription).where(
                    Subscription.status == "trial",
                    Subscription.trial_ends_at < now,
                )
            )
        )
        .scalars()
        .all()
    )
    processed = []
    for sub in expired:
        sub.status = "past_due"
        sub.past_due_since = now
        await _log_platform_audit(
            session,
            actor_id=actor_id or 0,
            action="subscription.trial_expired",
            target_type="subscription",
            target_id=sub.id,
            payload={"company_id": sub.company_id},
        )
        processed.append(
            {
                "company_id": sub.company_id,
                "company_name": sub.company.name if sub.company else str(sub.company_id),
                "action": "trial_expired",
            }
        )
    if processed:
        await session.commit()
    return processed


async def process_suspensions(
    session: AsyncSession,
    grace_days: int = 7,
    actor_id: int | None = None,
) -> list[dict[str, Any]]:
    now = datetime.now(UTC).replace(tzinfo=None)
    cutoff = now - timedelta(days=grace_days)
    overdue = (
        (
            await session.execute(
                select(Subscription).where(
                    Subscription.status == "past_due",
                    Subscription.past_due_since < cutoff,
                )
            )
        )
        .scalars()
        .all()
    )
    processed = []
    for sub in overdue:
        sub.status = "suspended"
        sub.suspended_at = now
        company = await session.scalar(select(Company).where(Company.id == sub.company_id))
        if company:
            company.status = "suspended"
        await _log_platform_audit(
            session,
            actor_id=actor_id or 0,
            action="subscription.suspended",
            target_type="subscription",
            target_id=sub.id,
            payload={"company_id": sub.company_id},
        )
        processed.append(
            {
                "company_id": sub.company_id,
                "company_name": company.name if company else str(sub.company_id),
                "action": "suspended",
            }
        )
    if processed:
        await session.commit()
    return processed


async def reactivate_tenant(
    session: AsyncSession,
    subscription_id: int,
    *,
    actor_id: int,
) -> Subscription | None:
    sub = await session.scalar(select(Subscription).where(Subscription.id == subscription_id))
    if sub is None:
        return None
    sub.status = "active"
    sub.suspended_at = None
    sub.past_due_since = None
    sub.overdue_warned_at = None
    company = await session.scalar(select(Company).where(Company.id == sub.company_id))
    if company:
        company.status = "active"
    await _log_platform_audit(
        session,
        actor_id=actor_id,
        action="subscription.reactivated",
        target_type="subscription",
        target_id=subscription_id,
        payload={"company_id": sub.company_id},
    )
    await session.commit()
    await session.refresh(sub)
    return sub


# ---------------------------------------------------------------------------
# Reconciliation
# ---------------------------------------------------------------------------


async def reconcile_billing(
    session: AsyncSession,
    settings: Settings,
    actor_id: int,
    auto_correct: bool = False,
) -> list[dict[str, Any]]:
    subs = (
        (
            await session.execute(
                select(Subscription).where(
                    Subscription.billing_provider_subscription_id.isnot(None),
                )
            )
        )
        .scalars()
        .all()
    )
    if not subs:
        return []
    client = _asaas_client(settings)
    discrepancies: list[dict[str, Any]] = []
    for sub in subs:
        try:
            remote = await client.get_subscription(sub.billing_provider_subscription_id)
        except (httpx.HTTPError, AsaasError, KeyError):
            discrepancies.append(
                {
                    "subscription_id": sub.id,
                    "company_id": sub.company_id,
                    "local_status": sub.status,
                    "remote_status": "fetch_error",
                    "corrected": False,
                }
            )
            continue
        remote_status = remote.get("status", "").lower()
        local_status = sub.status
        if remote_status != local_status:
            corrected = False
            if auto_correct:
                sub.status = remote_status
                corrected = True
            discrepancies.append(
                {
                    "subscription_id": sub.id,
                    "company_id": sub.company_id,
                    "local_status": local_status,
                    "remote_status": remote_status,
                    "corrected": corrected,
                }
            )
            await _log_platform_audit(
                session,
                actor_id=actor_id,
                action="billing.reconcile_discrepancy",
                target_type="subscription",
                target_id=sub.id,
                payload={
                    "local_status": local_status,
                    "remote_status": remote_status,
                    "corrected": corrected,
                },
            )
    if discrepancies:
        await session.commit()
    return discrepancies


# ---------------------------------------------------------------------------
# Platform users (equipe interna)
# ---------------------------------------------------------------------------


async def list_platform_users(session: AsyncSession) -> list[PlatformUser]:
    return list(
        (
            await session.execute(
                select(PlatformUser)
                .where(PlatformUser.deleted_at.is_(None))
                .order_by(PlatformUser.name)
            )
        )
        .scalars()
        .all()
    )


async def create_platform_user(
    session: AsyncSession,
    *,
    name: str,
    email: str,
    role: str,
    password: str,
    actor_id: int,
) -> PlatformUser:
    user = PlatformUser(
        name=name,
        email=email,
        role=role,
        password_hash=bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode(),
    )
    session.add(user)
    await session.flush()
    await _log_platform_audit(
        session,
        actor_id=actor_id,
        action="platform_user.create",
        target_type="platform_user",
        target_id=user.id,
        payload={"email": email, "role": role},
    )
    await session.commit()
    await session.refresh(user)
    return user


async def update_platform_user(
    session: AsyncSession,
    user_id: int,
    *,
    updates: dict[str, Any],
    actor_id: int,
) -> PlatformUser | None:
    user = await session.scalar(
        select(PlatformUser).where(PlatformUser.id == user_id, PlatformUser.deleted_at.is_(None))
    )
    if user is None:
        return None
    password = updates.pop("password", None)
    changed: dict[str, Any] = {}
    for field, value in updates.items():
        old = getattr(user, field, None)
        if str(old) != str(value):
            changed[field] = {"from": str(old), "to": str(value)}
            setattr(user, field, value)
    if password:
        user.password_hash = bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()
        changed["password"] = "changed"
    if changed:
        await _log_platform_audit(
            session,
            actor_id=actor_id,
            action="platform_user.update",
            target_type="platform_user",
            target_id=user_id,
            payload=changed,
        )
    await session.commit()
    await session.refresh(user)
    return user


async def soft_delete_platform_user(
    session: AsyncSession,
    user_id: int,
    *,
    actor_id: int,
) -> bool:
    user = await session.scalar(
        select(PlatformUser).where(PlatformUser.id == user_id, PlatformUser.deleted_at.is_(None))
    )
    if user is None:
        return False
    user.deleted_at = datetime.now(UTC).replace(tzinfo=None)
    user.active = False
    await _log_platform_audit(
        session,
        actor_id=actor_id,
        action="platform_user.delete",
        target_type="platform_user",
        target_id=user_id,
    )
    await session.commit()
    return True


# ---------------------------------------------------------------------------
# Support requests
# ---------------------------------------------------------------------------


async def list_support_requests(session: AsyncSession) -> list[dict[str, Any]]:
    rows = (
        await session.execute(
            select(SupportRequest, Company.name)
            .join(Company, Company.id == SupportRequest.company_id)
            .order_by(SupportRequest.created_at.desc())
        )
    ).all()
    return [{"request": req, "company_name": name} for req, name in rows]


async def update_support_request_status(
    session: AsyncSession,
    request_id: int,
    *,
    status: str,
    actor_id: int,
    actor_name: str,
    response_message: str | None = None,
) -> SupportRequest | None:
    req = await session.scalar(select(SupportRequest).where(SupportRequest.id == request_id))
    if req is None:
        return None

    # `audit_events`/`notifications` têm RLS por tenant e a sessão da plataforma
    # nunca passa por `current_user` — precisa vir antes de qualquer escrita
    # nessas tabelas. Redundante sob `registro_platform` (BYPASSRLS — ver
    # ADR-002), mantido pro caso de rodar algum dia sob uma sessão sem bypass.
    await set_tenant_context(session, req.company_id)

    old_status = req.status
    req.status = status
    audit_payload: dict[str, Any] = {"from": old_status, "to": status}
    timeline_actor = f"Suporte · {actor_name}"

    if old_status != status:
        await record_event(
            session,
            company_id=req.company_id,
            user_id=None,
            actor_name=timeline_actor,
            entity_type="support_request",
            entity_id=req.id,
            event_type="update",
            diff={"status": {"from": old_status, "to": status}},
        )

    if response_message is not None:
        req.response_message = response_message
        req.responded_by = actor_id
        audit_payload["response_message"] = response_message
        await record_event(
            session,
            company_id=req.company_id,
            user_id=None,
            actor_name=timeline_actor,
            entity_type="support_request",
            entity_id=req.id,
            event_type="comment",
            diff={"message": response_message},
        )

    await _log_platform_audit(
        session,
        actor_id=actor_id,
        action="support_request.update_status",
        target_type="support_request",
        target_id=request_id,
        payload=audit_payload,
    )
    if response_message is not None and req.user_id is not None:
        from app.domain.notifications.service import create_notification

        await create_notification(
            session,
            company_id=req.company_id,
            user_id=req.user_id,
            title="Seu chamado de suporte foi respondido",
            body=response_message,
            category="info",
            entity_type="support_request",
            entity_id=req.id,
        )
    await session.commit()
    await session.refresh(req)
    return req


# ---------------------------------------------------------------------------
# Usage
# ---------------------------------------------------------------------------


async def list_usage_records(session: AsyncSession, limit: int = 200) -> list[dict[str, Any]]:
    rows = (
        await session.execute(
            select(UsageRecord, Company.name)
            .join(Company, Company.id == UsageRecord.company_id)
            .order_by(UsageRecord.period_start.desc())
            .limit(limit)
        )
    ).all()
    return [{"record": rec, "company_name": name} for rec, name in rows]


async def snapshot_usage(session: AsyncSession) -> int:
    """Gera um registro de uso do dia corrente por tenant (usuários e ordens de serviço)."""
    today = datetime.now(UTC).date()
    month_start = datetime.combine(today.replace(day=1), datetime.min.time())
    companies = list(
        (await session.execute(select(Company.id).where(Company.deleted_at.is_(None))))
        .scalars()
        .all()
    )
    created = 0
    for company_id in companies:
        users_count = await session.scalar(
            select(func.count(User.id)).where(
                User.company_id == company_id,
                User.deleted_at.is_(None),
                User.active.is_(True),
            )
        )
        work_orders_count = await session.scalar(
            select(func.count(WorkOrder.id)).where(
                WorkOrder.company_id == company_id,
                WorkOrder.created_at >= month_start,
            )
        )
        for metric, value in (
            ("users", users_count or 0),
            ("work_orders", work_orders_count or 0),
        ):
            session.add(
                UsageRecord(
                    company_id=company_id,
                    metric=metric,
                    value=value,
                    period_start=today,
                    period_end=today,
                )
            )
            created += 1
    await session.commit()
    return created


# ---------------------------------------------------------------------------
# Configurações — e-mail transacional (Brevo)
# ---------------------------------------------------------------------------


async def get_platform_email_config(session: AsyncSession) -> dict[str, Any]:
    row = await session.scalar(select(PlatformSetting).where(PlatformSetting.key == "email"))
    return dict(row.value) if row else {}


async def get_effective_email_config(
    session: AsyncSession,
    settings: Settings,
) -> tuple[str, str, str]:
    """Retorna (api_key, from_address, from_name), priorizando o que foi
    configurado em /platform/settings/email sobre as variáveis de ambiente."""
    value = await get_platform_email_config(session)
    api_key = value.get("brevo_api_key") or settings.brevo_api_key
    from_address = value.get("email_from_address") or settings.mail_from_address
    from_name = value.get("email_from_name") or settings.mail_from_name
    return api_key, from_address, from_name


async def save_platform_email_config(
    session: AsyncSession,
    *,
    updates: dict[str, Any],
    actor_id: int,
) -> dict[str, Any]:
    row = await session.scalar(select(PlatformSetting).where(PlatformSetting.key == "email"))
    current = dict(row.value) if row else {}
    new_value = {**current, **{k: v for k, v in updates.items() if v is not None}}
    if row:
        row.value = new_value
    else:
        row = PlatformSetting(key="email", value=new_value)
        session.add(row)
    await _log_platform_audit(
        session,
        actor_id=actor_id,
        action="settings.email_update",
        target_type="platform_setting",
        target_id="email",
        payload={
            k: ("***" if k == "brevo_api_key" else v) for k, v in updates.items() if v is not None
        },
    )
    await session.commit()
    return new_value
