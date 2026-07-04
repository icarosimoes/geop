from datetime import datetime

from pydantic import BaseModel, Field


class EmployeeCreate(BaseModel):
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
    status: str = "active"
    user_id: int | None = None


class EmployeeUpdate(BaseModel):
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
    status: str | None = None
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
