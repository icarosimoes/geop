from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from uuid import uuid4

import structlog
from fastapi import APIRouter, FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from starlette.middleware.base import BaseHTTPMiddleware
from uvicorn.middleware.proxy_headers import ProxyHeadersMiddleware

from app.core.config import get_settings
from app.core.database import engine
from app.core.logging import configure_logging
from app.core.rate_limit import limiter
from app.domain.apartment_inspections.router import router as apartment_inspections_router
from app.domain.attachments.router import router as attachments_router
from app.domain.audit_reports.router import router as audit_reports_router
from app.domain.auth.router import router as auth_router
from app.domain.bulletin.router import router as bulletin_router
from app.domain.check_suites.router import router as check_suites_router
from app.domain.checklists.router import router as checklists_router
from app.domain.dashboard.router import router as dashboard_router
from app.domain.employees.router import router as employees_router
from app.domain.fiscal_requests.router import router as fiscal_requests_router
from app.domain.handoffs.router import router as handoffs_router
from app.domain.health.router import router as health_router
from app.domain.inspection_suites.router import router as inspection_suites_router
from app.domain.maintenance.router import router as maintenance_router
from app.domain.meetings.router import router as meetings_router
from app.domain.modules.router import router as modules_router
from app.domain.notifications.router import router as notifications_router
from app.domain.occurrences.router import router as occurrences_router
from app.domain.platform.router import router as platform_router
from app.domain.platform.webhook_router import router as asaas_webhook_router
from app.domain.preventive_plans.router import router as preventive_plans_router
from app.domain.procedures.router import router as procedures_router
from app.domain.registries.router import router as registries_router
from app.domain.roles.router import router as roles_router
from app.domain.settings.router import router as settings_router
from app.domain.shift_reports.router import router as shift_reports_router
from app.domain.stock.router import router as stock_router
from app.domain.timeclock.mobile_router import router as timeclock_mobile_router
from app.domain.timeclock.router import router as timeclock_router
from app.domain.timeclock.webhook_router import router as timeclock_webhook_router
from app.domain.timeline.router import router as timeline_router
from app.domain.users.router import router as users_router
from app.domain.work_diaries.router import router as work_diaries_router
from app.domain.work_orders.router import router as work_orders_router

settings = get_settings()
configure_logging(settings.environment)

if settings.sentry_dsn:
    try:
        import sentry_sdk

        sentry_sdk.init(
            dsn=settings.sentry_dsn,
            environment=settings.environment,
            traces_sample_rate=0.1,
            profiles_sample_rate=0.1,
            send_default_pii=False,
        )
    except ImportError:
        pass

logger = structlog.get_logger()


class RequestLoggingMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next) -> Response:  # type: ignore[override]
        structlog.contextvars.clear_contextvars()
        structlog.contextvars.bind_contextvars(
            request_id=request.headers.get("X-Request-ID") or uuid4().hex,
            method=request.method,
            path=request.url.path,
        )
        response: Response = await call_next(request)
        if response.status_code >= 500:
            logger.error("request_error", status=response.status_code)
        return response


@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncIterator[None]:
    from app.core.cache import start_redis, stop_redis

    try:
        from app.core.storage import ensure_bucket

        ensure_bucket()
    except Exception:
        pass
    await start_redis(settings.redis_url)
    yield
    await stop_redis()
    if engine is not None:
        await engine.dispose()


app = FastAPI(
    title=settings.app_name,
    version="0.1.0",
    docs_url="/docs" if settings.environment != "production" else None,
    redoc_url=None,
    lifespan=lifespan,
)
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)


@app.exception_handler(ValueError)
async def value_error_handler(request: Request, exc: ValueError):
    return JSONResponse(
        status_code=422,
        content={"detail": str(exc)},
    )


app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.web_origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type", "X-Request-ID", "X-Registro-Key"],
)
app.add_middleware(RequestLoggingMiddleware)
app.add_middleware(ProxyHeadersMiddleware, trusted_hosts=["*"])

v1_router = APIRouter(prefix=settings.api_prefix)
v1_router.include_router(health_router)
v1_router.include_router(auth_router)
v1_router.include_router(dashboard_router)
v1_router.include_router(employees_router)
v1_router.include_router(occurrences_router)
v1_router.include_router(fiscal_requests_router)
v1_router.include_router(users_router)
v1_router.include_router(registries_router)
v1_router.include_router(modules_router)
v1_router.include_router(notifications_router)
v1_router.include_router(settings_router)
v1_router.include_router(timeline_router)
v1_router.include_router(procedures_router)
v1_router.include_router(roles_router)
v1_router.include_router(attachments_router)
v1_router.include_router(platform_router)
v1_router.include_router(shift_reports_router)
v1_router.include_router(meetings_router)
v1_router.include_router(check_suites_router)
v1_router.include_router(inspection_suites_router)
v1_router.include_router(apartment_inspections_router)
v1_router.include_router(audit_reports_router)
v1_router.include_router(work_diaries_router)
v1_router.include_router(maintenance_router)
v1_router.include_router(bulletin_router)
v1_router.include_router(work_orders_router)
v1_router.include_router(preventive_plans_router)
v1_router.include_router(checklists_router)
v1_router.include_router(stock_router)
v1_router.include_router(handoffs_router)
v1_router.include_router(timeclock_router)
v1_router.include_router(timeclock_mobile_router)
v1_router.include_router(timeclock_webhook_router)
v1_router.include_router(asaas_webhook_router)
app.include_router(v1_router)
