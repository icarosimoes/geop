import re
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field, field_validator

from app.core.validators import normalize_doc, validate_cpf

EmployeeStatus = Literal["active", "inactive", "terminated"]


def _validate_cpf(value: str | None) -> str | None:
    if value is None or not value.strip():
        return value
    digits = normalize_doc(value)
    if len(digits) != 11 or not validate_cpf(digits):
        raise ValueError("CPF inválido")
    return digits


def _validate_birth_date(value: str | None) -> str | None:
    if value is None or not value.strip():
        return value
    try:
        datetime.strptime(value, "%Y-%m-%d")
    except ValueError as exc:
        raise ValueError("birth_date deve estar no formato YYYY-MM-DD") from exc
    return value


def _validate_address_zip(value: str | None) -> str | None:
    if value is None or not value.strip():
        return value
    digits = re.sub(r"\D", "", value)
    if len(digits) != 8:
        raise ValueError("address_zip deve ter 8 dígitos (CEP)")
    return f"{digits[:5]}-{digits[5:]}"


class _EmployeeFieldValidators(BaseModel):
    @field_validator("cpf", check_fields=False)
    @classmethod
    def _check_cpf(cls, v: str | None) -> str | None:
        return _validate_cpf(v)

    @field_validator("birth_date", check_fields=False)
    @classmethod
    def _check_birth_date(cls, v: str | None) -> str | None:
        return _validate_birth_date(v)

    @field_validator("address_zip", check_fields=False)
    @classmethod
    def _check_address_zip(cls, v: str | None) -> str | None:
        return _validate_address_zip(v)


class EmployeeCreate(_EmployeeFieldValidators):
    name: str
    cpf: str | None = None
    rg: str | None = None
    birth_date: str | None = None
    phone: str | None = None
    personal_email: str | None = None
    address_street: str | None = None
    address_number: str | None = None
    address_complement: str | None = None
    address_neighborhood: str | None = None
    address_city: str | None = None
    address_state: str | None = None
    address_zip: str | None = None
    status: EmployeeStatus = "active"
    user_id: int | None = None


class EmployeeUpdate(_EmployeeFieldValidators):
    name: str | None = None
    cpf: str | None = None
    rg: str | None = None
    birth_date: str | None = None
    phone: str | None = None
    personal_email: str | None = None
    address_street: str | None = None
    address_number: str | None = None
    address_complement: str | None = None
    address_neighborhood: str | None = None
    address_city: str | None = None
    address_state: str | None = None
    address_zip: str | None = None
    status: EmployeeStatus | None = None
    user_id: int | None = None


class EmployeeSummary(BaseModel):
    id: int
    name: str
    cpf: str | None
    personal_email: str | None
    phone: str | None
    status: str
    user_id: int | None
    avatar_url: str | None
    created_at: datetime
    updated_at: datetime


class EmployeeListResponse(BaseModel):
    items: list[EmployeeSummary]
    total: int
    page: int
    page_size: int


class EmployeeOption(BaseModel):
    id: int
    name: str


class EmployeeExternalIdCreate(BaseModel):
    system: str = Field(min_length=1, max_length=40)
    external_id: str = Field(min_length=1, max_length=120)


class EmployeeExternalIdSummary(BaseModel):
    id: int
    employee_id: int
    system: str
    external_id: str


class EmployeeDetailedSummary(EmployeeSummary):
    rg: str | None
    birth_date: str | None
    address_street: str | None
    address_number: str | None
    address_complement: str | None
    address_neighborhood: str | None
    address_city: str | None
    address_state: str | None
    address_zip: str | None
    external_ids: list[EmployeeExternalIdSummary] = Field(default_factory=list)
