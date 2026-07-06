# Backlog da modernização

## P0 — consolidar SaaS e receber dados reais

- [x] Criar MySQL local, migrations e seed fictício com dois tenants.
- [x] Separar autenticação tenant e plataforma.
- [x] Criar painel administrativo inicial.
- [x] Testar bloqueio de token com `company_id` divergente.
- [x] Receber dump de desenvolvimento e restaurar/importar em staging temporária.
- [x] Inventariar as 66 tabelas do dump V1 e importar o núcleo normalizado.
- [x] Importar todos os dados restantes do dump V1: reuniões (meetings + subjects + participants), relatórios de turno (shift_reports + filhas), comentários e participantes de ocorrências, conferências de suítes (check_suites + items), auditorias noturnas (audit_reports + itens), arquivos de procedimentos e notificações legadas.
- [x] Validar login compatível com hashes bcrypt Laravel.
- [x] Implementar página `/login` do produto tenant com cookie `httpOnly`.
- [x] Corrigir o login multitenant para validar a senha antes de revelar a lista de empresas.
- [x] Adicionar testes de login para e-mail único, senha inválida, e-mail em múltiplos tenants e seleção explícita de tenant.
- [x] Validar `company_id` positivo no contrato de login e documentar integralmente a resposta `422 multi_tenant`.
- [x] Criar migration de upgrade que renomeie com segurança um eventual tenant antigo `aero-v1` para `aero-hotel`, sem criar tenant duplicado.
- [x] Criar CI com Ruff, pytest e typecheck (GitHub Actions); mypy excluído até estabilizar.
- [x] Concluir inventário de índices, constraints e órfãos — migration `0017_schema_audit` corrige índices compostos, remove redundantes e adiciona `ondelete` em 10 FKs.
- [x] Testes cross-tenant: suite `test_cross_tenant.py` com validação de tokens por tenant, rejeição de token expirado e sem token em todos os endpoints autenticados.
- [x] Separar service layer dos routers — cada domínio possui `service.py` com lógica de negócio extraída; routers delegam para services.
- [x] Rate limiting com slowapi nos endpoints sensíveis: login (10/min), refresh (20/min), integração Chess (30/min).
- [x] Refresh token JWT (type=refresh, 7 dias) com endpoint `POST /auth/refresh` e auto-refresh transparente no frontend via cookie httpOnly.
- [x] Estabilizar mypy na imagem de desenvolvimento — causa era `PermissionError` no `.mypy_cache`; resolvido com `MYPY_CACHE_DIR=/tmp/.mypy_cache` no Dockerfile.

## P2 — identidade, ACL e cadastros

- [x] Usuários: CRUD via API com listagem, criação (bcrypt), atualização, soft delete e paginação server-side.
- [x] Setores, locais e funções: CRUD unificado via `/registries` com paginação e busca.
- [x] Procedimentos: CRUD via API (`/procedures`) com listagem paginada, busca, criação, atualização e soft delete.
- [x] Endpoint `PATCH /users/me` para edição de perfil pelo próprio usuário (nome, telefone, senha).
- [x] Anexos de procedimentos (upload, metadados e download) — página `/procedimentos` no frontend com upload via MinIO, listagem e download; eventos de auditoria `attachment_add`/`attachment_remove` registrados na timeline.
- [x] Timeline de alterações nos registros operacionais (front local, todas as telas).
- [x] Tabela de auditoria na API (`audit_events`) para persistir o histórico de alterações com `user_id`, `company_id` e diff JSON.
- [x] Padronizar design tokens no `globals.css` (espaçamento, cores, raios, sombras, tipografia, transições).
- [x] Unificar `DashboardShell` e `OperationalModule` em um `AppLayout` compartilhado, eliminando sidebar/topbar/navegação duplicados.
- [x] Componentes reutilizáveis de lista, formulário, estado vazio e confirmação — permissões ACL integradas ao `OperationalModule` (canView/canCreate/canEdit/canDelete); botões condicionados por `user.permissions`.
- [x] Persistir comentários e alterações da tratativa na API (`GET/POST /timeline/{entity_type}/{entity_id}`); frontend consome timeline da API para módulos conectados.
- [x] Tornar a auditoria imutável, com ator, tenant, data UTC, tipo de evento e diferenças estruturadas — `AuditEvent` já é imutável por design (sem `updated_at`/`deleted_at`, `created_at` com `server_default=func.now()`).
- [x] Registrar na timeline todos os campos específicos do domínio, inclusive os campos fiscais e anexos — timeline agora renderiza eventos `attachment_add`/`attachment_remove` com nome do arquivo; `procedure` adicionado como entity type válido; campos fiscais já eram capturados via `compute_diff` no payload.
- [x] Impedir a criação de eventos de alteração vazios: `record_event` retorna sem inserir quando `event_type == "update"` e `diff` é vazio.

## P3 — operação

- [x] Remover o corte nos primeiros 100 registros, carregando todas as páginas disponíveis da API de ocorrências.
- [x] Evoluir ocorrências para paginação e busca server-side sob demanda, com navegação via query params na URL.
- [x] Remover a precedência de dados antigos do `localStorage` sobre ocorrências retornadas pela API.
- [x] Implementar mutações de ocorrências na API com autorização e isolamento por empresa.
- [x] Dashboard com métricas reais agregadas do banco (ocorrências, fiscais, equipe, atividades recentes).
- [x] Todos os módulos operacionais conectados à API com CRUD completo e paginação server-side.
- [x] Tabela genérica `module_records` para módulos sem tabela própria (reuniões, inspeções, turnos, obra, manutenção, mural).
- [x] Ocorrências: participantes (tabela junction `occurrence_participants`), clone (`POST /occurrences/{id}/clone`), PDF (`GET /occurrences/{id}/pdf` via reportlab). Comentários e anexos já existiam via timeline/attachments.
- [x] Reuniões: promovidas para tabela dedicada `meetings` + `meeting_participants` (com papel: organizer/attendee/optional) + `meeting_subjects` (pautas com resolved). Migration de dados de `module_records`. CRUD completo + clone + subjects CRUD + ata PDF (`GET /meetings/{id}/pdf`).
- [x] Relatórios de turno: promovidos para tabela dedicada `shift_reports` com `shift_date`, `shift_type` (morning/afternoon/night), `status`. Migration de dados de `module_records`. CRUD completo com filtro por data.
- [x] Sistema ACL: `require_permission()` em todos os routers, seed de 35 permissões, role "Administrador" com wildcard `*`. CRUD de roles via `/roles`. Frontend condiciona ações por `user.permissions`.

## P3B — solicitações fiscais

- [x] Criar protótipo funcional no frontend com tipos de solicitação, campos condicionais, SLA, anexos e tratativa.
- [x] Criar modelo, migration, schemas, service, autorização e endpoints FastAPI para solicitações fiscais.
- [x] Integrar Chess Hotel via `POST /integrations/chess-hotel/tickets` com autenticação por header, resolução de usuário e SLA inicial.
- [x] Vincular solicitações fiscais a usuários do Registro (`requester_user_id`, `responsible_user_id`) e adicionar tracking/histórico para o Chess.
- [x] Validar e normalizar CPF/CNPJ e e-mail do tomador nos endpoints de solicitações fiscais.
- [x] Adicionar paginação server-side ao endpoint `GET /fiscal-requests` com busca por protocolo, solicitante e tipo.
- [x] Definir SLA no servidor: `sla_deadline` definido server-side (24h) ao criar solicitações fiscais do Registro e Chess; `sla_status` computado no servidor (on_time/warning/overdue/completed).
- [x] Evoluir SLA com timezone explícito, calendário útil, pausa e política de vencimento.
- [x] Substituir anexos Base64 no `localStorage` por armazenamento via MinIO (S3-compatible), com metadados no banco (`attachments`).
- [x] Validar tamanho (10MB), quantidade (20/registro), extensão e content-type dos anexos.
- [x] Restringir previews e downloads — CSP `default-src 'none'`, `nosniff`, `X-Frame-Options: DENY`, sanitização de filename no endpoint de download.
- [x] Notificações in-app: `create_notification()` dispara para responsáveis e notificados em todo `notify_record_event`; Chess Hotel notifica todos os usuários ativos ao criar solicitação fiscal.
- [x] Implementar preferências de notificação, destinatários por módulo e registro de entrega.
- [x] Backend de notificações in-app: model `Notification`, migration, endpoints de listagem paginada, marcar como lida e marcar todas como lidas.
- [x] Cobrir CRUD, SLA e isolamento cross-tenant com testes (52 testes; anexos e auditoria pendentes).

## P1 — comercial e cobrança

- [x] CRUD auditado de tenants, planos e assinaturas — endpoints platform com POST/GET/PATCH/DELETE para tenants, plans e subscriptions, todos auditados via `PlatformAuditLog`.
- [x] Definir trial, tolerância, suspensão e reativação — trial 14 dias, expiração para past_due, suspensão após 7 dias de tolerância (Company.status="suspended" bloqueia login), reativação via endpoint admin.
- [x] Configurar Asaas sandbox e segredos — `AsaasClient` com httpx async, config com `asaas_api_key`/`asaas_api_url`/`asaas_webhook_token` e variantes `_file` para produção.
- [x] Implementar webhook autenticado, idempotente e com replay — `POST /integrations/asaas/webhook` com dedup via tabela `webhook_events` (provider + external_id unique), header token auth, rate limit 60/min.
- [x] Implementar reconciliação periódica de cobranças — `POST /platform/billing/reconcile` compara status local vs Asaas API, loga discrepâncias, auto_correct opcional.

## P4 — inspeções e obra

- [x] Check suites e inspection suites — CRUD completo com items inline, auditoria, soft delete, tenant isolation.
- [x] Vistorias V2 e migração controlada da V1 — `apartment_inspections` + `apartment_inspection_items` com CRUD e migration de dados de `module_records`.
- [x] Auditorias e relatórios — `audit_reports` + `audit_report_items` com CRUD completo.
- [x] Diário de obra — `work_diaries` + 4 tabelas filhas (activities, teams, equipment, observations) com CRUD completo.

## P5 — corte e banco

- [x] Migrar infra de MySQL para PostgreSQL — Docker Compose com postgres:17-alpine, asyncpg como driver, MySQL mantido com profile `mysql-import` para dump V1.
- [x] Corrigir código MySQL-specific — `LAST_INSERT_ID()` → `RETURNING id`, `NOW()` → `CURRENT_TIMESTAMP`, boolean defaults `"1"`/`"0"` → `"true"`/`"false"`, backticks → double quotes.
- [x] Implementar RLS (Row-Level Security) — policies `tenant_isolation` em 24 tabelas com `company_id`, GUC `app.current_company_id` setado via `SET LOCAL` na dependency `current_user`.
- [x] Re-migrar dados de `module_records` para tabelas dedicadas — migration `0030` move reuniões (72) → `meetings` e relatórios de turno (1165) → `shift_reports`; inspeções (4497) e manutenção (104) permanecem em `module_records` (frontend usa `/modules/{slug}`).
- [x] Criar demo user para Aero Hotel — `demo@aerohotel.local` / `Registro@123` com role `legacy-admin` + permissão wildcard `*`.
- [x] Corrigir permissões do role `legacy-admin` — adicionada permissão `*` para que os endpoints do Registro funcionem (V1 usava códigos `legacy.controller.action`, API nova usa `module.action`).
- [x] Atualizar `import_v1.py` para escrever diretamente nas tabelas dedicadas em futuras importações — `import_meetings` grava em `meetings`/`meeting_participants`/`meeting_subjects` e `import_shift_reports` grava em `shift_reports`.
- [DESCONTINUADO] ~~Executar corte final — puxar dump MySQL atualizado do V1, importar via `import_v1.py`, rodar migrations (incluindo 0030), validar dados.~~ — decisão de 2026-07-04: a migração final do V1 (Laravel) não vai mais acontecer.

## P6 — documentação e governança

- [x] Definir `/docs` como fonte de verdade técnica, funcional, operacional e histórica do Registro.
- [x] Registrar que toda informação pertinente ao desenvolvimento e ao sistema deve ser mantida em `/docs`.
- [x] Corrigir referências atuais que instruíam login por slug; o histórico cronológico preserva menções ao contrato antigo.
- [x] Documentar o módulo de solicitações fiscais em `web-rotas-ui.md`, `domain-model.md` e `api-reference.md` conforme o backend for implementado.
- [x] Documentar o módulo de ocorrências (CRUD, soft delete, `legacy_id` nullable) em `api-reference.md` e `domain-model.md`.
- [x] Atualizar `mapa.md`, contratos, runbooks, memória, backlog e registro de trabalho — atualização de 21/06/2026 corrigiu PostgreSQL como banco ativo, domínios P1/P4 implementados, bloqueios atuais revisados.
- [x] Criar ADR quando uma decisão alterar stack, isolamento, persistência, segurança, deploy, cobrança ou estratégia de migração — ADR-001 (MySQL→PostgreSQL) e ADR-002 (RLS multi-tenant) criados em `docs/adr/`.
- [x] Manter documentação de estado atual separada de funcionalidades apenas planejadas — `docs/mapa.md` separado em seções "Implementado e operacional", "Planejado/pendente de produção" e "Limitações conhecidas".

## Correções de repositório

- [x] Restaurar `.idea/` e `.vscode/` no `.gitignore`.
- [x] Manter `docs/v1/`, dumps SQL, credenciais, secrets e arquivos locais fora do Git — `.gitignore` cobre `docs/v1/`, `*.sql`, `*.sql.gz`, `.env*`, `secrets/`, `backups/`.
- [x] Reforçar `.dockerignore` de api, web e admin — adicionados `docs/`, `*.sql`, `*.dump`, `secrets/`, `.mypy_cache`, `.coverage`, `tests/` para não entrarem nas imagens Docker.

## Próximos passos pendentes (prioridade)

### Alta — bloqueiam corte (DESCONTINUADO — ver nota abaixo)

1. ~~**Atualizar `import_v1.py`**~~ — ✅ reescrito para gravar diretamente em `meetings`, `meeting_participants`, `meeting_subjects` e `shift_reports`.
2. [DESCONTINUADO] ~~**Dump V1 atualizado** — puxar dump MySQL fresco do servidor V1 em produção. O dump local (`aero-2026-06-19.sql`) é snapshot de desenvolvimento.~~
3. [DESCONTINUADO] ~~**Inventário de anexos físicos** — mapear arquivos/volumes fora do banco na V1 (uploads, PDFs, imagens) para migração ao MinIO.~~
4. ~~**Testes de cobertura**~~ — ✅ expandido: 70 testes cobrindo SLA, CRUD, cross-tenant, anexos (9 testes) e auditoria (9 testes).

> **Nota (2026-07-04):** decidido não seguir mais com o corte final do V1 (Laravel/Chess legado de gestão). Os itens 2 e 3 acima, e o item 11 abaixo, ficam descontinuados.

### Média — valor operacional

5. ~~**Integração Evolution (WhatsApp)**~~ — ✅ implementado: `app/integrations/evolution.py` com `send_text`, `send_media`, `check_connection`; endpoints `GET /settings/evolution/status` e `POST /settings/evolution/test`; envio automático via `notify_record_event` para usuários com telefone cadastrado.
6. ~~**Separar estado atual de planejado na documentação**~~ — ✅ `docs/mapa.md` reestruturado com seções explícitas.
7. ~~**Promover módulos genéricos remanescentes**~~ — ✅ manutenção promovida para `maintenance_records` (com priority, location_id) e mural promovido para `bulletin_posts` (com pinned, expires_at, author). Migration de dados inclusa. Endpoints dedicados `/maintenance` e `/bulletin`.
8. ~~**Ata PDF de reuniões**~~ — ✅ endpoint `GET /meetings/{id}/pdf` com participantes, pautas e timeline (reportlab). Padrão idêntico ao PDF de ocorrências.
9. ~~**Higiene dos .dockerignore**~~ — ✅ adicionados `docs/`, `*.sql`, `*.dump`, `secrets/`, `.mypy_cache`, `.coverage` e `tests/` aos .dockerignore de api, web e admin.
10. ~~**Testes dos novos módulos**~~ — ✅ 7 arquivos de teste: work_orders, stock, handoffs, checklists, preventive_plans, maintenance e bulletin. CRUD + isolamento cross-tenant.

### Baixa — preparação futura

11. [DESCONTINUADO] ~~**Corte do Laravel** — procedimento documentado em `docs/migracao-postgresql.md`. Depende dos itens 2-3 acima.~~
12. **Remover profile `mysql-import`** — ✅ avaliado em `docs/infra/avaliacao-remocao-mysql-import.md`: manter por ora (custo baixo, útil para importações pontuais de conferência ao V1); remover quando o V1 for oficialmente descomissionado.

## P6 — evolução operacional

### Alta — valor operacional imediato

1. ~~**Ordens de Serviço (OS) com workflow**~~ — ✅ modelo `work_orders` com fluxo de estados (aberta → em andamento → aguardando material → concluída → validada), atribuição de responsável, SLA, vínculo com ocorrências e manutenção. Migration com RLS e permissões. Endpoints CRUD + transições de estado auditadas + summary. Server actions no frontend.
2. ~~**Kanban visual**~~ — ✅ componente `KanbanBoard` com drag-and-drop HTML5 para transição de status, modal de criação de OS, busca, badges de prioridade, SLA e exclusão. CSS responsivo com estados visuais de drag.

### Média — automação e controle

3. ~~**Manutenção preventiva com agendamento**~~ — ✅ modelo `preventive_plans` com recorrência (daily→annual), geração automática de OS via `POST /preventive-plans/generate`, avanço de `next_due`, CRUD completo com permissões. Frontend em `/preventivas`.
4. ~~**Controle de materiais e estoque operacional**~~ — ✅ modelo `stock_items` + `stock_movements` com entrada/saída/ajuste, vínculo com OS e ocorrências, alerta de estoque mínimo. CRUD completo com permissões `stock.*`. Frontend em `/estoque`.
5. ~~**Checklists operacionais recorrentes**~~ — ✅ templates com itens (`checklist_templates` + `checklist_template_items`), execuções automáticas por agenda (`checklist_executions` + `checklist_execution_items`), toggle individual de itens, conclusão com notas. CRUD completo com permissões. Frontend em `/checklists`.

### Média — visibilidade e comunicação

6. ~~**Dashboard com KPIs operacionais avançados**~~ — ✅ endpoint `/dashboard/metrics` expandido com `kpis`: OS (total, por status/prioridade/categoria, tempo médio resolução, SLA compliance %, atrasadas, semana), ocorrências (por status, taxa conclusão, por setor, atrasadas), fiscais (por status/tipo, SLA compliance %, atrasadas), tendência 7 dias. Frontend com painéis de indicadores, gráficos de barras e tendência semanal.
7. ~~**Comunicação entre turnos aprimorada**~~ — ✅ modelo `shift_handoffs` com pendências direcionadas por turno/data, fluxo pendente → lido → resolvido com timestamps e responsáveis, endpoint `GET /handoffs/pending` para pendências não resolvidas do turno. CRUD completo com permissões `handoff.*`. Frontend em `/pendencias`.

### Baixa — alcance e adoção

8. ~~**App mobile / PWA**~~ — ✅ PWA implementado com manifest, service worker (network-first para navegação, cache-first para assets), ícones SVG, meta tags Apple, safe-area-inset e display standalone.

## P7 — melhorias de engenharia

### Alta — bloqueiam produção

1. ~~**Structured logging com structlog**~~ — ✅ `app/core/logging.py` configura structlog com contextvars (company_id, user_id, request_id). Middleware em `main.py` limpa/vincula contexto por request. `auth.py` vincula company_id/user_id ao autenticar. Todos os 5 módulos que usavam `logging.getLogger` migrados para `structlog.get_logger()`. JSON em produção, console colorido em dev.
2. ~~**Testes de integração contra PostgreSQL real**~~ — ✅ `conftest.py` detecta `DATABASE_URL` ou `TEST_DATABASE_URL` e usa PostgreSQL quando disponível (SQLite como fallback local). Em PostgreSQL, `_current_user_test` seta `SET LOCAL app.current_company_id` para exercitar RLS. CI já roda com PostgreSQL 17 + Alembic migrations. `docker-compose.test.yml` com PostgreSQL tmpfs para testes locais. `aiosqlite` adicionado a dev dependencies.
3. ~~**CI mais robusto**~~ — ✅ CI reforçado: `pip-audit --strict` para CVEs em dependências, cobertura mínima subida para 60%, `alembic heads` para detectar branches divergentes, coverage XML como artifact.

### Média — valor operacional

4. ~~**Cache e performance**~~ — ✅ Redis com cache por tenant no dashboard, cache global de permissões, invalidação nas mutações e readiness.
5. ~~**Background tasks**~~ — ✅ `notify_record_event` refatorado: criação de registros in-app é síncrona (com commit), envio de email (Brevo) e WhatsApp (Evolution) é disparado em background via `asyncio.create_task`. PDF mantido inline (rápido e necessário na resposta). Evolução para Celery/ARQ se necessário.
6. ~~**Exportação em lote**~~ — ✅ utilitário genérico `generate_xlsx()` em `app/core/export.py` (openpyxl, header estilizado, auto-width, limite 10k linhas). Endpoints `GET /export` em ocorrências, manutenção, checklists (execuções) e cadastros. Testes de permissão e validação de xlsx inclusos.
7. ~~**Versionamento da API**~~ — ✅ Routers agrupados em `v1_router` (APIRouter com prefix `/api/v1`) em `main.py`. Estratégia documentada em `docs/api-versionamento.md`: versionamento por prefixo de URL, regras de deprecação, exemplo de coexistência v1/v2.

### Média — qualidade de código

8. ~~**Schemas inline no router**~~ — ✅ `maintenance/schemas.py` e `bulletin/schemas.py` criados. Routers importam de schemas ao invés de definir Pydantic models inline. Consistente com o padrão dos outros domínios.
9. ~~**Tipagem dos retornos de service**~~ — ✅ Todos os 19 services tipados com NamedTuples nomeados (ex: `OccurrenceRow`, `WorkOrderRow`, `HandoffRow`). Retornos de funções anotados com tipos concretos ao invés de `tuple` genérico. Routers continuam funcionando via unpacking posicional.
10. ~~**Testes de permissão**~~ — ✅ `test_permissions.py` com 20 testes cobrindo 4 domínios (occurrences, bulletin, maintenance, checklists). Valida 403 sem permissão, 403 com permissão errada e 200/201 com permissão específica. Suite completa: 147/147 passando.

### Baixa — preparação para escala

11. ~~**Paginação por cursor**~~ — ✅ Utilitário genérico `app/core/pagination.py` com encode/decode de cursor opaco (base64). Endpoints `/cursor` adicionados em ocorrências, OS e timeline como alternativa aos endpoints offset existentes. Response: `{items, next_cursor, has_more}`.
12. ~~**Backup e deploy**~~ — ✅ Service `backup` melhorado com validação `pg_restore --list`. Novo service `backup-minio` com `mc mirror` diário. Script `scripts/backup-restore.sh` para backup/restore manual. Documentação completa em `docs/infra/backup-restore.md` com RTO/RPO, procedimento de restore, checklist pós-restore e estratégia off-site.

## P8 — auditoria de segurança e qualidade (2026-06-22)

Itens identificados na auditoria completa de sistema. Documentação detalhada em `docs/auditoria-2026-06-22.md`.

### Critical — corrigir imediatamente

- [x] **[C1] Fix SQL injection no RLS context** — ✅ `auth.py` já usa binding parametrizado `:cid`.
- [x] **[C2] Remover credenciais hardcoded do admin login** — ✅ removidos `defaultValue` do formulário.
- [x] **[C3] Testes para integração Chess Hotel** — ✅ 22 testes em `test_chess_integration.py`: auth por header, resolução de email, criação de tickets, tracking por protocolo, cross-user isolation.

### High — corrigir em breve

- [x] **[H1] Fix SQL injection no import V1** — ✅ `VALID_TABLES` allowlist com validação antes do `text()`.
- [x] **[H2] Adicionar soft-delete filter em lookups de Role/Sector** — ✅ `Sector.deleted_at.is_(None)` adicionado em `get_sector_name`. Role não tem `deleted_at` (sem soft-delete).
- [x] **[H3] Fix N+1 query em notificações WhatsApp** — ✅ `User.phone` adicionado ao `_resolve_users`, eliminando query individual por recipient.
- [x] **[H4] Padronizar error handling nos routers** — ✅ Global `@app.exception_handler(ValueError)` em `main.py` retorna 422.
- [x] **[H5] Adicionar CSP headers no Next.js** — ✅ CSP, X-Frame-Options, X-Content-Type-Options, Referrer-Policy, Permissions-Policy em `web/next.config.ts` e `admin/next.config.ts`.
- [x] **[H6] Implementar CSRF protection** — ✅ Já coberto: Next.js 16 valida Origin em Server Actions, cookies `SameSite=Lax`, CORS restrito no backend, CSP `form-action 'self'`.
- [x] **[H7] Criar middleware de proteção de rotas** — ✅ `web/middleware.ts` e `admin/middleware.ts` centralizados com redirect para login.
- [x] **[H8] Implementar token refresh no admin** — ✅ `platformFetch()` retry no 401, endpoint `POST /platform/auth/refresh`, cookies de refresh token.
- [x] **[H9] Habilitar access logs em produção** — ✅ `--access-log` no Dockerfile.
- [x] **[H10] Fix rate limiter para X-Forwarded-For** — ✅ `rate_limit.py` lê `X-Forwarded-For` header.
- [x] **[H11] Adicionar approval gate no deploy** — ✅ `environment: production` no job `deploy` do `publish.yml`.
- [x] **[H12] Adicionar testes no frontend** — ✅ vitest configurado em web e admin com testes de login e server actions.

### Medium — planejar correção

- [x] **[M1] Fix race condition em attachments** — ✅ `SELECT ... FOR UPDATE` na contagem de anexos.
- [x] **[M2] Restringir filename sanitization a ASCII** — ✅ Regex `[^a-zA-Z0-9_\s\-\.\(\)]` sem `re.UNICODE`.
- [x] **[M3] Substituir `except Exception` na integração Asaas** — ✅ `except (httpx.HTTPError, AsaasError, KeyError)`.
- [x] **[M4] Documentar padrão de paginação** — ✅ `docs/api-paginacao.md` com regras offset vs cursor, formato de resposta e endpoints suportados.
- [x] **[M5] Gerar Request ID quando ausente** — ✅ `uuid4().hex` gerado quando `X-Request-ID` ausente.
- [x] **[M6] Mover script do Service Worker para arquivo** — ✅ `public/sw-loader.js` criado, `dangerouslySetInnerHTML` removido do layout.
- [x] **[M7] Implementar refresh token rotation** — ✅ O endpoint `/auth/refresh` já emite novo refresh token a cada uso.
- [x] **[M8] Extrair auth logic duplicada** — ✅ `web/lib/auth.ts` com `tryRefreshToken`, `getValidToken`, `setTokenCookies`. `api.ts` e `actions.ts` importam dele.
- [x] **[M9] Validação de tipo nas respostas da API** — ✅ Zod schemas em `web/lib/schemas.ts` com `safeParse` (log + fallback). Validação aplicada em: TenantUser, TokenResponse, Notifications, Timeline, Attachments, RegistryOptions, UserSearch. Tipos inferidos dos schemas via `z.infer`.
- [x] **[M10] Reduzir uso de `"use client"`** — ✅ Avaliado: todos os 10 componentes com `"use client"` usam hooks React legitimamente (useState/useEffect para interatividade, usePathname). Dados já são passados como props de Server Components. Arquitetura está correta.
- [x] **[M11] Validação de arquivo no client antes do upload** — ✅ Tipo e tamanho validados em `fiscal-request-form.tsx` antes do upload.
- [x] **[M12] Acessibilidade** — ✅ ARIA combobox/listbox nos autocompletes, keyboard navigation (↑↓ Enter Escape), `aria-live` nas notificações, tabIndex em itens interativos, focus styling para itens ativos.
- [x] **[M13] Configurar error tracking centralizado** — ✅ `sentry-sdk[fastapi]` adicionado, init condicional por `SENTRY_DSN` env var com traces 10% e profiling. Basta configurar o DSN em produção.
- [x] **[M14] Habilitar persistência no Redis** — ✅ `--appendonly yes --appendfsync everysec` no `docker-stack.yml`.
- [x] **[M15] Avaliar PostgreSQL com failover** — ✅ avaliado em `docs/infra/avaliacao-postgresql-failover.md`: não implementar agora (infra single-node Swarm, ganho real exige multi-node); RPO/RTO atuais (24h/1h) aceitos como meta.
- [x] **[M16] Configurar log rotation no Docker** — ✅ `json-file` driver com `max-size: 10m`, `max-file: 3` em api, web, admin.
- [x] **[M17] Testar procedimento de restore** — ✅ Roteiro detalhado em `docs/infra/teste-restore.md`: procedimento de 6 passos, checklist pós-restore, template de registro mensal, troubleshooting.
- [x] **[M18] Avaliar replicação do MinIO** — ✅ avaliado em `docs/infra/avaliacao-minio-replicacao.md`: não implementar clustering agora; risco real é backup e volume de produção morarem no mesmo host — ação futura de menor esforço seria apontar `mc mirror` para destino externo.

### Low — quando houver oportunidade

- [x] **[L1] Cookie `secure` explícito por ambiente** — ✅ `COOKIE_SECURE` env var com fallback para `NODE_ENV`.
- [x] **[L2] Log de permissão específica para wildcard** — ✅ `logger.debug("permission_check", required=code, granted_via="wildcard")`.
- [x] **[L3] Avaliar i18n** — ✅ avaliado em `docs/avaliacao-i18n.md`: não implementar agora, sem sinal de demanda real por outro idioma; reabrir quando houver tenant/mercado concreto exigindo.
- [x] **[L4] Configurar image optimization no Next.js** — ✅ `formats: ["image/avif", "image/webp"]` em `next.config.ts`.
- [x] **[L5] Revisar filtros do Alembic env.py** — ✅ Revisado: filtro de index/FK mantido pois naming diverge entre models e migrations legacy (indexes compostos vs single-column). Adicionado filtro de column attributes. Drift real (tabelas/colunas novas ou removidas) continua reportado.
- [x] **[L6] Padronizar error response** — ✅ Padrão `{"code": "...", "message": "..."}` já consistente nos routers.

### Testes — gaps de cobertura

- [x] **[T1] Testes para domínio occurrences** — ✅ 19 testes em `test_occurrences.py`: CRUD, clone, cross-tenant, permissões.
- [x] **[T2] Testes para domínio users** — ✅ 15 testes em `test_users.py`: CRUD, perfil, cross-tenant.
- [x] **[T3] Testes para domínio dashboard** — ✅ 4 testes em `test_dashboard.py` (requerem PostgreSQL).
- [x] **[T4] Testes para domínio notifications** — ✅ 13 testes em `test_notifications.py`: listagem, marcação, preferências, cross-tenant.
- [x] **[T5] Testes para domínios restantes** — ✅ meetings (18), shift_reports (16), roles (14, requerem PostgreSQL), procedures (14).
- [x] **[T6] Testes unitários de service layer** — ✅ 45 testes em `test_storage_service.py`, `test_security.py` (novos), `test_audit.py` (novos): validate_file, magic bytes, token encode/decode, compute_diff edge cases.
- [x] **[T7] Testes de negative path** — ✅ 55 testes em `test_negative_paths.py`: auth (12), occurrences (12), fiscal_requests (11), users (12), attachments (8), work_orders (11), general (5). Cobrem 422, 404, 401, 403, validação e edge cases.

## P9 — auditoria do domínio employees/timeclock/escalas (2026-07-04)

Itens identificados no levantamento do WIP não commitado de `employees`, `timeclock` e escalas.

### Critical — corrigido

- [x] **[E1] Índice duplicado em `Employee.status`** — ✅ `index=True` redundante removido da coluna; colidia com `ix_employees_status` (composto) e derrubava a criação de tabelas em toda a suíte de testes (482 testes afetados).
- [x] **[E2] Backfill incorreto de `employee_id` na migration 0044** — ✅ `upgrade()`/`downgrade()` reescritos para resolver `employee_id` via `JOIN` em `employees.user_id` (+ `company_id`), em vez de copiar `user_id` direto assumindo `employees.id == users.id`.

### Alta — corrigido

- [x] **[E3] `external-ids` sem schema Pydantic** — ✅ `EmployeeExternalIdCreate` criado e usado no router; payload inválido agora retorna 422.
- [x] **[E4] Falha de isolamento em `delete_employee_external_id`** — ✅ service e router agora exigem `employee_id` também no delete; deletar external-id de outro funcionário retorna 404.
- [x] **[E5] Auditoria ausente em `EmployeeExternalId`** — ✅ create/delete geram `AuditEvent` (`entity_type="employee_external_id"`), igual ao restante do domínio.

### Média — corrigido

- [x] **[E6] `status` do Employee sem enum/Literal** — ✅ `Literal["active", "inactive", "terminated"]` em `EmployeeCreate`/`EmployeeUpdate`, alinhado com `STATUS_LABELS` do frontend.
- [x] **[E7] Sem validação de formato para `cpf`/`birth_date`/`address_zip`** — ✅ CPF valida dígito verificador (reaproveitando `app.core.validators`) e normaliza para 11 dígitos; `birth_date` valida `YYYY-MM-DD`; `address_zip` valida CEP de 8 dígitos e normaliza para `XXXXX-XXX`. CPF agora é **obrigatório** em `EmployeeCreate` (backend) e no formulário (frontend), com as mesmas validações replicadas no cliente (`web/lib/validators.ts`) e busca automática de endereço por CEP via ViaCEP (server action `lookupCepAction`).
- [x] **[E8] Testes faltando** — ✅ adicionados: payload malformado em `external-ids` (422), delete cross-employee (cobre E4, 404), paginação com `page_size` acima do limite (422).
- [x] **[E9] `fetchEmployees`/`fetchEmployee` sem validação Zod** — ✅ `EmployeeSummarySchema`/`EmployeeDetailedSchema` criados em `web/lib/schemas.ts`; `Employee`/`EmployeeDetailed` agora são `z.infer` desses schemas e `fetchEmployees`/`fetchEmployee` usam `safeParse`, igual a `searchEmployees`.

### Baixa — implementado em 2026-07-04

- [x] **[E10] Cargo/admissão/matrícula** no cadastro de funcionário — ✅ `job_title`, `hire_date`, `termination_date`, `registration_number` (migration `20260704_0046`), com as mesmas validações de formato de data já usadas em `birth_date`. Salário/dados bancários ficaram fora de propósito (dados sensíveis, tratamento à parte).
- [x] **[E11] Setor/departamento** vinculado ao funcionário — ✅ `sector_id` reaproveitando o cadastro de Setor já usado por `User` (`registries` categoria `"Setor"`), sem duplicar conceito. `EmployeeDetailedSummary.sector_name` traz o nome resolvido.
- [x] **[E12] Upload de avatar** — ✅ `POST /employees/{id}/avatar`, mesmo fluxo de `POST /users/{id}/avatar` (MinIO/S3, validação de assinatura de arquivo).
- [x] **[E13] Histórico de mudança de status** — ✅ `"employee"` registrado em `VALID_ENTITY_TYPES`/`ENTITY_MODEL_MAP` do domínio de timeline; `GET /timeline/employee/{id}` já funciona reaproveitando os `AuditEvent`s existentes, sem tabela de histórico dedicada.
- [x] **[E14] Importação em lote** de funcionários — ✅ `POST /employees/import`, CSV validado linha a linha com o mesmo schema `EmployeeCreate` do cadastro manual; uma linha inválida não interrompe as demais, resposta traz resultado por linha.

## P10 — Portal do Colaborador e agente Go de ponto (2026-07-04)

- [x] **[PC1] Backend do Portal do Colaborador** — ✅ token `employee_session` isolado do login de `User`, login por PIN com lockout, geofencing por Haversine, escala e contracheque. 14 testes dedicados em `test_timeclock_mobile.py`, 517 testes totais passando. Ver [portal-colaborador.md](portal-colaborador.md).
- [x] **[PC2] Frontend PWA `colaborador/`** — ✅ app Next.js independente (porta 3002), login/troca de PIN, ponto com geolocalização, escala, contracheque. Typecheck e build limpos.
- [x] **[PC3] Agente Go de ponte local (`agent/`)** — ✅ cliente REST Control iD, sync com fila de retry offline, UI local de configuração, systray best-effort. Build/vet/test passando.
- [x] **[PC4] Catálogo de relógios de ponto** — ✅ [relogios-de-ponto-catalogo.md](relogios-de-ponto-catalogo.md), priorizando Control iD (já suportado no backend).
- [x] **[PC5] Deploy do `colaborador/` no Swarm de produção** — ✅ serviço `colaborador` adicionado ao `docker-stack.yml` (imagem GHCR, Traefik em `REGISTRO_COLABORADOR_HOST`, porta 3002); publicação e deploy automatizados em `publish.yml` (build+push+rollout); runbooks `deploy-swarm.md` e `deploy-novo-dominio.md` atualizados com o quarto host/serviço.
- [x] **[PC6] Cadastro de `Location` com lat/lng e de `EmployeeCredential` via UI administrativa** — ✅ `PATCH/POST/GET /registries` agora aceita e retorna `latitude`/`longitude`/`geofence_radius_m` quando `category=Local` (auditado via `AuditEvent`, ignorado para Setor/Função); tela `/cadastros/locais` ganhou campos de latitude, longitude e raio de geofencing no formulário. Tela de funcionários (`/cadastros/funcionarios`) ganhou botão "Resetar PIN" (permissão `timeclock.manage`) que chama `POST /timeclock/employees/{id}/pin/reset` e exibe o novo PIN uma única vez. 2 testes novos em `test_registries.py`.
- [ ] **[PC7] Validação em hardware real** — o payload de push do Control iD (webhook) e o formato de resposta da API REST local (usado pelo agente Go) não foram validados contra um equipamento físico; parsing é deliberadamente tolerante, mas pode exigir ajuste fino.
- [x] **[PC8] Importação em lote de contracheque** — ✅ como não há ERP de folha fixo entre os clientes (folha terceirizada, cada um usa o sistema do próprio contador), a solução é agnóstica de ERP: `POST /timeclock/employees/payslips/import` recebe um ZIP de PDFs + manifesto CSV e casa cada arquivo a um funcionário por CPF (fallback matrícula), reimportando a mesma competência como atualização em vez de erro. UI em `/ponto/contracheques`. 7 testes novos em `test_payslip_import.py`. `EmployeeExternalId.system` já deixa o caminho aberto para um adapter de API real (ex. TOTVS) no futuro, sem código especulativo agora. Ver [portal-colaborador.md](portal-colaborador.md#importação-de-contracheque-em-lote-2026-07-05).
- [x] **[PC9] Turnos padrão por tenant** — ✅ `ensure_default_shifts()` cadastra 6 turnos padrão (Manhã, Tarde, Noite, Comercial, 12x36 Diurno/Noturno) em toda empresa nova (`create_tenant`); `api/app/backfill_default_shifts.py` aplica retroativamente aos tenants existentes. Ver [escala-de-trabalho.md](escala-de-trabalho.md).
- [x] **[PC10] Usuários e Perfis de acesso movidos para Configurações** — ✅ `/usuarios` e `/perfis` viraram abas dentro de `/configuracoes`, reaproveitando `OperationalModule`/`RoleManager`; removidos do submenu "Cadastros" da sidebar. `/perfis` mantém redirect para compatibilidade com links antigos.
- [x] **[PC11] Banco de horas** — ✅ modelo `HourBankEntry`, cálculo diário (escala x pontos batidos) via `POST /timeclock/hour-bank/{id}/recalculate`, saldo inicial migrável via `POST /timeclock/hour-bank/{id}/initial-balance`, consulta em `GET /timeclock/hour-bank/{id}` (RH) e `GET /timeclock/mobile/hour-bank` (funcionário). Frontend `/ponto/banco-de-horas` e aba "Banco" no `colaborador/`. 5 testes em `test_hour_bank.py`. Ver [escala-de-trabalho.md](escala-de-trabalho.md#banco-de-horas-e-ajuste-de-ponto-2026-07-05).
- [x] **[PC12] Ajuste de ponto com aprovação** — ✅ modelo `PunchAdjustmentRequest`: funcionário solicita correção de batida existente ou lançamento de batida esquecida pelo Portal do Colaborador (`POST /timeclock/mobile/adjustments`); RH aprova/rejeita em `/ponto/ajustes` (`POST /timeclock/adjustments/{id}/review`), reaproveitando `update_punch`/`create_manual_punch`; notificação in-app para gestores com permissão `punch_adjustment.manage`. 8 testes em `test_punch_adjustments.py`.

## Implantação em produção (2026-07-05) — concluída manualmente (CI indisponível)

`git push origin main` foi feito, mas o GitHub Actions do repositório estava com "account
locked due to a billing issue" (falha em 5s no job `Publish images`, sem sequer iniciar o
build) — a conta do GitHub está com problema de cobrança, não é um bug no workflow. Diante
disso, o build e o deploy foram feitos manualmente, sem depender do CI:

1. **Build local + push manual pro GHCR** — as 4 imagens (`api`, `web`, `admin`, `colaborador`)
   buildadas localmente (`docker build --target production`) e enviadas para
   `ghcr.io/icarosimoes/registro/*:sha-6f2677d5df1a1e9cb9adce1756bd757e2a50c75b` via
   `docker login ghcr.io` com token do `gh auth token` (escopo `write:packages` já habilitado).
2. **Backup manual do Postgres antes de tocar no banco** — `pg_dump -Fc` disparado dentro do
   container `registro_backup` (mesmo comando do cron diário), validado com `pg_restore --list`
   antes de prosseguir.
3. **Primeiro deploy do serviço `colaborador`** — `docker-stack.yml` atualizado copiado para
   `/opt/registro/` (não é um checkout git, arquivo solto); `REGISTRO_COLABORADOR_HOST` e
   `IMAGE_TAG` adicionados/atualizados em `/opt/registro/.env.prod` (backup do arquivo anterior
   mantido ao lado); `docker stack deploy -c docker-stack.yml --with-registry-auth registro`
   criou `registro_colaborador` e `registro_backup-minio` (este já estava no compose de uma
   entrega anterior mas nunca tinha sido aplicado) e atualizou os demais serviços.
4. **Migrations 0047 e 0048** — Swarm roda em 2 nós; os containers do `registro_api` estavam no
   nó worker, não no manager onde a sessão SSH estava — `docker exec` direto não alcança
   container em outro nó. Aplicado via o procedimento documentado em
   [deploy-swarm.md](infra/deploy-swarm.md#migrations-no-swarm): rede overlay temporária +
   `docker run` com a imagem nova da API conectado ao container do `db` (que roda no manager),
   `alembic upgrade head`. Confirmado `SELECT version_num FROM alembic_version` = `20260705_0048`.
5. **Validação pós-deploy** — `docker service ls` com todos os 8 serviços `registro_*` em
   `N/N` saudável; `curl` 200 em `api.registro.solidsd.com.br/api/v1/health`; `web`/`admin`
   respondendo 307 (redirect de login, esperado sem sessão); logs do `registro_colaborador`
   ("Ready") e do `registro_api` (rolling update limpo, sem erro).
6. **DNS de `colaborador.registro.solidsd.com.br`** — ✅ resolvido pelo usuário; `curl
   https://colaborador.registro.solidsd.com.br/login` responde `200` com certificado Let's
   Encrypt válido via Traefik. Portal do Colaborador acessível publicamente.
7. **PC7 continua bloqueado** — validação em hardware físico do Control iD só é possível depois
   do agente Go estar rodando contra um relógio real; não é pré-requisito deste deploy.

## P11 — Relatórios, abono de ponto e Espelho de Ponto (2026-07-06)

- [x] **[P11.1] Relatórios de ocorrências e SLA fiscal** — ✅ `GET /reports/occurrences` e `GET /reports/fiscal-requests-sla` (`report.view`), frontend `/relatorios`. Sem exportação nesta entrega.
- [x] **[P11.2] Ajustes de ponto redesenhado + abono** — ✅ abas, painel de estatísticas com ranking de solicitantes, drawers "Ajustar Ponto"/"Abonar Ponto". Abono (`PunchExcusal`) neutraliza o banco de horas sem aprovação (quem cria já é o aprovador). Bug de isolamento entre tenants encontrado e corrigido (`employee_id` de outra empresa era aceito). Ver [escala-de-trabalho.md](escala-de-trabalho.md#abono-de-ponto-espelho-de-ponto-e-notificações-2026-07-06).
- [x] **[P11.3] Notificações conectadas ao sino** — ✅ abono notifica gestores (exceto autor); clique em notificação de ajuste/abono navega para `/ponto/ajustes` (primeiro mapeamento `entity_type` → rota no `notification-panel.tsx`).
- [x] **[P11.4] Espelho de Ponto** — ✅ grade diária (batidas, crédito/débito, HE 50%/100%, adicional noturno, saldo) + export Excel/PDF, `/ponto/espelho`. Primeiro proxy de download via Route Handler Next.js do projeto.
- [ ] **[P11.5] Banco de teste isolado** — a suíte roda contra o banco de desenvolvimento (sem `TEST_DATABASE_URL`), acumulando dados a cada execução; colide com o seed fictício de ponto em `test_hour_bank.py::test_recalculate_hour_bank_matches_exact_shift` (data hardcoded `2026-07-06`). Configurar banco de teste isolado ou revisar datas hardcoded.
- [ ] **[P11.6] Cobertura de teste automatizado** — abono, espelho e notificações foram verificados manualmente (curl + navegador), sem testes `pytest` novos.
- [x] **[P11.7] Calendário de feriados no cálculo de HE 100%** — ✅ `Holiday` (`holidays`, migration `20260706_0051`), CRUD em `/ponto/feriados` (`holiday.view`/`holiday.manage`). Feriado cadastrado entra em `is_rest_day` no espelho, junto com domingo/folga agendada. Cadastro 100% manual por tenant (sem integração com base nacional). Ver [escala-de-trabalho.md](escala-de-trabalho.md#feriados-2026-07-06).
- [x] **[P11.8] "Hora noturna reduzida" (52min30s) da CLT** — ✅ `mirror.py` agora aplica `NIGHT_COMBINED_RATE` (redução da hora noturna + adicional de 20%, ≈34,29% combinado) sobre os minutos noturnos reais, em vez de só 20%. Testado em `test_mirror_night_differential_uses_reduced_hour`.
- [x] **[P11.9] Filtro por Equipe/Departamento no Espelho de Ponto** — ✅ reaproveita `Sector` (não criou conceito novo de "Equipe"): `GET /timeclock/mirror/by-sector` + seletor "Filtrar por: Funcionário/Setor" em `/ponto/espelho`, renderizando um card por funcionário ativo do setor. Exportação Excel/PDF em lote por setor ficou fora de escopo (só por funcionário individual).
- [ ] **[P11.10] Exportação AFDT/ACJEF/AFD (Portaria 671/MTE)** — formatos regulatórios binários/assinados digitalmente, fora do escopo desta entrega (só Excel/PDF).
- [x] **[P11.11] Padronização visual dos formulários de filtro (módulo Ponto)** — ✅ padrão `.report-filter-field`/`.report-filter-group` documentado em [web-rotas-ui.md](web-rotas-ui.md#padrão-de-campo-e-filtro-report-filter-field) e aplicado em todas as telas de `/ponto`; corrigidos dois bugs reais (botão invisível por especificidade CSS em `.module-toolbar`, `input[type=date]` quebrando linha sozinho). Obrigatório em telas novas.
- [ ] **[P11.12] Confirmar estilo do seletor de arquivo em browser real** — `::file-selector-button` (usado em Contracheques) foi validado só via `getComputedStyle`; o Chromium headless shell da skill `run-web` não pinta o pseudo-elemento. Conferir visualmente em Chrome/Edge na próxima vez que a tela for tocada.
- [x] **[P11.13] Hora extra paga em dinheiro (salário individual ou por cargo)** — ✅ `Employee.salary` (migration `20260707_0052`) + salário-base por cargo (`cargo_salaries`, fallback quando o funcionário não tem salário individual) + toggle `overtime_paid_in_cash` em `/configuracoes` → Ponto. Valor em R$ (`overtime_50_value`/`overtime_100_value`) calculado a partir da jornada mensal esperada do funcionário, exibido no espelho de ponto. Quando ligado e há salário resolvível, `recalculate_hour_bank` para de bancar a HE (só o déficit continua virando banco de horas). 5 testes novos (`test_overtime_pay.py`). Ver [escala-de-trabalho.md](escala-de-trabalho.md#hora-extra-paga-em-dinheiro-2026-07-06).

## Definition of Done por módulo

Contrato, autorização, isolamento por empresa, estados de UI, CRUD necessário, anexos/exportações, testes, comparação de dados, observabilidade, documentação e rollback precisam estar aprovados antes do corte. Uma entrega não está concluída se a documentação pertinente em `/docs` estiver ausente ou desatualizada.
