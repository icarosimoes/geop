from datetime import date, datetime, time
from decimal import Decimal

import sqlalchemy as sa
from sqlalchemy import (
    JSON,
    Boolean,
    Date,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    SmallInteger,
    String,
    Text,
    Time,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TenantMixin, TimestampMixin


class LegacyEntityMixin:
    legacy_id: Mapped[int | None] = mapped_column(Integer, nullable=True)


class Sector(Base, TenantMixin, LegacyEntityMixin, TimestampMixin):
    __tablename__ = "sectors"
    __table_args__ = (UniqueConstraint("company_id", "legacy_id", name="uq_sectors_legacy"),)

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(255))
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime)


class Location(Base, TenantMixin, LegacyEntityMixin, TimestampMixin):
    __tablename__ = "locations"
    __table_args__ = (UniqueConstraint("company_id", "legacy_id", name="uq_locations_legacy"),)

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(255))
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime)


class Function(Base, TenantMixin, LegacyEntityMixin, TimestampMixin):
    __tablename__ = "functions"
    __table_args__ = (UniqueConstraint("company_id", "legacy_id", name="uq_functions_legacy"),)

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(255))
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime)


class Procedure(Base, TenantMixin, LegacyEntityMixin, TimestampMixin):
    __tablename__ = "procedures"
    __table_args__ = (UniqueConstraint("company_id", "legacy_id", name="uq_procedures_legacy"),)

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(255))
    link: Mapped[str | None] = mapped_column(String(255))
    file: Mapped[str | None] = mapped_column(String(255))
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime)


class Occurrence(Base, TenantMixin, LegacyEntityMixin, TimestampMixin):
    __tablename__ = "occurrences"
    __table_args__ = (UniqueConstraint("company_id", "legacy_id", name="uq_occurrences_legacy"),)

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    title: Mapped[str] = mapped_column(String(255))
    description: Mapped[str | None] = mapped_column(Text)
    comments: Mapped[str | None] = mapped_column(Text)
    unit: Mapped[str | None] = mapped_column(String(255))
    deadline: Mapped[date | None] = mapped_column(Date)
    status: Mapped[int] = mapped_column(Integer, default=1, index=True)
    legacy_type_id: Mapped[int | None] = mapped_column(Integer)
    legacy_receiver_user_id: Mapped[int | None] = mapped_column(Integer)
    location_id: Mapped[int | None] = mapped_column(
        ForeignKey("locations.id", ondelete="SET NULL"),
    )
    sector_id: Mapped[int | None] = mapped_column(
        ForeignKey("sectors.id", ondelete="SET NULL"),
    )
    owner_user_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"),
    )
    created_by_user_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"),
    )
    updated_by_user_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"),
    )
    notify_user_ids: Mapped[list | None] = mapped_column(JSON)
    file: Mapped[str | None] = mapped_column(Text)
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime)


class FiscalRequest(Base, TenantMixin, TimestampMixin):
    __tablename__ = "fiscal_requests"
    __table_args__ = (Index("ix_fiscal_requests_company_status", "company_id", "status"),)

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    protocol: Mapped[str] = mapped_column(String(40), unique=True)
    request_type: Mapped[str] = mapped_column(String(120), index=True)
    title: Mapped[str | None] = mapped_column(String(255))
    apartment: Mapped[str | None] = mapped_column(String(40))
    requester: Mapped[str] = mapped_column(String(160))
    requester_email: Mapped[str | None] = mapped_column(String(255), index=True)
    requester_user_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"),
        index=True,
    )
    responsible_user_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"),
        index=True,
    )
    chess_user_id: Mapped[str | None] = mapped_column(String(80))
    reservation_number: Mapped[str | None] = mapped_column(String(80))
    sla_deadline: Mapped[datetime | None] = mapped_column(DateTime)
    sla_paused_at: Mapped[datetime | None] = mapped_column(DateTime)
    sla_paused_seconds: Mapped[int] = mapped_column(Integer, default=0)
    description: Mapped[str | None] = mapped_column(Text)
    origin: Mapped[str] = mapped_column(String(80), default="chess-hotel")
    status: Mapped[str] = mapped_column(String(40), default="Em andamento", index=True)
    payload: Mapped[dict] = mapped_column(JSON)


class AuditEvent(Base, TenantMixin):
    __tablename__ = "audit_events"
    __table_args__ = (
        Index("ix_audit_events_company_entity", "company_id", "entity_type", "entity_id"),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    entity_type: Mapped[str] = mapped_column(String(80))
    entity_id: Mapped[int] = mapped_column(Integer)
    event_type: Mapped[str] = mapped_column(String(40))
    diff: Mapped[dict | None] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())


class ModuleRecord(Base, TenantMixin, TimestampMixin):
    __tablename__ = "module_records"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    legacy_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    module: Mapped[str] = mapped_column(String(80), index=True)
    title: Mapped[str] = mapped_column(String(255))
    description: Mapped[str | None] = mapped_column(Text)
    category: Mapped[str | None] = mapped_column(String(120))
    status: Mapped[str] = mapped_column(String(60), default="Em andamento")
    owner_user_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"),
    )
    created_by_user_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"),
    )
    notify_user_ids: Mapped[list | None] = mapped_column(JSON)
    payload: Mapped[dict | None] = mapped_column(JSON)
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime)


class Notification(Base, TenantMixin):
    __tablename__ = "notifications"
    __table_args__ = (Index("ix_notifications_user_unread", "user_id", "read_at"),)

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    title: Mapped[str] = mapped_column(String(255))
    body: Mapped[str | None] = mapped_column(Text)
    category: Mapped[str] = mapped_column(String(60), default="info", index=True)
    entity_type: Mapped[str | None] = mapped_column(String(80))
    entity_id: Mapped[int | None] = mapped_column(Integer)
    read_at: Mapped[datetime | None] = mapped_column(DateTime)
    email_sent_at: Mapped[datetime | None] = mapped_column(DateTime)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())


class NotificationPreference(Base, TenantMixin):
    __tablename__ = "notification_preferences"
    __table_args__ = (
        UniqueConstraint("user_id", "company_id", "module", name="uq_notif_pref_user_module"),
        Index("ix_notif_pref_company_user", "company_id", "user_id"),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    module: Mapped[str] = mapped_column(String(80))
    in_app: Mapped[bool] = mapped_column(Boolean, server_default=sa.true())
    email: Mapped[bool] = mapped_column(Boolean, server_default=sa.true())


class Attachment(Base, TenantMixin):
    __tablename__ = "attachments"
    __table_args__ = (
        Index("ix_attachments_company_entity", "company_id", "entity_type", "entity_id"),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    entity_type: Mapped[str] = mapped_column(String(80))
    entity_id: Mapped[int] = mapped_column(Integer)
    filename: Mapped[str] = mapped_column(String(255))
    content_type: Mapped[str] = mapped_column(String(120))
    size_bytes: Mapped[int] = mapped_column(Integer)
    storage_key: Mapped[str] = mapped_column(String(500), unique=True)
    uploaded_by_user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id"),
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        server_default=func.now(),
    )


class OccurrenceParticipant(Base):
    __tablename__ = "occurrence_participants"

    occurrence_id: Mapped[int] = mapped_column(
        ForeignKey("occurrences.id", ondelete="CASCADE"),
        primary_key=True,
    )
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"),
        primary_key=True,
    )
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())


class Meeting(Base, TenantMixin, LegacyEntityMixin, TimestampMixin):
    __tablename__ = "meetings"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    title: Mapped[str] = mapped_column(String(255))
    description: Mapped[str | None] = mapped_column(Text)
    scheduled_at: Mapped[datetime | None] = mapped_column(DateTime)
    location: Mapped[str | None] = mapped_column(String(255))
    status: Mapped[str] = mapped_column(String(60), default="Agendada")
    owner_user_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"),
    )
    created_by_user_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"),
    )
    notify_user_ids: Mapped[list | None] = mapped_column(JSON)
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime)


class MeetingParticipant(Base):
    __tablename__ = "meeting_participants"
    __table_args__ = (UniqueConstraint("meeting_id", "user_id", name="uq_meeting_participant"),)

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    meeting_id: Mapped[int] = mapped_column(
        ForeignKey("meetings.id", ondelete="CASCADE"),
    )
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"),
    )
    role: Mapped[str] = mapped_column(String(20), default="attendee")
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())


class MeetingSubject(Base):
    __tablename__ = "meeting_subjects"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    meeting_id: Mapped[int] = mapped_column(
        ForeignKey("meetings.id", ondelete="CASCADE"),
    )
    title: Mapped[str] = mapped_column(String(255))
    description: Mapped[str | None] = mapped_column(Text)
    sort_order: Mapped[int] = mapped_column(Integer, default=0)
    resolved: Mapped[bool] = mapped_column(default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())


class ShiftReport(Base, TenantMixin, LegacyEntityMixin, TimestampMixin):
    __tablename__ = "shift_reports"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    title: Mapped[str] = mapped_column(String(255))
    description: Mapped[str | None] = mapped_column(Text)
    shift_date: Mapped[date | None] = mapped_column(Date)
    shift_type: Mapped[str | None] = mapped_column(String(20))
    status: Mapped[str] = mapped_column(String(60), default="Em andamento")
    started_at: Mapped[datetime | None] = mapped_column(DateTime)
    ended_at: Mapped[datetime | None] = mapped_column(DateTime)
    supervisor: Mapped[str | None] = mapped_column(String(120))
    occupation: Mapped[str | None] = mapped_column(String(20))
    average_daily: Mapped[str | None] = mapped_column(String(20))
    guests: Mapped[int | None] = mapped_column(Integer)
    uhs: Mapped[int | None] = mapped_column(Integer)
    maintenance_count: Mapped[int | None] = mapped_column(Integer)
    cleaning: Mapped[int | None] = mapped_column(Integer)
    walk_in: Mapped[int | None] = mapped_column(Integer)
    input_quantity: Mapped[int | None] = mapped_column(Integer)
    output_quantity: Mapped[int | None] = mapped_column(Integer)
    return_of_customers: Mapped[int | None] = mapped_column(Integer)
    observations: Mapped[str | None] = mapped_column(Text)
    notes_ab: Mapped[str | None] = mapped_column(Text)
    notes_reception: Mapped[str | None] = mapped_column(Text)
    notes_reservations: Mapped[str | None] = mapped_column(Text)
    notes_governance: Mapped[str | None] = mapped_column(Text)
    notes_maintenance: Mapped[str | None] = mapped_column(Text)
    notes_ti: Mapped[str | None] = mapped_column(Text)
    notes_security: Mapped[str | None] = mapped_column(Text)
    payload: Mapped[dict | None] = mapped_column(JSON)
    owner_user_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"),
    )
    created_by_user_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"),
    )
    notify_user_ids: Mapped[list | None] = mapped_column(JSON)
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime)


# ---------------------------------------------------------------------------
# Inspections & Construction (P4)
# ---------------------------------------------------------------------------


class CheckSuite(Base, TenantMixin, TimestampMixin):
    __tablename__ = "check_suites"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(255))
    description: Mapped[str | None] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(60), default="Ativo")
    owner_user_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"),
    )
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime)


class CheckSuiteItem(Base):
    __tablename__ = "check_suite_items"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    suite_id: Mapped[int] = mapped_column(
        ForeignKey("check_suites.id", ondelete="CASCADE"),
    )
    label: Mapped[str] = mapped_column(String(255))
    sort_order: Mapped[int] = mapped_column(Integer, default=0)
    checked: Mapped[bool] = mapped_column(Boolean, default=False)


class InspectionSuite(Base, TenantMixin, TimestampMixin):
    __tablename__ = "inspection_suites"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(255))
    description: Mapped[str | None] = mapped_column(Text)
    type: Mapped[str | None] = mapped_column(String(80))
    status: Mapped[str] = mapped_column(String(60), default="Ativo")
    owner_user_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"),
    )
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime)


class InspectionSuiteItem(Base):
    __tablename__ = "inspection_suite_items"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    suite_id: Mapped[int] = mapped_column(
        ForeignKey("inspection_suites.id", ondelete="CASCADE"),
    )
    area: Mapped[str | None] = mapped_column(String(255))
    item_name: Mapped[str] = mapped_column(String(255))
    expected_condition: Mapped[str | None] = mapped_column(String(255))
    sort_order: Mapped[int] = mapped_column(Integer, default=0)


class ApartmentInspection(Base, TenantMixin, TimestampMixin):
    __tablename__ = "apartment_inspections"
    __table_args__ = (Index("ix_apartment_inspections_type", "company_id", "inspection_type"),)

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    unit: Mapped[str | None] = mapped_column(String(80))
    apartment: Mapped[str | None] = mapped_column(String(80))
    inspection_type: Mapped[str] = mapped_column(String(40))
    inspection_suite_id: Mapped[int | None] = mapped_column(
        ForeignKey("inspection_suites.id", ondelete="SET NULL"),
    )
    inspector_user_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"),
    )
    scheduled_at: Mapped[datetime | None] = mapped_column(DateTime)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime)
    status: Mapped[str] = mapped_column(String(60), default="Pendente")
    notes: Mapped[str | None] = mapped_column(Text)
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime)


class ApartmentInspectionItem(Base):
    __tablename__ = "apartment_inspection_items"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    inspection_id: Mapped[int] = mapped_column(
        ForeignKey("apartment_inspections.id", ondelete="CASCADE"),
    )
    suite_item_id: Mapped[int | None] = mapped_column(
        ForeignKey("inspection_suite_items.id", ondelete="SET NULL"),
    )
    condition: Mapped[str] = mapped_column(String(40), default="ok")
    notes: Mapped[str | None] = mapped_column(Text)
    sort_order: Mapped[int] = mapped_column(Integer, default=0)


class AuditReport(Base, TenantMixin, TimestampMixin):
    __tablename__ = "audit_reports"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    report_date: Mapped[date] = mapped_column(Date)
    shift_type: Mapped[str | None] = mapped_column(String(20))
    auditor_user_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"),
    )
    status: Mapped[str] = mapped_column(String(60), default="Em andamento")
    notes: Mapped[str | None] = mapped_column(Text)
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime)


class AuditReportItem(Base):
    __tablename__ = "audit_report_items"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    report_id: Mapped[int] = mapped_column(
        ForeignKey("audit_reports.id", ondelete="CASCADE"),
    )
    category: Mapped[str | None] = mapped_column(String(120))
    description: Mapped[str | None] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(40), default="ok")
    notes: Mapped[str | None] = mapped_column(Text)
    sort_order: Mapped[int] = mapped_column(Integer, default=0)


class WorkDiary(Base, TenantMixin, TimestampMixin):
    __tablename__ = "work_diaries"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    diary_date: Mapped[date] = mapped_column(Date)
    title: Mapped[str] = mapped_column(String(255))
    description: Mapped[str | None] = mapped_column(Text)
    weather: Mapped[str | None] = mapped_column(String(60))
    status: Mapped[str] = mapped_column(String(60), default="Em andamento")
    owner_user_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"),
    )
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime)


class WorkDiaryActivity(Base):
    __tablename__ = "work_diary_activities"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    diary_id: Mapped[int] = mapped_column(
        ForeignKey("work_diaries.id", ondelete="CASCADE"),
    )
    description: Mapped[str] = mapped_column(Text)
    start_time: Mapped[datetime | None] = mapped_column(DateTime)
    end_time: Mapped[datetime | None] = mapped_column(DateTime)
    status: Mapped[str] = mapped_column(String(60), default="Planejada")
    sort_order: Mapped[int] = mapped_column(Integer, default=0)


class WorkDiaryTeam(Base):
    __tablename__ = "work_diary_teams"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    diary_id: Mapped[int] = mapped_column(
        ForeignKey("work_diaries.id", ondelete="CASCADE"),
    )
    worker_name: Mapped[str] = mapped_column(String(160))
    role: Mapped[str | None] = mapped_column(String(120))
    hours_worked: Mapped[Decimal | None] = mapped_column(Numeric(5, 2))
    sort_order: Mapped[int] = mapped_column(Integer, default=0)


class WorkDiaryEquipment(Base):
    __tablename__ = "work_diary_equipment"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    diary_id: Mapped[int] = mapped_column(
        ForeignKey("work_diaries.id", ondelete="CASCADE"),
    )
    equipment_name: Mapped[str] = mapped_column(String(160))
    quantity: Mapped[int] = mapped_column(Integer, default=1)
    hours_used: Mapped[Decimal | None] = mapped_column(Numeric(5, 2))
    sort_order: Mapped[int] = mapped_column(Integer, default=0)


class WorkDiaryObservation(Base):
    __tablename__ = "work_diary_observations"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    diary_id: Mapped[int] = mapped_column(
        ForeignKey("work_diaries.id", ondelete="CASCADE"),
    )
    content: Mapped[str] = mapped_column(Text)
    category: Mapped[str | None] = mapped_column(String(80))
    sort_order: Mapped[int] = mapped_column(Integer, default=0)


class MaintenanceRecord(Base, TenantMixin, LegacyEntityMixin, TimestampMixin):
    __tablename__ = "maintenance_records"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    title: Mapped[str] = mapped_column(String(255))
    description: Mapped[str | None] = mapped_column(Text)
    category: Mapped[str | None] = mapped_column(String(120))
    status: Mapped[str] = mapped_column(String(60), default="Em andamento")
    priority: Mapped[str | None] = mapped_column(String(20))
    location_id: Mapped[int | None] = mapped_column(
        ForeignKey("locations.id", ondelete="SET NULL"),
    )
    owner_user_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"),
    )
    created_by_user_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"),
    )
    notify_user_ids: Mapped[list | None] = mapped_column(JSON)
    payload: Mapped[dict | None] = mapped_column(JSON)
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime)


class BulletinPost(Base, TenantMixin, TimestampMixin):
    __tablename__ = "bulletin_posts"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    title: Mapped[str] = mapped_column(String(255))
    body: Mapped[str | None] = mapped_column(Text)
    pinned: Mapped[bool] = mapped_column(Boolean, default=False)
    expires_at: Mapped[datetime | None] = mapped_column(DateTime)
    author_user_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"),
    )
    notify_user_ids: Mapped[list | None] = mapped_column(JSON)
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime)


# ---------------------------------------------------------------------------
# Work Orders (P6)
# ---------------------------------------------------------------------------

WORK_ORDER_STATUSES = ("aberta", "em_andamento", "aguardando_material", "concluida", "validada")


class WorkOrder(Base, TenantMixin, TimestampMixin):
    __tablename__ = "work_orders"
    __table_args__ = (Index("ix_work_orders_status", "company_id", "status"),)

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    title: Mapped[str] = mapped_column(String(255))
    description: Mapped[str | None] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(40), default="aberta")
    priority: Mapped[str | None] = mapped_column(String(20))
    category: Mapped[str | None] = mapped_column(String(120))
    location_id: Mapped[int | None] = mapped_column(
        ForeignKey("locations.id", ondelete="SET NULL"),
    )
    occurrence_id: Mapped[int | None] = mapped_column(
        ForeignKey("occurrences.id", ondelete="SET NULL"),
    )
    maintenance_id: Mapped[int | None] = mapped_column(
        ForeignKey("maintenance_records.id", ondelete="SET NULL"),
    )
    assigned_user_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"),
    )
    created_by_user_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"),
    )
    validated_by_user_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"),
    )
    notify_user_ids: Mapped[list | None] = mapped_column(JSON)
    sla_hours: Mapped[int | None] = mapped_column(Integer)
    sla_deadline: Mapped[datetime | None] = mapped_column(DateTime)
    started_at: Mapped[datetime | None] = mapped_column(DateTime)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime)
    validated_at: Mapped[datetime | None] = mapped_column(DateTime)
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime)


# ---------------------------------------------------------------------------
# Stock / Materials Control (P7)
# ---------------------------------------------------------------------------

MOVEMENT_TYPES = ("entrada", "saida", "ajuste")


class StockItem(Base, TenantMixin, TimestampMixin):
    __tablename__ = "stock_items"
    __table_args__ = (Index("ix_stock_items_company", "company_id"),)

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(255))
    category: Mapped[str | None] = mapped_column(String(120))
    unit: Mapped[str] = mapped_column(String(40), default="un")
    min_quantity: Mapped[int] = mapped_column(Integer, default=0)
    current_quantity: Mapped[int] = mapped_column(Integer, default=0)
    location_id: Mapped[int | None] = mapped_column(
        ForeignKey("locations.id", ondelete="SET NULL"),
    )
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime)


class StockMovement(Base, TenantMixin, TimestampMixin):
    __tablename__ = "stock_movements"
    __table_args__ = (Index("ix_stock_movements_item", "item_id"),)

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    item_id: Mapped[int] = mapped_column(
        ForeignKey("stock_items.id", ondelete="CASCADE"),
    )
    movement_type: Mapped[str] = mapped_column(String(20))
    quantity: Mapped[int] = mapped_column(Integer)
    reason: Mapped[str | None] = mapped_column(String(255))
    work_order_id: Mapped[int | None] = mapped_column(
        ForeignKey("work_orders.id", ondelete="SET NULL"),
    )
    occurrence_id: Mapped[int | None] = mapped_column(
        ForeignKey("occurrences.id", ondelete="SET NULL"),
    )
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"),
    )


# ---------------------------------------------------------------------------
# Shift Handoff (P7)
# ---------------------------------------------------------------------------

HANDOFF_STATUS = ("pendente", "lido", "resolvido")


class ShiftHandoff(Base, TenantMixin, TimestampMixin):
    __tablename__ = "shift_handoffs"
    __table_args__ = (Index("ix_shift_handoffs_company_date", "company_id", "target_date"),)

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    shift_report_id: Mapped[int | None] = mapped_column(
        ForeignKey("shift_reports.id", ondelete="SET NULL"),
    )
    title: Mapped[str] = mapped_column(String(255))
    description: Mapped[str | None] = mapped_column(Text)
    priority: Mapped[str] = mapped_column(String(20), default="normal")
    category: Mapped[str | None] = mapped_column(String(120))
    target_shift: Mapped[str | None] = mapped_column(String(20))
    target_date: Mapped[date] = mapped_column(Date)
    status: Mapped[str] = mapped_column(String(20), default="pendente")
    read_at: Mapped[datetime | None] = mapped_column(DateTime)
    read_by_user_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"),
    )
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime)
    resolved_by_user_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"),
    )
    resolution_notes: Mapped[str | None] = mapped_column(Text)
    created_by_user_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"),
    )
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime)


# ---------------------------------------------------------------------------
# Preventive Maintenance Plans (P7)
# ---------------------------------------------------------------------------

RECURRENCE_TYPES = ("daily", "weekly", "biweekly", "monthly", "quarterly", "semiannual", "annual")


class PreventivePlan(Base, TenantMixin, TimestampMixin):
    __tablename__ = "preventive_plans"
    __table_args__ = (Index("ix_preventive_plans_company_active", "company_id", "active"),)

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(255))
    description: Mapped[str | None] = mapped_column(Text)
    recurrence: Mapped[str] = mapped_column(String(20))
    category: Mapped[str | None] = mapped_column(String(120))
    priority: Mapped[str] = mapped_column(String(20), default="media")
    sla_hours: Mapped[int | None] = mapped_column(Integer)
    location_id: Mapped[int | None] = mapped_column(
        ForeignKey("locations.id", ondelete="SET NULL"),
    )
    assigned_user_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"),
    )
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    next_due: Mapped[date | None] = mapped_column(Date)
    last_generated_at: Mapped[datetime | None] = mapped_column(DateTime)
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime)


# ---------------------------------------------------------------------------
# Recurring Checklists (P7)
# ---------------------------------------------------------------------------

CHECKLIST_RECURRENCE_TYPES = ("daily", "weekly", "biweekly", "monthly")


class ChecklistTemplate(Base, TenantMixin, TimestampMixin):
    __tablename__ = "checklist_templates"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(255))
    description: Mapped[str | None] = mapped_column(Text)
    recurrence: Mapped[str] = mapped_column(String(20))
    category: Mapped[str | None] = mapped_column(String(120))
    assigned_user_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"),
    )
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    next_due: Mapped[date | None] = mapped_column(Date)
    last_generated_at: Mapped[datetime | None] = mapped_column(DateTime)
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime)


class ChecklistTemplateItem(Base):
    __tablename__ = "checklist_template_items"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    template_id: Mapped[int] = mapped_column(
        ForeignKey("checklist_templates.id", ondelete="CASCADE"),
    )
    label: Mapped[str] = mapped_column(String(255))
    sort_order: Mapped[int] = mapped_column(Integer, default=0)


class ChecklistExecution(Base, TenantMixin, TimestampMixin):
    __tablename__ = "checklist_executions"
    __table_args__ = (Index("ix_checklist_exec_company_due", "company_id", "due_date"),)

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    template_id: Mapped[int] = mapped_column(
        ForeignKey("checklist_templates.id", ondelete="CASCADE"),
    )
    due_date: Mapped[date] = mapped_column(Date)
    status: Mapped[str] = mapped_column(String(40), default="pendente")
    completed_at: Mapped[datetime | None] = mapped_column(DateTime)
    completed_by_user_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"),
    )
    notes: Mapped[str | None] = mapped_column(Text)
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime)


class ChecklistExecutionItem(Base):
    __tablename__ = "checklist_execution_items"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    execution_id: Mapped[int] = mapped_column(
        ForeignKey("checklist_executions.id", ondelete="CASCADE"),
    )
    label: Mapped[str] = mapped_column(String(255))
    sort_order: Mapped[int] = mapped_column(Integer, default=0)
    checked: Mapped[bool] = mapped_column(Boolean, default=False)
    checked_at: Mapped[datetime | None] = mapped_column(DateTime)


class LegacyImportRun(Base):
    __tablename__ = "legacy_import_runs"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    source: Mapped[str] = mapped_column(String(80))
    checksum_sha256: Mapped[str] = mapped_column(String(64), unique=True)
    status: Mapped[str] = mapped_column(String(20))
    report: Mapped[str | None] = mapped_column(Text)
    started_at: Mapped[datetime] = mapped_column(DateTime)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime)


# ---------------------------------------------------------------------------
# Ponto eletrônico / Escala de trabalho
# ---------------------------------------------------------------------------


class WorkSchedule(Base, TenantMixin, TimestampMixin):
    __tablename__ = "work_schedules"
    __table_args__ = (
        UniqueConstraint("company_id", "user_id", "weekday", name="uq_work_schedules_user_day"),
        Index("ix_work_schedules_user", "company_id", "user_id"),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    weekday: Mapped[int] = mapped_column(SmallInteger)  # 0=segunda ... 6=domingo
    start_time: Mapped[time] = mapped_column(Time)
    end_time: Mapped[time] = mapped_column(Time)
    break_start: Mapped[time | None] = mapped_column(Time)
    break_end: Mapped[time | None] = mapped_column(Time)
    tolerance_minutes: Mapped[int] = mapped_column(Integer, default=10)
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime)


class TimeClockDevice(Base, TenantMixin, TimestampMixin):
    __tablename__ = "time_clock_devices"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(255))
    model: Mapped[str] = mapped_column(String(40), default="control_id")
    serial_number: Mapped[str | None] = mapped_column(String(120))
    location_id: Mapped[int | None] = mapped_column(
        ForeignKey("locations.id", ondelete="SET NULL"),
    )
    webhook_token: Mapped[str] = mapped_column(String(64), unique=True)
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime)


class TimeClockEnrollment(Base, TenantMixin, TimestampMixin):
    __tablename__ = "time_clock_enrollments"
    __table_args__ = (
        UniqueConstraint("company_id", "external_id", name="uq_timeclock_enrollment_external"),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    external_id: Mapped[str] = mapped_column(String(80))


class TimePunch(Base, TenantMixin):
    __tablename__ = "time_punches"
    __table_args__ = (
        Index("ix_time_punches_user_date", "company_id", "user_id", "punched_at"),
        UniqueConstraint(
            "device_id", "external_event_id", name="uq_time_punches_device_event"
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    device_id: Mapped[int | None] = mapped_column(
        ForeignKey("time_clock_devices.id", ondelete="SET NULL"),
    )
    punched_at: Mapped[datetime] = mapped_column(DateTime)
    punch_type: Mapped[str | None] = mapped_column(String(10))
    source: Mapped[str] = mapped_column(String(20), default="device")
    external_event_id: Mapped[str | None] = mapped_column(String(120))
    status: Mapped[str | None] = mapped_column(String(20))
    raw_payload: Mapped[dict | None] = mapped_column(JSON)
    created_by_user_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"),
    )
    notes: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
