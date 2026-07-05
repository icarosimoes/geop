"""Portal do Colaborador: geofencing em Location/Employee, credenciais por PIN,
batidas via mobile e contracheques.

Revision ID: 20260704_0047
Revises: 20260704_0046
Create Date: 2026-07-04

- Location: latitude, longitude, geofence_radius_m (geofencing por raio).
- Employee: location_id (para resolver a Location do funcionário no punch mobile).
- employee_credentials: PIN numérico (bcrypt) para login do app do colaborador.
- time_punches: latitude, longitude, distance_m (preenchidos quando source="mobile").
- employee_payslips: metadado de competência do contracheque, aponta para Attachment.
"""

import sqlalchemy as sa

from alembic import op

revision = "20260704_0047"
down_revision = "20260704_0046"
branch_labels = None
depends_on = None

RLS_TABLES = ["employee_credentials", "employee_payslips"]


def upgrade() -> None:
    # --- Location: geofencing -------------------------------------------------
    op.add_column("locations", sa.Column("latitude", sa.Numeric(9, 6), nullable=True))
    op.add_column("locations", sa.Column("longitude", sa.Numeric(9, 6), nullable=True))
    op.add_column(
        "locations",
        sa.Column("geofence_radius_m", sa.Integer(), nullable=False, server_default="100"),
    )

    # --- Employee -> Location ---------------------------------------------------
    op.add_column("employees", sa.Column("location_id", sa.Integer(), nullable=True))
    op.create_index("ix_employees_location_id", "employees", ["location_id"])
    op.create_foreign_key(
        "fk_employees_location_id",
        "employees",
        "locations",
        ["location_id"],
        ["id"],
        ondelete="SET NULL",
    )

    # --- TimePunch: geolocalização da batida mobile -----------------------------
    op.add_column("time_punches", sa.Column("latitude", sa.Numeric(9, 6), nullable=True))
    op.add_column("time_punches", sa.Column("longitude", sa.Numeric(9, 6), nullable=True))
    op.add_column("time_punches", sa.Column("distance_m", sa.Numeric(10, 2), nullable=True))

    # --- employee_credentials ----------------------------------------------------
    op.create_table(
        "employee_credentials",
        sa.Column("id", sa.Integer(), nullable=False, autoincrement=True),
        sa.Column("company_id", sa.Integer(), nullable=False),
        sa.Column("employee_id", sa.Integer(), nullable=False),
        sa.Column("pin_hash", sa.String(255), nullable=False),
        sa.Column("failed_attempts", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("locked_until", sa.DateTime(), nullable=True),
        sa.Column("must_change_pin", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("pin_set_at", sa.DateTime(), nullable=True),
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
        sa.ForeignKeyConstraint(["employee_id"], ["employees.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("employee_id", name="uq_employee_credentials_employee"),
    )
    op.create_index(
        "ix_employee_credentials_company", "employee_credentials", ["company_id"]
    )

    # --- employee_payslips ---------------------------------------------------
    op.create_table(
        "employee_payslips",
        sa.Column("id", sa.Integer(), nullable=False, autoincrement=True),
        sa.Column("company_id", sa.Integer(), nullable=False),
        sa.Column("employee_id", sa.Integer(), nullable=False),
        sa.Column("reference_month", sa.Date(), nullable=False),
        sa.Column("attachment_id", sa.Integer(), nullable=False),
        sa.Column("uploaded_by_user_id", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.Column("deleted_at", sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(["company_id"], ["companies.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["employee_id"], ["employees.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["attachment_id"], ["attachments.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["uploaded_by_user_id"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "company_id",
            "employee_id",
            "reference_month",
            name="uq_employee_payslips_month",
        ),
    )
    op.create_index(
        "ix_employee_payslips_employee", "employee_payslips", ["company_id", "employee_id"]
    )

    for table in RLS_TABLES:
        op.execute(f"ALTER TABLE {table} ENABLE ROW LEVEL SECURITY")
        op.execute(
            f"CREATE POLICY tenant_isolation ON {table} "
            "USING (company_id = current_setting('app.current_company_id')::int)"
        )


def downgrade() -> None:
    for table in RLS_TABLES:
        op.execute(f"DROP POLICY IF EXISTS tenant_isolation ON {table}")
        op.execute(f"ALTER TABLE {table} DISABLE ROW LEVEL SECURITY")

    op.drop_index("ix_employee_payslips_employee", table_name="employee_payslips")
    op.drop_table("employee_payslips")

    op.drop_index("ix_employee_credentials_company", table_name="employee_credentials")
    op.drop_table("employee_credentials")

    op.drop_column("time_punches", "distance_m")
    op.drop_column("time_punches", "longitude")
    op.drop_column("time_punches", "latitude")

    op.drop_constraint("fk_employees_location_id", "employees", type_="foreignkey")
    op.drop_index("ix_employees_location_id", table_name="employees")
    op.drop_column("employees", "location_id")

    op.drop_column("locations", "geofence_radius_m")
    op.drop_column("locations", "longitude")
    op.drop_column("locations", "latitude")
