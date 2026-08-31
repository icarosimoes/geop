# Role restrita do Postgres (corrige RLS inerte)

## Contexto

`docs/auditoria-2026-07-03.md#c1` identificou em 03/07/2026 que a role usada pela API
(`registro`, criada via `POSTGRES_USER=registro` na imagem oficial do Postgres) é
**superusuário** — e superusuário ignora RLS incondicionalmente, mesmo com `FORCE ROW
LEVEL SECURITY`. As policies `tenant_isolation` de 24+ tabelas (ADR-002) nunca
protegeram nada; o isolamento entre tenants dependia inteiramente do filtro
`company_id` da aplicação. O achado ficou órfão (não linkado no `README.md` nem no
`backlog.md`) até ser reconfirmado em 31/08/2026 (ver
[registro-trabalho.md](../registro-trabalho.md#2026-08-31--central-de-suporte-chamados-e-achado-crítico-de-rls-inerte-reencontrado)).

## O que foi corrigido no código (já em `main`)

Três roles, três propósitos:

| Role | Atributos | Usada por | Env var |
|---|---|---|---|
| `registro` | superusuário (dona das tabelas) | só `alembic upgrade head` | `DATABASE_MIGRATION_URL` |
| `registro_app` | `NOSUPERUSER NOBYPASSRLS` | rotas de tenant (runtime normal) | `DATABASE_URL` |
| `registro_platform` | `NOSUPERUSER BYPASSRLS` | só rotas `/platform/*` | `DATABASE_PLATFORM_URL` |

- **Migration `20260831_0070`**: cria `registro_app`/`registro_platform` (idempotente,
  não reseta senha de role já existente), concede DML nas tabelas/sequences
  existentes e `ALTER DEFAULT PRIVILEGES` pras futuras. Roda como parte normal de
  `alembic upgrade head` — não precisa de passo manual pra existir.
- **Migration `20260831_0071`**: function `SECURITY DEFINER`
  `find_login_candidates(email, company_id)` — o primeiro passo do login precisa
  achar a quais empresas um e-mail pertence antes de saber o `company_id` (sustenta
  o fluxo `422 multi_tenant`), o que é incompatível com o GUC de tenant único de
  `registro_app`. A function roda com o privilégio da role dona (bypassa RLS só
  nesse SELECT específico, com os mesmos filtros de segurança que a query ORM já
  aplicava), e só ela ganha `EXECUTE` — não uma concessão de bypass geral.
- **`app/core/rls.py::set_tenant_context`**: helper único pra setar o GUC
  `app.current_company_id` a partir de um `company_id` já validado (claim de JWT
  com assinatura verificada). Usado em `current_user`, `/auth/me`,
  `/auth/refresh`, `/auth/impersonate`, `/auth/sso/exchange`, `/auth/set-password`,
  no Portal do Colaborador (`mobile_auth.py`) e no callback OAuth do e-mail — todos
  tinham a ordem invertida (consultavam a tabela RLS antes de setar o GUC), o que
  nunca dava erro com superusuário e quebra a rota inteira com a role restrita.
- **`app/core/database.py`**: `engine`/`SessionLocal` (runtime, `registro_app`),
  `platform_engine`/`PlatformSessionLocal` (`/platform/*`, `registro_platform`) e
  `migration_engine`/`MigrationSessionLocal` (scripts administrativos —
  `app/seed.py`, `app/backfill_default_shifts.py` — que criam dados pra múltiplos
  tenants de uma vez, mesma natureza da role de migration).
- **`app/integrations/notifications.py::deliver_notifications`**: roda em
  background (`asyncio.create_task`, fora do request original) e abre sessão nova
  — precisa de `set_tenant_context` explícito antes de tocar `notifications` (RLS).
- **`set_tenant_context` usa `is_local=false` (escopo de sessão, não de transação)** —
  achado numa segunda rodada (2026-08-31, ao ligar a timeline dos chamados de
  suporte): a primeira versão usava `set_config(..., true)` (`SET LOCAL`), que some
  no primeiro `commit()`. Qualquer service que faz `record_event` + commit e depois
  mais uma query na mesma request (comum — `add_comment`, por exemplo, fazia
  exatamente isso) voltava a bater em "unrecognized configuration parameter" ou
  "invalid input syntax for type integer" (GUC "existe" pro backend mas com valor
  vazio) numa query **depois** do commit. Isso não é específico de chamados de
  suporte — **quebrava o recurso de comentário em qualquer entidade** (`POST
  /timeline/{entity_type}/{entity_id}/comment`, usado por ordens de serviço,
  solicitações fiscais, procedimentos, reuniões, etc.) assim que a role restrita
  entrasse em produção. `is_local=false` casa com o `RESET app.current_company_id`
  que já existia no `finally` de `require_session` — esse `RESET` só faz sentido
  pra limpar estado de **sessão**, então essa sempre foi a intenção original, só
  não é o que o `set_config(..., true)` fazia.
- Todas as três URLs são **opcionais**: sem configurar `DATABASE_MIGRATION_URL`/
  `DATABASE_PLATFORM_URL`, tudo cai pra `DATABASE_URL` (comportamento de uma role
  só, igual a antes desta mudança) — só isso já bastava pra rodar os testes durante
  o desenvolvimento sem quebrar nada.

## Dev local (`docker-compose.yml`) — já aplicado

```yaml
DATABASE_MIGRATION_URL: postgresql+asyncpg://registro:registro@postgres:5432/registro
DATABASE_URL: postgresql+asyncpg://registro_app:registro-app-dev-only@postgres:5432/registro
DATABASE_PLATFORM_URL: postgresql+asyncpg://registro_platform:registro-platform-dev-only@postgres:5432/registro
```

Validado de ponta a ponta no dev real (`geop-api-1`/`geop-postgres-1`) em 31/08/2026:
login, `/auth/me`, `/registries` isolado por tenant (tenant A e B veem só o próprio
`Local`), `/platform/auth/login`, `/platform/metrics` e `/platform/support-requests`
(cross-tenant, via `registro_platform`), `/auth/impersonate` (ticket +
troca por sessão), `/auth/refresh`, `app.seed` (banco vazio, cria os dois tenants
demo) — tudo com as roles restritas, sem cair pra superusuário em nenhum ponto.

As senhas de dev (`registro-app-dev-only`/`registro-platform-dev-only`) são as
mesmas que a migration usa por padrão quando `APP_DB_ROLE_PASSWORD`/
`PLATFORM_DB_ROLE_PASSWORD` não estão no ambiente — **nunca usar esses valores em
produção**.

## Produção — rollout em duas etapas (não aplicado, requer ação manual)

A migration já roda sozinha no próximo `alembic upgrade head` de produção (mesmo
procedimento de sempre, documentado em
[deploy-swarm.md](deploy-swarm.md#migrations-no-swarm)) — isso sozinho **não muda
nenhum comportamento**: sem `DATABASE_MIGRATION_URL`/`DATABASE_PLATFORM_URL`
configuradas no `docker-stack.yml`, a API de produção continua inteira na role
`registro` (superusuário) de sempre. As roles restritas só ficam criadas, sem uso.

### Etapa A — já é suficiente rodar o deploy normal

Nada a fazer além do deploy de rotina. Confirmar depois:

```bash
docker exec $(docker ps -q -f name=registro_db) psql -U registro -d registro -c "\du registro_app registro_platform"
```

Deve mostrar as duas roles sem `Superuser`; `registro_app` sem `Bypass RLS`,
`registro_platform` com `Bypass RLS`.

### Etapa B — trocar as roles em runtime (decisão do usuário, exige acesso à VPS)

1. **Gerar senhas fortes** pras duas roles (não reaproveitar os defaults de dev):
   ```bash
   openssl rand -base64 32   # uma pra registro_app, outra pra registro_platform
   ```
2. **Setar as senhas reais nas roles** (via `psql` como `registro`, dentro do
   container do banco em produção):
   ```sql
   ALTER ROLE registro_app PASSWORD 'SENHA_FORTE_1';
   ALTER ROLE registro_platform PASSWORD 'SENHA_FORTE_2';
   ```
3. **Criar os secrets do Swarm** (mesmo padrão de `registro_database_url` já
   existente):
   ```bash
   echo -n "postgresql+asyncpg://registro:SENHA_ATUAL@db:5432/registro" | docker secret create registro_database_migration_url -
   echo -n "postgresql+asyncpg://registro_app:SENHA_FORTE_1@db:5432/registro" | docker secret create registro_database_app_url -
   echo -n "postgresql+asyncpg://registro_platform:SENHA_FORTE_2@db:5432/registro" | docker secret create registro_database_platform_url -
   ```
4. **Atualizar `docker-stack.yml`** (serviço `api`): renomear o secret atual
   `registro_database_url` para alimentar `DATABASE_MIGRATION_URL_FILE`, e apontar
   `DATABASE_URL_FILE`/`DATABASE_PLATFORM_URL_FILE` pros dois secrets novos:
   ```yaml
   environment:
     DATABASE_MIGRATION_URL_FILE: /run/secrets/registro_database_migration_url
     DATABASE_URL_FILE: /run/secrets/registro_database_app_url
     DATABASE_PLATFORM_URL_FILE: /run/secrets/registro_database_platform_url
   secrets:
     - registro_database_migration_url
     - registro_database_app_url
     - registro_database_platform_url
     # ... demais secrets inalterados
   ```
5. **Deploy e validação** — mesmo procedimento de sempre
   ([deploy-swarm.md](deploy-swarm.md)): backup antes, `docker stack deploy`,
   confirmar `/api/v1/health/ready`, testar login de um tenant real e do painel
   admin, conferir isolamento (dois tenants distintos veem dados diferentes),
   conferir que `/platform/metrics` e `/platform/support-requests` continuam
   agregando todos os tenants.
6. **Rollback**: reverter o `docker-stack.yml` pro secret único
   `registro_database_url` em todas as três env vars — não precisa desfazer a
   migration (as roles restritas ficam, só sem uso).

### Por que não foi feito pelo agente

Sem acesso SSH/GHCR à VPS de produção (mesma limitação de todo o resto do runbook
de deploy). A etapa A é segura de aplicar via CI/deploy normal; a etapa B precisa de
decisão explícita do usuário — troca de credencial de banco em produção é o tipo de
mudança que não deve acontecer sem confirmação humana mesmo quando o agente tem
acesso técnico.
