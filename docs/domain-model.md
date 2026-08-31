# Modelo de domínio

Este modelo descreve o schema legado conhecido pelas migrations. Deve ser confirmado contra um dump sanitizado ou o MySQL antes de criar mappings definitivos.

```text
PlatformUser ──► PlatformAuditLog
Plan ──► Subscription ──► Company ──► User ──► Role ──► Permission
                    └────► Invoice

Company
  ├── Sector
  ├── Local
  ├── Func
  ├── Procedure ──► ProcedureFile
  ├── Meeting
  │     ├── subjects / topics
  │     ├── invited / registered participants
  │     └── subject attachments
  ├── ShiftReport
  │     ├── frequencies / maintenance / complaints / extras
  │     └── comments / uploads
  ├── InspectionSuite ──► InspectionSuiteItem
  ├── CheckSuite ──► CheckSuiteItem
  ├── ApartmentInspection ──► items / attachments / types
  ├── AuditReport ──► item1 / item2 / item3
  ├── WorkDiary ──► activities / teams / equipment / observations
  ├── AuditEvent (imutável por empresa)
  ├── Notification (in-app por usuário, com tracking de e-mail)
  ├── NotificationPreference (preferências in-app/email por usuário e módulo)
  ├── FiscalRequest (persistente) ──► attachments
  ├── Meeting ──► MeetingParticipant (com papel) + MeetingSubject (pautas)
  ├── ShiftReport (turno com data, tipo e horários)
  ├── WorkOrder (OS com workflow de 5 estados, absorveu Ocorrências em 2026-07-14)
  │     └── WorkOrderParticipant (junction work_order ↔ user)
  ├── PreventivePlan (manutenção preventiva recorrente → gera WorkOrder)
  ├── ChecklistTemplate ──► ChecklistTemplateItem
  ├── ChecklistExecution ──► ChecklistExecutionItem
  ├── StockItem ──► StockMovement (→ WorkOrder)
  ├── ShiftHandoff (pendências entre turnos → ShiftReport)
  ├── Supplier ──► SupplierContact
  ├── Contract ──► ContractAmendment
  │     └── ContractApprovalStep (fluxo sequential por aprovador)
  ├── ModuleRecord (genérico: inspeções, obra, manutenção, mural)
  ├── TimeClockDevice ──► TimePunch (relógio físico, webhook Control iD)
  ├── EmployeeCredential (PIN do Portal do Colaborador, 1:1 com Employee)
  ├── EmployeePayslip ──► Attachment (contracheque por competência)
  ├── HourBankEntry (banco de horas: calculado por período ou saldo inicial)
  └── PunchAdjustmentRequest ──► TimePunch (ajuste de ponto solicitado pelo funcionário, sujeito a aprovação)
```

## Agregados principais

| Agregado | Tabelas centrais | Regras a preservar |
| --- | --- | --- |
| Identidade e acesso | `users`, `roles`, `permissions`, `role_permissions`, `companies` | bcrypt, soft delete, empresa, RBAC com permissões por módulo, convite por e-mail |
| Plataforma SaaS | `platform_users`, `plans`, `subscriptions`, `invoices`, `platform_audit_logs` | sessão isolada, centavos, estado explícito e auditoria |
| Núcleo V1 importado | `sectors`, `locations`, `functions`, `procedures` | tenant `aero-hotel` (Aero Hotel), `legacy_id` (nullable — null em registros criados pelo GEOP), soft delete e relações remapeadas. `occurrences` foi dropada em 2026-07-14 (fusão em `work_orders`) — deixou de fazer parte do corte V1, que já estava descontinuado |
| Cadastros | `sectors`, `locals`, `funcs`, `procedures`, `procedure_files` | empresa, anexos e exclusão lógica quando existente |
| Reuniões | `meetings`, assuntos, pautas e participantes | início da reunião, ata, anexos e PDF |
| Turnos | `shift_reports` e tabelas filhas | aprovação/teste, anexos e Excel |
| Inspeções | `check_suites`, `check_suite_items`, `inspection_suites`, `inspection_suite_items`, `apartment_inspections`, `apartment_inspection_items`, `audit_reports`, `audit_report_items` | CRUD com items inline, soft delete, auditoria, tenant isolation. Vistorias suportam tipos checkin/checkout/periodic e vínculo com inspection_suite. Dados migrados de `module_records` |
| Diário de obra | `work_diaries`, `work_diary_activities`, `work_diary_teams`, `work_diary_equipment`, `work_diary_observations` | CRUD completo com 4 tabelas filhas gerenciadas inline (delete+re-insert). Soft delete, auditoria, tenant isolation |
| Comercial e cobrança | `plans`, `subscriptions`, `invoices`, `webhook_events` | CRUD auditado via `PlatformAuditLog`. Trial 14d → past_due → suspended (bloqueia login). Asaas sandbox integration, webhook idempotente com dedup, reconciliação periódica |
| Solicitações fiscais | `fiscal_requests` | tenant, tipo, título, descrição, protocolo único, origin, status, `requester_user_id`, `responsible_user_id`, `sla_deadline`, `sla_paused_at`, `sla_paused_seconds`, `chess_user_id`, `reservation_number` e `payload` JSON |
| Módulos genéricos | `module_records` | tenant, `module` (slug), `title`, `description`, `category`, `status`, `owner_user_id`, `legacy_id`, `payload` JSON e soft delete. Remanescente para inspeções e diários de obra. Reuniões e relatórios de turno foram promovidos para tabelas dedicadas; manutenção para `maintenance_records`; mural para `bulletin_posts` |
| Manutenção | `maintenance_records` | tabela dedicada com title, description, priority, status, location_id, owner_user_id, payload JSON. Permissões: `maintenance.view/create/edit/delete` |
| Mural | `bulletin_posts` | tabela dedicada com title, body, pinned, expires_at, author_user_id. Permissões: `bulletin.view/create/edit/delete` |
| Reuniões | `meetings`, `meeting_participants`, `meeting_subjects` | tabela dedicada com scheduled_at, location, participantes com papel (organizer/attendee/optional), pautas com resolved. Migrados de `module_records` |
| Relatórios de turno | `shift_reports` | tabela dedicada com shift_date, shift_type (morning/afternoon/night), status, started_at, ended_at. Migrados de `module_records` |
| Ordens de serviço | `work_orders` | workflow de 5 estados (aberta → em_andamento → aguardando_material [rótulo exibido: "Aguardando"] → concluída → validada), `priority` (urgente/alta/media/baixa), `category`, `sla_hours`/`sla_deadline`, `sector_id`, `unit` (unidade/apartamento), `comments`, `deadline` (prazo manual, independente do SLA), vínculo opcional com `maintenance_records`, `assigned_user_id`, `created_by_user_id`, `validated_by_user_id`, participantes M2M (`work_order_participants`). Absorveu em 2026-07-14 o domínio "Ocorrências" (tabela `occurrences` dropada sem migração de dados — ver `memoria-projeto.md`), inclusive export XLSX, export PDF e clone. Transições auditadas com timestamps (`started_at`, `completed_at`, `validated_at`). RLS com policy `tenant_isolation`. Permissões: `work_order.view/create/edit/delete` |
| Manutenção preventiva | `preventive_plans` | planos recorrentes (daily→annual) que geram `work_orders` automaticamente via `POST /preventive-plans/generate`. Campos: name, recurrence, category, priority, sla_hours, location_id, assigned_user_id, active, next_due, last_generated_at. Permissões: `preventive_plan.view/create/edit/delete` |
| Checklists recorrentes | `checklist_templates` → `checklist_template_items`, `checklist_executions` → `checklist_execution_items` | templates com itens reutilizáveis; execuções geradas por agenda via `POST /checklists/generate`. Cada item tem checked/checked_at individual. Status: pendente → concluido. Permissões: `checklist.view/create/edit/delete` |
| Estoque e materiais | `stock_items`, `stock_movements` | itens com quantity/min_quantity/unit/category/location. Movimentações (entrada/saída/ajuste) vinculáveis a `work_orders`. Saída valida estoque. Permissões: `stock.view/create/edit/delete` |
| Pendências de turno | `shift_handoffs` | comunicação entre turnos com fluxo pendente → lido → resolvido. Direcionável por turno (morning/afternoon/night) e data. Vínculo opcional com `shift_reports`. Confirmação de leitura e resolução com timestamps. Permissões: `handoff.view/create/edit/delete` |
| Contratos | `suppliers`, `supplier_contacts`, `contracts`, `contract_amendments`, `contract_approval_steps` | fornecedores com contatos múltiplos; contratos com ciclo de vida (rascunho → em_aprovacao → ativo → suspenso/encerrado); fluxo de aprovação sequential por etapas; aditivos (prazo/valor/objeto/outros) que atualizam campos do contrato; integração financeira (custo/orçamento/pagamento). Anexos via sistema genérico (`entity_type="contract"`). Permissões: `contract.view/create/edit/delete/approve` |
| Notificações | `notifications`, `notification_preferences` | por tenant e usuário, `title`, `body`, `category`, `entity_type`/`entity_id` (link opcional ao registro), `read_at` para leitura, `email_sent_at` para tracking de entrega. Preferências por módulo (in_app/email) em `notification_preferences`. Destinatários por módulo em `company_settings` (chave `notification_recipients`) |
| Anexos | `attachments` | por tenant, `entity_type`/`entity_id` polimórfico, `filename`, `content_type`, `size_bytes`, `storage_key` (MinIO/S3), `uploaded_by_user_id` (inclui `entity_type="employee_payslip"`) |
| Ponto eletrônico (relógio físico) | `time_clock_devices`, `time_clock_enrollments`, `time_punches` | dispositivo autenticado por `webhook_token` (não JWT), `TimeClockEnrollment.external_id` mapeia matrícula do relógio → `employee_id`. `TimePunch.source` ∈ {`device`, `manual`, `mobile`} |
| Portal do Colaborador | `employee_credentials`, `employee_payslips` | ver [portal-colaborador.md](portal-colaborador.md). `EmployeeCredential` (PIN hash, lockout, 1:1 com `Employee`) e `EmployeePayslip` (`reference_month` + `attachment_id`) isolados do cadastro de RH por preocupação, mesmo padrão de `TimeClockEnrollment` |
| Banco de horas | `hour_bank_entries` | um lançamento por `employee_id`+`reference_date`+`source`. `source="calculated"` (gerado por período via `POST /timeclock/hour-bank/{id}/recalculate`, comparando turno agendado x pontos batidos) ou `source="initial_balance"` (lançamento único, manual, para saldo migrado de outro sistema). Ver [escala-de-trabalho.md](escala-de-trabalho.md#banco-de-horas-e-ajuste-de-ponto-2026-07-05) |
| Ajuste de ponto | `punch_adjustment_requests` | solicitação do funcionário (Portal do Colaborador) para corrigir uma `TimePunch` existente (`punch_id` preenchido) ou lançar uma batida esquecida (`punch_id` null). `status` ∈ {`pending`, `approved`, `rejected`}; aprovação reaproveita `update_punch`/`create_manual_punch` e grava `resulting_punch_id`. Uma solicitação só pode ser revisada uma vez |
| Conferência de discrepâncias | `discrepancy_reports`, `discrepancy_report_entries` | conferência por local/unidade com duas verificações (`first_code`/`second_code`, string livre até 40 caracteres), observações, responsáveis (`prepared_by_user_id`/`checked_by_user_id`/`received_by_user_id`), `status` ∈ {`draft`, `submitted`, `closed`} — fechada não aceita mais nenhum PATCH. Resumo por código e contagem de divergências calculados no servidor. Exportação em PDF (reportlab). RLS na tabela pai; `discrepancy_report_entries` não tem `company_id` próprio, herda isolamento via `report_id`. Permissões: `discrepancy_report.view/create/edit/delete`. Primeiro vertical slice das oportunidades do legado, ver [oportunidades-legado-operacao.md](oportunidades-legado-operacao.md) |
| Cliente de e-mail | `email_accounts`, `email_messages`, `email_alert_rules` | conta IMAP/POP3 por tenant, `auth_type` ∈ {`password` (`password_enc`, ofuscado base64 — não é criptografia real), `oauth` (`oauth_access_token_enc`/`oauth_refresh_token_enc`/`oauth_token_expires_at`, contas Gmail via OAuth2 — ver [gmail-oauth-setup.md](integracoes/gmail-oauth-setup.md))}. `email_messages` é cache local pós-sincronização (dedupe por UID IMAP persistente/UIDL POP3, nunca número de sequência). `email_alert_rules` dispara WhatsApp (Evolution) quando uma mensagem casa o filtro (`subject`/`domain`/`sender`). Sincronização é manual/sob demanda — sem job periódico no projeto |
| Auditoria | `audit_events` | imutável por tenant (sem `updated_at`/`deleted_at`), `user_id`, `entity_type`, `entity_id`, `event_type` (`create`, `update`, `delete`, `comment`, `attachment_add`, `attachment_remove`), `diff` JSON com antes/depois por campo |

## Convenções de dados

- IDs legados são preservados enquanto o MySQL for a fonte de verdade.
- Como IDs novos podem colidir com dados fictícios, a identidade V1 é preservada por `company_id` + `legacy_id`. O campo `legacy_id` é nullable — registros criados pelo GEOP ficam com valor null; registros importados da V1 mantêm o ID original.
- `company_id` deve participar de toda consulta de negócio. Além do filtro ORM (application-level), o PostgreSQL aplica RLS (Row-Level Security) com policies `tenant_isolation` em todas as tabelas com `company_id`. O GUC `app.current_company_id` é setado via `SET LOCAL` na dependency `current_user` — rotas platform (sem GUC) operam como superuser com `BYPASSRLS`.
- `deleted_at` significa exclusão lógica; registros apagados não autenticam nem aparecem por padrão.
- Anexos exigem inventário de caminho físico, metadados e política de acesso antes do corte.
- Dinheiro, se surgir em módulos futuros, usa centavos inteiros ou `Decimal`, nunca `float`.
- Usuário da plataforma nunca possui `company_id`; acesso cross-tenant é uma capacidade administrativa separada.
- IDs externos do Asaas são opcionais e únicos quando preenchidos; o GEOP mantém suas próprias chaves.
- Toda mutação em ordens de serviço, solicitações fiscais, procedimentos e anexos gera automaticamente um `AuditEvent` com `user_id`, `company_id`, `entity_type`, `entity_id`, `event_type` e `diff` JSON. O diff registra apenas campos que mudaram, com valor anterior e novo. Eventos de anexo (`attachment_add`, `attachment_remove`) registram `filename`, `content_type` e `size_bytes`. A timeline do frontend consome esses eventos via `GET /timeline/{entity_type}/{entity_id}`.
- Solicitações fiscais possuem modelo persistente (`fiscal_requests`) com `company_id`, `protocol`, `request_type`, `title`, `apartment`, `requester`, `requester_email`, `requester_user_id`, `responsible_user_id`, `chess_user_id`, `reservation_number`, `sla_deadline`, `sla_paused_at`, `sla_paused_seconds`, `description`, `origin`, `status` e `payload` JSON para campos específicos do tipo. O protocolo é gerado como `REG-{id:06d}`. O campo `origin` marca registros criados pelo GEOP como `registro`; o valor `chess-hotel` só aparece em registros históricos da integração Chess Hotel, descontinuada — nenhum código novo grava esse valor. CPF/CNPJ e e-mail do tomador no `payload` são validados e normalizados na criação e atualização. Anexos permanecem planejados.
- O SLA de solicitações fiscais é calculado em dias úteis (seg-sex 8h-18h) na timezone do tenant (`companies.timezone`, padrão `America/Sao_Paulo`). A função `calculate_business_deadline()` em `app/core/sla.py` avança apenas em horário útil, pulando fins de semana e feriados configuráveis. O status "Em espera" pausa o SLA automaticamente (`sla_paused_at`); ao retomar, os segundos pausados são acumulados em `sla_paused_seconds` e descontados do deadline efetivo. O `sla_status` computado pode ser: `on_time`, `warning` (≤4h), `overdue`, `paused` ou `completed`.
- Anexos são armazenados na tabela `attachments` com vínculo polimórfico por `entity_type`/`entity_id` (ex: `fiscal_request/42`). Os arquivos ficam no MinIO (S3-compatible) com chave `{company_id}/{entity_type}/{entity_id}/{uuid}.ext`. Validações: tamanho máximo 10MB, máximo 20 anexos por registro, extensões e content-types permitidos (imagens, PDFs, documentos Office, CSV, TXT, ZIP). O storage service (`app/core/storage.py`) abstrai o MinIO via boto3, compatível com AWS S3 em produção.
- A tabela `companies` possui campo `timezone` (VARCHAR 60, default `America/Sao_Paulo`) para cálculo de SLA e exibição de horários na timezone do tenant.
- Procedimentos possuem CRUD completo via `/procedures` com `name`, `link`, `file` e soft delete. Seguem o mesmo padrão de isolamento por `company_id` e auditoria dos demais módulos.
- Notificações in-app são persistidas na tabela `notifications` com `company_id`, `user_id`, `title`, `body`, `category` (default `info`), `entity_type`/`entity_id` opcionais para link ao registro de origem, e `read_at` para estado de leitura. A criação programática é feita via `create_notification()` em `app/domain/notifications/service.py`.
- Ordens de serviço possuem workflow com máquina de estados: `aberta` → `em_andamento` → `aguardando_material` | `concluida` → `validada`. A chave do estado continua `aguardando_material` (sem mudança de schema), mas o rótulo exibido é genérico ("Aguardando", cobre qualquer tipo de espera, não só material) desde a fusão com Ocorrências. A transição `aguardando_material` → `em_andamento` e `concluida` → `em_andamento` permitem retorno. `validada` é estado terminal. Transições são validadas no service (`TRANSITIONS` dict) e rejeitadas com 422 se inválidas. Cada transição registra `AuditEvent` com diff do status e timestamps automáticos (`started_at` na primeira ida a `em_andamento`, `completed_at` em `concluida`, `validated_at` + `validated_by_user_id` em `validada`). O SLA é calculado no momento da criação: `sla_deadline = now() + sla_hours` se `sla_hours` for fornecido.
- **2026-07-14 — Ocorrências fundida em Ordens de Serviço.** A tabela `occurrences` (e `occurrence_participants`) foi dropada sem migrar dados de nenhum tenant (autorizado explicitamente pelo usuário). Todos os recursos que só existiam em Ocorrências (participantes M2M, export XLSX, export PDF, clone, campos `unit`/`comments`/`deadline`/`sector_id`) foram portados para `work_orders`/`work_order_participants`. Permissões `occurrence.*` foram removidas de `permissions`/`role_permissions`; papéis customizados de tenants que só tinham `occurrence.*` concedido explicitamente não ganharam `work_order.*` automaticamente (não havia estado de tenant a preservar). O módulo "Ocorrências" saiu do menu e do sistema de módulos do frontend; a tela `/ordens-servico` ganhou um toggle Kanban/Lista (Kanban continua padrão).
- Autenticação usa dois tokens JWT: access token (30min, type=access, contém permissions) e refresh token (7 dias, type=refresh, contém apenas sub e company_id). O frontend armazena ambos em cookies httpOnly e faz auto-refresh transparente quando o access expira.
- Rate limiting via slowapi protege endpoints sensíveis: login (10/min), refresh (20/min). Exceder retorna 429.
- Cada domínio possui `service.py` com lógica de negócio separada do router. Services recebem session e parâmetros tipados, facilitando reuso (ex: `fiscal_requests.service.create_fiscal_request()`) e testes unitários sem dependência do FastAPI.
- O Portal do Colaborador usa um terceiro tipo de token JWT, `employee_session` (`sub`=employee_id, `company_id`, sem `permissions`/`role_id`), completamente isolado dos tokens `access`/`refresh` de `User` — nenhum dos dois abre rotas do outro (testado nos dois sentidos). `Location` ganhou `latitude`/`longitude`/`geofence_radius_m` para geofencing por Haversine na batida mobile. Ver [portal-colaborador.md](portal-colaborador.md).
