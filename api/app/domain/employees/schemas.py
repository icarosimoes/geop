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


def _validate_cpf_required(value: str) -> str:
    if not value or not value.strip():
        raise ValueError("CPF é obrigatório")
    return _validate_cpf(value)


def _validate_date_format(value: str | None, field_name: str) -> str | None:
    if value is None or not value.strip():
        return value
    try:
        datetime.strptime(value, "%Y-%m-%d")
    except ValueError as exc:
        raise ValueError(f"{field_name} deve estar no formato YYYY-MM-DD") from exc
    return value


def _validate_address_zip(value: str | None) -> str | None:
    if value is None or not value.strip():
        return value
    digits = re.sub(r"\D", "", value)
    if len(digits) != 8:
        raise ValueError("address_zip deve ter 8 dígitos (CEP)")
    return f"{digits[:5]}-{digits[5:]}"


class _EmployeeFieldValidators(BaseModel):
    @field_validator("birth_date", check_fields=False)
    @classmethod
    def _check_birth_date(cls, v: str | None) -> str | None:
        return _validate_date_format(v, "birth_date")

    @field_validator("address_zip", check_fields=False)
    @classmethod
    def _check_address_zip(cls, v: str | None) -> str | None:
        return _validate_address_zip(v)


class EmployeeCreate(_EmployeeFieldValidators):
    name: str
    cpf: str
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
    job_title: str | None = None
    hire_date: str | None = None
    termination_date: str | None = None
    registration_number: str | None = None
    salary: float | None = None
    sector_id: int | None = None

    @field_validator("cpf")
    @classmethod
    def _check_cpf(cls, v: str) -> str:
        return _validate_cpf_required(v)

    @field_validator("hire_date")
    @classmethod
    def _check_hire_date(cls, v: str | None) -> str | None:
        return _validate_date_format(v, "hire_date")

    @field_validator("termination_date")
    @classmethod
    def _check_termination_date(cls, v: str | None) -> str | None:
        return _validate_date_format(v, "termination_date")


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
    job_title: str | None = None
    hire_date: str | None = None
    termination_date: str | None = None
    registration_number: str | None = None
    salary: float | None = None
    sector_id: int | None = None

    @field_validator("cpf")
    @classmethod
    def _check_cpf(cls, v: str | None) -> str | None:
        return _validate_cpf(v)

    @field_validator("hire_date")
    @classmethod
    def _check_hire_date(cls, v: str | None) -> str | None:
        return _validate_date_format(v, "hire_date")

    @field_validator("termination_date")
    @classmethod
    def _check_termination_date(cls, v: str | None) -> str | None:
        return _validate_date_format(v, "termination_date")


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
    job_title: str | None
    hire_date: str | None
    termination_date: str | None
    registration_number: str | None
    salary: float | None
    sector_id: int | None
    sector_name: str | None
    external_ids: list[EmployeeExternalIdSummary] = Field(default_factory=list)


class EmployeeImportRowResult(BaseModel):
    row: int
    ok: bool
    name: str | None = None
    id: int | None = None
    error: str | None = None


class EmployeeImportResult(BaseModel):
    total: int
    created: int
    failed: int
    results: list[EmployeeImportRowResult]
