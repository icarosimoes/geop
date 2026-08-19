# Migração MySQL → PostgreSQL

## Contexto

O GEOP nasceu com MySQL 8.4 para manter compatibilidade com o sistema legado Laravel (Chess Hotel V1). Com o codebase estabilizado e os dados do V1 importados, o banco foi migrado para PostgreSQL 17 com Row-Level Security (RLS) para isolamento por tenant.

## O que mudou

| Item | Antes (MySQL) | Depois (PostgreSQL) |
|---|---|---|
| Driver | `asyncmy` | `asyncpg` |
| Imagem Docker | `mysql:8.4.8` | `postgres:17-alpine` |
| Porta dev | 3307 | 5433 |
| Connection string | `mysql+asyncmy://registro:registro@mysql:3306/registro` | `postgresql+asyncpg://registro:registro@postgres:5432/registro` |
| Isolamento tenant | Filtro ORM apenas | Filtro ORM + RLS (24 tabelas) |
| Boolean defaults | `sa.text("1")` / `"0"` | `sa.text("true")` / `"false"` |
| Auto-increment ID | `LAST_INSERT_ID()` | `RETURNING id` |
| Timestamp function | `NOW()` | `CURRENT_TIMESTAMP` |
| Upsert | `ON DUPLICATE KEY UPDATE` | `ON CONFLICT ... DO UPDATE` |
| Quoting | Backticks `` ` `` | Double quotes `"` |

## Docker Compose

```bash
# Subir ambiente normal (PostgreSQL + MinIO + API + Web + Admin)
docker compose up -d

# Subir MySQL temporariamente para importação do dump V1
docker compose --profile mysql-import up -d mysql

# Parar MySQL após importação
docker compose --profile mysql-import stop mysql
```

O MySQL só sobe com o profile `mysql-import`. Sem o profile, apenas PostgreSQL roda.

## RLS (Row-Level Security)

### Como funciona

1. **Migration 0029** cria policies `tenant_isolation` em 24 tabelas com `company_id`
2. A dependency `current_user` em `app/core/auth.py` seta o GUC após autenticação:
   ```python
   await session.execute(
       text("SET LOCAL app.current_company_id = :cid"),
       {"cid": str(user.company_id)},
   )
   ```
3. O RLS filtra automaticamente — queries só retornam registros do tenant autenticado
4. Rotas platform (admin) não setam o GUC — o owner do banco tem `BYPASSRLS`

### Tabelas com RLS
`users`, `roles`, `sectors`, `locations`, `functions`, `procedures`, `occurrences`, `fiscal_requests`, `audit_events`, `module_records`, `notifications`, `notification_preferences`, `attachments`, `meetings`, `shift_reports`, `check_suites`, `inspection_suites`, `apartment_inspections`, `audit_reports`, `work_diaries`, `subscriptions`, `invoices`, `company_settings`

### Tabelas sem RLS (platform-level)
`companies`, `plans`, `permissions`, `role_permissions`, `platform_users`, `platform_audit_logs`, `webhook_events`, `legacy_import_runs`

### Tabelas filhas (sem company_id direto)
`occurrence_participants`, `meeting_participants`, `meeting_subjects`, `check_suite_items`, `inspection_suite_items`, `apartment_inspection_items`, `audit_report_items`, `work_diary_activities`, `work_diary_teams`, `work_diary_equipment`, `work_diary_observations`

Isolamento é herdado via FK CASCADE da tabela pai.

## Procedimento de importação do dump V1

### Pré-requisitos
- Dump MySQL do V1 (`.sql`)
- Containers rodando: `docker compose up -d`

### Passo a passo

```bash
# 1. Subir MySQL temporário
docker compose --profile mysql-import up -d mysql

# 2. Aguardar MySQL ficar healthy
docker exec geop-mysql-1 mysqladmin ping -h 127.0.0.1 -u root -pregistro-root --silent

# 3. Criar database legado e importar dump
docker exec geop-mysql-1 mysql -u root -pregistro-root -e "CREATE DATABASE IF NOT EXISTS legacy_v1;"
(echo "SET FOREIGN_KEY_CHECKS=0;"; cat docs/aero-YYYY-MM-DD.sql) | \
  docker exec -i geop-mysql-1 mysql -u root -pregistro-root legacy_v1

# 4. Instalar driver MySQL no container da API (temporário)
docker exec -u root geop-api-1 pip install asyncmy

# 5. Rodar importação
docker exec \
  -e LEGACY_DATABASE_URL="mysql+asyncmy://root:registro-root@mysql:3306/legacy_v1" \
  geop-api-1 python -m app.import_v1

# 6. Parar MySQL
docker compose --profile mysql-import stop mysql
```

### O que o import faz
- Cria tenant `aero-hotel` (ou reutiliza se existir)
- Importa: usuários (59), setores (17), locais (69), funções (13), procedimentos (6)
- Importa: ocorrências (375) + comentários + participantes
- Importa: reuniões (72), relatórios de turno (1165), check suites (4497), auditorias (104)
- Importa: notificações legadas (3336)
- Preserva `legacy_id` para rastreabilidade V1 → GEOP
- Gera `LegacyImportRun` com checksum do dump (idempotente — re-rodar com mesmo dump não duplica)

### Para produção (corte final)
1. Puxar dump MySQL atualizado do servidor V1
2. Seguir o mesmo procedimento acima no ambiente de produção
3. Validar dados: contagem de registros, login de usuários, integridade de FKs
4. Desligar o Laravel V1
5. Apontar DNS para o GEOP

## Arquivos modificados na migração

### Infra
- `docker-compose.yml` — PostgreSQL principal, MySQL como profile
- `api/pyproject.toml` — `asyncpg` principal, `asyncmy` em optional `mysql-import`
- `api/alembic.ini` — URL PostgreSQL
- `.env.example` e `api/.env.example` — URLs e variáveis PostgreSQL

### Código corrigido (MySQL → PostgreSQL)
- `api/app/models/operations.py` — boolean `server_default=sa.true()`
- `api/app/core/auth.py` — `SET LOCAL app.current_company_id` para RLS
- `api/app/core/dependencies.py` — `_session_with_tenant` helper
- `api/app/import_v1.py` — quoting dinâmico (backtick para MySQL, double quotes para PostgreSQL)
- 4 data migrations (0018, 0021, 0023, 0028) — `RETURNING id`, `CURRENT_TIMESTAMP`, `ON CONFLICT`
- 3 schema migrations (0020, 0024, 0027) — boolean defaults `"true"`/`"false"`
- Migration 0017 — tolerante a constraints inexistentes (`_drop_fk_safe`)

### RLS
- `api/alembic/versions/20260620_0029_rls_policies.py` — policies em 24 tabelas
- `api/app/core/auth.py` — `SET app.current_company_id` após autenticar (sem `LOCAL`, funciona sem transação explícita)
- `api/app/core/dependencies.py` — `RESET app.current_company_id` no `finally` da session (limpa GUC ao devolver conexão ao pool)

### Notas de implementação RLS

- `SET LOCAL` não funciona com asyncpg sem transação explícita — usar `SET` (session-level)
- `SET` persiste na conexão — `RESET` obrigatório no `finally` para evitar leak entre requests
- PostgreSQL não aceita bind params (`$1`) em `SET` — usar f-string com `int()` validado
- O owner do banco tem `BYPASSRLS` por default — `FORCE ROW LEVEL SECURITY` na migration garante que o owner também é filtrado
- GUC vazio (`''`) faz `::int` falhar — o `RESET` garante que conexões sem tenant não vejam dados

### Docs
- `CLAUDE.md` — stack atualizada
- `docs/arquitetura.md` — PostgreSQL ativo
- `docs/backlog.md` — P5 marcado
- `docs/domain-model.md` — nota sobre RLS
- `docs/agentes/jarvis-saas.md` — PostgreSQL + RLS detalhado
- `docs/agentes/jarvis-asaas.md` — integração implementada
- `docs/migracao-postgresql.md` — guia completo de migração e importação

## Auditoria pós-migração (2026-06-20)

### Status: migração completa ✓

Auditoria automatizada varreu todo o codebase em busca de resquícios MySQL e incompatibilidades PostgreSQL.

### Problemas encontrados e corrigidos

| # | Problema | Severidade | Correção |
|---|---|---|---|
| 1 | CI (GitHub Actions) rodava testes contra MySQL 8.4 com `asyncmy` | **Crítica** | Substituído por PostgreSQL 17 com `asyncpg` em `.github/workflows/ci.yml` |

### Pontos verificados sem problemas

- **Código de aplicação** (`api/app/`): zero referências MySQL — nenhum `asyncmy`, `LAST_INSERT_ID`, `IFNULL`, `ON DUPLICATE KEY`, backtick quoting, ou `sa.text("0")`/`sa.text("1")`
- **SQLAlchemy models**: usam `func.now()` e `sa.true()` (abstrações portáveis)
- **Raw SQL**: único uso é `SELECT 1` no health check (portável)
- **Alembic migrations** (29 arquivos): nenhuma referência MySQL-específica
- **`alembic.ini`**: connection string PostgreSQL
- **`docker-compose.yml`**: PostgreSQL como serviço principal, MySQL só via profile `mysql-import`
- **`pyproject.toml`**: `asyncpg` como dependência principal, `asyncmy` em optional `mysql-import`
- **`.env.example`**: URLs PostgreSQL
- **RLS**: `SET app.current_company_id` e `RESET` implementados corretamente em `auth.py` / `dependencies.py`
- **`import_v1.py`**: corretamente usa quoting dinâmico (backtick para MySQL source, double quotes para PostgreSQL target)
- **Testes unitários**: usam SQLite in-memory (não dependem de nenhum dos dois)

### Referências MySQL restantes (esperadas e seguras)

1. `api/app/import_v1.py` — script de importação V1, lê de MySQL e escreve em PostgreSQL
2. `api/pyproject.toml` optional `[mysql-import]` — só instalado manualmente para importação
3. `docker-compose.yml` service `mysql` — só sobe com `--profile mysql-import`
4. `.env.example` — documenta variáveis `LEGACY_DATABASE_URL` para importação
5. `docs/migracao-postgresql.md` — esta documentação

### Recomendações futuras

- Após concluir a importação V1 em produção, considerar remover o profile `mysql-import` e a dependência `asyncmy`
- Manter `import_v1.py` como referência histórica, mas não é necessário para operação normal
