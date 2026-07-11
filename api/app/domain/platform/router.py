from datetime import UTC, datetime
from typing import Annotated

import jwt
from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi import Query as QueryParam
from fastapi.security import OAuth2PasswordBearer
from pydantic import BaseModel
from sqlalchemy import case, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings, get_settings
from app.core.dependencies import require_session
from app.core.rate_limit import limiter
from app.core.security import (
    create_platform_refresh_token,
    create_platform_token,
    decode_platform_refresh_token,
    decode_platform_token,
    verify_laravel_password,
)
from app.domain.platform import service
from app.domain.platform.schemas import (
    FeatureFlagCreate,
    FeatureFlagResponse,
    FeatureFlagUpdate,
    InvoiceSummary,
    LifecycleProcessed,
    LifecycleResponse,
    PlanCreate,
    PlanResponse,
    PlanUpdate,
    PlatformLoginRequest,
    PlatformMetricsResponse,
    PlatformTokenResponse,
    PlatformUserCreate,
    PlatformUserResponse,
    PlatformUserUpdate,
    SubscriptionDetail,
    SubscriptionUpdate,
    SupportRequestResponse,
    SupportRequestUpdate,
    TenantCreate,
    TenantDetail,
    TenantSummary,
    TenantUpdate,
    UsageRecordResponse,
)
from app.models import Company, Plan, PlatformAuditLog, PlatformUser, Subscription, User

router = APIRouter(prefix="/platform", tags=["platform"])
platform_oauth = OAuth2PasswordBearer(tokenUrl="/api/v1/platform/auth/login")


async def current_platform_user(
    token: Annotated[str, Depends(platform_oauth)],
    session: Annotated[AsyncSession, Depends(require_session)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> PlatformUser:
    try:
        claims = decode_platform_token(token, settings.jwt_secret)
        user_id = int(claims["sub"])
    except (jwt.InvalidTokenError, KeyError, TypeError, ValueError) as exc:
        raise HTTPException(status_code=401, detail={"code": "invalid_platform_token"}) from exc
    user = await session.scalar(
        select(PlatformUser).where(
            PlatformUser.id == user_id,
            PlatformUser.active.is_(True),
            PlatformUser.deleted_at.is_(None),
        )
    )
    if user is None:
        raise HTTPException(status_code=401, detail={"code": "inactive_platform_user"})
    return user


# ---------------------------------------------------------------------------
# Auth
# ---------------------------------------------------------------------------


@router.post("/auth/login", response_model=PlatformTokenResponse)
@limiter.limit("10/minute")
async def platform_login(
    request: Request,
    payload: PlatformLoginRequest,
    session: Annotated[AsyncSession, Depends(require_session)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> PlatformTokenResponse:
    user = await session.scalar(
        select(PlatformUser).where(
            PlatformUser.email == payload.email,
            PlatformUser.active.is_(True),
            PlatformUser.deleted_at.is_(None),
        )
    )
    if user is None or not verify_laravel_password(payload.password, user.password_hash):
        raise HTTPException(status_code=401, detail={"code": "invalid_credentials"})
    user.last_login_at = datetime.now(UTC).replace(tzinfo=None)
    session.add(
        PlatformAuditLog(
            platform_user_id=user.id,
            action="platform.login",
            target_type="platform_user",
            target_id=str(user.id),
            payload=None,
            created_at=datetime.now(UTC).replace(tzinfo=None),
        )
    )
    await session.commit()
    return PlatformTokenResponse(
        access_token=create_platform_token(
            subject=user.id,
            role=user.role,
            secret=settings.jwt_secret,
            minutes=settings.access_token_minutes,
        ),
        refresh_token=create_platform_refresh_token(
            subject=user.id,
            role=user.role,
            secret=settings.jwt_secret,
            days=settings.refresh_token_days,
        ),
        expires_in=settings.access_token_minutes * 60,
        name=user.name,
        role=user.role,
    )


class PlatformRefreshRequest(BaseModel):
    refresh_token: str


@router.post("/auth/refresh", response_model=PlatformTokenResponse)
@limiter.limit("20/minute")
async def platform_refresh(
    request: Request,
    body: PlatformRefreshRequest,
    session: Annotated[AsyncSession, Depends(require_session)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> PlatformTokenResponse:
    try:
        claims = decode_platform_refresh_token(body.refresh_token, settings.jwt_secret)
        user_id = int(claims["sub"])
    except (jwt.InvalidTokenError, KeyError, TypeError, ValueError) as exc:
        raise HTTPException(
            status_code=401,
            detail={"code": "invalid_refresh_token", "message": "Refresh token inválido"},
        ) from exc
    user = await session.scalar(
        select(PlatformUser).where(
            PlatformUser.id == user_id,
            PlatformUser.active.is_(True),
            PlatformUser.deleted_at.is_(None),
        )
    )
    if user is None:
        raise HTTPException(
            status_code=401,
            detail={"code": "inactive_platform_user", "message": "Usuário indisponível"},
        )
    return PlatformTokenResponse(
        access_token=create_platform_token(
            subject=user.id,
            role=user.role,
            secret=settings.jwt_secret,
            minutes=settings.access_token_minutes,
        ),
        refresh_token=create_platform_refresh_token(
            subject=user.id,
            role=user.role,
            secret=settings.jwt_secret,
            days=settings.refresh_token_days,
        ),
        expires_in=settings.access_token_minutes * 60,
        name=user.name,
        role=user.role,
    )


# ---------------------------------------------------------------------------
# Metrics
# ---------------------------------------------------------------------------


@router.get("/metrics", response_model=PlatformMetricsResponse)
async def platform_metrics(
    _: Annotated[PlatformUser, Depends(current_platform_user)],
    session: Annotated[AsyncSession, Depends(require_session)],
) -> PlatformMetricsResponse:
    tenants_total, tenants_active = (
        await session.execute(
            select(
                func.count(Company.id), func.sum(case((Company.status == "active", 1), else_=0))
            ).where(Company.deleted_at.is_(None))
        )
    ).one()
    trial, past_due = (
        await session.execute(
            select(
                func.sum(case((Subscription.status == "trial", 1), else_=0)),
                func.sum(case((Subscription.status == "past_due", 1), else_=0)),
            )
        )
    ).one()
    mrr = await session.scalar(
        select(func.coalesce(func.sum(Plan.price_cents), 0))
        .join(Subscription, Subscription.plan_id == Plan.id)
        .where(Subscription.status == "active", Plan.billing_period == "monthly")
    )
    return PlatformMetricsResponse(
        tenants_total=tenants_total or 0,
        tenants_active=tenants_active or 0,
        tenants_trial=trial or 0,
        tenants_past_due=past_due or 0,
        mrr_cents=mrr or 0,
    )


# ---------------------------------------------------------------------------
# Tenants CRUD
# ---------------------------------------------------------------------------


@router.get("/tenants", response_model=list[TenantSummary])
async def list_tenants(
    _: Annotated[PlatformUser, Depends(current_platform_user)],
    session: Annotated[AsyncSession, Depends(require_session)],
) -> list[TenantSummary]:
    rows = (
        (
            await session.execute(
                select(
                    Company.id,
                    Company.name,
                    Company.slug,
                    Company.email,
                    Company.document,
                    Company.timezone,
                    Company.status,
                    func.count(User.id.distinct()).label("users_count"),
                    Subscription.status.label("subscription_status"),
                    Plan.name.label("plan_name"),
                    Subscription.trial_ends_at,
                )
                .outerjoin(User, User.company_id == Company.id)
                .outerjoin(Subscription, Subscription.company_id == Company.id)
                .outerjoin(Plan, Plan.id == Subscription.plan_id)
                .where(Company.deleted_at.is_(None))
                .group_by(Company.id, Subscription.id, Plan.id)
                .order_by(Company.name)
            )
        )
        .mappings()
        .all()
    )
    return [TenantSummary(**dict(row)) for row in rows]


@router.post("/tenants", response_model=TenantDetail, status_code=201)
async def create_tenant(
    admin: Annotated[PlatformUser, Depends(current_platform_user)],
    payload: TenantCreate,
    session: Annotated[AsyncSession, Depends(require_session)],
) -> TenantDetail:
    try:
        company = await service.create_tenant(
            session,
            name=payload.name,
            slug=payload.slug,
            email=payload.email,
            document=payload.document,
            timezone=payload.timezone,
            plan_id=payload.plan_id,
            trial_days=payload.trial_days,
            actor_id=admin.id,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail={"code": str(exc)}) from exc
    detail = await service.get_tenant_detail(session, company.id)
    return _build_tenant_detail(detail)


@router.get("/tenants/{tenant_id}", response_model=TenantDetail)
async def get_tenant(
    tenant_id: int,
    _: Annotated[PlatformUser, Depends(current_platform_user)],
    session: Annotated[AsyncSession, Depends(require_session)],
) -> TenantDetail:
    detail = await service.get_tenant_detail(session, tenant_id)
    if detail is None:
        raise HTTPException(status_code=404, detail={"code": "not_found"})
    return _build_tenant_detail(detail)


@router.patch("/tenants/{tenant_id}", response_model=TenantDetail)
async def update_tenant(
    tenant_id: int,
    admin: Annotated[PlatformUser, Depends(current_platform_user)],
    payload: TenantUpdate,
    session: Annotated[AsyncSession, Depends(require_session)],
) -> TenantDetail:
    updates = payload.model_dump(exclude_unset=True)
    if not updates:
        raise HTTPException(status_code=422, detail={"code": "no_fields"})
    company = await service.update_tenant(session, tenant_id, updates=updates, actor_id=admin.id)
    if company is None:
        raise HTTPException(status_code=404, detail={"code": "not_found"})
    detail = await service.get_tenant_detail(session, tenant_id)
    return _build_tenant_detail(detail)


@router.delete("/tenants/{tenant_id}", status_code=204)
async def delete_tenant(
    tenant_id: int,
    admin: Annotated[PlatformUser, Depends(current_platform_user)],
    session: Annotated[AsyncSession, Depends(require_session)],
) -> None:
    deleted = await service.soft_delete_tenant(session, tenant_id, actor_id=admin.id)
    if not deleted:
        raise HTTPException(status_code=404, detail={"code": "not_found"})


# ---------------------------------------------------------------------------
# Plans CRUD
# ---------------------------------------------------------------------------


@router.get("/plans", response_model=list[PlanResponse])
async def list_plans(
    _: Annotated[PlatformUser, Depends(current_platform_user)],
    session: Annotated[AsyncSession, Depends(require_session)],
) -> list[PlanResponse]:
    plans = (await session.execute(select(Plan).order_by(Plan.price_cents))).scalars().all()
    return [PlanResponse.model_validate(plan, from_attributes=True) for plan in plans]


@router.post("/plans", response_model=PlanResponse, status_code=201)
async def create_plan(
    admin: Annotated[PlatformUser, Depends(current_platform_user)],
    payload: PlanCreate,
    session: Annotated[AsyncSession, Depends(require_session)],
) -> PlanResponse:
    plan = await service.create_plan(
        session,
        code=payload.code,
        name=payload.name,
        price_cents=payload.price_cents,
        currency=payload.currency,
        billing_period=payload.billing_period,
        features=payload.features,
        limits=payload.limits,
        active=payload.active,
        public=payload.public,
        actor_id=admin.id,
    )
    return PlanResponse.model_validate(plan, from_attributes=True)


@router.patch("/plans/{plan_id}", response_model=PlanResponse)
async def update_plan(
    plan_id: int,
    admin: Annotated[PlatformUser, Depends(current_platform_user)],
    payload: PlanUpdate,
    session: Annotated[AsyncSession, Depends(require_session)],
) -> PlanResponse:
    updates = payload.model_dump(exclude_unset=True)
    if not updates:
        raise HTTPException(status_code=422, detail={"code": "no_fields"})
    plan = await service.update_plan(session, plan_id, updates=updates, actor_id=admin.id)
    if plan is None:
        raise HTTPException(status_code=404, detail={"code": "not_found"})
    return PlanResponse.model_validate(plan, from_attributes=True)


@router.delete("/plans/{plan_id}", status_code=204)
async def delete_plan(
    plan_id: int,
    admin: Annotated[PlatformUser, Depends(current_platform_user)],
    session: Annotated[AsyncSession, Depends(require_session)],
) -> None:
    try:
        deleted = await service.soft_delete_plan(session, plan_id, actor_id=admin.id)
    except ValueError as exc:
        raise HTTPException(status_code=409, detail={"code": str(exc)}) from exc
    if not deleted:
        raise HTTPException(status_code=404, detail={"code": "not_found"})


# ---------------------------------------------------------------------------
# Subscriptions
# ---------------------------------------------------------------------------


@router.get("/subscriptions/{subscription_id}", response_model=SubscriptionDetail)
async def get_subscription(
    subscription_id: int,
    _: Annotated[PlatformUser, Depends(current_platform_user)],
    session: Annotated[AsyncSession, Depends(require_session)],
) -> SubscriptionDetail:
    data = await service.get_subscription_with_invoices(session, subscription_id)
    if data is None:
        raise HTTPException(status_code=404, detail={"code": "not_found"})
    return _build_subscription_detail(data["subscription"], data["invoices"])


@router.patch("/subscriptions/{subscription_id}", response_model=SubscriptionDetail)
async def update_subscription(
    subscription_id: int,
    admin: Annotated[PlatformUser, Depends(current_platform_user)],
    payload: SubscriptionUpdate,
    session: Annotated[AsyncSession, Depends(require_session)],
) -> SubscriptionDetail:
    updates = payload.model_dump(exclude_unset=True)
    if not updates:
        raise HTTPException(status_code=422, detail={"code": "no_fields"})
    sub = await service.update_subscription(
        session,
        subscription_id,
        updates=updates,
        actor_id=admin.id,
    )
    if sub is None:
        raise HTTPException(status_code=404, detail={"code": "not_found"})
    data = await service.get_subscription_with_invoices(session, subscription_id)
    return _build_subscription_detail(data["subscription"], data["invoices"])


# ---------------------------------------------------------------------------
# Billing lifecycle
# ---------------------------------------------------------------------------


@router.post("/billing/process-expirations", response_model=LifecycleResponse)
async def process_expirations(
    admin: Annotated[PlatformUser, Depends(current_platform_user)],
    session: Annotated[AsyncSession, Depends(require_session)],
) -> LifecycleResponse:
    results = await service.process_trial_expirations(session, actor_id=admin.id)
    return LifecycleResponse(
        processed=[LifecycleProcessed(**r) for r in results],
    )


@router.post("/billing/process-suspensions", response_model=LifecycleResponse)
async def process_suspensions(
    admin: Annotated[PlatformUser, Depends(current_platform_user)],
    session: Annotated[AsyncSession, Depends(require_session)],
) -> LifecycleResponse:
    results = await service.process_suspensions(session, actor_id=admin.id)
    return LifecycleResponse(
        processed=[LifecycleProcessed(**r) for r in results],
    )


@router.post("/billing/reconcile")
async def reconcile(
    admin: Annotated[PlatformUser, Depends(current_platform_user)],
    session: Annotated[AsyncSession, Depends(require_session)],
    settings: Annotated[Settings, Depends(get_settings)],
    auto_correct: bool = QueryParam(False),
) -> dict:
    discrepancies = await service.reconcile_billing(
        session,
        settings,
        actor_id=admin.id,
        auto_correct=auto_correct,
    )
    return {"discrepancies": discrepancies}


@router.post("/subscriptions/{subscription_id}/reactivate", response_model=SubscriptionDetail)
async def reactivate_subscription(
    subscription_id: int,
    admin: Annotated[PlatformUser, Depends(current_platform_user)],
    session: Annotated[AsyncSession, Depends(require_session)],
) -> SubscriptionDetail:
    sub = await service.reactivate_tenant(session, subscription_id, actor_id=admin.id)
    if sub is None:
        raise HTTPException(status_code=404, detail={"code": "not_found"})
    data = await service.get_subscription_with_invoices(session, subscription_id)
    return _build_subscription_detail(data["subscription"], data["invoices"])


# ---------------------------------------------------------------------------
# Feature flags
# ---------------------------------------------------------------------------


@router.get("/feature-flags", response_model=list[FeatureFlagResponse])
async def list_feature_flags(
    _: Annotated[PlatformUser, Depends(current_platform_user)],
    session: Annotated[AsyncSession, Depends(require_session)],
) -> list[FeatureFlagResponse]:
    flags = await service.list_feature_flags(session)
    return [FeatureFlagResponse.model_validate(f, from_attributes=True) for f in flags]


@router.post("/feature-flags", response_model=FeatureFlagResponse, status_code=201)
async def create_feature_flag(
    admin: Annotated[PlatformUser, Depends(current_platform_user)],
    payload: FeatureFlagCreate,
    session: Annotated[AsyncSession, Depends(require_session)],
) -> FeatureFlagResponse:
    flag = await service.create_feature_flag(
        session,
        key=payload.key,
        description=payload.description,
        enabled_default=payload.enabled_default,
        targeting_rules=payload.targeting_rules,
        actor_id=admin.id,
    )
    return FeatureFlagResponse.model_validate(flag, from_attributes=True)


@router.patch("/feature-flags/{flag_id}", response_model=FeatureFlagResponse)
async def update_feature_flag(
    flag_id: int,
    admin: Annotated[PlatformUser, Depends(current_platform_user)],
    payload: FeatureFlagUpdate,
    session: Annotated[AsyncSession, Depends(require_session)],
) -> FeatureFlagResponse:
    updates = payload.model_dump(exclude_unset=True)
    if not updates:
        raise HTTPException(status_code=422, detail={"code": "no_fields"})
    flag = await service.update_feature_flag(session, flag_id, updates=updates, actor_id=admin.id)
    if flag is None:
        raise HTTPException(status_code=404, detail={"code": "not_found"})
    return FeatureFlagResponse.model_validate(flag, from_attributes=True)


@router.delete("/feature-flags/{flag_id}", status_code=204)
async def delete_feature_flag(
    flag_id: int,
    admin: Annotated[PlatformUser, Depends(current_platform_user)],
    session: Annotated[AsyncSession, Depends(require_session)],
) -> None:
    deleted = await service.soft_delete_feature_flag(session, flag_id, actor_id=admin.id)
    if not deleted:
        raise HTTPException(status_code=404, detail={"code": "not_found"})


# ---------------------------------------------------------------------------
# Platform users (equipe interna)
# ---------------------------------------------------------------------------


@router.get("/users", response_model=list[PlatformUserResponse])
async def list_platform_users(
    _: Annotated[PlatformUser, Depends(current_platform_user)],
    session: Annotated[AsyncSession, Depends(require_session)],
) -> list[PlatformUserResponse]:
    users = await service.list_platform_users(session)
    return [PlatformUserResponse.model_validate(u, from_attributes=True) for u in users]


@router.post("/users", response_model=PlatformUserResponse, status_code=201)
async def create_platform_user(
    admin: Annotated[PlatformUser, Depends(current_platform_user)],
    payload: PlatformUserCreate,
    session: Annotated[AsyncSession, Depends(require_session)],
) -> PlatformUserResponse:
    user = await service.create_platform_user(
        session,
        name=payload.name,
        email=payload.email,
        role=payload.role,
        password=payload.password,
        actor_id=admin.id,
    )
    return PlatformUserResponse.model_validate(user, from_attributes=True)


@router.patch("/users/{user_id}", response_model=PlatformUserResponse)
async def update_platform_user(
    user_id: int,
    admin: Annotated[PlatformUser, Depends(current_platform_user)],
    payload: PlatformUserUpdate,
    session: Annotated[AsyncSession, Depends(require_session)],
) -> PlatformUserResponse:
    updates = payload.model_dump(exclude_unset=True)
    if not updates:
        raise HTTPException(status_code=422, detail={"code": "no_fields"})
    user = await service.update_platform_user(session, user_id, updates=updates, actor_id=admin.id)
    if user is None:
        raise HTTPException(status_code=404, detail={"code": "not_found"})
    return PlatformUserResponse.model_validate(user, from_attributes=True)


@router.delete("/users/{user_id}", status_code=204)
async def delete_platform_user(
    user_id: int,
    admin: Annotated[PlatformUser, Depends(current_platform_user)],
    session: Annotated[AsyncSession, Depends(require_session)],
) -> None:
    deleted = await service.soft_delete_platform_user(session, user_id, actor_id=admin.id)
    if not deleted:
        raise HTTPException(status_code=404, detail={"code": "not_found"})


# ---------------------------------------------------------------------------
# Support requests
# ---------------------------------------------------------------------------


@router.get("/support-requests", response_model=list[SupportRequestResponse])
async def list_support_requests(
    _: Annotated[PlatformUser, Depends(current_platform_user)],
    session: Annotated[AsyncSession, Depends(require_session)],
) -> list[SupportRequestResponse]:
    rows = await service.list_support_requests(session)
    return [
        SupportRequestResponse(
            id=row["request"].id,
            company_id=row["request"].company_id,
            company_name=row["company_name"],
            contact_name=row["request"].contact_name,
            contact_whatsapp=row["request"].contact_whatsapp,
            message=row["request"].message,
            status=row["request"].status,
            created_at=row["request"].created_at,
        )
        for row in rows
    ]


@router.patch("/support-requests/{request_id}", response_model=SupportRequestResponse)
async def update_support_request(
    request_id: int,
    admin: Annotated[PlatformUser, Depends(current_platform_user)],
    payload: SupportRequestUpdate,
    session: Annotated[AsyncSession, Depends(require_session)],
) -> SupportRequestResponse:
    req = await service.update_support_request_status(
        session, request_id, status=payload.status, actor_id=admin.id
    )
    if req is None:
        raise HTTPException(status_code=404, detail={"code": "not_found"})
    company = await session.scalar(select(Company).where(Company.id == req.company_id))
    return SupportRequestResponse(
        id=req.id,
        company_id=req.company_id,
        company_name=company.name if company else None,
        contact_name=req.contact_name,
        contact_whatsapp=req.contact_whatsapp,
        message=req.message,
        status=req.status,
        created_at=req.created_at,
    )


# ---------------------------------------------------------------------------
# Usage
# ---------------------------------------------------------------------------


@router.get("/usage", response_model=list[UsageRecordResponse])
async def list_usage(
    _: Annotated[PlatformUser, Depends(current_platform_user)],
    session: Annotated[AsyncSession, Depends(require_session)],
    limit: int = QueryParam(200, le=1000),
) -> list[UsageRecordResponse]:
    rows = await service.list_usage_records(session, limit=limit)
    return [
        UsageRecordResponse(
            id=row["record"].id,
            company_id=row["record"].company_id,
            company_name=row["company_name"],
            metric=row["record"].metric,
            value=row["record"].value,
            period_start=row["record"].period_start,
            period_end=row["record"].period_end,
            created_at=row["record"].created_at,
        )
        for row in rows
    ]


@router.post("/usage/snapshot")
async def create_usage_snapshot(
    _: Annotated[PlatformUser, Depends(current_platform_user)],
    session: Annotated[AsyncSession, Depends(require_session)],
) -> dict:
    created = await service.snapshot_usage(session)
    return {"created": created}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _build_subscription_detail(sub: Subscription, invoices: list) -> SubscriptionDetail:
    return SubscriptionDetail(
        id=sub.id,
        plan_id=sub.plan_id,
        plan_name=sub.plan.name,
        plan_code=sub.plan.code,
        status=sub.status,
        trial_ends_at=sub.trial_ends_at,
        current_period_start=sub.current_period_start,
        current_period_end=sub.current_period_end,
        past_due_since=sub.past_due_since,
        suspended_at=sub.suspended_at,
        invoices=[
            InvoiceSummary(
                id=inv.id,
                value_cents=inv.value_cents,
                status=inv.status,
                due_date=inv.due_date,
                payment_date=inv.payment_date,
                external_payment_id=inv.external_payment_id,
            )
            for inv in invoices
        ],
    )


def _build_tenant_detail(detail: dict) -> TenantDetail:
    company = detail["company"]
    sub = detail["subscription"]
    invoices = detail["invoices"]
    return TenantDetail(
        id=company.id,
        name=company.name,
        slug=company.slug,
        email=company.email,
        document=company.document,
        status=company.status,
        timezone=company.timezone,
        users_count=detail["users_count"],
        created_at=company.created_at,
        subscription=_build_subscription_detail(sub, invoices) if sub else None,
    )
