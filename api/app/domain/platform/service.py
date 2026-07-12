from datetime import UTC, datetime, timedelta
from typing import Any

import bcrypt
import httpx
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings
from app.domain.timeclock.service import ensure_default_shifts
from app.integrations.asaas import AsaasClient, AsaasError
from app.models import (
    Company,
    Invoice,
    Occurrence,
    Plan,
    PlatformAuditLog,
    PlatformUser,
    Subscription,
    SupportRequest,
    UsageRecord,
    User,
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
        description=f"Registro — {plan.name}",
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
) -> SupportRequest | None:
    req = await session.scalar(select(SupportRequest).where(SupportRequest.id == request_id))
    if req is None:
        return None
    old_status = req.status
    req.status = status
    await _log_platform_audit(
        session,
        actor_id=actor_id,
        action="support_request.update_status",
        target_type="support_request",
        target_id=request_id,
        payload={"from": old_status, "to": status},
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
    """Gera um registro de uso do dia corrente por tenant (usuários e ocorrências)."""
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
        occurrences_count = await session.scalar(
            select(func.count(Occurrence.id)).where(
                Occurrence.company_id == company_id,
                Occurrence.created_at >= month_start,
            )
        )
        for metric, value in (("users", users_count or 0), ("occurrences", occurrences_count or 0)):
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
