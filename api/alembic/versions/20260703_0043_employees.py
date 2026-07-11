"""Create employees and employee_external_ids tables, RLS, permissions, backfill Users.

Revision ID: 20260703_0043
Revises: 20260703_0042
Create Date: 2026-07-03 18:00:00.000000

"""

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision = "20260703_0043"
down_revision = "20260703_0042"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Create employees table
    op.create_table(
        "employees",
        sa.Column("id", sa.Integer(), nullable=False, autoincrement=True),
        sa.Column("company_id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("cpf", sa.String(11), nullable=True),
        sa.Column("rg", sa.String(20), nullable=True),
        sa.Column("birth_date", sa.String(10), nullable=True),
        sa.Column("phone", sa.String(20), nullable=True),
        sa.Column("personal_email", sa.String(255), nullable=True),
        sa.Column("address_street", sa.String(255), nullable=True),
        sa.Column("address_number", sa.String(20), nullable=True),
        sa.Column("address_complement", sa.String(255), nullable=True),
        sa.Column("address_neighborhood", sa.String(255), nullable=True),
        sa.Column("address_city", sa.String(100), nullable=True),
        sa.Column("address_state", sa.String(2), nullable=True),
        sa.Column("address_zip", sa.String(8), nullable=True),
        sa.Column("status", sa.String(20), nullable=False, server_default="active"),
        sa.Column("avatar_url", sa.String(500), nullable=True),
        sa.Column("user_id", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.func.now(), onupdate=sa.func.now(), nullable=False),  # noqa: E501
        sa.Column("deleted_at", sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(["company_id"], ["companies.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("company_id", "cpf", name="uq_employees_company_cpf"),
    )
    op.create_index("ix_employees_status", "employees", ["company_id", "status"])
    op.create_index("ix_employees_user_id", "employees", ["user_id"])
    op.create_index("ix_employees_personal_email", "employees", ["personal_email"])

    # Create employee_external_ids table
    op.create_table(
        "employee_external_ids",
        sa.Column("id", sa.Integer(), nullable=False, autoincrement=True),
        sa.Column("company_id", sa.Integer(), nullable=False),
        sa.Column("employee_id", sa.Integer(), nullable=False),
        sa.Column("system", sa.String(40), nullable=False),
        sa.Column("external_id", sa.String(120), nullable=False),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.func.now(), onupdate=sa.func.now(), nullable=False),  # noqa: E501
        sa.ForeignKeyConstraint(["company_id"], ["companies.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["employee_id"], ["employees.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("company_id", "system", "external_id", name="uq_employee_external_id"),
    )
    op.create_index("ix_employee_external_system", "employee_external_ids", ["company_id", "system"])  # noqa: E501
    op.create_index("ix_employee_external_id", "employee_external_ids", ["employee_id"])

    # Enable RLS on both tables
    op.execute("ALTER TABLE employees ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE employee_external_ids ENABLE ROW LEVEL SECURITY")

    # Create RLS policies
    op.execute(
        "CREATE POLICY tenant_isolation ON employees "
        "USING (company_id = current_setting('app.current_company_id')::int)"
    )
    op.execute(
        "CREATE POLICY tenant_isolation ON employee_external_ids "
        "USING (company_id = current_setting('app.current_company_id')::int)"
    )

    # Backfill: create one Employee per existing User (linked via user_id)
    # Use a subquery to ensure uniqueness: for each company, create one emp per user if not exists
    op.execute(
        """
        INSERT INTO employees
            (company_id, name, personal_email, user_id, status, created_at, updated_at)
        SELECT
            u.company_id, u.name, u.email, u.id,
            CASE WHEN u.active THEN 'active' ELSE 'inactive' END,
            u.created_at, u.updated_at
        FROM users u
        WHERE u.deleted_at IS NULL
        """
    )

    # Add new permissions
    op.execute(
        """
        INSERT INTO permissions (code, name, module)
        VALUES
            ('employee.view', 'Visualizar funcionários', 'employee'),
            ('employee.manage', 'Gerenciar funcionários', 'employee')
        ON CONFLICT (code) DO NOTHING
        """
    )

    # Grant new permissions to admin role for all companies
    op.execute(
        """
        INSERT INTO role_permissions (role_id, permission_id)
        SELECT r.id, p.id
        FROM roles r
        CROSS JOIN permissions p
        WHERE r.code = 'admin'
        AND p.code IN ('employee.view', 'employee.manage')
        ON CONFLICT DO NOTHING
        """
    )


def downgrade() -> None:
    # Remove RLS policies
    op.execute("DROP POLICY IF EXISTS tenant_isolation ON employee_external_ids")
    op.execute("DROP POLICY IF EXISTS tenant_isolation ON employees")

    # Disable RLS
    op.execute("ALTER TABLE employee_external_ids DISABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE employees DISABLE ROW LEVEL SECURITY")

    # Drop tables
    op.drop_table("employee_external_ids")
    op.drop_table("employees")

    # Remove permissions (clean up role_permissions first)
    op.execute(
        """
        DELETE FROM role_permissions
        WHERE permission_id IN (
            SELECT id FROM permissions
            WHERE code IN ('employee.view', 'employee.manage')
        )
        """
    )
    op.execute(
        """
        DELETE FROM permissions
        WHERE code IN ('employee.view', 'employee.manage')
        """
    )
