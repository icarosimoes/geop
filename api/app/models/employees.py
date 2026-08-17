from datetime import date, datetime
from decimal import Decimal

import sqlalchemy as sa
from sqlalchemy import Boolean, Date, ForeignKey, Index, Integer, Numeric, String, UniqueConstraint
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

    # Dados contratuais (MVP: cargo, admissão/desligamento, matrícula)
    job_title: Mapped[str | None] = mapped_column(String(120), nullable=True)
    hire_date: Mapped[str | None] = mapped_column(String(10), nullable=True)  # YYYY-MM-DD
    termination_date: Mapped[str | None] = mapped_column(String(10), nullable=True)  # YYYY-MM-DD
    registration_number: Mapped[str | None] = mapped_column(String(40), nullable=True)

    # Salário mensal (usado para calcular o valor em R$ da hora extra no espelho de ponto)
    salary: Mapped[Decimal | None] = mapped_column(Numeric(10, 2), nullable=True)

    # Setor/departamento (reaproveita o cadastro de Setor usado por User/Ocorrências)
    sector_id: Mapped[int | None] = mapped_column(
        ForeignKey("sectors.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )

    # Local de trabalho (usado para geofencing no ponto mobile do Portal do Colaborador)
    location_id: Mapped[int | None] = mapped_column(
        ForeignKey("locations.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )

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


class EmployeeCredential(Base, TenantMixin, TimestampMixin):
    """Credencial de PIN do Portal do Colaborador — separada de Employee (dado de RH)
    para não misturar cadastro com segredo de autenticação. 1:1 com Employee."""

    __tablename__ = "employee_credentials"
    __table_args__ = (UniqueConstraint("employee_id", name="uq_employee_credentials_employee"),)

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    employee_id: Mapped[int] = mapped_column(
        ForeignKey("employees.id", ondelete="CASCADE"),
        index=True,
    )
    pin_hash: Mapped[str] = mapped_column(String(255))
    failed_attempts: Mapped[int] = mapped_column(Integer, default=0)
    locked_until: Mapped[datetime | None] = mapped_column(sa.DateTime, nullable=True)
    must_change_pin: Mapped[bool] = mapped_column(Boolean, default=True)
    pin_set_at: Mapped[datetime | None] = mapped_column(sa.DateTime, nullable=True)
    deleted_at: Mapped[datetime | None] = mapped_column(sa.DateTime, nullable=True)


class EmployeePayslip(Base, TenantMixin):
    """Contracheque (PDF) de um funcionário para uma competência (mês/ano)."""

    __tablename__ = "employee_payslips"
    __table_args__ = (
        UniqueConstraint(
            "company_id", "employee_id", "reference_month", name="uq_employee_payslips_month"
        ),
        Index("ix_employee_payslips_employee", "company_id", "employee_id"),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    employee_id: Mapped[int] = mapped_column(
        ForeignKey("employees.id", ondelete="CASCADE"),
    )
    reference_month: Mapped[date] = mapped_column(Date)
    attachment_id: Mapped[int] = mapped_column(
        ForeignKey("attachments.id", ondelete="CASCADE"),
    )
    uploaded_by_user_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    # Valores estruturados (opcionais): permitem que integrações (ex.: sync com o
    # módulo de Folha do ERP Solid) alimentem a reflexão financeira sem depender
    # de OCR no PDF anexado. Upload manual antigo continua funcionando sem eles.
    gross_amount: Mapped[Decimal | None] = mapped_column(Numeric(15, 2), nullable=True)
    net_amount: Mapped[Decimal | None] = mapped_column(Numeric(15, 2), nullable=True)
    inss_amount: Mapped[Decimal | None] = mapped_column(Numeric(15, 2), nullable=True)
    irrf_amount: Mapped[Decimal | None] = mapped_column(Numeric(15, 2), nullable=True)
    fgts_amount: Mapped[Decimal | None] = mapped_column(Numeric(15, 2), nullable=True)
    created_at: Mapped[datetime] = mapped_column(sa.DateTime, server_default=sa.func.now())
    deleted_at: Mapped[datetime | None] = mapped_column(sa.DateTime, nullable=True)
