"""create time_clock_devices, time_clock_enrollments, time_punches and permissions

Revision ID: 20260703_0041
Revises: 20260703_0040
Create Date: 2026-07-03
"""

import sqlalchemy as sa

from alembic import op

revision = "20260703_0041"
down_revision = "20260703_0040"
branch_labels = None
depends_on = None

PERMISSIONS = [
    ("timeclock.view", "Ver batidas de ponto", "timeclock"),
    ("timeclock.manage", "Gerenciar dispositivos, vínculos e batidas de ponto", "timeclock"),
]

RLS_TABLES = ["time_clock_devices", "time_clock_enrollments", "time_punches"]


def upgrade() -> None:
    op.create_table(
        "time_clock_devices",
        sa.Column("id", sa.Integer(), nullable=False, autoincrement=True),
        sa.Column("company_id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("model", sa.String(40), nullable=False, server_default="control_id"),
        sa.Column("serial_number", sa.String(120), nullable=True),
        sa.Column("location_id", sa.Integer(), nullable=True),
        sa.Column("webhook_token", sa.String(64), nullable=False),
        sa.Column("active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.Column(
            "updated_at",
            sa.DateTime(),
            server_default=sa.func.now(),
            onupdate=sa.func.now(),
            nullable=False,
        ),
        sa.Column("deleted_at", sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(["company_id"], ["companies.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["location_id"], ["locations.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("webhook_token", name="uq_time_clock_devices_token"),
    )

    op.create_table(
        "time_clock_enrollments",
        sa.Column("id", sa.Integer(), nullable=False, autoincrement=True),
        sa.Column("company_id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("external_id", sa.String(80), nullable=False),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.Column(
            "updated_at",
            sa.DateTime(),
            server_default=sa.func.now(),
            onupdate=sa.func.now(),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["company_id"], ["companies.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "company_id", "external_id", name="uq_timeclock_enrollment_external"
        ),
    )

    op.create_table(
        "time_punches",
        sa.Column("id", sa.Integer(), nullable=False, autoincrement=True),
        sa.Column("company_id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=True),
        sa.Column("device_id", sa.Integer(), nullable=True),
        sa.Column("punched_at", sa.DateTime(), nullable=False),
        sa.Column("punch_type", sa.String(10), nullable=True),
        sa.Column("source", sa.String(20), nullable=False, server_default="device"),
        sa.Column("external_event_id", sa.String(120), nullable=True),
        sa.Column("status", sa.String(20), nullable=True),
        sa.Column("raw_payload", sa.JSON(), nullable=True),
        sa.Column("created_by_user_id", sa.Integer(), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["company_id"], ["companies.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(
            ["device_id"], ["time_clock_devices.id"], ondelete="SET NULL"
        ),
        sa.ForeignKeyConstraint(["created_by_user_id"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "device_id", "external_event_id", name="uq_time_punches_device_event"
        ),
    )
    op.create_index(
        "ix_time_punches_user_date", "time_punches", ["company_id", "user_id", "punched_at"]
    )

    for table in RLS_TABLES:
        op.execute(f"ALTER TABLE {table} ENABLE ROW LEVEL SECURITY")
        op.execute(
            f"CREATE POLICY tenant_isolation ON {table} "
            "USING (company_id = current_setting('app.current_company_id')::int)"
        )

    conn = op.get_bind()
    for code, name, module in PERMISSIONS:
        conn.execute(
            sa.text(
                "INSERT INTO permissions (code, name, module) VALUES (:code, :name, :module) "
                "ON CONFLICT (code) DO NOTHING"
            ),
            {"code": code, "name": name, "module": module},
        )
    conn.execute(
        sa.text(
            """
            INSERT INTO role_permissions (role_id, permission_id)
            SELECT r.id, p.id
            FROM roles r
            CROSS JOIN permissions p
            WHERE r.code = 'admin'
              AND p.code IN ('timeclock.view', 'timeclock.manage')
            ON CONFLICT DO NOTHING
            """
        )
    )


def downgrade() -> None:
    for table in RLS_TABLES:
        op.execute(f"DROP POLICY IF EXISTS tenant_isolation ON {table}")
        op.execute(f"ALTER TABLE {table} DISABLE ROW LEVEL SECURITY")
    op.drop_index("ix_time_punches_user_date", table_name="time_punches")
    op.drop_table("time_punches")
    op.drop_table("time_clock_enrollments")
    op.drop_table("time_clock_devices")
    conn = op.get_bind()
    for code, _, _ in PERMISSIONS:
        conn.execute(sa.text("DELETE FROM permissions WHERE code = :code"), {"code": code})
