"""replace work_schedules (weekday recorrente) por shifts + schedule_entries

Revision ID: 20260703_0042
Revises: 20260703_0041
Create Date: 2026-07-03
"""

import sqlalchemy as sa

from alembic import op

revision = "20260703_0042"
down_revision = "20260703_0041"
branch_labels = None
depends_on = None

OLD_PERMISSIONS = ["work_schedule.view", "work_schedule.manage"]

NEW_PERMISSIONS = [
    ("shift.view", "Ver turnos", "shift"),
    ("shift.manage", "Gerenciar turnos", "shift"),
    ("schedule.view", "Ver escala de trabalho", "schedule"),
    ("schedule.manage", "Gerenciar escala de trabalho", "schedule"),
]

RLS_TABLES = ["shifts", "schedule_entries"]


def upgrade() -> None:
    op.execute("DROP POLICY IF EXISTS tenant_isolation ON work_schedules")
    op.execute("ALTER TABLE work_schedules DISABLE ROW LEVEL SECURITY")
    op.drop_index("ix_work_schedules_user", table_name="work_schedules")
    op.drop_table("work_schedules")

    conn = op.get_bind()
    for code in OLD_PERMISSIONS:
        conn.execute(sa.text("DELETE FROM permissions WHERE code = :code"), {"code": code})

    op.create_table(
        "shifts",
        sa.Column("id", sa.Integer(), nullable=False, autoincrement=True),
        sa.Column("company_id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(80), nullable=False),
        sa.Column("start_time", sa.Time(), nullable=False),
        sa.Column("end_time", sa.Time(), nullable=False),
        sa.Column("break_start", sa.Time(), nullable=True),
        sa.Column("break_end", sa.Time(), nullable=True),
        sa.Column("tolerance_minutes", sa.Integer(), nullable=False, server_default="10"),
        sa.Column("color", sa.String(7), nullable=False, server_default="#2563eb"),
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
        sa.PrimaryKeyConstraint("id"),
    )

    op.create_table(
        "schedule_entries",
        sa.Column("id", sa.Integer(), nullable=False, autoincrement=True),
        sa.Column("company_id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("date", sa.Date(), nullable=False),
        sa.Column("shift_id", sa.Integer(), nullable=True),
        sa.Column("source", sa.String(20), nullable=False, server_default="manual"),
        sa.Column("notes", sa.Text(), nullable=True),
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
        sa.ForeignKeyConstraint(["shift_id"], ["shifts.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("company_id", "user_id", "date", name="uq_schedule_entries_user_date"),
    )
    op.create_index("ix_schedule_entries_date", "schedule_entries", ["company_id", "date"])
    op.create_index(
        "ix_schedule_entries_user_date", "schedule_entries", ["company_id", "user_id", "date"]
    )

    for table in RLS_TABLES:
        op.execute(f"ALTER TABLE {table} ENABLE ROW LEVEL SECURITY")
        op.execute(
            f"CREATE POLICY tenant_isolation ON {table} "
            "USING (company_id = current_setting('app.current_company_id')::int)"
        )

    for code, name, module in NEW_PERMISSIONS:
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
              AND p.code IN ('shift.view', 'shift.manage', 'schedule.view', 'schedule.manage')
            ON CONFLICT DO NOTHING
            """
        )
    )


def downgrade() -> None:
    for table in RLS_TABLES:
        op.execute(f"DROP POLICY IF EXISTS tenant_isolation ON {table}")
        op.execute(f"ALTER TABLE {table} DISABLE ROW LEVEL SECURITY")
    op.drop_index("ix_schedule_entries_user_date", table_name="schedule_entries")
    op.drop_index("ix_schedule_entries_date", table_name="schedule_entries")
    op.drop_table("schedule_entries")
    op.drop_table("shifts")

    conn = op.get_bind()
    for code, _, _ in NEW_PERMISSIONS:
        conn.execute(sa.text("DELETE FROM permissions WHERE code = :code"), {"code": code})

    op.create_table(
        "work_schedules",
        sa.Column("id", sa.Integer(), nullable=False, autoincrement=True),
        sa.Column("company_id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("weekday", sa.SmallInteger(), nullable=False),
        sa.Column("start_time", sa.Time(), nullable=False),
        sa.Column("end_time", sa.Time(), nullable=False),
        sa.Column("break_start", sa.Time(), nullable=True),
        sa.Column("break_end", sa.Time(), nullable=True),
        sa.Column("tolerance_minutes", sa.Integer(), nullable=False, server_default="10"),
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
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("company_id", "user_id", "weekday", name="uq_work_schedules_user_day"),
    )
    op.create_index("ix_work_schedules_user", "work_schedules", ["company_id", "user_id"])
    op.execute("ALTER TABLE work_schedules ENABLE ROW LEVEL SECURITY")
    op.execute(
        "CREATE POLICY tenant_isolation ON work_schedules "
        "USING (company_id = current_setting('app.current_company_id')::int)"
    )
    for code, name, module in [
        ("work_schedule.view", "Ver escalas de trabalho", "work_schedule"),
        ("work_schedule.manage", "Editar escalas de trabalho", "work_schedule"),
    ]:
        conn.execute(
            sa.text(
                "INSERT INTO permissions (code, name, module) VALUES (:code, :name, :module) "
                "ON CONFLICT (code) DO NOTHING"
            ),
            {"code": code, "name": name, "module": module},
        )
