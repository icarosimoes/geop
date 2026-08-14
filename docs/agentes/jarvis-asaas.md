# Jarvis — Asaas

O Asaas é o provedor de cobrança da assinatura do GEOP. A integração está implementada com sandbox ativo.

## Implementação

- **Client**: `app/integrations/asaas.py` — `AsaasClient` com httpx async, timeout 30s.
- **Config**: `asaas_api_key`, `asaas_api_url` (default sandbox), `asaas_webhook_token` em `app/core/config.py`. Variantes `_file` para produção (Docker Secrets).
- **Provisionamento**: `provision_asaas_customer` e `provision_asaas_subscription` em `app/domain/platform/service.py` criam customer/subscription no Asaas e persistem IDs localmente (`Company.asaas_customer_id`, `Subscription.billing_provider_subscription_id`).

## Fronteiras

- Credencial da plataforma e eventual credencial de tenant são segredos diferentes.
- A chave nunca chega ao navegador, log, banco em texto aberto ou imagem Docker.
- `subscriptions` guarda o vínculo comercial; `invoices` espelha cobranças e eventos externos.
- IDs externos são referências, não chaves primárias do GEOP.
- Valores usam centavos inteiros e datas usam UTC.

## Webhook

- **Endpoint**: `POST /api/v1/integrations/asaas/webhook` em `app/domain/platform/webhook_router.py`.
- **Autenticação**: header `asaas-access-token` comparado em tempo constante com `settings.asaas_webhook_token`.
- **Idempotência**: tabela `webhook_events` com constraint unique `(provider, external_id)`. IntegrityError = já processado → 200.
- **Rate limit**: 60/min via slowapi.
- **Eventos processados**:
  - `PAYMENT_CONFIRMED` / `PAYMENT_RECEIVED` → `Invoice.status = "paid"`, `payment_date` preenchido.
  - `PAYMENT_OVERDUE` → `Invoice.status = "overdue"`, `Subscription.past_due_since` setado.
  - `SUBSCRIPTION_DELETED` → `Subscription.status = "canceled"`.
- **Auditoria**: todo evento processado gera `PlatformAuditLog`.

## Reconciliação

- **Endpoint**: `POST /api/v1/platform/billing/reconcile?auto_correct=false`.
- Para cada subscription com `billing_provider_subscription_id`, faz GET no Asaas e compara status.
- Discrepâncias são logadas em `PlatformAuditLog`.
- Com `auto_correct=true`, corrige status local para match com Asaas.

## Operação

Antes da ativação em produção são obrigatórios:
- [x] Sandbox funcional com client async.
- [x] Webhook idempotente com dedup e comparação constante de token.
- [x] Reconciliação periódica via endpoint admin.
- [ ] Rotação de chave API e webhook token.
- [ ] URL HTTPS dedicada para webhook em produção.
- [ ] Alerta de falhas (webhook errors, reconciliation discrepancies).
- [ ] Replay seguro de eventos perdidos.
- [ ] Runbook de indisponibilidade do Asaas.

Nenhum webhook pode habilitar acesso cross-tenant.
