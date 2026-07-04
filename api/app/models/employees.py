from datetime import datetime

import sqlalchemy as sa
from sqlalchemy import ForeignKey, Index, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TenantMixin, TimestampMixin


class Employee(Base, TenantMixin, TimestampMixin):
    """Funcionário: entidade de RH separada de User (que é conta de login)."""

    __tablename__ = "employees"
    __table_args__ = (
        UniqueConstraint("company_id", "cpf", name="uq_employees_company_cpf"),
        Index("ix_employees_status", "company_id", "status"),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)

    # Dados pessoais
    name: Mapped[str] = mapped_column(String(255))
    cpf: Mapped[str | None] = mapped_column(String(11), nullable=True)
    rg: Mapped[str | None] = mapped_column(String(20), nullable=True)
    birth_date: Mapped[str | None] = mapped_column(String(10), nullable=True)  # YYYY-MM-DD
    phone: Mapped[str | None] = mapped_column(String(20), nullable=True)
    personal_email: Mapped[str | None] = mapped_column(String(255), nullable=True, index=True)

    # Endereço
    address_street: Mapped[str | None] = mapped_column(String(255), nullable=True)
    address_number: Mapped[str | None] = mapped_column(String(20), nullable=True)
    address_complement: Mapped[str | None] = mapped_column(String(255), nullable=True)
    address_neighborhood: Mapped[str | None] = mapped_column(String(255), nullable=True)
    address_city: Mapped[str | None] = mapped_column(String(100), nullable=True)
    address_state: Mapped[str | None] = mapped_column(String(2), nullable=True)
    address_zip: Mapped[str | None] = mapped_column(String(10), nullable=True)

    # Organizacional: status "active", "inactive" ou "terminated"
    status: Mapped[str] = mapped_column(String(20), default="active")
    avatar_url: Mapped[str | None] = mapped_column(String(500), nullable=True)

    # Vínculo opcional com User (nem todo employee loga no sistema)
    user_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )

    # Auditoria
    deleted_at: Mapped[datetime | None] = mapped_column(sa.DateTime, nullable=True)


class EmployeeExternalId(Base, TenantMixin):
    """Identificadores externos do funcionário em sistemas integrados (ERP, folha, etc)."""

    __tablename__ = "employee_external_ids"
    __table_args__ = (
        UniqueConstraint("company_id", "system", "external_id", name="uq_employee_external_id"),
        Index("ix_employee_external_system", "company_id", "system"),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    employee_id: Mapped[int] = mapped_column(
        ForeignKey("employees.id", ondelete="CASCADE"),
        index=True,
    )
    system: Mapped[str] = mapped_column(String(40))  # "totvs", "senior", "chess-hotel", etc
    external_id: Mapped[str] = mapped_column(String(120))  # ID no sistema externo
    created_at: Mapped[datetime] = mapped_column(sa.DateTime, server_default=sa.func.now())
    updated_at: Mapped[datetime] = mapped_column(
        sa.DateTime, server_default=sa.func.now(), onupdate=sa.func.now()
    )
