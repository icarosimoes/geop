from collections import Counter
from datetime import date, datetime
from typing import NamedTuple

from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import aliased

from app.core.audit import compute_diff, record_event
from app.models import DiscrepancyReport, DiscrepancyReportEntry, Location, User


class DiscrepancyReportRow(NamedTuple):
    report: DiscrepancyReport
    prepared_by_name: str | None
    entry_count: int
    discrepancy_count: int


class DiscrepancyReportDetail(NamedTuple):
    report: DiscrepancyReport
    prepared_by_name: str | None
    checked_by_name: str | None
    received_by_name: str | None
    entries: list[tuple[DiscrepancyReportEntry, str]]


async def _entry_rows(
    session: AsyncSession,
    company_id: int,
    report_id: int,
) -> list[tuple[DiscrepancyReportEntry, str]]:
    rows = await session.execute(
        select(DiscrepancyReportEntry, Location.name)
        .join(Location, Location.id == DiscrepancyReportEntry.location_id)
        .where(
            DiscrepancyReportEntry.report_id == report_id,
            Location.company_id == company_id,
        )
        .order_by(Location.name, DiscrepancyReportEntry.id)
    )
    return [(entry, location_name) for entry, location_name in rows.all()]


def _discrepancy_count(entries: list[tuple[DiscrepancyReportEntry, str]]) -> int:
    return sum(1 for entry, _ in entries if entry.first_code != entry.second_code)


async def list_reports(
    session: AsyncSession,
    company_id: int,
    page: int,
    page_size: int,
    date_from: date | None = None,
    date_to: date | None = None,
    status: str | None = None,
) -> tuple[list[DiscrepancyReportRow], int]:
    filters = [
        DiscrepancyReport.company_id == company_id,
        DiscrepancyReport.deleted_at.is_(None),
    ]
    if date_from:
        filters.append(DiscrepancyReport.report_date >= date_from)
    if date_to:
        filters.append(DiscrepancyReport.report_date <= date_to)
    if status:
        filters.append(DiscrepancyReport.status == status)

    total = await session.scalar(select(func.count(DiscrepancyReport.id)).where(*filters)) or 0
    reports = (
        await session.execute(
            select(DiscrepancyReport, User.name)
            .outerjoin(User, User.id == DiscrepancyReport.prepared_by_user_id)
            .where(*filters)
            .order_by(DiscrepancyReport.report_date.desc(), DiscrepancyReport.id.desc())
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
    ).all()

    result = []
    for report, prepared_by_name in reports:
        entries = await _entry_rows(session, company_id, report.id)
        result.append(
            DiscrepancyReportRow(
                report,
                prepared_by_name,
                len(entries),
                _discrepancy_count(entries),
            )
        )
    return result, total


async def get_report(
    session: AsyncSession,
    company_id: int,
    report_id: int,
) -> DiscrepancyReportDetail | None:
    prepared_by_user = aliased(User)
    checked_by_user = aliased(User)
    received_by_user = aliased(User)
    row = await session.execute(
        select(
            DiscrepancyReport,
            prepared_by_user.name,
            checked_by_user.name,
            received_by_user.name,
        )
        .outerjoin(prepared_by_user, prepared_by_user.id == DiscrepancyReport.prepared_by_user_id)
        .outerjoin(checked_by_user, checked_by_user.id == DiscrepancyReport.checked_by_user_id)
        .outerjoin(received_by_user, received_by_user.id == DiscrepancyReport.received_by_user_id)
        .where(
            DiscrepancyReport.id == report_id,
            DiscrepancyReport.company_id == company_id,
            DiscrepancyReport.deleted_at.is_(None),
        )
    )
    result = row.first()
    if result is None:
        return None
    report, prepared_by_name, checked_by_name, received_by_name = result
    return DiscrepancyReportDetail(
        report,
        prepared_by_name,
        checked_by_name,
        received_by_name,
        await _entry_rows(session, company_id, report.id),
    )


async def _validated_entries(
    session: AsyncSession,
    company_id: int,
    entries: list[dict],
) -> None:
    location_ids = [entry["location_id"] for entry in entries]
    if len(location_ids) != len(set(location_ids)):
        raise ValueError("Cada local só pode aparecer uma vez na conferência")
    if not location_ids:
        return
    found = await session.scalars(
        select(Location.id).where(
            Location.company_id == company_id,
            Location.deleted_at.is_(None),
            Location.id.in_(location_ids),
        )
    )
    if set(found.all()) != set(location_ids):
        raise ValueError("Local não encontrado nesta empresa")


async def _sync_entries(
    session: AsyncSession,
    company_id: int,
    report_id: int,
    entries: list[dict],
) -> None:
    await _validated_entries(session, company_id, entries)
    await session.execute(
        delete(DiscrepancyReportEntry).where(DiscrepancyReportEntry.report_id == report_id)
    )
    for entry in entries:
        session.add(DiscrepancyReportEntry(report_id=report_id, **entry))


async def create_report(
    session: AsyncSession,
    company_id: int,
    user_id: int,
    data: dict,
) -> DiscrepancyReportDetail:
    entries = data.pop("entries", [])
    await _validated_entries(session, company_id, entries)
    report = DiscrepancyReport(company_id=company_id, **data)
    session.add(report)
    await session.flush()
    await _sync_entries(session, company_id, report.id, entries)
    await record_event(
        session,
        company_id=company_id,
        user_id=user_id,
        entity_type="discrepancy_report",
        entity_id=report.id,
        event_type="create",
    )
    await session.commit()
    return await get_report(session, company_id, report.id)  # type: ignore[return-value]


async def update_report(
    session: AsyncSession,
    company_id: int,
    user_id: int,
    report_id: int,
    updates: dict,
) -> DiscrepancyReportDetail | None:
    report = await session.scalar(
        select(DiscrepancyReport).where(
            DiscrepancyReport.id == report_id,
            DiscrepancyReport.company_id == company_id,
            DiscrepancyReport.deleted_at.is_(None),
        )
    )
    if report is None:
        return None
    if report.status == "closed":
        raise ValueError("A conferência fechada não pode ser alterada")

    entries = updates.pop("entries", None)
    await _validated_entries(session, company_id, entries or []) if entries is not None else None
    before = {field: str(getattr(report, field)) for field in updates}
    for field, value in updates.items():
        setattr(report, field, value)
    if entries is not None:
        await _sync_entries(session, company_id, report.id, entries)
    diff = compute_diff(before, {field: str(value) for field, value in updates.items()})
    if entries is not None:
        diff = {**(diff or {}), "entries": {"from": "updated", "to": "updated"}}
    if diff:
        await record_event(
            session,
            company_id=company_id,
            user_id=user_id,
            entity_type="discrepancy_report",
            entity_id=report.id,
            event_type="update",
            diff=diff,
        )
    await session.commit()
    return await get_report(session, company_id, report.id)


async def delete_report(
    session: AsyncSession,
    company_id: int,
    user_id: int,
    report_id: int,
) -> bool:
    report = await session.scalar(
        select(DiscrepancyReport).where(
            DiscrepancyReport.id == report_id,
            DiscrepancyReport.company_id == company_id,
            DiscrepancyReport.deleted_at.is_(None),
        )
    )
    if report is None:
        return False
    report.deleted_at = datetime.now()
    await record_event(
        session,
        company_id=company_id,
        user_id=user_id,
        entity_type="discrepancy_report",
        entity_id=report.id,
        event_type="delete",
    )
    await session.commit()
    return True


def code_summary(entries: list[tuple[DiscrepancyReportEntry, str]]) -> Counter[str]:
    counts: Counter[str] = Counter()
    for entry, _ in entries:
        for code in (entry.first_code, entry.second_code):
            if code:
                counts[code] += 1
    return counts
