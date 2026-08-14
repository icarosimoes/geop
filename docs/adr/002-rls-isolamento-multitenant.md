# ADR-002: Row-Level Security como estratégia de isolamento multi-tenant

**Data**: 2026-06-20
**Status**: Aceita
**Decisores**: Ícaro Simoes

## Contexto

O GEOP é um SaaS multitenant. Até a migração para PostgreSQL, o isolamento por empresa dependia exclusivamente de filtros `WHERE company_id = :cid` no ORM (SQLAlchemy). Um bug no service layer ou uma query raw sem filtro poderia expor dados entre tenants.

## Decisão

Ativar Row-Level Security (RLS) no PostgreSQL com policies `tenant_isolation` em todas as tabelas que possuem `company_id`, usando um GUC (`app.current_company_id`) setado por request.

## Alternativas consideradas

1. **Filtro ORM apenas** — mais simples, sem dependência de feature do banco. Descartado porque não protege contra queries raw, migrations ou scripts ad-hoc.
2. **Schema por tenant** — isolamento máximo. Descartado porque não escala para o modelo SaaS planejado (muitos tenants pequenos) e complica migrations.
3. **RLS com GUC (escolhida)** — defesa em profundidade no banco, sem mudar a estrutura de tabelas.

## Implementação

### Mecanismo
1. Migration `0029_rls_policies` cria policies em 24 tabelas
2. `FORCE ROW LEVEL SECURITY` garante que o owner também é filtrado
3. A dependency `current_user` em `auth.py` seta `SET app.current_company_id = <int>` após autenticação
4. O `finally` da session em `dependencies.py` executa `RESET app.current_company_id`

### Tabelas com RLS (24)
`users`, `roles`, `sectors`, `locations`, `functions`, `procedures`, `occurrences`, `fiscal_requests`, `audit_events`, `module_records`, `notifications`, `notification_preferences`, `attachments`, `meetings`, `shift_reports`, `check_suites`, `inspection_suites`, `apartment_inspections`, `audit_reports`, `work_diaries`, `subscriptions`, `invoices`, `company_settings`

### Tabelas sem RLS (platform-level)
`companies`, `plans`, `permissions`, `role_permissions`, `platform_users`, `platform_audit_logs`, `webhook_events`, `legacy_import_runs`

### Tabelas filhas (sem company_id direto)
Herdam isolamento via FK CASCADE da tabela pai.

## Consequências

### Positivas
- Defesa em profundidade — mesmo queries raw ou scripts ad-hoc respeitam o isolamento
- Rotas platform (admin) funcionam sem filtro — owner tem `BYPASSRLS`
- Compatível com o filtro ORM existente — dupla camada de proteção

### Negativas
- `SET` session-level exige `RESET` obrigatório no `finally` — leak se falhar
- GUC vazio causa `::int` falhar — comportamento fail-closed (seguro, mas pode gerar 500 em vez de 403)
- `SET LOCAL` não funciona com asyncpg sem transação explícita — forçou uso de `SET` session-level
- Testes unitários com SQLite não exercitam RLS — cobertura depende de testes de integração com PostgreSQL

## Notas técnicas

- PostgreSQL não aceita bind params em `SET` — usar f-string com `int()` validado
- `FORCE ROW LEVEL SECURITY` é necessário porque o owner do banco tem `BYPASSRLS` por default
