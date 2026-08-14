# Jarvis — SaaS e multiempresa

O GEOP é preparado para comercialização como SaaS. Empresa cliente, usuário da empresa e operador da plataforma são contextos distintos e nunca compartilham uma sessão implicitamente.

## Banco — PostgreSQL 17 com RLS

- Driver: `asyncpg` (async). MySQL disponível apenas para importação do dump V1 (`docker compose --profile mysql-import up mysql`).
- Toda entidade de negócio possui `company_id` e é filtrada em duas camadas:
  1. **Aplicação** — repository/service filtra explicitamente por `company_id` (obrigatório).
  2. **RLS** — policy `tenant_isolation` em 24 tabelas com `company_id`. GUC `app.current_company_id` setado via `SET LOCAL` na dependency `current_user` após autenticação. Rotas platform (sem GUC) operam com `BYPASSRLS` do owner do banco.
- Operação cross-company é administrativa, explícita e auditável.
- ACL não substitui isolamento por empresa.

## Autenticação

- JWT tenant usa `type=access`; JWT administrativo usa `type=platform_access`.
- Usuário da plataforma vive em `platform_users`, fora de `users`.
- Tenants com `Company.status = "suspended"` são bloqueados no login — o filtro `Company.status == "active"` em `auth/repository.py` rejeita automaticamente.
- O painel administrativo usa cookie `httpOnly` criado no servidor Next.js.

## Núcleo da plataforma

- `companies`: tenants.
- `plans`: catálogo comercial versionável com features/limits JSON.
- `subscriptions`: plano e estado comercial do tenant. CRUD auditado via `PlatformAuditLog`.
- `invoices`: espelho local das cobranças externas (Asaas).
- `webhook_events`: dedup de eventos de webhook (provider + external_id unique).
- `platform_users`: operadores internos.
- `platform_audit_logs`: ações cross-tenant e administrativas.

## Lifecycle de assinatura

```
trial (14d) → past_due → suspended (7d tolerância) → canceled
                ↑                        ↓
            reactivate ←─────────── admin endpoint
```

- **Trial**: 14 dias. Expiração processada via `POST /platform/billing/process-expirations`.
- **Past due**: sem pagamento após trial. Tolerância de 7 dias.
- **Suspended**: `POST /platform/billing/process-suspensions` seta `Subscription.status = "suspended"` e `Company.status = "suspended"` (bloqueia login).
- **Reactivation**: `POST /platform/subscriptions/{id}/reactivate` restaura status active.
- Endpoints callable por cron com token platform admin.

## Integração Asaas

- `AsaasClient` em `app/integrations/asaas.py` — httpx async, sandbox por default.
- Config: `asaas_api_key`, `asaas_api_url`, `asaas_webhook_token` com variantes `_file` para produção.
- Provisionamento: `provision_asaas_customer` e `provision_asaas_subscription` em `platform/service.py`.
- Webhook: `POST /integrations/asaas/webhook` com dedup via `webhook_events`, header token auth (`asaas-access-token`), rate limit 60/min.
- Reconciliação: `POST /platform/billing/reconcile` compara status local vs Asaas API, auto_correct opcional.

## Preços e valores

- Preços em centavos inteiros (`price_cents`, `value_cents`).
- Estado de assinatura não é inferido da interface.
- IDs externos do Asaas são opcionais e únicos quando preenchidos; o GEOP mantém suas próprias chaves.

## Critérios obrigatórios

- Teste negativo prova que token de uma empresa não lê dados de outra.
- Endpoint administrativo revalida operador ativo e registra mutações em auditoria.
- Migração e seed são repetíveis; seed de demonstração nunca usa senha padrão em produção.
- Integração de cobrança é adaptador externo: o domínio não depende do SDK do provedor.
