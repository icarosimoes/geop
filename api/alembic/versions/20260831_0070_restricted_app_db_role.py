"""roles restritas para runtime da API (corrige RLS inerte)

Revision ID: 20260831_0070
Revises: 20260831_0069
Create Date: 2026-08-31

Achado (docs/auditoria-2026-07-03.md#c1, reconfirmado 2026-08-31): a role usada pela
API (`registro`, via `POSTGRES_USER`) é criada como SUPERUSUÁRIO pela imagem oficial
do Postgres. Superusuário ignora RLS incondicionalmente, mesmo com FORCE ROW LEVEL
SECURITY — então as policies `tenant_isolation` de 24+ tabelas (ADR-002) nunca
protegeram nada; o isolamento entre tenants dependia inteiramente do filtro
`company_id` da aplicação.

Cria duas roles sem SUPERUSER/CREATEDB/CREATEROLE, com DML nas tabelas/sequences
existentes e default privileges para as futuras (criadas pela role de migration,
dona das tabelas):

- `registro_app`: NOBYPASSRLS. Usada pelas rotas de tenant — depende do GUC
  `app.current_company_id` (setado por `app/core/rls.py::set_tenant_context` a
  partir de um claim de JWT já validado) para o RLS filtrar por empresa.
- `registro_platform`: BYPASSRLS. Usada só pelas rotas `/platform/*`, que por
  natureza leem/escrevem entre tenants (billing, assinaturas, métricas). É a
  intenção original do ADR-002 ("rotas platform operam como superuser com
  BYPASSRLS") — só que agora isolada nessa role específica, não no app inteiro.

Rodar com uma role só continua funcionando (comportamento inalterado) até o
operador apontar `DATABASE_URL`/`DATABASE_PLATFORM_URL` (runtime) para essas
roles e `DATABASE_MIGRATION_URL` para a role dona das tabelas — ver
docs/infra/role-restrita-postgres.md.

Idempotente: pode rodar de novo sem recriar as roles nem resetar senha de uma
role já existente (evita sobrescrever segredo de produção com o default de dev).
"""

import os

import sqlalchemy as sa

from alembic import op

revision = "20260831_0070"
down_revision = "20260831_0069"
branch_labels = None
depends_on = None

# (nome da role, tem BYPASSRLS, env var da senha, senha default de dev)
ROLES = [
    ("registro_app", False, "APP_DB_ROLE_PASSWORD", "registro-app-dev-only"),
    ("registro_platform", True, "PLATFORM_DB_ROLE_PASSWORD", "registro-platform-dev-only"),
]


def _create_or_configure_role(
    conn: sa.Connection, role: str, bypass_rls: bool, password_env_var: str, default_password: str
) -> None:
    role_exists = conn.execute(
        sa.text("SELECT 1 FROM pg_roles WHERE rolname = :role"), {"role": role}
    ).scalar()
    if not role_exists:
        # CREATE ROLE é DDL: Postgres não aceita bind param ($1) na posição da
        # senha (erro de sintaxe), só literal. Escapa aspas simples manualmente —
        # mesmo nível de confiança de outros segredos deste repo já montados via
        # f-string em SQL de bootstrap (não é input de usuário final).
        password = os.environ.get(password_env_var, default_password)
        escaped_password = password.replace("'", "''")
        conn.execute(sa.text(f"CREATE ROLE {role} LOGIN PASSWORD '{escaped_password}'"))

    bypass_clause = "BYPASSRLS" if bypass_rls else "NOBYPASSRLS"
    conn.execute(
        sa.text(
            f"ALTER ROLE {role} NOSUPERUSER {bypass_clause} "
            "NOCREATEDB NOCREATEROLE NOREPLICATION"
        )
    )
    conn.execute(sa.text(f"GRANT USAGE ON SCHEMA public TO {role}"))
    conn.execute(
        sa.text(f"GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA public TO {role}")
    )
    conn.execute(sa.text(f"GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA public TO {role}"))

    # Tabelas/sequences criadas por migrations futuras (rodadas pela role dona,
    # current_user desta conexão) já nascem com privilégio pra essa role. O %I
    # dentro do format() é resolvido pelo Postgres com current_user (bind da
    # própria conexão); só o nome da role (constante fixa, não input externo) é
    # interpolado pelo Python.
    conn.execute(
        sa.text(
            "DO $do$ BEGIN "
            "EXECUTE format("
            "'ALTER DEFAULT PRIVILEGES FOR ROLE %I IN SCHEMA public "
            f"GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES TO {role}', current_user); "
            "EXECUTE format("
            "'ALTER DEFAULT PRIVILEGES FOR ROLE %I IN SCHEMA public "
            f"GRANT USAGE, SELECT ON SEQUENCES TO {role}', current_user); "
            "END $do$;"
        )
    )


def upgrade() -> None:
    conn = op.get_bind()
    for role, bypass_rls, password_env_var, default_password in ROLES:
        _create_or_configure_role(conn, role, bypass_rls, password_env_var, default_password)


def downgrade() -> None:
    # Intencionalmente não reversível: derrubar uma role enquanto o app pode
    # estar conectado com ela derrubaria produção. Reverter é uma decisão
    # operacional manual (ver runbook), não uma migration automática.
    pass
