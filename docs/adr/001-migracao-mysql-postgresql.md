# ADR-001: Migração de MySQL para PostgreSQL

**Data**: 2026-06-20
**Status**: Aceita
**Decisores**: Ícaro Simoes

## Contexto

O GEOP nasceu com MySQL 8.4 para manter compatibilidade com o sistema legado Laravel (Chess Hotel V1), que usa MySQL em produção. Com o codebase estabilizado e todos os domínios operacionais implementados na nova stack (FastAPI + Next.js), surgiu a oportunidade de migrar para PostgreSQL antes do corte final.

## Decisão

Migrar o banco principal de MySQL 8.4 para PostgreSQL 17 (asyncpg), mantendo MySQL disponível apenas como fonte temporária para importação do dump V1.

## Alternativas consideradas

1. **Manter MySQL** — compatibilidade total com V1, sem custo de migração. Descartado porque MySQL não suporta RLS nativo e limita o isolamento multi-tenant a filtros ORM.
2. **Migrar após corte** — menor risco imediato. Descartado porque atrasaria a validação do RLS e forçaria manter código MySQL-specific por mais tempo.
3. **Migrar agora (escolhida)** — permite validar RLS antes do corte final, elimina código MySQL-specific e alinha com o ecossistema.

## Consequências

### Positivas
- RLS nativo com policies em 24 tabelas — isolamento de tenant no banco, não apenas no ORM
- Eliminação de todo código MySQL-specific (`LAST_INSERT_ID`, `NOW()`, backticks, boolean `"1"`/`"0"`)
- `asyncpg` como driver — melhor performance que `asyncmy` para cargas async
- Possibilidade de usar features PostgreSQL futuras (JSONB, full-text search, partitioning)

### Negativas
- MySQL mantido como profile Docker para importação V1 — complexidade residual até o corte final
- Todas as 29 migrations reescritas para PostgreSQL — custo único
- CI atualizado de MySQL para PostgreSQL — risco de regressão coberto por auditoria automatizada

## Implementação

- `docker-compose.yml`: PostgreSQL como serviço principal, MySQL como profile `mysql-import`
- `api/pyproject.toml`: `asyncpg` principal, `asyncmy` em optional `mysql-import`
- 29 migrations Alembic revalidadas para PostgreSQL
- `import_v1.py` com quoting dinâmico (lê MySQL, escreve PostgreSQL)
- Auditoria automatizada confirmou zero resquícios MySQL no código de aplicação
