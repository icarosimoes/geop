"""function SECURITY DEFINER para o lookup de login por e-mail (cross-tenant)

Revision ID: 20260831_0071
Revises: 20260831_0070
Create Date: 2026-08-31

O primeiro passo do login (`find_active_users_by_email`) precisa achar a quais
empresas um e-mail pertence ANTES de saber o `company_id` — é o que sustenta o
fluxo `422 multi_tenant` já documentado. Nenhum valor único de
`app.current_company_id` resolve isso: é uma leitura cross-tenant legítima, não
um bug de ordenação do GUC (esses foram corrigidos direto no código, ver
app/core/rls.py).

Com `registro_app` restrita (migration `20260831_0070`), essa query pararia de
enxergar usuários de outras empresas. Em vez de conceder BYPASSRLS pra
`registro_app` (o que reabriria o problema pra toda query, não só essa), esta
migration cria uma function `SECURITY DEFINER` — dona da role de migration
(mesmo privilégio de sempre), com filtro de segurança embutido no corpo (ativo,
não deletado, empresa ativa — os mesmos filtros que a query ORM já aplicava).
Só essa function ganha `EXECUTE` pra `registro_app`/`registro_platform`; o
GRANT em `users` continua não incluindo leitura cross-tenant nenhuma.

A function já retorna nome da empresa, role e permissões (em vez de só a linha
de `users`) porque um `selectinload` de `Role` feito depois, pela ORM, seria
uma query separada — fora do bypass da function, e sem um único
`company_id` pra escopar (o e-mail pode casar com usuários de mais de uma
empresa). Concentrar tudo aqui evita uma segunda leitura cross-tenant sem
proteção nenhuma.

`SET search_path = public` protege contra search_path hijacking (guidance
padrão do Postgres pra funções SECURITY DEFINER).
"""

import sqlalchemy as sa

from alembic import op

revision = "20260831_0071"
down_revision = "20260831_0070"
branch_labels = None
depends_on = None

FUNCTION_SQL = """
CREATE OR REPLACE FUNCTION find_login_candidates(p_email text, p_company_id integer DEFAULT NULL)
RETURNS TABLE (
    id integer,
    name varchar,
    email varchar,
    phone varchar,
    password varchar,
    company_id integer,
    company_name varchar,
    role_id integer,
    role_name varchar,
    permissions text[]
)
LANGUAGE sql
SECURITY DEFINER
SET search_path = public
STABLE
AS $$
    SELECT
        u.id, u.name, u.email, u.phone, u.password,
        u.company_id, c.name AS company_name,
        r.id AS role_id, r.name AS role_name,
        COALESCE(
            (SELECT array_agg(p.code ORDER BY p.code)
             FROM role_permissions rp
             JOIN permissions p ON p.id = rp.permission_id
             WHERE rp.role_id = r.id),
            ARRAY[]::text[]
        ) AS permissions
    FROM users u
    JOIN companies c ON c.id = u.company_id
    LEFT JOIN roles r ON r.id = u.role_id
    WHERE u.email = p_email
      AND u.active IS TRUE
      AND u.deleted_at IS NULL
      AND c.status = 'active'
      AND c.deleted_at IS NULL
      AND (p_company_id IS NULL OR u.company_id = p_company_id)
    ORDER BY u.company_id, u.id;
$$;
"""


def upgrade() -> None:
    conn = op.get_bind()
    conn.execute(sa.text(FUNCTION_SQL))
    conn.execute(
        sa.text(
            "GRANT EXECUTE ON FUNCTION find_login_candidates(text, integer) "
            "TO registro_app, registro_platform"
        )
    )


def downgrade() -> None:
    op.execute("DROP FUNCTION IF EXISTS find_login_candidates(text, integer)")
