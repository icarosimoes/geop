"""Migrate timeclock tables from user_id to employee_id.

Revision ID: 20260703_0044
Revises: 20260703_0043
Create Date: 2026-07-03 18:15:00.000000

Migrates:
- schedule_entries.user_id -> employee_id
- time_clock_enrollments.user_id -> employee_id
- time_punches.user_id -> employee_id
"""

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision = "20260703_0044"
down_revision = "20260703_0043"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # =========================================================================
    # schedule_entries: user_id -> employee_id
    # =========================================================================

    # Add new column
    op.add_column("schedule_entries", sa.Column("employee_id", sa.Integer(), nullable=True))

    # Backfill: resolve employee_id via employees.user_id (do not assume employees.id == users.id)
    op.execute(
        """
        UPDATE schedule_entries se
        SET employee_id = e.id
        FROM employees e
        WHERE e.user_id = se.user_id
        AND e.company_id = se.company_id
        """
    )

    # Create foreign key for employee_id
    op.create_foreign_key(
        "fk_schedule_entries_employee_id",
        "schedule_entries",
        "employees",
        ["employee_id"],
        ["id"],
        ondelete="CASCADE",
    )

    # Create new indices
    op.create_index("ix_schedule_entries_employee_date", "schedule_entries", ["company_id", "employee_id", "date"])  # noqa: E501

    # Create new unique constraint
    op.create_unique_constraint(
        "uq_schedule_entries_employee_date",
        "schedule_entries",
        ["company_id", "employee_id", "date"],
    )

    # Drop old constraint and index
    op.drop_constraint("uq_schedule_entries_user_date", "schedule_entries", type_="unique")
    op.drop_index("ix_schedule_entries_user_date", table_name="schedule_entries")
    op.drop_index("ix_schedule_entries_date", table_name="schedule_entries")

    # Drop old column with CASCADE to remove associated constraints
    op.execute("ALTER TABLE schedule_entries DROP COLUMN user_id CASCADE")

    # =========================================================================
    # time_clock_enrollments: user_id -> employee_id
    # =========================================================================

    # Add new column
    op.add_column("time_clock_enrollments", sa.Column("employee_id", sa.Integer(), nullable=True))

    # Backfill: resolve employee_id via employees.user_id (do not assume employees.id == users.id)
    op.execute(
        """
        UPDATE time_clock_enrollments tce
        SET employee_id = e.id
        FROM employees e
        WHERE e.user_id = tce.user_id
        AND e.company_id = tce.company_id
        """
    )

    # Create foreign key
    op.create_foreign_key(
        "fk_time_clock_enrollments_employee_id",
        "time_clock_enrollments",
        "employees",
        ["employee_id"],
        ["id"],
        ondelete="CASCADE",
    )

    # Drop old column with CASCADE to remove associated constraints
    op.execute("ALTER TABLE time_clock_enrollments DROP COLUMN user_id CASCADE")

    # =========================================================================
    # time_punches: user_id -> employee_id (created_by_user_id stays as is)
    # =========================================================================

    # Add new column
    op.add_column("time_punches", sa.Column("employee_id", sa.Integer(), nullable=True))

    # Backfill: resolve employee_id via employees.user_id (do not assume employees.id == users.id)
    op.execute(
        """
        UPDATE time_punches tp
        SET employee_id = e.id
        FROM employees e
        WHERE e.user_id = tp.user_id
        AND e.company_id = tp.company_id
        """
    )

    # Create foreign key
    op.create_foreign_key(
        "fk_time_punches_employee_id",
        "time_punches",
        "employees",
        ["employee_id"],
        ["id"],
        ondelete="SET NULL",
    )

    # Create new index
    op.create_index("ix_time_punches_employee_date", "time_punches", ["company_id", "employee_id", "punched_at"])  # noqa: E501

    # Drop old index
    op.drop_index("ix_time_punches_user_date", table_name="time_punches")

    # Drop old column with CASCADE to remove associated constraints
    op.execute("ALTER TABLE time_punches DROP COLUMN user_id CASCADE")


def downgrade() -> None:
    # =========================================================================
    # schedule_entries: employee_id -> user_id
    # =========================================================================

    op.add_column("schedule_entries", sa.Column("user_id", sa.Integer(), nullable=True))
    op.execute(
        """
        UPDATE schedule_entries se
        SET user_id = e.user_id
        FROM employees e
        WHERE e.id = se.employee_id
        """
    )
    op.create_foreign_key(
        "fk_schedule_entries_user_id",
        "schedule_entries",
        "users",
        ["user_id"],
        ["id"],
        ondelete="CASCADE",
    )
    op.create_index("ix_schedule_entries_date", "schedule_entries", ["company_id", "date"])
    op.create_index("ix_schedule_entries_user_date", "schedule_entries", ["company_id", "user_id", "date"])  # noqa: E501
    op.create_unique_constraint(
        "uq_schedule_entries_user_date",
        "schedule_entries",
        ["company_id", "user_id", "date"],
    )
    op.drop_constraint("uq_schedule_entries_employee_date", "schedule_entries", type_="unique")
    op.drop_index("ix_schedule_entries_employee_date", table_name="schedule_entries")
    op.drop_constraint("fk_schedule_entries_employee_id", "schedule_entries", type_="foreignkey")
    op.drop_column("schedule_entries", "employee_id")

    # =========================================================================
    # time_clock_enrollments: employee_id -> user_id
    # =========================================================================

    op.add_column("time_clock_enrollments", sa.Column("user_id", sa.Integer(), nullable=True))
    op.execute(
        """
        UPDATE time_clock_enrollments tce
        SET user_id = e.user_id
        FROM employees e
        WHERE e.id = tce.employee_id
        """
    )
    op.create_foreign_key(
        "fk_time_clock_enrollments_user_id",
        "time_clock_enrollments",
        "users",
        ["user_id"],
        ["id"],
        ondelete="CASCADE",
    )
    op.create_unique_constraint(
        "uq_timeclock_enrollment_external",
        "time_clock_enrollments",
        ["company_id", "external_id"],
    )
    op.drop_constraint("fk_time_clock_enrollments_employee_id", "time_clock_enrollments", type_="foreignkey")  # noqa: E501
    op.drop_column("time_clock_enrollments", "employee_id")

    # =========================================================================
    # time_punches: employee_id -> user_id
    # =========================================================================

    op.add_column("time_punches", sa.Column("user_id", sa.Integer(), nullable=True))
    op.execute(
        """
        UPDATE time_punches tp
        SET user_id = e.user_id
        FROM employees e
        WHERE e.id = tp.employee_id
        """
    )
    op.create_foreign_key(
        "fk_time_punches_user_id",
        "time_punches",
        "users",
        ["user_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_index("ix_time_punches_user_date", "time_punches", ["company_id", "user_id", "punched_at"])  # noqa: E501
    op.drop_constraint("fk_time_punches_employee_id", "time_punches", type_="foreignkey")
    op.drop_index("ix_time_punches_employee_date", table_name="time_punches")
    op.drop_column("time_punches", "employee_id")
