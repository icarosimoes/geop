# Referência da API

Base local: `http://localhost:8000/api/v1`. OpenAPI: `http://localhost:8000/docs` fora de produção.

## Endpoints implementados

| Método | Rota | Autenticação | Resultado |
| --- | --- | --- | --- |
| `GET` | `/health` | pública | processo FastAPI está vivo |
| `GET` | `/health/ready` | pública | conexão do banco pronta ou não configurada |
| `POST` | `/auth/login` | pública (10/min) | JWT access + refresh e perfil |
| `POST` | `/auth/refresh` | pública (20/min) | renova tokens via refresh token |
| `GET` | `/auth/me` | Bearer | perfil revalidado no PostgreSQL |
| `POST` | `/auth/set-password` | pública (5/min) | define senha via token de convite |
| `GET` | `/occurrences` | `occurrence.view` | ocorrências paginadas e isoladas por empresa |
| `GET` | `/occurrences/{id}` | `occurrence.view` | detalhe com participantes |
| `POST` | `/occurrences` | `occurrence.create` | cria ocorrência |
| `PATCH` | `/occurrences/{id}` | `occurrence.edit` | atualiza ocorrência |
| `DELETE` | `/occurrences/{id}` | `occurrence.delete` | soft delete de ocorrência |
| `POST` | `/occurrences/{id}/clone` | `occurrence.create` | duplica ocorrência com participantes |
| `GET` | `/occurrences/{id}/pdf` | `occurrence.view` | exporta PDF da ocorrência |
| `POST` | `/integrations/chess-hotel/users/resolve` | `X-Registro-Key` (30/min) | resolve usuário Chess no Registro por e-mail |
| `POST` | `/integrations/chess-hotel/tickets` | `X-Registro-Key` (30/min) | cria solicitação fiscal via integração Chess Hotel |
| `GET` | `/integrations/chess-hotel/tickets` | `X-Registro-Key` | lista solicitações do usuário Chess com tracking |
| `GET` | `/fiscal-requests` | `fiscal_request.view` | solicitações fiscais paginadas do tenant |
| `POST` | `/fiscal-requests` | `fiscal_request.create` | cria solicitação fiscal |
| `PATCH` | `/fiscal-requests/{id}` | `fiscal_request.edit` | atualiza solicitação fiscal |
| `DELETE` | `/fiscal-requests/{id}` | `fiscal_request.delete` | exclui solicitação fiscal |
| `GET` | `/dashboard/metrics` | Tenant Bearer | métricas agregadas do dashboard |
| `PATCH` | `/users/me` | Tenant Bearer | edição de perfil do próprio usuário |
| `GET` | `/users` | `user.view` | usuários paginados do tenant |
| `GET` | `/users/search?q=` | `user.view` | autocomplete de usuários ativos (max 10) |
| `POST` | `/users` | `user.create` | cria usuário |
| `POST` | `/users/invite` | `user.create` (10/min) | cria usuário e envia convite por e-mail |
| `POST` | `/users/{id}/avatar` | `user.edit` | upload de foto (JPEG/PNG/WebP, max 2MB) |
| `PATCH` | `/users/{id}` | `user.edit` | atualiza usuário |
| `DELETE` | `/users/{id}` | `user.delete` | soft delete de usuário |
| `GET` | `/roles` | `user.view` | lista roles do tenant com contagem de usuários |
| `GET` | `/roles/{id}` | `user.view` | detalhe do role com permissões |
| `POST` | `/roles` | `user.edit` | cria role com permissões |
| `PATCH` | `/roles/{id}` | `user.edit` | atualiza role/permissões |
| `DELETE` | `/roles/{id}` | `user.edit` | exclui role (só se sem usuários) |
| `GET` | `/roles/permissions` | `user.view` | lista todas as permissões agrupadas por módulo |
| `GET` | `/registries` | `registry.view` | cadastros (setores, locais e funções) |
| `POST` | `/registries` | `registry.create` | cria cadastro |
| `PATCH` | `/registries/{id}?category=` | `registry.edit` | atualiza cadastro |
| `DELETE` | `/registries/{id}?category=` | `registry.delete` | soft delete de cadastro |
| `GET` | `/meetings` | `meeting.view` | reuniões paginadas do tenant |
| `GET` | `/meetings/{id}` | `meeting.view` | detalhe com participantes e pautas |
| `POST` | `/meetings` | `meeting.create` | cria reunião com participantes e pautas |
| `PATCH` | `/meetings/{id}` | `meeting.edit` | atualiza reunião |
| `DELETE` | `/meetings/{id}` | `meeting.delete` | soft delete de reunião |
| `POST` | `/meetings/{id}/clone` | `meeting.create` | duplica reunião |
| `GET` | `/meetings/{id}/pdf` | `meeting.view` | exporta PDF da ata de reunião |
| `POST` | `/meetings/{id}/subjects` | `meeting.edit` | adiciona pauta |
| `PATCH` | `/meetings/{id}/subjects/{sid}` | `meeting.edit` | atualiza pauta (toggle resolved) |
| `DELETE` | `/meetings/{id}/subjects/{sid}` | `meeting.edit` | remove pauta |
| `GET` | `/shift-reports` | `shift_report.view` | relatórios de turno paginados (filtro por data) |
| `GET` | `/shift-reports/{id}` | `shift_report.view` | detalhe do relatório |
| `POST` | `/shift-reports` | `shift_report.create` | cria relatório de turno |
| `PATCH` | `/shift-reports/{id}` | `shift_report.edit` | atualiza relatório |
| `DELETE` | `/shift-reports/{id}` | `shift_report.delete` | soft delete de relatório |
| `GET` | `/modules/{slug}` | `module.view` | registros genéricos paginados |
| `POST` | `/modules/{slug}` | `module.create` | cria registro genérico |
| `PATCH` | `/modules/{slug}/{id}` | `module.edit` | atualiza registro genérico |
| `DELETE` | `/modules/{slug}/{id}` | `module.delete` | soft delete de registro genérico |
| `GET` | `/procedures` | `procedure.view` | procedimentos paginados do tenant |
| `POST` | `/procedures` | `procedure.create` | cria procedimento |
| `PATCH` | `/procedures/{id}` | `procedure.edit` | atualiza procedimento |
| `DELETE` | `/procedures/{id}` | `procedure.delete` | soft delete de procedimento |
| `GET` | `/notifications` | Tenant Bearer | notificações in-app paginadas do usuário |
| `PATCH` | `/notifications/{id}/read` | Tenant Bearer | marca notificação como lida |
| `POST` | `/notifications/read-all` | Tenant Bearer | marca todas as notificações como lidas |
| `GET` | `/notifications/preferences` | Tenant Bearer | preferências de notificação do usuário |
| `PUT` | `/notifications/preferences/{module}` | Tenant Bearer | atualiza preferência de um módulo |
| `GET` | `/settings/evolution` | `settings.view` | configuração da Evolution API |
| `POST` | `/settings/evolution` | `settings.edit` | salva configuração da Evolution API |
| `GET` | `/settings/evolution/status` | `settings.view` | verifica conexão com a instância Evolution |
| `POST` | `/settings/evolution/test` | `settings.edit` | envia mensagem de teste via Evolution |
| `GET` | `/settings/brevo` | `settings.view` | configuração do Brevo (e-mail) |
| `POST` | `/settings/brevo` | `settings.edit` | salva configuração do Brevo |
| `POST` | `/settings/brevo/test` | `settings.edit` | envia e-mail de teste via Brevo com a config salva |
| `GET` | `/settings/notification-recipients` | `settings.view` | destinatários por módulo |
| `PUT` | `/settings/notification-recipients/{module}` | `settings.edit` | define destinatários de um módulo |
| `GET` | `/settings/timeclock` | `settings.view` | HE paga em dinheiro + salário por cargo |
| `POST` | `/settings/timeclock` | `settings.edit` | salva HE paga em dinheiro + salário por cargo |
| `POST` | `/attachments` | Tenant Bearer (multipart) | upload de anexo para entidade |
| `GET` | `/attachments?entity_type=&entity_id=` | Tenant Bearer | lista anexos de uma entidade |
| `GET` | `/attachments/{id}/download` | Tenant Bearer | download do arquivo |
| `DELETE` | `/attachments/{id}` | Tenant Bearer | exclui anexo (S3 + banco) |
| `GET` | `/timeline/{entity_type}/{entity_id}` | Tenant Bearer | timeline de alterações do registro |
| `POST` | `/timeline/{entity_type}/{entity_id}/comment` | Tenant Bearer | adiciona comentário ao registro |
| `POST` | `/platform/auth/login` | pública | JWT administrativo isolado |
| `GET` | `/platform/metrics` | Platform Bearer | métricas SaaS agregadas |
| `GET` | `/platform/tenants` | Platform Bearer | empresas e assinatura |
| `POST` | `/platform/tenants` | Platform Bearer | cria tenant + subscription trial |
| `GET` | `/platform/tenants/{id}` | Platform Bearer | detalhe do tenant com subscription |
| `PATCH` | `/platform/tenants/{id}` | Platform Bearer | atualiza tenant |
| `DELETE` | `/platform/tenants/{id}` | Platform Bearer | soft delete do tenant |
| `GET` | `/platform/plans` | Platform Bearer | catálogo de planos |
| `POST` | `/platform/plans` | Platform Bearer | cria plano |
| `PATCH` | `/platform/plans/{id}` | Platform Bearer | atualiza plano |
| `DELETE` | `/platform/plans/{id}` | Platform Bearer | desativa plano (bloqueia se há assinaturas) |
| `GET` | `/platform/subscriptions/{id}` | Platform Bearer | detalhe da assinatura com faturas |
| `PATCH` | `/platform/subscriptions/{id}` | Platform Bearer | atualiza assinatura |
| `POST` | `/platform/subscriptions/{id}/reactivate` | Platform Bearer | reativa tenant suspenso |
| `POST` | `/platform/billing/process-expirations` | Platform Bearer | processa trials expirados |
| `POST` | `/platform/billing/process-suspensions` | Platform Bearer | suspende tenants em atraso |
| `POST` | `/platform/billing/reconcile` | Platform Bearer | reconcilia status local vs Asaas |
| `POST` | `/integrations/asaas/webhook` | `asaas-access-token` (60/min) | webhook idempotente do Asaas |
| `GET` | `/check-suites` | `check_suite.view` | checklists paginados |
| `GET` | `/check-suites/{id}` | `check_suite.view` | detalhe com itens |
| `POST` | `/check-suites` | `check_suite.create` | cria checklist com itens inline |
| `PATCH` | `/check-suites/{id}` | `check_suite.edit` | atualiza checklist |
| `DELETE` | `/check-suites/{id}` | `check_suite.delete` | soft delete |
| `GET` | `/inspection-suites` | `inspection_suite.view` | suítes de inspeção paginadas |
| `GET` | `/inspection-suites/{id}` | `inspection_suite.view` | detalhe com itens |
| `POST` | `/inspection-suites` | `inspection_suite.create` | cria suíte com itens inline |
| `PATCH` | `/inspection-suites/{id}` | `inspection_suite.edit` | atualiza suíte |
| `DELETE` | `/inspection-suites/{id}` | `inspection_suite.delete` | soft delete |
| `GET` | `/apartment-inspections` | `apartment_inspection.view` | vistorias paginadas |
| `GET` | `/apartment-inspections/{id}` | `apartment_inspection.view` | detalhe com itens |
| `POST` | `/apartment-inspections` | `apartment_inspection.create` | cria vistoria com itens |
| `PATCH` | `/apartment-inspections/{id}` | `apartment_inspection.edit` | atualiza vistoria |
| `DELETE` | `/apartment-inspections/{id}` | `apartment_inspection.delete` | soft delete |
| `GET` | `/audit-reports` | `audit_report.view` | auditorias paginadas |
| `GET` | `/audit-reports/{id}` | `audit_report.view` | detalhe com itens |
| `POST` | `/audit-reports` | `audit_report.create` | cria auditoria com itens |
| `PATCH` | `/audit-reports/{id}` | `audit_report.edit` | atualiza auditoria |
| `DELETE` | `/audit-reports/{id}` | `audit_report.delete` | soft delete |
| `GET` | `/work-diaries` | `work_diary.view` | diários de obra paginados |
| `GET` | `/work-diaries/{id}` | `work_diary.view` | detalhe com filhos |
| `POST` | `/work-diaries` | `work_diary.create` | cria diário com atividades/equipes/equipamentos/observações |
| `PATCH` | `/work-diaries/{id}` | `work_diary.edit` | atualiza diário |
| `DELETE` | `/work-diaries/{id}` | `work_diary.delete` | soft delete |
| `GET` | `/work-orders` | `work_order.view` | ordens de serviço paginadas (filtro por status, prioridade, busca) |
| `GET` | `/work-orders/summary` | `work_order.view` | contagem por status e mapa de transições |
| `GET` | `/work-orders/{id}` | `work_order.view` | detalhe da ordem de serviço |
| `POST` | `/work-orders` | `work_order.create` | cria ordem de serviço com SLA opcional |
| `PATCH` | `/work-orders/{id}` | `work_order.edit` | atualiza ordem de serviço |
| `POST` | `/work-orders/{id}/transition/{status}` | `work_order.edit` | transição de status com validação de fluxo |
| `DELETE` | `/work-orders/{id}` | `work_order.delete` | soft delete de ordem de serviço |
| `GET` | `/preventive-plans` | `preventive_plan.view` | planos preventivos paginados (filtro por busca, ativos) |
| `GET` | `/preventive-plans/{id}` | `preventive_plan.view` | detalhe do plano preventivo |
| `POST` | `/preventive-plans` | `preventive_plan.create` | cria plano preventivo com recorrência |
| `PATCH` | `/preventive-plans/{id}` | `preventive_plan.edit` | atualiza plano preventivo |
| `DELETE` | `/preventive-plans/{id}` | `preventive_plan.delete` | soft delete de plano preventivo |
| `POST` | `/preventive-plans/generate` | `preventive_plan.edit` | gera OS para planos vencidos |
| `GET` | `/checklists/templates` | `checklist.view` | templates de checklist paginados |
| `GET` | `/checklists/templates/{id}` | `checklist.view` | detalhe do template com itens |
| `POST` | `/checklists/templates` | `checklist.create` | cria template com itens inline |
| `PATCH` | `/checklists/templates/{id}` | `checklist.edit` | atualiza template e itens |
| `DELETE` | `/checklists/templates/{id}` | `checklist.delete` | soft delete de template |
| `GET` | `/checklists/executions` | `checklist.view` | execuções paginadas (filtro por template, status) |
| `GET` | `/checklists/executions/{id}` | `checklist.view` | detalhe da execução com itens |
| `POST` | `/checklists/executions/{id}/toggle` | `checklist.edit` | marca/desmarca item individual |
| `POST` | `/checklists/executions/{id}/complete` | `checklist.edit` | conclui execução com notas opcionais |
| `POST` | `/checklists/generate` | `checklist.edit` | gera execuções para templates vencidos |
| `GET` | `/stock/items` | `stock.view` | itens de estoque paginados (filtro por busca, abaixo do mínimo) |
| `GET` | `/stock/items/{id}` | `stock.view` | detalhe do item de estoque |
| `POST` | `/stock/items` | `stock.create` | cria item de estoque |
| `PATCH` | `/stock/items/{id}` | `stock.edit` | atualiza item de estoque |
| `DELETE` | `/stock/items/{id}` | `stock.delete` | soft delete de item de estoque |
| `POST` | `/stock/movements` | `stock.edit` | registra movimentação (entrada/saída/ajuste) |
| `GET` | `/stock/movements` | `stock.view` | movimentações paginadas (filtro por item) |
| `GET` | `/handoffs` | `handoff.view` | pendências de turno paginadas (filtro por data, turno, status) |
| `GET` | `/handoffs/pending` | `handoff.view` | pendências não resolvidas para data/turno |
| `GET` | `/handoffs/{id}` | `handoff.view` | detalhe da pendência |
| `POST` | `/handoffs` | `handoff.create` | cria pendência de turno |
| `PATCH` | `/handoffs/{id}` | `handoff.edit` | atualiza pendência |
| `POST` | `/handoffs/{id}/read` | `handoff.view` | marca pendência como lida |
| `POST` | `/handoffs/{id}/resolve` | `handoff.edit` | resolve pendência com notas |
| `DELETE` | `/handoffs/{id}` | `handoff.delete` | soft delete de pendência |
| `GET` | `/maintenance` | `maintenance.view` | registros de manutenção paginados |
| `GET` | `/maintenance/{id}` | `maintenance.view` | detalhe do registro de manutenção |
| `POST` | `/maintenance` | `maintenance.create` | cria registro de manutenção |
| `PATCH` | `/maintenance/{id}` | `maintenance.edit` | atualiza registro de manutenção |
| `DELETE` | `/maintenance/{id}` | `maintenance.delete` | soft delete de registro de manutenção |
| `GET` | `/bulletin` | `bulletin.view` | avisos do mural paginados |
| `POST` | `/bulletin` | `bulletin.create` | cria aviso no mural |
| `PATCH` | `/bulletin/{id}` | `bulletin.edit` | atualiza aviso do mural |
| `DELETE` | `/bulletin/{id}` | `bulletin.delete` | soft delete de aviso do mural |
| `GET` | `/contracts/suppliers` | `contract.view` | fornecedores paginados (filtro: search, active_only) |
| `GET` | `/contracts/suppliers/options` | `contract.view` | lista simplificada para autocomplete |
| `GET` | `/contracts/suppliers/{id}` | `contract.view` | detalhe do fornecedor com contatos |
| `POST` | `/contracts/suppliers` | `contract.create` | cria fornecedor |
| `PATCH` | `/contracts/suppliers/{id}` | `contract.edit` | atualiza fornecedor |
| `DELETE` | `/contracts/suppliers/{id}` | `contract.delete` | soft delete de fornecedor |
| `POST` | `/contracts/suppliers/{id}/contacts` | `contract.edit` | adiciona contato ao fornecedor |
| `PATCH` | `/contracts/contacts/{id}` | `contract.edit` | atualiza contato |
| `DELETE` | `/contracts/contacts/{id}` | `contract.edit` | remove contato |
| `GET` | `/contracts` | `contract.view` | contratos paginados (filtros: search, status, contract_type, supplier_id, expiring_in_days) |
| `GET` | `/contracts/{id}` | `contract.view` | detalhe com aditivos e etapas de aprovação |
| `POST` | `/contracts` | `contract.create` | cria contrato com fluxo de aprovação opcional (`approver_user_ids`) |
| `PATCH` | `/contracts/{id}` | `contract.edit` | atualiza dados do contrato |
| `PATCH` | `/contracts/{id}/status` | `contract.edit` | altera status manualmente |
| `DELETE` | `/contracts/{id}` | `contract.delete` | soft delete de contrato |
| `POST` | `/contracts/{id}/amendments` | `contract.edit` | registra aditivo (atualiza end_date/total_value no contrato) |
| `POST` | `/contracts/{id}/approve` | `contract.approve` | aprovador decide sua etapa (`{approved, comment?}`) |

### Login

```json
{
  "email": "usuario@empresa.com.br",
  "password": "senha",
  "company_id": 1
}
```

`company_id` é opcional. Se o e-mail pertencer a um único tenant, o login resolve automaticamente. Se pertencer a mais de um, a API retorna `422` com `code: "multi_tenant"` e a lista de empresas disponíveis; o front exibe um seletor e reenvia com `company_id`. O access token expõe `sub`, `company_id`, `role_id`, `permissions`, `type=access`, `iat` e `exp`. O algoritmo aceito é exclusivamente HS256.

No fluxo multitenant, a senha é validada antes da resposta de seleção. A API retorna somente os tenants cujos usuários possuem credencial compatível; senha inválida responde `401` sem revelar empresas. `company_id`, quando informado, deve ser um inteiro positivo.

O token da plataforma contém `type=platform_access` e não é aceito nas rotas tenant. O painel admin o mantém em cookie `httpOnly`; a API continua recebendo Bearer pela conexão server-side.

### Refresh token

O login retorna `access_token` (curta duração, padrão 30min) e `refresh_token` (longa duração, padrão 7 dias, `type=refresh`). O frontend armazena ambos em cookies `httpOnly`. Quando o access token expira (401), o frontend chama `POST /auth/refresh` com o refresh token para obter novos tokens sem pedir a senha novamente. O refresh token contém apenas `sub` e `company_id` (sem permissions) — ao renovar, a API revalida o usuário no banco e gera tokens atualizados.

### Rate limiting

Endpoints sensíveis possuem rate limiting por IP via slowapi:

| Endpoint | Limite |
| --- | --- |
| `POST /auth/login` | 10 req/min |
| `POST /auth/refresh` | 20 req/min |
| `POST /integrations/chess-hotel/users/resolve` | 30 req/min |
| `POST /integrations/chess-hotel/tickets` | 30 req/min |
| `POST /integrations/asaas/webhook` | 60 req/min |

Exceder o limite retorna `429 Too Many Requests`.

### Arquitetura: service layer

Cada domínio possui um `service.py` com a lógica de negócio separada do router. Os routers lidam apenas com parsing HTTP, validação de input e mapeamento de resposta. Os services recebem session e parâmetros tipados, facilitando reuso (ex: `fiscal_requests.service.create_from_chess()` pode ser chamado por qualquer integração) e testes unitários sem dependência de FastAPI.

### Erros estruturados

```json
{
  "detail": {
    "code": "invalid_credentials",
    "message": "E-mail ou senha inválidos"
  }
}
```

| Código | HTTP | Significado |
| --- | --- | --- |
| `database_unavailable` | 503 | `DATABASE_URL` ausente |
| `invalid_credentials` | 401 | usuário ou senha inválidos |
| `invalid_token` | 401 | JWT inválido, expirado ou de tipo incorreto |
| `inactive_user` | 401 | usuário removido, inativo ou fora da empresa do token |

## Contrato de listas

Todas as listas paginadas respondem `{items, total, page, page_size}` e aceitam `page`, `page_size` e `search` (quando aplicável). Endpoints que seguem este contrato: `/occurrences`, `/fiscal-requests`, `/users`, `/registries`, `/modules/{slug}`, `/procedures`, `/notifications`, `/meetings`, `/shift-reports`, `/work-orders`, `/preventive-plans`, `/checklists/templates`, `/checklists/executions`, `/stock/items`, `/stock/movements`, `/handoffs`, `/maintenance`, `/bulletin`, `/check-suites`, `/inspection-suites`, `/apartment-inspections`, `/audit-reports` e `/work-diaries`.

### Ocorrências

O CRUD de ocorrências está operacional. Todas as rotas exigem Tenant Bearer e isolam por `company_id`.

#### `POST /occurrences`

Cria uma ocorrência. O campo `legacy_id` não é enviado — registros criados pelo Registro ficam com `legacy_id` null. Os campos `created_by_user_id` e `updated_by_user_id` são preenchidos automaticamente com o usuário autenticado.

```json
{
  "title": "Revisar vistoria do apartamento 302",
  "description": "Pendência identificada na inspeção de ontem",
  "status": 1,
  "sector_id": 1,
  "location_id": 5,
  "owner_user_id": 2,
  "deadline": "2026-06-25"
}
```

Campos opcionais: `description`, `unit`, `deadline`, `sector_id`, `location_id`, `owner_user_id`. O `status` é inteiro: `1` = Em andamento, `2` = Concluído, `3` = Aguardando (padrão: `1`). Responde `201` com o registro criado, resolvendo `category` (nome do setor), `owner` (nome do usuário) e `location` (nome do local).

#### `PATCH /occurrences/{id}`

Atualiza campos da ocorrência. Aceita qualquer subconjunto de `title`, `description`, `unit`, `deadline`, `status`, `sector_id`, `location_id` e `owner_user_id`. Registra `updated_by_user_id` automaticamente.

#### `DELETE /occurrences/{id}`

Exclusão lógica — preenche `deleted_at` sem destruir o registro. Responde `204`. Retorna `404` se o registro não existir, já estiver excluído ou pertencer a outro tenant.

### Solicitações fiscais

O CRUD de solicitações fiscais está operacional. Todas as rotas exigem Tenant Bearer e isolam por `company_id`.

#### `POST /fiscal-requests`

Cria uma solicitação fiscal autenticada.

```json
{
  "request_type": "Dados do tomador incorretos",
  "title": "Correção CPF hóspede UH 305",
  "apartment": "305",
  "requester": "Ícaro Simoes",
  "description": "CPF informado está incorreto na NF",
  "status": "Em andamento",
  "payload": { "taxpayerDoc": "123.456.789-00" }
}
```

Responde `201` com o registro criado, incluindo `id`, `protocol` (`REG-{id:06d}`), `created_at` e `updated_at`. O campo `payload` armazena campos adicionais específicos do tipo (tomador, reserva, nota, etc.) como JSON.

#### `PATCH /fiscal-requests/{id}`

Atualiza campos da solicitação. Aceita qualquer subconjunto de `request_type`, `title`, `apartment`, `requester`, `description`, `status` e `payload`. Campos não enviados permanecem inalterados.

#### `DELETE /fiscal-requests/{id}`

Exclui a solicitação. Responde `204` sem corpo. Retorna `404` se o registro não existir ou pertencer a outro tenant.

#### `POST /integrations/chess-hotel/tickets`

Endpoint de integração para o Chess Hotel. Autenticado por header `X-Registro-Key` (variável `CHESS_HOTEL_INTEGRATION_KEY`). Resolve o tenant pelo slug configurado em `CHESS_HOTEL_COMPANY_SLUG` e o usuário Registro pelo e-mail do solicitante. Calcula `sla_deadline` (24h corridas) e vincula `requester_user_id`. Retorna protocolo, status, responsável, SLA e URL de acompanhamento.

O payload do Chess Hotel agora inclui `solicitanteEmail`, `chessUserId` e `hotel` além dos campos originais. O campo `reservationNumber` é promovido a coluna própria.

#### SLA inteligente

O `sla_deadline` é calculado em **dias úteis** (seg-sex, 8h-18h) na timezone do tenant (`companies.timezone`). O SLA padrão é 24h úteis (≈2,4 dias corridos). O campo `sla_status` é computado a cada consulta:

| Status | Condição |
| --- | --- |
| `on_time` | mais de 4h úteis restantes |
| `warning` | ≤4h restantes |
| `overdue` | deadline ultrapassado |
| `paused` | registro em status "Em espera" |
| `completed` | status "Concluído" ou "Cancelado" |

**Pausa**: quando o status muda para "Em espera", o SLA é congelado. Ao retomar (qualquer outro status), os segundos pausados são acumulados e descontados do deadline efetivo. Múltiplas pausas são somadas.

**Feriados**: `calculate_business_deadline()` aceita um set de datas (`YYYY-MM-DD`) como feriados. Integração com `CompanySetting` para configuração por tenant está preparada.

#### `POST /integrations/chess-hotel/users/resolve`

Verifica se um e-mail do Chess corresponde a um usuário ativo no tenant do Registro. Retorna `{ "exists": true, "id": 1, "name": "...", "email": "..." }` ou `404` se não encontrar.

#### `GET /integrations/chess-hotel/tickets?email=...`

Lista as últimas 50 solicitações do usuário (por `requester_user_id`) com histórico de auditoria e status de tracking. Retorna o perfil do usuário e array de `FiscalRequestTracking` com protocolo, status, responsável, SLA, flag de conclusão, URL e histórico de eventos.

### Timeline

A timeline agrega eventos de auditoria de um registro e os apresenta como thread de conversa. Lê da tabela `audit_events` e resolve o nome do ator via join com `users`.

#### `GET /timeline/{entity_type}/{entity_id}`

Retorna todos os eventos do registro em ordem cronológica. Cada item inclui `id`, `event_type`, `user` (nome), `message` (para comentários e anexos), `changes` (para updates) e `created_at`.

Entity types válidos: `occurrence`, `fiscal_request`, `procedure`, `meeting`, `shift_report`, `inspecoes`, `diarios-obra`, `manutencao`, `mural`.

Tipos de evento renderizados:

| `event_type` | Exibição |
| --- | --- |
| `create` | "Criou o registro" |
| `update` | Diff campo a campo |
| `delete` | "Excluiu o registro" |
| `comment` | Mensagem livre do usuário |
| `attachment_add` | "Anexou \"{filename}\"" |
| `attachment_remove` | "Removeu anexo \"{filename}\"" |

#### `POST /timeline/{entity_type}/{entity_id}/comment`

Adiciona comentário ao registro. Body: `{ "message": "texto" }`. Dispara notificação para o dono e criador do registro (ocorrências e solicitações fiscais). Responde `201` com o comentário criado.

### Auditoria

Toda mutação em ocorrências, solicitações fiscais, procedimentos e anexos gera um `AuditEvent` com `company_id`, `user_id`, `entity_type`, `entity_id`, `event_type` e `diff` JSON. O diff registra campo a campo o valor anterior e o novo, apenas quando há mudança. Eventos de create e delete não possuem diff. A tabela `audit_events` é imutável por design (sem `updated_at`/`deleted_at`, `created_at` com `server_default=func.now()`).

| `entity_type` | `event_type` | Quando |
| --- | --- | --- |
| `occurrence` | `create` | POST /occurrences |
| `occurrence` | `update` | PATCH /occurrences/{id}, apenas se houve diff |
| `occurrence` | `delete` | DELETE /occurrences/{id} |
| `fiscal_request` | `create` | POST /fiscal-requests |
| `fiscal_request` | `create_from_chess` | POST /integrations/chess-hotel/tickets |
| `fiscal_request` | `update` | PATCH /fiscal-requests/{id}, apenas se houve diff |
| `fiscal_request` | `delete` | DELETE /fiscal-requests/{id} |
| `{entity_type}` | `attachment_add` | POST /attachments — registra filename, content_type e size_bytes |
| `{entity_type}` | `attachment_remove` | DELETE /attachments/{id} — registra filename |

### Validação de campos fiscais

O `payload` de solicitações fiscais valida automaticamente:

| Campo | Regra |
| --- | --- |
| `taxpayerDoc` | CPF (11 dígitos) ou CNPJ (14 dígitos) com verificação de dígitos; normalizado para formato com pontuação |
| `taxpayerEmail` | formato básico de e-mail; normalizado para lowercase e trim |

Valores inválidos retornam `422`.

### Dashboard

`GET /dashboard/metrics` retorna indicadores agregados em tempo real do tenant:

```json
{
  "open_occurrences": 12,
  "my_occurrences": 3,
  "open_fiscal": 4,
  "completed_month": 28,
  "active_users": 26,
  "active_sectors": 5,
  "recent": [
    { "id": 1048, "title": "...", "area": "Governança", "owner": "Marina Costa", "status": "Em andamento", "updated_at": "..." }
  ],
  "kpis": {
    "work_orders": {
      "total": 15,
      "by_status": {"aberta": 5, "em_andamento": 4, "concluida": 6},
      "by_priority": {"urgente": 2, "alta": 5, "media": 8},
      "by_category": {"Elétrica": 4, "Hidráulica": 3, "Geral": 8},
      "avg_resolution_hours": 12.5,
      "sla_compliance_pct": 85,
      "overdue": 2,
      "created_week": 8,
      "completed_week": 5
    },
    "occurrences": {
      "by_status": {"em_andamento": 8, "concluido": 20, "aguardando": 4},
      "completion_rate_pct": 62,
      "by_sector": {"Governança": 5, "Operação": 3},
      "overdue": 1
    },
    "fiscal_requests": {
      "by_status": {"Em andamento": 3, "Concluído": 10},
      "by_type": {"Nota travada": 5, "Dados incorretos": 3},
      "sla_compliance_pct": 90,
      "overdue": 0
    },
    "trend": [
      {"date": "2026-06-15", "work_orders": 2, "occurrences": 3, "fiscal_requests": 1}
    ]
  }
}
```

| Campo | Descrição |
| --- | --- |
| `open_occurrences` | ocorrências com status 1 (em andamento) ou 3 (aguardando) |
| `my_occurrences` | subconjunto de `open_occurrences` atribuídas ao usuário logado |
| `open_fiscal` | solicitações fiscais com status diferente de "Concluído" |
| `completed_month` | ocorrências concluídas (status 2) no mês corrente |
| `active_users` | usuários ativos e não excluídos do tenant |
| `active_sectors` | setores não excluídos do tenant |
| `recent` | últimas atividades recentes de todos os módulos |
| `kpis.work_orders` | KPIs de ordens de serviço: total, distribuição por status/prioridade/categoria, tempo médio de resolução (horas), SLA compliance (%), atrasadas, criadas/concluídas na semana |
| `kpis.occurrences` | KPIs de ocorrências: distribuição por status, taxa de conclusão mensal (%), distribuição por setor (top 8), atrasadas |
| `kpis.fiscal_requests` | KPIs de solicitações fiscais: distribuição por status/tipo (top 8), SLA compliance (%), atrasadas |
| `kpis.trend` | tendência dos últimos 7 dias: contagem diária de OS, ocorrências e fiscais |

### Manutenção preventiva

Planos de manutenção recorrente que geram ordens de serviço automaticamente quando a data programada chega.

#### Modelo

- `preventive_plans`: name, description, recurrence (daily/weekly/biweekly/monthly/quarterly/semiannual/annual), category, priority, sla_hours, location_id, assigned_user_id, active, next_due, last_generated_at

#### `POST /preventive-plans`

Cria um plano preventivo. Requer `name` e `recurrence`. Se `next_due` não for informado, calcula automaticamente com base na recorrência.

```json
{
  "name": "Revisão ar-condicionado suíte 301",
  "recurrence": "quarterly",
  "category": "HVAC",
  "priority": "media",
  "sla_hours": 48,
  "assigned_user_id": 5,
  "location_id": 12
}
```

#### `POST /preventive-plans/generate`

Verifica todos os planos ativos com `next_due <= hoje` e gera uma OS para cada um. O título da OS é prefixado com `[Preventiva]`. Após gerar, avança `next_due` conforme a recorrência e registra `last_generated_at`. Retorna `{generated: N, work_order_ids: [...]}`.

### Checklists recorrentes

Templates de verificação reutilizáveis com geração automática de execuções por agenda.

#### Modelos

- `checklist_templates`: name, description, recurrence (daily/weekly/biweekly/monthly), category, assigned_user_id, active, next_due
- `checklist_template_items`: template_id, label, sort_order
- `checklist_executions`: template_id, due_date, status (pendente/concluido), completed_at, completed_by_user_id, notes
- `checklist_execution_items`: execution_id, label, sort_order, checked, checked_at

#### `POST /checklists/templates`

Cria um template com itens inline.

```json
{
  "name": "Abertura turno manhã",
  "recurrence": "daily",
  "category": "Operação",
  "items": [
    {"label": "Verificar lobby", "sort_order": 0},
    {"label": "Checar piscina", "sort_order": 1},
    {"label": "Inspecionar elevadores", "sort_order": 2}
  ]
}
```

#### `POST /checklists/executions/{id}/toggle`

Marca ou desmarca um item individual. Body: `{item_id: 5, checked: true}`. Registra `checked_at` quando marcado.

#### `POST /checklists/executions/{id}/complete`

Conclui a execução. Body opcional: `{notes: "Observação"}`. Registra `completed_at` e `completed_by_user_id`.

#### `POST /checklists/generate`

Gera execuções para templates ativos com `next_due <= hoje`. Copia os itens do template para a execução. Avança `next_due` conforme a recorrência. Retorna `{generated: N, execution_ids: [...]}`.

### Controle de estoque

Registro de materiais com movimentações de entrada, saída e ajuste, vinculáveis a ordens de serviço ou ocorrências.

#### Modelo

- `stock_items`: name, category, unit (padrão "un"), min_quantity, current_quantity, location_id
- `stock_movements`: item_id, movement_type (entrada/saida/ajuste), quantity, reason, work_order_id, occurrence_id, user_id

#### `POST /stock/items`

Cria um item de estoque. Requer `name`.

```json
{
  "name": "Toalha de banho",
  "category": "Amenities",
  "unit": "un",
  "min_quantity": 50,
  "current_quantity": 120,
  "location_id": 3
}
```

#### `POST /stock/movements`

Registra uma movimentação. Atualiza `current_quantity` do item automaticamente. Para `saida`, valida estoque suficiente. Para `ajuste`, o `quantity` passa a ser o novo saldo.

```json
{
  "item_id": 1,
  "movement_type": "saida",
  "quantity": 5,
  "reason": "Consumo do turno manhã",
  "work_order_id": 42
}
```

Retorna `422` se estoque insuficiente para saída ou tipo inválido.

#### `GET /stock/items?below_min=true`

Filtra itens com `current_quantity < min_quantity` para alertas de reposição.

### Pendências de turno (Handoff)

Comunicação estruturada entre turnos com fluxo pendente → lido → resolvido.

#### Modelo

- `shift_handoffs`: title, description, priority (normal/alta/urgente), category, target_shift (morning/afternoon/night), target_date, status (pendente/lido/resolvido), shift_report_id (vínculo opcional com relatório de turno), read_at/read_by_user_id, resolved_at/resolved_by_user_id/resolution_notes, created_by_user_id

#### `POST /handoffs`

Cria uma pendência para o próximo turno.

```json
{
  "title": "Hóspede UH 412 solicitou late checkout",
  "description": "Confirmar com recepção se há disponibilidade até 14h",
  "priority": "alta",
  "target_shift": "morning",
  "target_date": "2026-06-22"
}
```

#### `GET /handoffs/pending?target_date=2026-06-22&target_shift=morning`

Retorna pendências não resolvidas para a data/turno informados (inclui pendências de datas anteriores ainda abertas e pendências sem turno específico). Limite de 50 itens.

#### `POST /handoffs/{id}/read`

Marca como lido. Idempotente. Registra `read_at` e `read_by_user_id`, muda status para `lido`.

#### `POST /handoffs/{id}/resolve`

Resolve a pendência. Body opcional: `{resolution_notes: "..."}`. Registra timestamps e muda status para `resolvido`. Se não lida, marca como lida automaticamente.

### Usuários

O CRUD de usuários está operacional. Todas as rotas exigem Tenant Bearer e isolam por `company_id`.

#### `GET /users`

Lista usuários do tenant com paginação e busca. Aceita `page`, `page_size` e `search` (busca por nome ou e-mail). Responde `{items, total, page, page_size}`. Cada item inclui `id`, `name`, `email`, `role_name`, `active` e `updated_at`.

#### `POST /users`

Cria um usuário. Requer `name`, `email` e `password`. Opcionais: `role_id` e `active`. A senha é armazenada com hash bcrypt. Retorna `409` se o e-mail já existir no tenant.

#### `PATCH /users/{id}`

Atualiza campos do usuário. Aceita qualquer subconjunto de `name`, `email`, `password`, `role_id` e `active`. Se `password` for enviada, gera novo hash bcrypt.

#### `DELETE /users/{id}`

Exclusão lógica — preenche `deleted_at` e desativa o usuário. Retorna `400` se o usuário tentar excluir a si mesmo.

### Cadastros (Registries)

Endpoint unificado para setores, locais e funções. O campo `category` identifica o tipo: `"Setor"`, `"Local"` ou `"Função"`.

#### `GET /registries`

Lista todos os cadastros do tenant combinados em uma única listagem, com paginação e busca por nome. Responde `{items, total, page, page_size}`.

#### `POST /registries`

Cria um cadastro. Requer `name` e `category`. A `category` deve ser `"Setor"`, `"Local"` ou `"Função"`; valores inválidos retornam `400`.

#### `PATCH /registries/{id}?category=Setor`

Atualiza o nome do cadastro. O `category` é obrigatório como query parameter para identificar a tabela correta. Quando `category=Local`, aceita também `latitude`, `longitude` e `geofence_radius_m` (usados no geofencing do Portal do Colaborador — ver [portal-colaborador.md](portal-colaborador.md)); esses campos são ignorados para `Setor`/`Função`. `GET`/`POST`/`PATCH /registries` retornam `latitude`/`longitude`/`geofence_radius_m` (nulos fora de `Local`).

#### `DELETE /registries/{id}?category=Setor`

Exclusão lógica do cadastro. O `category` é obrigatório como query parameter.

### Módulos genéricos

Endpoint unificado para módulos operacionais que compartilham a mesma estrutura: reuniões, relatórios de turno, inspeções, diário de obra, manutenção e mural. O `{slug}` identifica o módulo.

Slugs válidos: `inspecoes`, `diarios-obra`, `manutencao`. (Reuniões e relatórios de turno foram promovidos para `/meetings` e `/shift-reports`; mural foi promovido para `/bulletin`.)

Registros importados da V1 possuem `legacy_id` e `payload` JSON com dados ricos (subjects, participants, frequencies, items de conferência, etc.) preservados da estrutura original.

#### `GET /modules/{slug}`

Lista registros do módulo com paginação e busca. Aceita `page`, `page_size` e `search`. Responde `{items, total, page, page_size}`. Cada item inclui `id`, `title`, `description`, `category`, `owner` (nome do usuário), `status` e `updated_at`.

#### `POST /modules/{slug}`

Cria um registro. Requer `title`. Opcionais: `description`, `category`, `status` (padrão: "Em andamento") e `owner_user_id` (padrão: usuário logado).

#### `PATCH /modules/{slug}/{id}`

Atualiza campos do registro. Aceita qualquer subconjunto de `title`, `description`, `category`, `status` e `owner_user_id`.

#### `DELETE /modules/{slug}/{id}`

Exclusão lógica — preenche `deleted_at`. Retorna `404` se o registro não existir, já estiver excluído ou pertencer a outro tenant/módulo.

### Auditoria de novos endpoints

Toda mutação nos novos endpoints (usuários, cadastros e módulos genéricos) gera `AuditEvent`:

| `entity_type` | `event_type` | Quando |
| --- | --- | --- |
| `user` | `create` / `update` / `delete` | CRUD de usuários |
| `registry` | `create` / `delete` | CRUD de cadastros |
| `{module_slug}` | `create` / `update` / `delete` | CRUD de módulos genéricos |

### Perfil do usuário

#### `PATCH /users/me`

Permite ao usuário autenticado editar seu próprio perfil. Aceita `name`, `phone` e `password`. Não permite alterar `email`, `role_id` ou `active` — essas alterações exigem o endpoint administrativo `PATCH /users/{id}`. Se `password` for enviada, gera novo hash bcrypt. Retorna `422` se nenhum campo for enviado.

### Procedimentos

O CRUD de procedimentos está operacional. Todas as rotas exigem Tenant Bearer e isolam por `company_id`.

#### `GET /procedures`

Lista procedimentos do tenant com paginação e busca por nome. Aceita `page`, `page_size` e `search`. Responde `{items, total, page, page_size}`. Cada item inclui `id`, `name`, `link`, `file` e `updated_at`.

#### `POST /procedures`

Cria um procedimento. Requer `name`. Opcionais: `link` e `file`.

#### `PATCH /procedures/{id}`

Atualiza campos do procedimento. Aceita qualquer subconjunto de `name`, `link` e `file`.

#### `DELETE /procedures/{id}`

Exclusão lógica — preenche `deleted_at`. Retorna `404` se o registro não existir, já estiver excluído ou pertencer a outro tenant.

### Notificações in-app

Notificações persistentes por usuário com suporte a leitura e contagem de não lidas.

#### `GET /notifications`

Lista notificações do usuário autenticado com paginação. Aceita `page`, `page_size` e `unread_only` (boolean). Responde `{items, total, unread, page, page_size}`. Cada item inclui `id`, `title`, `body`, `category`, `entity_type`, `entity_id`, `read_at`, `email_sent_at` e `created_at`. O campo `unread` sempre indica o total de não lidas (independente do filtro).

#### `PATCH /notifications/{id}/read`

Marca uma notificação como lida. Idempotente — se já lida, retorna sem alterar. Retorna `404` se a notificação não pertencer ao usuário.

#### `POST /notifications/read-all`

Marca todas as notificações não lidas do usuário como lidas. Responde `204`.

#### `GET /notifications/preferences`

Lista preferências de notificação do usuário autenticado para todos os módulos válidos. Módulos sem preferência salva retornam `in_app: true, email: true` (default). Responde `[{module, in_app, email}]`.

Módulos válidos: `occurrences`, `fiscal_requests`, `meetings`, `shift_reports`, `procedures`, `inspections`, `maintenance`, `modules`.

#### `PUT /notifications/preferences/{module}`

Atualiza preferência de notificação do usuário para um módulo. Body: `{in_app: bool, email: bool}`. Retorna `{module, in_app, email}`. Retorna `400` se o módulo for inválido.

### Destinatários por módulo

Configuração a nível de empresa — define quais usuários recebem notificações de cada módulo por padrão (além dos envolvidos diretos no registro). Armazenado em `company_settings` com chave `notification_recipients`.

#### `GET /settings/notification-recipients`

Lista destinatários configurados para todos os módulos. Requer `settings.view`. Responde `[{module, user_ids}]`.

#### `PUT /settings/notification-recipients/{module}`

Define a lista de `user_ids` que recebem notificações de um módulo. Requer `settings.edit`. Body: `{user_ids: [int]}`. Retorna `{module, user_ids}`. Retorna `400` se o módulo for inválido.

### Registro de entrega

Cada notificação inclui o campo `email_sent_at` (datetime ou null) que indica quando o e-mail correspondente foi enviado com sucesso via Brevo. O campo é preenchido automaticamente pelo sistema — não há endpoint para alterá-lo.

### Auditoria dos novos endpoints

| `entity_type` | `event_type` | Quando |
| --- | --- | --- |
| `procedure` | `create` / `update` / `delete` | CRUD de procedimentos |
| `user` | `update_profile` | PATCH /users/me |

### Anexos

Anexos são armazenados no MinIO (S3-compatible) e referenciados na tabela `attachments` com vínculo polimórfico por `entity_type`/`entity_id`.

#### `POST /attachments?entity_type=fiscal_request&entity_id=42`

Upload multipart. Envia o arquivo no campo `file` do form-data. Query params obrigatórios: `entity_type` e `entity_id`.

Entity types válidos: `fiscal_request`, `occurrence`, `procedure`, `module_record`.

Validações:
- Tamanho máximo: 10MB (configurável via `ATTACHMENT_MAX_SIZE_MB`)
- Máximo por registro: 20 (configurável via `ATTACHMENT_MAX_PER_ENTITY`)
- Extensões permitidas: `.jpg`, `.jpeg`, `.png`, `.gif`, `.webp`, `.svg`, `.pdf`, `.doc`, `.docx`, `.xls`, `.xlsx`, `.csv`, `.txt`, `.zip`, `.rar`, `.7z`
- Content-types correspondentes validados

Responde `201` com metadados do anexo (`id`, `filename`, `content_type`, `size_bytes`, `created_at`). Retorna `422` se o arquivo violar alguma regra.

#### `GET /attachments?entity_type=fiscal_request&entity_id=42`

Lista anexos de uma entidade. Responde `{items, total}`.

#### `GET /attachments/{id}/download`

Download do arquivo com `Content-Disposition: attachment`. Isolado por `company_id` — um tenant não pode baixar anexos de outro.

#### `DELETE /attachments/{id}`

Exclui o anexo do MinIO e do banco. Registra evento de auditoria `attachment_remove` com o nome do arquivo. Responde `204`. Retorna `404` se o anexo não existir ou pertencer a outro tenant.

### ACL (Controle de Acesso)

O sistema de permissões usa uma factory `require_permission(code)` em `app/core/permissions.py`. Cada endpoint protegido declara a permissão necessária via `Annotated[AuthenticatedUser, require_permission("modulo.acao")]`. O JWT já carrega `permissions: list[str]` populadas a partir do role do usuário. A permissão wildcard `*` (Administrador) bypassa todas as verificações.

#### Permissões disponíveis

| Módulo | Códigos |
| --- | --- |
| occurrence | `occurrence.view`, `.create`, `.edit`, `.delete` |
| fiscal_request | `fiscal_request.view`, `.create`, `.edit`, `.delete` |
| user | `user.view`, `.create`, `.edit`, `.delete` |
| registry | `registry.view`, `.create`, `.edit`, `.delete` |
| module | `module.view`, `.create`, `.edit`, `.delete` |
| procedure | `procedure.view`, `.create`, `.edit`, `.delete` |
| settings | `settings.view`, `.edit` |
| meeting | `meeting.view`, `.create`, `.edit`, `.delete` |
| shift_report | `shift_report.view`, `.create`, `.edit`, `.delete` |
| check_suite | `check_suite.view`, `.create`, `.edit`, `.delete` |
| inspection_suite | `inspection_suite.view`, `.create`, `.edit`, `.delete` |
| apartment_inspection | `apartment_inspection.view`, `.create`, `.edit`, `.delete` |
| audit_report | `audit_report.view`, `.create`, `.edit`, `.delete` |
| work_diary | `work_diary.view`, `.create`, `.edit`, `.delete` |
| work_order | `work_order.view`, `.create`, `.edit`, `.delete` |
| preventive_plan | `preventive_plan.view`, `.create`, `.edit`, `.delete` |
| checklist | `checklist.view`, `.create`, `.edit`, `.delete` |
| stock | `stock.view`, `.create`, `.edit`, `.delete` |
| handoff | `handoff.view`, `.create`, `.edit`, `.delete` |
| maintenance | `maintenance.view`, `.create`, `.edit`, `.delete` |
| bulletin | `bulletin.view`, `.create`, `.edit`, `.delete` |
| hour_bank | `hour_bank.view`, `.manage` |
| punch_adjustment | `punch_adjustment.view`, `.manage` |
| system | `*` (acesso total) |

Sem a permissão necessária, a API retorna `403 Forbidden` com `{"code": "forbidden", "required": "modulo.acao"}`.

#### Roles (`/roles`)

CRUD de cargos por tenant. Cada role tem um conjunto de permissões atribuídas via tabela junction `role_permissions`. A exclusão de um role só é permitida se nenhum usuário estiver atribuído a ele (retorna `409 role_has_users`).

### Ocorrências — funcionalidades adicionais

#### `GET /occurrences/{id}`

Detalhe de uma ocorrência com participantes. Retorna `OccurrenceDetail` com campos adicionais: `unit`, `participants: [{id, name}]` e `notify_user_ids`.

#### `POST /occurrences/{id}/clone`

Duplica uma ocorrência. Copia todos os campos, participantes e notificações. O título recebe prefixo "Cópia de ". O status volta para 1 (Em andamento). Timeline e anexos não são copiados. Retorna `201` com a nova ocorrência.

#### `GET /occurrences/{id}/pdf`

Exporta a ocorrência em PDF (reportlab). Inclui: header com nome da empresa, metadata (status, setor, local, responsável, prazo), descrição, participantes e histórico completo da timeline. Retorna `StreamingResponse` com `Content-Disposition: attachment`.

#### Participantes de ocorrências

A criação e atualização de ocorrências agora aceitam `participant_ids: list[int]` para vincular participantes. Os participantes são armazenados na tabela `occurrence_participants` (junction com chave composta `occurrence_id` + `user_id`).

### Reuniões (`/meetings`)

Reuniões foram promovidas de `module_records` para tabelas dedicadas: `meetings`, `meeting_participants` e `meeting_subjects`. Dados existentes foram migrados automaticamente.

#### Modelo

- `meetings`: title, description, scheduled_at (datetime), location, status, owner_user_id, notify_user_ids, deleted_at
- `meeting_participants`: meeting_id, user_id, role (organizer/attendee/optional)
- `meeting_subjects`: meeting_id, title, description, sort_order, resolved (boolean)

#### `POST /meetings`

Cria uma reunião com participantes e pautas em uma única chamada.

```json
{
  "title": "Alinhamento operacional semanal",
  "scheduled_at": "2026-06-25T09:00:00",
  "location": "Sala de reuniões",
  "status": "Agendada",
  "owner_user_id": 1,
  "participants": [
    {"user_id": 2, "role": "attendee"},
    {"user_id": 3, "role": "organizer"}
  ],
  "subjects": [
    {"title": "Revisão de indicadores", "sort_order": 0},
    {"title": "Planejamento da semana", "sort_order": 1}
  ],
  "notify_user_ids": [2, 3]
}
```

#### Pautas (`/meetings/{id}/subjects`)

- `POST /meetings/{id}/subjects` — adiciona pauta
- `PATCH /meetings/{id}/subjects/{sid}` — atualiza pauta (toggle resolved, reorder)
- `DELETE /meetings/{id}/subjects/{sid}` — remove pauta

#### `POST /meetings/{id}/clone`

Duplica a reunião com participantes e pautas. Título com prefixo "Cópia de ". Status volta para "Agendada".

#### Timeline e anexos

Reuniões usam os mesmos endpoints genéricos de timeline (`entity_type="meeting"`) e anexos. Toda mutação gera `AuditEvent`.

### Relatórios de turno (`/shift-reports`)

Relatórios de turno foram promovidos de `module_records` para a tabela `shift_reports`. Dados existentes foram migrados automaticamente.

#### Modelo

- `shift_reports`: title, description, shift_date (date), shift_type (morning/afternoon/night), status, started_at, ended_at, owner_user_id, notify_user_ids, deleted_at

#### `GET /shift-reports`

Lista relatórios com paginação, busca e filtro por data. Aceita query params opcionais `date_from` e `date_to` (formato `YYYY-MM-DD`).

#### `POST /shift-reports`

```json
{
  "title": "Turno manhã — Bloco A",
  "shift_date": "2026-06-20",
  "shift_type": "morning",
  "status": "Em andamento",
  "owner_user_id": 1,
  "description": "Passagem de turno com pendências do noturno."
}
```

#### Timeline e anexos

Relatórios usam `entity_type="shift_report"` para timeline e anexos.

### Infraestrutura: MinIO

O MinIO é o storage S3-compatible para anexos. Em dev, roda como container Docker (`localhost:9000` API, `localhost:9001` console). O bucket `registro-attachments` é criado automaticamente no startup da API. Em produção, pode ser substituído por AWS S3 ou qualquer storage S3-compatible via variáveis `S3_ENDPOINT_URL`, `S3_ACCESS_KEY`, `S3_SECRET_KEY` e `S3_BUCKET`.

### Portal do Colaborador (`/timeclock/mobile`)

Documentação completa em [portal-colaborador.md](portal-colaborador.md). Resumo do contrato:

```
POST /timeclock/mobile/login       { company_slug, registration_number, pin } → employee_session token
POST /timeclock/mobile/pin         (auth) { old_pin?, new_pin }
POST /timeclock/mobile/punch       (auth) { latitude, longitude } → TimePunch (geofencing por Haversine)
GET  /timeclock/mobile/status      (auth) → próximo tipo de batida esperado
GET  /timeclock/mobile/schedule    (auth) ?start&end → CalendarEntry[] do próprio funcionário
GET  /timeclock/mobile/payslips    (auth) → lista dos próprios contracheques
GET  /timeclock/mobile/payslips/{id}/download  (auth) → PDF, valida posse
GET  /timeclock/mobile/hour-bank   (auth) → saldo do banco de horas do próprio funcionário
POST /timeclock/mobile/adjustments (auth) { punch_id?, requested_punched_at, requested_punch_type?, reason } → solicita ajuste de ponto
GET  /timeclock/mobile/adjustments (auth) → lista as próprias solicitações de ajuste
```

Autenticado por token `employee_session`, um namespace de JWT isolado do `access`/`refresh`
de `User` — nunca intercambiáveis. Endpoint administrativo de reset de PIN:
`POST /timeclock/employees/{employee_id}/pin/reset` (`timeclock.manage`, no router principal).

### Banco de horas e ajuste de ponto (`/timeclock`)

Documentação completa em [escala-de-trabalho.md](escala-de-trabalho.md#banco-de-horas-e-ajuste-de-ponto-2026-07-05).

```
GET  /timeclock/hour-bank/{employee_id}                 (hour_bank.view)   → saldo total + extrato diário
POST /timeclock/hour-bank/{employee_id}/recalculate     (hour_bank.manage) { start_date, end_date } → recalcula o período (escala x pontos)
POST /timeclock/hour-bank/{employee_id}/initial-balance (hour_bank.manage) { effective_date, balance_minutes, notes? } → define/substitui o saldo inicial

GET  /timeclock/adjustments              (punch_adjustment.view)   ?status&employee_id → fila de solicitações
POST /timeclock/adjustments/{id}/review  (punch_adjustment.manage) { approve, review_notes? } → aprova (cria/corrige o TimePunch) ou rejeita
```

### Abono de ponto e estatísticas de ajuste (`/timeclock`) (2026-07-06)

Documentação completa em [escala-de-trabalho.md](escala-de-trabalho.md#abono-de-ponto-espelho-de-ponto-e-notificações-2026-07-06).

```
GET  /timeclock/adjustments/stats                       (punch_adjustment.view) → tendência mensal (6 meses) + top 5/bottom 5 solicitantes
GET  /timeclock/excusals                                (punch_adjustment.view) ?employee_id → lista abonos concedidos
POST /timeclock/excusals                                (timeclock.manage) { employee_id, reference_date, minutes?, reason } → concede abono (404 se employee_id não pertence à empresa)
```

Abono cria um `HourBankEntry(source="excused")` que neutraliza o saldo do dia (sem apagar o lançamento `"calculated"`), e notifica os demais usuários com permissão `punch_adjustment.manage`/`*` (exceto quem criou).

### Espelho de ponto (`/timeclock/mirror`) (2026-07-06)

Documentação completa em [escala-de-trabalho.md](escala-de-trabalho.md#feriados-2026-07-06).

```
GET /timeclock/mirror           (timeclock.view) ?employee_id&date_from&date_to → grade diária (batidas, crédito/débito, HE 50%/100%, adicional noturno, saldo)
GET /timeclock/mirror/by-sector (timeclock.view) ?sector_id&date_from&date_to → { mirrors: [...] } com um espelho por funcionário ativo do setor
GET /timeclock/mirror/export    (timeclock.view) ?employee_id&date_from&date_to&format=xlsx|pdf → mesmo relatório em Excel ou PDF (só por funcionário individual)
```

HE 100% considera domingo, folga agendada (`ScheduleEntry` com `shift_id IS NULL`) **ou feriado cadastrado** em `/timeclock/holidays`. Adicional noturno aplica a hora noturna reduzida da CLT (art. 73 §1º) combinada com o adicional de 20%.

Frontend: `/ponto/espelho`, com seletor "Filtrar por: Funcionário/Setor". Download via proxy Next.js (`web/app/api/ponto/espelho/export/route.ts`) — o browser não tem acesso ao JWT `httpOnly`, então a rota interna lê o token no servidor e repassa `Authorization: Bearer` para a API.

### Feriados (`/timeclock/holidays`) (2026-07-06)

```
GET    /timeclock/holidays       (holiday.view)   ?year? → lista feriados do tenant (opcionalmente filtrado por ano)
POST   /timeclock/holidays       (holiday.manage) { date, name } → cria feriado (409 duplicate_date se já existe feriado nessa data)
DELETE /timeclock/holidays/{id}  (holiday.manage) → remove feriado
```

Frontend: `/ponto/feriados`. Usado exclusivamente para qualificar HE 100% no espelho de ponto (ver acima) — sem integração com base nacional/municipal de feriados.

### Hora extra paga em dinheiro (`/settings/timeclock`) (2026-07-06)

Documentação completa em [escala-de-trabalho.md](escala-de-trabalho.md#hora-extra-paga-em-dinheiro-2026-07-06).

```
GET  /settings/timeclock (settings.view) → { overtime_paid_in_cash, cargo_salaries: {cargo: salário} }
POST /settings/timeclock (settings.edit) { overtime_paid_in_cash, cargo_salaries } → salva configuração
```

Quando `overtime_paid_in_cash=true`, `GET /timeclock/mirror`/`/mirror/by-sector` passam a incluir `overtime_50_value`/`overtime_100_value` (em R$, `null` quando não há salário resolvível) em cada dia e nos totais. `Employee` ganhou o campo `salary` (`PATCH /employees/{id}`, também em `GET /employees/{id}` como parte do `EmployeeDetailedSummary`) — usado com prioridade sobre `cargo_salaries[job_title]`. Quando o toggle está ligado e há salário resolvível, `POST /timeclock/hour-bank/{id}/recalculate` para de somar a HE ao saldo do banco de horas (só o déficit continua sendo banco de horas negativo).

Frontend: toggle e tabela de "salário-base por cargo" em `/configuracoes` (aba "Ponto"); campo "Salário" em `/cadastros/funcionarios`; valor em R$ exibido sob os minutos de HE 50%/100% em `/ponto/espelho`; aviso em `/ponto/banco-de-horas` quando o toggle está ligado.

### Relatórios — ocorrências e SLA de solicitações fiscais (`/reports`) (2026-07-05)

```
GET /reports/occurrences         (report.view) ?date_from&date_to → total, por status, por setor, taxa de conclusão, atrasadas, tendência diária
GET /reports/fiscal-requests-sla (report.view) ?date_from&date_to → total, por status/tipo, sla_compliance_pct, tempo médio de resolução, breakdown por estado de SLA, tendência diária
```

Sem `date_from`/`date_to`, usa o mês corrente. Frontend: `/relatorios`. Sem exportação (não há endpoint de export nesta primeira entrega).

### Plataforma — usuários, suporte e uso (`/platform/*`) (2026-07-11)

```
GET    /platform/users                        → equipe interna da plataforma (PlatformUser)
POST   /platform/users                        → { name, email, role, password }
PATCH  /platform/users/{id}                   → name?, email?, role?, password?, active?
DELETE /platform/users/{id}                   → soft delete + active=false

GET    /platform/support-requests             → pedidos de suporte de todos os tenants, com company_name
PATCH  /platform/support-requests/{id}        → { status: pending|contacted|resolved }

GET    /platform/usage?limit=200              → registros de uso por tenant (metric, value, period_start/end)
POST   /platform/usage/snapshot               → gera um snapshot do dia corrente (usuários ativos e ocorrências do mês) por tenant
```

Todas as rotas exigem `PlatformUser` autenticado (`current_platform_user`) e toda mutação é auditada em `PlatformAuditLog`. `SupportRequest` e `UsageRecord` não têm RLS (mesmo padrão de `subscriptions`/`invoices`: tabelas cross-tenant administradas apenas pela plataforma).

Endpoint tenant-facing correspondente para abrir um pedido de suporte:

```
POST /support/request   (autenticado como usuário do tenant) → { contact_name, contact_whatsapp, message? }
```

Acionado pelo botão "Ajuda e suporte" no `web/` (`components/help-button.tsx`), visível em todas as páginas autenticadas do tenant. Não há endpoint de criação manual de `usage_records` além do snapshot — não há Celery no Registro, então a geração é sob demanda pelo botão "Gerar snapshot de hoje" no admin.

Frontend admin: `/users`, `/support-requests`, `/usage`.

> Feature flags (`feature_flags`) foram implementadas em 2026-07-11 e removidas no mesmo dia (decisão: não seguir com a funcionalidade). Migration `20260711_0057_drop_feature_flags` desfaz a tabela.

### Plataforma — e-mail transacional (`/platform/settings/email`) (2026-07-11)

```
GET  /platform/settings/email  → { brevo_configured, email_from_address, email_from_name }
POST /platform/settings/email  → { brevo_api_key?, email_from_address?, email_from_name? }
```

Configuração global (tabela `platform_settings`, chave `email`), no mesmo padrão do Aloji. Sobrepõe `BREVO_API_KEY`/`MAIL_FROM_ADDRESS`/`MAIL_FROM_NAME` do `.env` da API para os e-mails transacionais do sistema (hoje: convite de usuário em `POST /users/invite`). Campos em branco no POST mantêm o valor salvo anteriormente — a API key nunca é retornada pelo GET, só a flag `brevo_configured`.

`app.domain.platform.service.get_effective_email_config(session, settings)` é o ponto único de resolução: DB (`platform_settings.email`) tem prioridade, cai para as env vars quando não configurado. Novos fluxos de e-mail transacional (reset de senha, etc.) devem chamar essa função em vez de ler `settings.brevo_api_key` direto.

Distinto do Brevo por tenant (`/settings/brevo`, tabela `company_settings`), que cada empresa configura em `/configuracoes` no `web/` para os próprios avisos de módulo — esse continua inalterado.

Frontend admin: `/settings` (`admin/app/(app)/settings/email-settings-form.tsx`).

#### Testar envio (Brevo por tenant, 2026-07-13)

```
POST /settings/brevo/test  { to: string }  → { status: "sent", message_id }
```

Dispara um e-mail real via `app.integrations.brevo.send_email()` usando a config já salva em `company_settings.brevo` (não aceita credenciais no body — sempre usa o que está persistido). `422 not_configured` se a empresa ainda não salvou nenhuma config; `502 send_failed` (com `status` = código HTTP retornado pela Brevo) se a API rejeitar a chave/remetente — cenário mais comum quando o domínio do remetente não está autenticado (SPF/DKIM) na conta Brevo, algo que a API do Registro não verifica nem pode automatizar.

Frontend `web/`: seção "Testar envio" em `/configuracoes?tab=integracoes`, só aparece depois que `has_credentials` é `true` (`BrevoSettingsSection` em `web/components/settings-sections.tsx`).
