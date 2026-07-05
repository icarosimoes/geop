"""Autenticação do Portal do Colaborador (Employee, não User).

Namespace de token completamente separado do fluxo de `User`/`current_user`:
o token `employee_session` nunca deve abrir rotas protegidas por
`require_permission` (que exige `access` de `User`), e vice-versa.
"""

from dataclasses import dataclass
from typing import Annotated

import jwt
import structlog
from fastapi import Depends, HTTPException
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings, get_settings
from app.core.dependencies import require_session
from app.core.security import decode_employee_session_token
from app.models import Employee

logger = structlog.get_logger()

employee_oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/timeclock/mobile/login")


@dataclass
class AuthenticatedEmployee:
    employee_id: int
    company_id: int


async def require_employee_session(
    token: Annotated[str, Depends(employee_oauth2_scheme)],
    session: Annotated[AsyncSession, Depends(require_session)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> AuthenticatedEmployee:
    try:
        claims = decode_employee_session_token(token, settings.jwt_secret)
        employee_id = int(claims["sub"])
        company_id = int(claims["company_id"])
    except (jwt.InvalidTokenError, KeyError, TypeError, ValueError) as exc:
        raise HTTPException(status_code=401, detail={"code": "invalid_token"}) from exc

    employee = await session.scalar(
        select(Employee).where(
            Employee.id == employee_id,
            Employee.company_id == company_id,
            Employee.deleted_at.is_(None),
            Employee.status == "active",
        )
    )
    if employee is None:
        raise HTTPException(status_code=401, detail={"code": "inactive_employee"})

    if session.bind is not None and session.bind.dialect.name == "postgresql":
        await session.execute(
            text("SELECT set_config('app.current_company_id', :cid, true)"),
            {"cid": str(company_id)},
        )
    structlog.contextvars.bind_contextvars(company_id=company_id, employee_id=employee_id)
    return AuthenticatedEmployee(employee_id=employee_id, company_id=company_id)
