# Registro de trabalho

## 2026-06-22 — Sprint 1 de segurança e screenshots Chess Hotel

### Correções de segurança (Sprint 1)

- **SQL injection no RLS context** (`api/app/core/auth.py:31`): substituída f-string interpolation por query parametrizada (`text("SET LOCAL ... = :cid"), {"cid": str(cid)}`).
- **Credenciais hardcoded no admin login** (`admin/app/(auth)/login/page.tsx`): removidos `defaultValue` com email e senha do formulário. Substituídos por `placeholder` genérico e texto informativo.
- **Access logs em produção** (`api/Dockerfile:35`): trocado `--no-access-log` por `--access-log` no CMD de produção para permitir auditoria de requests HTTP.
- **Rate limiter atrás de proxy** (`api/app/core/rate_limit.py`): substituído `get_remote_address` do slowapi por função customizada `_get_client_ip` que lê `X-Forwarded-For`. Adicionado `ProxyHeadersMiddleware` do uvicorn em `api/app/main.py` para resolver IP real do Traefik.

### Screenshots na integração Chess Hotel

- Adicionado campo `screenshots` (array de strings base64) ao schema `FiscalRequestCreate` com limite de 5 imagens.
- No router, após criar o chamado, cada screenshot é decodificado, formato detectado por magic bytes (PNG/JPEG/WebP), e salvo como attachment no MinIO via `create_attachment` existente.
- Screenshots inválidos são logados e ignorados — não bloqueiam a criação do chamado.
- Campo `attachments_count` adicionado à resposta `FiscalRequestCreated`.
- Screenshots excluídos do payload JSON (não armazena base64 no banco).
- Documentação `chess-hotel-api.md` atualizada com seção Screenshots, campo na tabela e exemplo com base64.

### Postman Collection

- Gerado `docs/integracoes/chess-hotel-api.postman_collection.json` com todos os 4 endpoints da integração Chess Hotel.
- Variáveis de collection: `base_url`, `integration_key`, `hotel_slug`.
- Autenticação por API Key (`X-Registro-Key`) configurada na collection.
- Exemplos de request e response (sucesso e erros) em cada endpoint.
- Request "2b" dedicado mostrando exemplo com screenshot base64.

## 2026-06-22 — CI/CD, cobertura e deploy automático

### CI — pip-audit e cobertura

- `pip-audit --strict` falhava porque `registro-api` não existe no PyPI. Corrigido gerando `requirements.txt` via `pip freeze --exclude registro-api` e auditando com `-r`.
- Cobertura estava em 54% (threshold 60%). Excluídos `import_v1.py`, `seed.py` e geradores PDF da cobertura. Adicionados 46 testes para `validators`, `pagination` e `cache`. Cobertura final: 60.19%.
- Atualizadas dependências com CVEs: `cryptography` 46→48.0.1 (GHSA-537c-gmf6-5ccf), `pytest` 8→9.0.3 (CVE-2025-71176), `pytest-asyncio` 0.24→1.4.
- Aplicado `ruff format` em 8 arquivos de service.

### Frontend

- Dockerfile do web não copiava `public/` no estágio de produção (modo standalone do Next.js). Adicionado `COPY ... /app/public`. Corrige 404 em `manifest.json` e `sw.js` (PWA não funcionava no mobile).
- Hydration mismatch no dashboard (React error #418): `formatRelativeTime` usava `Date.now()` que diverge entre server e client. Adiado para após montagem no client.

### Deploy automático

- Workflow `publish.yml` agora inclui job `deploy` que conecta via SSH na VPS e atualiza os serviços no Swarm após publicação das imagens.
- Secrets `VPS_SSH_KEY` e `VPS_HOST` configurados no repositório GitHub.
- `api/build/` adicionado ao `.gitignore` (artefatos de `pip install` não-editável).

## 2026-06-22 — Host dedicado para API

- Rota pública da API movida para `api.registro.solidsd.com.br`.
- Front e painel continuam consumindo `http://api:8000/api/v1` internamente no overlay do Swarm.
- DNS aponta diretamente para a VPS e o TLS é emitido pelo resolver `letsencrypt` do Traefik.
- Criado `infra/deploy-novo-dominio.md` com procedimento reproduzível, validações e troubleshooting baseado nas falhas reais do primeiro deploy.
- Corrigido no guia principal o exemplo de secrets do PostgreSQL: senha e URL precisam derivar da mesma variável aleatória.

## 2026-06-22 — Preparação do deploy Swarm

- Definidos os hosts `registro.solidsd.com.br` e `painel.registro.solidsd.com.br`.
- A API passou a ser publicada no host do produto sob `/api/v1`, sem terceiro DNS.
- Stack de produção completada com PostgreSQL 17, Redis e MinIO persistentes, fixados no manager.
- Adicionado backup diário do PostgreSQL, com checksum e retenção local de 14 dias.
- Credenciais de PostgreSQL, MinIO, JWT e integração Chess são fornecidas por Docker Secrets.
- Configuração S3 da API passou a aceitar credenciais por arquivos de secret.
- Redis documentado como implementado para dashboard, permissões e readiness.
- Criado workflow de publicação das três imagens no GHCR com tags imutáveis por SHA.
- Corrigida a página `/definir-senha` para renderizar `useSearchParams` sob `Suspense`, permitindo o build de produção do Next.js.
- `httpx` movido para as dependências de runtime da API, pois integrações Brevo, Evolution e Asaas o importam na imagem de produção.
- Seed inicial corrigido para reutilizar permissões criadas pelas migrations, mantendo execução idempotente em PostgreSQL novo.
- Routers do Registro alinhados ao certificate resolver `letsencrypt` configurado no Traefik compartilhado da VPS.

### Deploy concluído

- Stack `registro` publicada no Swarm com API 2 réplicas, web 2, admin 1, PostgreSQL 1, Redis 1, MinIO 1 e backup 1.
- Migrations Alembic aplicadas até `20260621_0039` por tarefa única e removível.
- Seed inicial executado; credenciais aleatórias ficaram somente em `/opt/registro/initial-credentials.txt`, modo `0600`.
- Front e API publicados em `https://registro.solidsd.com.br`; painel em `https://painel.registro.solidsd.com.br`.
- Registro DNS do painel colocado em DNS-only porque o certificado Universal do Cloudflare não cobre subdomínio de segundo nível; o origin usa certificado Let’s Encrypt válido.
- Validado: health, readiness com banco/cache conectados, TLS, frontend, painel, login tenant, login platform e checksum do primeiro backup.
- Workflow de imagens limitado a mudanças em `api/`, `web/`, `admin/` ou no próprio workflow, evitando rebuild em commits apenas documentais.

## 2026-06-21 — Controle de Estoque e Pendências de Turno

### Controle de materiais e estoque

- Modelos `StockItem` + `StockMovement` em `operations.py`.
- `StockItem`: name, category, unit, min_quantity, current_quantity, location_id. Soft delete.
- `StockMovement`: item_id, movement_type (entrada/saída/ajuste), quantity, reason, vínculo opcional com work_order_id e occurrence_id.
- Domínio `domain/stock/` com router, schemas e service — CRUD de itens + movimentações com validação de estoque.
- Saída valida estoque suficiente, ajuste define saldo absoluto, entrada soma ao saldo.
- Filtro `below_min=true` para alertas de reposição.
- Migration `0037_stock_handoff` com tabelas e 4 permissões `stock.*`.
- Server actions: `createStockItemAction`, `updateStockItemAction`, `deleteStockItemAction`, `createStockMovementAction`.
- Navegação: item "Estoque" na sidebar com ícone Package, módulo `/estoque`.

### Pendências de turno (Handoff)

- Modelo `ShiftHandoff` com fluxo pendente → lido → resolvido.
- Campos: title, description, priority (normal/alta/urgente), category, target_shift (morning/afternoon/night), target_date, shift_report_id (vínculo opcional).
- Confirmação de leitura: `read_at`, `read_by_user_id`. Resolução: `resolved_at`, `resolved_by_user_id`, `resolution_notes`.
- Domínio `domain/handoffs/` com router, schemas e service — CRUD + read + resolve + pending.
- `GET /handoffs/pending` retorna pendências não resolvidas para data/turno (inclui atrasadas de dias anteriores).
- 4 permissões `handoff.*`.
- Server actions: `createHandoffAction`, `updateHandoffAction`, `markHandoffReadAction`, `resolveHandoffAction`, `deleteHandoffAction`.
- Navegação: item "Pendências turno" na sidebar com ícone ArrowRightLeft, módulo `/pendencias`.

## 2026-06-21 — Dashboard KPIs, Manutenção Preventiva e Checklists Recorrentes

### Dashboard com KPIs avançados

- Endpoint `/dashboard/metrics` expandido com campo `kpis` contendo indicadores detalhados.
- **Ordens de Serviço**: total, distribuição por status/prioridade/categoria, tempo médio de resolução, SLA compliance %, OS atrasadas, criadas/concluídas na semana.
- **Ocorrências**: distribuição por status, taxa de conclusão mensal, distribuição por setor (top 8), atrasadas por deadline.
- **Solicitações Fiscais**: distribuição por status/tipo (top 8), SLA compliance %, atrasadas.
- **Tendência 7 dias**: contagem diária de OS, ocorrências e fiscais.
- Frontend: seção "Indicadores detalhados" com 3 painéis (grid responsivo), gráficos de barras por distribuição, gráfico de tendência semanal com 3 séries. Sidebar expandido com OS ativas e da semana.

### Manutenção preventiva

- Modelo `PreventivePlan` em `operations.py` com recorrência (daily/weekly/biweekly/monthly/quarterly/semiannual/annual), categoria, prioridade, SLA, localização, responsável, `next_due`, `last_generated_at`.
- Domínio `domain/preventive_plans/` com router, schemas e service — CRUD completo.
- Endpoint `POST /preventive-plans/generate` gera OS automaticamente para planos vencidos, com título `[Preventiva] {nome}`, avança `next_due` conforme recorrência.
- Migration `0036_preventive_checklists` com tabelas e 4 permissões `preventive_plan.*`.
- Server actions no frontend: `createPreventivePlanAction`, `updatePreventivePlanAction`, `deletePreventivePlanAction`, `generatePreventiveOrdersAction`.
- Navegação: item "Preventivas" na sidebar com ícone Timer, módulo `/preventivas` listando planos da API.

### Checklists recorrentes

- Modelos: `ChecklistTemplate` + `ChecklistTemplateItem` (templates com itens ordenados), `ChecklistExecution` + `ChecklistExecutionItem` (instâncias com check individual e conclusão).
- Domínio `domain/checklists/` com router, schemas e service — templates CRUD + execuções com toggle/complete.
- Endpoint `POST /checklists/generate` gera execuções para templates vencidos, copiando itens do template, avançando `next_due`.
- 4 permissões `checklist.*` atribuídas ao role admin.
- Server actions: `createChecklistTemplateAction`, `updateChecklistTemplateAction`, `deleteChecklistTemplateAction`, `toggleChecklistItemAction`, `completeChecklistAction`, `generateChecklistExecutionsAction`.
- Navegação: item "Checklists" na sidebar com ícone CalendarCheck, módulo `/checklists` listando templates da API.

## 2026-06-21 — Ordens de Serviço, Kanban e PWA

### Ordens de Serviço (work_orders)

- Modelo `WorkOrder` com fluxo de estados (aberta → em andamento → aguardando material → concluída → validada).
- Migration `0035_work_orders` com tabela, RLS (`tenant_isolation`) e 4 permissões (`work_order.view/create/edit/delete`).
- Domínio `domain/work_orders/` com router, schemas e service — CRUD completo com transições de estado auditadas.
- Atribuição de responsável, SLA calculado no servidor, vínculo com ocorrências e manutenção.
- Endpoint `GET /work-orders/summary` com contagem por status e mapa de transições permitidas.
- Server actions no frontend: `createWorkOrderAction`, `updateWorkOrderAction`, `transitionWorkOrderAction`, `deleteWorkOrderAction`.

### Kanban visual

- Componente `kanban-board.tsx` com drag-and-drop HTML5 para transição de status entre colunas.
- Modal de criação de OS com título, descrição, prioridade (urgente/alta/média/baixa), categoria e SLA em horas.
- Exclusão de OS direto no card com confirmação.
- Feedback visual: card arrastado com opacidade, coluna-alvo com outline azul, toast de erro para transições inválidas, loading indicator fixo.
- Badges de prioridade coloridos e exibição de SLA no card.
- CSS responsivo: no mobile as colunas empilham verticalmente.

### PWA (Progressive Web App)

- `manifest.json` com nome, tema e ícones.
- Service worker (`sw.js`) com network-first para navegação e cache-first para assets.
- Ícones SVG gerados via `scripts/generate-icons.mjs`.
- Meta tags Apple, safe-area-inset e display standalone no layout.

### Backlog P6 — evolução operacional

Adicionada seção de evolução operacional ao backlog com roadmap de funcionalidades:
- Alta: Ordens de Serviço com workflow (implementado), Kanban visual (implementado).
- Média: manutenção preventiva, controle de materiais, checklists recorrentes, KPIs avançados, handoff entre turnos.
- Baixa: PWA (implementado).

## 2026-06-21 — Import V1 reescrito, Evolution WhatsApp, testes e relatórios de turno completos

### import_v1.py reescrito para tabelas dedicadas

- Reuniões: grava diretamente em `meetings` + `meeting_participants` + `meeting_subjects` (antes escrevia em `module_records`).
- Relatórios de turno: grava diretamente em `shift_reports` com campos estruturados (antes escrevia em `module_records`).
- Participantes convidados e registrados mapeados para `meeting_participants`.
- Pautas (subjects + new_subjects) unificadas em `meeting_subjects`.
- Meetings e ShiftReport agora incluem `LegacyEntityMixin` (campo `legacy_id`).

### Relatórios de turno — campos completos do V1

20 colunas adicionadas à tabela `shift_reports` para reproduzir o formulário completo do V1:
- **Indicadores**: `supervisor`, `occupation`, `average_daily`, `guests`, `uhs`, `maintenance_count`, `cleaning`, `walk_in`, `input_quantity`, `output_quantity`, `return_of_customers`.
- **Notas por setor**: `observations`, `notes_ab`, `notes_reception`, `notes_reservations`, `notes_governance`, `notes_maintenance`, `notes_ti`, `notes_security`.
- **Payload JSON**: frequências, manutenções, reclamações, extras e comentários do turno.
- Migration 0034 cria as colunas e migra dados do payload legado em `module_records` para os novos campos via match por título.
- Frontend: formulário de edição com seções "Indicadores" e "Observações por setor", fetch de detalhe ao abrir modal.
- Schema `ShiftReportDetail` com todos os campos no endpoint `GET /shift-reports/{id}`.

### Integração Evolution (WhatsApp) — envio real

- Módulo `app/integrations/evolution.py` com `send_text`, `send_media` e `check_connection`.
- Endpoint `GET /settings/evolution/status` — verifica conexão com a instância.
- Endpoint `POST /settings/evolution/test` — envia mensagem de teste.
- `notify_record_event` envia WhatsApp via Evolution para destinatários com telefone cadastrado.

### Tabelas dedicadas para manutenção e mural

- Modelo `MaintenanceRecord` (`maintenance_records`) com prioridade, location e payload — tabela nova e vazia, para ordens de manutenção reais.
- Modelo `BulletinPost` (`bulletin_posts`) com pinned, expires_at e autor — mural de avisos.
- Domínios `domain/maintenance/` e `domain/bulletin/` com CRUD completo e endpoints dedicados.
- Auditorias noturnas (104 registros) permanecem em `module_records` — são dados legados, não manutenção.

### Testes — de 52 para 70

- 9 testes de anexos: upload, validação de tipo/extensão, cross-tenant, limite por registro, delete.
- 9 testes de auditoria: record_event (create/update/delete/attachment_add), compute_diff, isolamento por tenant.
- Fix do conftest: bypass do RLS `SET app.current_company_id` para SQLite, `current_user` override sem DB lookup, token com permissão wildcard `*`.
- Desbloqueou 11 testes pre-existentes (fiscal_requests e cross_tenant_crud) que falhavam por incompatibilidade SQLite/RLS.

### Documentação — estado atual vs planejado

- `docs/mapa.md` reestruturado com seções "Implementado e operacional", "Planejado/pendente de produção" e "Limitações conhecidas".
- `docs/backlog.md` atualizado com itens concluídos (import_v1, testes, Evolution, documentação, módulos genéricos).

### Dashboard

- Query UNION ALL inclui `maintenance_records` (vazia) e `module_records` com `module='manutencao'` (auditorias noturnas).

## 2026-06-21 — Dashboard multi-módulo

O endpoint `/dashboard/metrics` foi reescrito para agregar atividades recentes de **todos os módulos operacionais** em vez de apenas ocorrências:

- **Módulos incluídos**: Ocorrências (5), Reuniões (5), Relatórios de turno (5), Inspeções (3), Manutenção (3), Solicitações Fiscais (5 quando houver).
- **Implementação**: `UNION ALL` com `LIMIT` por subquery para garantir representação balanceada de todos os módulos, ordenado por `updated_at DESC`.
- **Frontend**: coluna "Módulo" com badge adicionada à tabela de atividades recentes; busca filtra por módulo.
- **Schema**: campo `module` adicionado a `RecentActivity` (router + frontend types).

## 2026-06-21 — Painel admin no padrão Jarvis/Aloji

### Reescrita completa do painel admin

O painel admin (`admin/`) foi reescrito do zero no padrão Jarvis/Aloji:

- **Design system**: Tailwind CSS 4 + Lucide icons + Sonner (toasts). Design tokens OKLch (paleta navy `#1D3461`). `cn()` helper com clsx + tailwind-merge.
- **Layout**: sidebar colapsável com gradiente navy, navegação com ícones (Dashboard, Empresas, Planos, Auditoria, Configurações), menu do usuário com avatar. Header com label "Plataforma · Super Admin".
- **Route groups**: `(auth)` para login isolado, `(app)` para páginas autenticadas com sidebar.
- **Dashboard**: 4 stat cards (empresas, trial, inadimplentes, MRR) com dados reais da API `/platform/metrics`.
- **Empresas**: tabela com busca, badges de status (trial/ativo/inadimplente/suspenso/cancelado), menu de ações por assinatura (suspender/reativar/cancelar), modal de criação de tenant, delete com confirmação.
- **Planos**: cards com preço formatado em BRL, limites e status ativo/inativo.
- **Auditoria**: tabela de logs administrativos da plataforma.
- **Configurações**: placeholder para futuro.
- **API proxy**: route handler `/api/proxy/[...path]` para mutations client-side (POST/PATCH/DELETE proxeados para `/platform/*`).
- **Auth**: Server Actions + httpOnly cookies (mesmo padrão Aloji).
- **Deps adicionadas**: tailwindcss, @tailwindcss/postcss, lucide-react, clsx, tailwind-merge, sonner.
- **Arquivos antigos removidos**: `app/actions.ts`, `app/login/page.tsx`, `app/dashboard/page.tsx` (substituídos por route groups).

### Acesso

- URL: `http://localhost:3001`
- Login: `admin@registro.local` / `RegistroAdmin@123`

## 2026-06-21 — Correção das telas: dados reais em todas as 11 telas

### Diagnóstico

Todas as 11 telas operacionais exibiam dados mock em vez de dados reais. Duas causas:

1. **Dados no company errado**: o seed user `icaro@registro.local` pertencia a company_id=1 (Empresa Demonstração) que não tem dados. Todos os dados importados do V1 pertencem a company_id=4 (Aero Hotel).
2. **Tabelas dedicadas vazias**: as data migrations (0021, 0023) que moviam reuniões e turnos de `module_records` para `meetings`/`shift_reports` rodaram ANTES do import V1, numa base vazia. Os 72 reuniões e 1165 turnos ficaram presos em `module_records`.
3. **Permissões incompatíveis**: o role `legacy-admin` tinha apenas permissões V1 (`legacy.meetingcontroller.index`), mas a API nova exige `meeting.view`, `occurrence.view`, etc.

### Correção — migration 0030

- Moveu 72 reuniões de `module_records` → `meetings` (com `scheduled_at` e `location` extraídos do payload JSON).
- Moveu 1165 relatórios de turno de `module_records` → `shift_reports` (com `shift_date` e `shift_type` extraídos do payload).
- Soft-deleted os registros migrados em `module_records`.
- Manteve inspeções (4497) e manutenção (104) em `module_records` — frontend usa `/modules/inspecoes` e `/modules/manutencao` (endpoints genéricos).
- Criou demo user `demo@aerohotel.local` / `Registro@123` para Aero Hotel.
- Adicionou permissão wildcard `*` ao role `legacy-admin`.
- Remapeou `audit_events`, `attachments` e `notifications` referenciando os IDs antigos para os novos.

### Validação via API (todos os endpoints com token Aero Hotel)

| Endpoint | Registros |
|---|---|
| `/dashboard/metrics` | 289 abertas, 23 ativos, 17 setores |
| `/meetings` | 72 |
| `/shift-reports` | 1165 |
| `/modules/inspecoes` | 4497 |
| `/modules/manutencao` | 104 |
| `/occurrences` | 317 |
| `/registries` | 99 |
| `/users` | 23 |
| `/procedures` | 6 |
| `/modules/diarios-obra` | 0 (sem dados V1) |
| `/modules/mural` | 0 (sem dados V1) |
| `/fiscal-requests` | 0 (sem dados V1) |

### Nota sobre o tenant Aero Hotel

O Aero Hotel é um **cliente real**, não apenas dados de teste. O dump `aero-2026-06-19.sql` contém dados operacionais reais. O demo user é temporário para desenvolvimento; no corte final, os usuários do V1 farão login com suas senhas bcrypt preservadas do Laravel.

## 2026-06-21 — P5/P6: documentação, governança e readiness de corte

### P6 — Documentação e governança

- Atualizado `mapa.md`: PostgreSQL 17 como banco ativo (era "planejado"), fonte de dados FastAPI corrigida de MySQL para PostgreSQL, todos os domínios P1/P4 refletidos, bloqueios atuais revisados.
- Atualizado `desenvolvimento.md`: porta 5433 (era 3307), referências MySQL substituídas por PostgreSQL, seção de importação V1 adicionada.
- Atualizado `runbook-producao.md`: banco PostgreSQL (era MySQL), comando `pg_dump` adicionado.
- Atualizado `importacao-legado.md`: tabela de estado expandida com todos os domínios importados (reuniões, turnos, check suites, auditorias, notificações), banco destino PostgreSQL, pendências de corte final documentadas.
- Atualizado `arquitetura.md`: removida frase "MySQL só será substituído depois que todos os domínios estiverem equivalentes" — MySQL já foi substituído.
- Atualizado `memoria-projeto.md`: restrições atualizadas para refletir PostgreSQL como banco principal, seção multiempresa atualizada com RLS ativo.
- Criado `docs/adr/` com ADR-001 (migração MySQL→PostgreSQL) e ADR-002 (RLS como isolamento multi-tenant).

### P5 — Readiness de corte

- Auditado `import_v1.py`: script funcional e idempotente, cobre todos os domínios (59 users, 17 sectors, 69 locations, 13 functions, 6 procedures, 375 occurrences, 72 meetings, 1165 shift reports, 4497 check suites, 104 audit reports, 3336 notifications).
- **Issue identificada**: `import_v1.py` escreve reuniões, relatórios de turno, check suites e audit reports em `module_records` (tabela genérica). As data migrations (0021, 0023, 0028) que moviam esses dados para tabelas dedicadas já rodaram no Alembic e não serão re-executadas num banco PostgreSQL limpo. O script precisa ser atualizado para escrever diretamente nas tabelas dedicadas antes do corte final.
- Pendente: puxar dump MySQL atualizado do servidor V1 em produção.

## 2026-06-20 (sessão 4)

### P3B — Preferências de notificação, destinatários por módulo e registro de entrega

- Migration `0024_notification_preferences`: tabela `notification_preferences` (user_id, company_id, module, in_app, email) + coluna `email_sent_at` em `notifications`.
- Model `NotificationPreference` em `models/operations.py`.
- Endpoints de preferências do usuário: `GET /notifications/preferences` (lista todos os módulos com defaults) e `PUT /notifications/preferences/{module}`.
- Endpoints de destinatários por módulo: `GET /settings/notification-recipients` e `PUT /settings/notification-recipients/{module}` — armazenados em `company_settings` com chave `notification_recipients`.
- `notify_record_event` agora consulta preferências individuais e destinatários por módulo antes de criar notificações in-app ou enviar e-mails; `email_sent_at` preenchido após envio bem-sucedido via Brevo.
- Fluxo Chess Hotel respeita destinatários por módulo — se configurados, notifica apenas a lista; senão, fallback para todos os usuários ativos.

## 2026-06-20 (sessão 3)

### P2 — ACL e identidade

- Criado `app/core/permissions.py` com factory `require_permission(code)` que verifica `user.permissions` do JWT.
- Seed de 35 permissões via migration `0018_seed_permissions` (occurrence.*, fiscal_request.*, user.*, registry.*, module.*, procedure.*, settings.*, meeting.*, shift_report.*, wildcard `*`).
- Role "Administrador" com `*` criado para cada empresa existente; todos os users sem role recebem o role admin (backwards compat).
- Todos os 7 routers modificados: `Depends(current_user)` → `require_permission("modulo.acao")` com permissões granulares por endpoint.
- Novo domínio `domain/roles/` com CRUD de cargos (router, service, schemas) — lista, detalhe, criação, atualização, exclusão (protegida contra roles com users), listagem de permissões agrupadas por módulo.
- Frontend: `OperationalModule` condiciona botões Novo/Editar/Excluir por `user.permissions` (canView, canCreate, canEdit, canDelete).

### P3 — Ocorrências: participantes, clone e PDF

- Migration `0019_occurrence_participants` com tabela junction `occurrence_participants` (PK composta).
- Modelo `OccurrenceParticipant` em `models/operations.py`.
- `GET /occurrences/{id}` — endpoint de detalhe com participantes.
- `POST /occurrences/{id}/clone` — duplica ocorrência com participantes, título "Cópia de ...", status resetado.
- `GET /occurrences/{id}/pdf` — exporta PDF via reportlab com metadata, descrição, participantes e timeline.
- Schemas: `OccurrenceDetail`, `ParticipantSummary`; `participant_ids` adicionado a Create/Update.
- Service: `_sync_participants`, `_get_participants`, `get_occurrence`, `clone_occurrence`.

### P3 — Reuniões: tabela dedicada

- Migrations `0020_meetings` (3 tabelas: meetings, meeting_participants, meeting_subjects) e `0021_migrate_reunioes_data` (migra dados de module_records → meetings, remapeia audit_events, attachments e notifications).
- Modelos: `Meeting`, `MeetingParticipant`, `MeetingSubject` em `models/operations.py`.
- Novo domínio `domain/meetings/` com CRUD completo + subjects CRUD + clone.
- Frontend: form dedicado com scheduled_at (datetime-local), location, status (Agendada/Em andamento/Concluída/Cancelada).
- `VALID_MODULES` reduzido: removidos `reunioes` e `relatorios-turno`.
- Timeline service atualizado: entity types `meeting` e `shift_report` adicionados.

### P3 — Relatórios de turno: tabela dedicada

- Migration `0022_shift_reports` com tabela dedicada (shift_date, shift_type, status) e `0023_migrate_relatorios_turno_data`.
- Modelo `ShiftReport` em `models/operations.py`.
- Novo domínio `domain/shift_reports/` com CRUD completo e filtro por data.
- Frontend: form dedicado com shift_date, shift_type (Manhã/Tarde/Noite), status.

### Dependências e infra

- Adicionados `reportlab>=4.2` (PDF) e `openpyxl>=3.1` (Excel) ao `pyproject.toml`.
- 6 novas migrations (0018-0023), 3 novos domínios, 1 novo módulo core.

## 2026-06-19

- Inventariado o legado: Laravel 7, PHP 7.2+, 131 migrations e 194 views Blade.
- Identificados os domínios principais e contratos de usuários/ACL.
- Confirmada a referência Jarvis em `/home/icarosimoes/dev/aloji/docs/agentes`.
- Definida migração incremental para FastAPI + Next.js, mantendo o MySQL.
- Iniciada a fundação paralela em `api/` e `web/`.
- Registrado o redesign inspirado na referência enviada: sidebar expansível, topbar, busca global, indicadores, tabelas densas e drawers contextuais.

## Pendências

- Obter acesso de desenvolvimento ou dump sem dados sensíveis do MySQL.
- Gerar inventário real de tabelas, volumes, constraints e inconsistências.
- Validar política de compatibilidade das senhas Laravel.
- Escolher o primeiro módulo funcional após autenticação/ACL.

## 2026-06-19 — Organização da versão legada

- Aplicação renomeada para **Registro**.
- Código, migrations, views, assets, testes e configuração Laravel movidos para `docs/v1/`.
- Banco MySQL legado mantido com o nome atual para evitar risco operacional.
- Referências da nova API, frontend e documentação atualizadas para Registro.

## 2026-06-19 — Fundação Docker/Swarm

- Criadas imagens Docker multi-stage para FastAPI e Next.js.
- Criado `docker-compose.yml` para desenvolvimento local.
- Criado `docker-stack.yml` para produção Swarm com duas réplicas, healthchecks, rolling update e rollback.
- Conexão de produção preparada para Docker Secret externo.
- Documentado o diretório `/opt/registro`, GHCR, deploy e rollback.

## 2026-06-19 — Fluxo Git simplificado

- Desenvolvimento passou a ocorrer diretamente na branch `main`.
- `docs/v1/` foi mantido no disco local e incluído no `.gitignore`.
- A aplicação Laravel legada foi removida do índice do Git para não ser enviada novamente ao GitHub.

## 2026-06-19 — Primeira fatia de autenticação

- Implementados `POST /api/v1/auth/login` e `GET /api/v1/auth/me`.
- Preservada compatibilidade com bcrypt, usuários ativos, soft delete, papéis, empresas e ACL do Laravel.
- A sessão inclui `company_id`; `/auth/me` revalida usuário e empresa no banco.
- Adicionado Docker Secret independente para a chave JWT no Swarm.
- A validação com usuários reais permanece pendente até configurar acesso seguro ao MySQL.

## 2026-06-19 — Documentação no padrão Aloji

- Inventariados stack atual, quatro endpoints, 60 tabelas legadas e 123 declarações de rota Laravel.
- Criados documentos de arquitetura, domínio, API, UI, desenvolvimento, segurança e backlog.
- Criados inventário V1, plano MySQL/PostgreSQL, runbook de produção e critérios de testes.
- Adaptados para o Registro os agentes Jarvis de engenharia, layout/CRUD, performance, segurança e multiempresa.
- Excluídos deliberadamente os padrões Aloji de reservas, Channex, Asaas, CRM e financeiro por falta de aderência ao domínio.

## 2026-06-19 — Base SaaS, MySQL e admin

- Adicionado MySQL 8.4 ao Compose, migration Alembic inicial e seed fictício com dois tenants.
- Criados modelos de empresas, usuários, papéis, permissões, planos, assinaturas, faturas, operadores e auditoria da plataforma.
- Separados JWT tenant e plataforma; login tenant aceita `company_slug` e revalida o tenant.
- Criada API administrativa de métricas, tenants e planos.
- Criado painel Next.js separado em `admin/`, com sessão em cookie `httpOnly`.
- Adicionado serviço admin à stack Swarm e mantido MySQL de produção externo.
- Adaptados os agentes Jarvis SaaS e Asaas; integração de cobrança continua desativada.
- Documentado o procedimento futuro de importação do dump Laravel.

## 2026-06-19 — Entrada autenticada do tenant

- A raiz do produto deixou de exibir diretamente o protótipo estático.
- Criados login tenant, cookie `httpOnly`, revalidação em `/auth/me`, dashboard protegido e logout.
- O protótipo visual foi preservado em `/design-preview`; seus indicadores continuam fictícios até os módulos operacionais serem conectados.

## 2026-06-19 — MVP funcional do portal

- Conectados todos os itens do menu do tenant a telas autenticadas.
- Implementados busca, filtro, paginação, detalhes, criação, edição, exclusão confirmada, restauração e exportação CSV.
- Criadas telas de ocorrências, reuniões, turno, inspeções, diário de obra, manutenção, cadastros, usuários, mural, configurações e conta.
- Dados operacionais de teste ficam no `localStorage`, isolados por `company_id`; a API continua sendo a próxima etapa para persistência e autorização reais.

## 2026-06-19 — Importação do dump V1

- Restaurado `aero-2026-06-19.sql` em staging MySQL separada com 66 tabelas.
- Identificado que `companies` está vazia e os usuários da V1 possuem `company_id` nulo.
- Criado tenant sintético `aero-hotel`, preservando hashes Laravel e IDs antigos em `legacy_id`.
- Importados 59 usuários, 17 setores, 69 locais, 13 funções, 6 procedimentos e 375 ocorrências.
- Criada migration `20260619_0002`, importador idempotente por checksum e `GET /occurrences`.
- Validada paridade de 375 ocorrências; a API retorna 317 registros não excluídos.

## 2026-06-19 — Tenant Aero Hotel e login sem slug

- Tenant V1 renomeado de `aero-v1` para `aero-hotel` (nome "Aero Hotel") no código, base e documentação.
- Documentado plano de produção: dump fresco da V1 em operação será reimportado pelo mesmo ETL idempotente.
- Login removeu campo `company_slug`; agora aceita apenas e-mail e senha.
- Se o e-mail pertence a um único tenant, entra direto. Se pertence a mais de um, API retorna `422 multi_tenant` com lista de empresas e o front exibe seletor.
- Front de login convertido para Client Component com seletor de tenant dinâmico.
- Padrão alinhado com o Aloji.

## 2026-06-19 — Tratativa (timeline de conversa)

- `HistoryEntry` agora possui `type` (`comment`, `change`, `create`) e campo `message` para comentários livres.
- Comentários podem ser adicionados diretamente no drawer de detalhes via campo de texto e botão enviar.
- Criações, edições e comentários aparecem em ordem cronológica como uma conversa de ticket.
- Avatares coloridos por tipo: azul (comentário), roxo (alteração de campos), verde (criação).
- Alterações exibem chips detalhando cada campo modificado com valor anterior e novo.
- Timeline visível tanto no drawer de detalhes (com campo de comentário) quanto no modal de edição (somente leitura).
- Modal de edição alarga automaticamente quando o registro possui histórico.
- Presente em todas as telas operacionais: ocorrências, reuniões, relatórios de turno, inspeções, diário de obra, manutenção, cadastros, usuários e mural.
- Dados persistidos no `localStorage` por tenant; futuramente serão gravados pela API com auditoria real.

## 2026-06-20 — Revisão técnica e governança documental

- Revisadas as alterações recentes de autenticação, tenant Aero Hotel, timeline e solicitações fiscais.
- Confirmados os quatro serviços locais ativos no Docker: API, web, admin e MySQL.
- Executados `npm run typecheck`, build de produção do Next.js e testes da API no container; frontend aprovado e 7 testes da API aprovados.
- Confirmados no banco local o tenant `aero-hotel`, 60 usuários vinculados e 375 ocorrências importadas.
- Identificado que o login multitenant revela a lista de empresas antes de validar a senha; correção e testes foram priorizados no backlog.
- Identificado que a interface carrega apenas 100 ocorrências e pode substituir os dados da API por uma cópia antiga do `localStorage`.
- Identificado que tratativas, edições, comentários e o módulo fiscal ainda não possuem persistência na API.
- Registradas pendências de anexos, SLA, notificações, validação fiscal, auditoria, cross-tenant, documentação e CI.
- Definido formalmente que toda informação pertinente ao desenvolvimento e ao sistema deve ser documentada em `/docs`.
- Atualizados `backlog.md`, `memoria-projeto.md` e o padrão documental com essa regra permanente.

## 2026-06-20 — Autenticação multitenant e ocorrências

- Corrigido o fluxo multitenant para validar hashes antes de retornar opções de empresa.
- Removida a segunda consulta que listava tenants apenas pelo e-mail; as opções agora derivam exclusivamente dos usuários autenticados.
- Adicionado `company_name` ao resultado interno de autenticação e ordenação determinística por empresa.
- Adicionada validação positiva para `company_id`.
- Criados cinco testes de serviço/contrato de autenticação; suíte total validada com 12 testes e Ruff sem erros.
- A página de ocorrências passou a buscar a primeira página e carregar em paralelo as páginas restantes da API.
- Ocorrências vindas da API não consultam nem gravam dados operacionais no `localStorage`.
- Ações de criação, edição, exclusão e comentário ficam ocultas para ocorrências reais até a API de mutações existir; a tela informa o modo leitura.
- Restaurados `.idea/` e `.vscode/` no `.gitignore`.
- Validação final: 12 testes da API, Ruff, TypeScript e build Next.js aprovados; os quatro serviços Docker permaneceram ativos e a API saudável.
- O mypy 1.20.2 da imagem encerrou com erro interno da própria ferramenta, sem produzir diagnóstico do código; estabilização registrada no backlog.

## 2026-06-20 — CRUD de solicitações fiscais e ocorrências

- Criado modelo `FiscalRequest` com `company_id`, `protocol`, `request_type`, `title`, `description`, `apartment`, `requester`, `origin`, `status` e `payload` JSON.
- Criadas migrations `0003` (tabela), `0004` (colunas `title`/`description`) e `0005` (`legacy_id` nullable em todas as tabelas legadas).
- Criada migration `0006` para renomear tenant `aero-v1` para `aero-hotel` sem duplicar, cobrindo cenário de dump antigo.
- Implementados endpoints `POST/GET/PATCH/DELETE /fiscal-requests` com Tenant Bearer e isolamento por `company_id`.
- Implementado `POST /integrations/chess-hotel/tickets` com autenticação por header `X-Registro-Key` e resolução de tenant por slug.
- Implementados endpoints `POST/PATCH/DELETE /occurrences` com soft delete, `created_by_user_id` e `updated_by_user_id`.
- Criadas server actions no frontend (`createFiscalRequestAction`, `updateFiscalRequestAction`, `deleteFiscalRequestAction`, `createOccurrenceAction`, `updateOccurrenceAction`, `deleteOccurrenceAction`).
- Frontend de ocorrências e solicitações fiscais agora permite criar, editar e excluir via API; mensagem de "modo leitura" removida.
- Frontend de módulos API-backed recarrega dados a cada 15 segundos e em eventos de foco/visibilidade.
- Componente `RegistroLauncher.vue` validado no Chess Hotel (localhost:8081) abrindo drawer de "Nova Solicitação Fiscal".
- Documentados os novos endpoints, modelo de domínio atualizado e rotas web revisadas em `api-reference.md`, `domain-model.md`, `web-rotas-ui.md` e `chess-hotel-implementacao.md`.
- Todos os endpoints testados end-to-end: create, update, delete, list, isolamento cross-tenant e integração Chess Hotel.

## 2026-06-20 — Auditoria, paginação, validação e CI

- Criada tabela `audit_events` (migration `0007`) com `company_id`, `user_id`, `entity_type`, `entity_id`, `event_type` e `diff` JSON.
- Criado service `app/core/audit.py` com `record_event` e `compute_diff`; integrado em todos os endpoints de mutação de ocorrências e solicitações fiscais.
- Diff registra campo a campo o valor anterior e novo, apenas quando há mudança; create e delete não possuem diff.
- Evoluído o frontend de ocorrências para paginação server-side (20 por página) com busca via query params na URL e debounce de 400ms.
- O server component busca uma única página da API em vez de carregar todas em paralelo.
- Criado `app/core/validators.py` com validação de CPF (dígitos verificadores), CNPJ (dígitos verificadores) e e-mail básico.
- CPF/CNPJ validados e normalizados no `payload` de solicitações fiscais (create e update); valores inválidos rejeitados com 422.
- E-mail do tomador normalizado para lowercase e trim.
- Adicionadas colunas `requester_email`, `requester_user_id`, `responsible_user_id`, `chess_user_id`, `reservation_number` e `sla_deadline` a `fiscal_requests` (migration `0008`).
- Integração Chess Hotel expandida: resolução de usuário por e-mail, cálculo de SLA (24h), tracking de solicitações com histórico de auditoria, e URL de acompanhamento.
- Criado CI mínimo em `.github/workflows/ci.yml` com 3 jobs: Ruff (lint + format), pytest (com MySQL service), TypeScript typecheck.
- Documentação atualizada em `api-reference.md`, `domain-model.md`, `web-rotas-ui.md`, `mapa.md`, `backlog.md` e `registro-trabalho.md`.

## 2026-06-20 — Dados reais em todas as telas

- Removidos todos os dados hardcoded e mock do dashboard e módulos operacionais.
- Criado endpoint `GET /dashboard/metrics` com métricas agregadas em tempo real: ocorrências abertas, solicitações fiscais pendentes, concluídos no mês, equipe ativa, setores e últimas 10 atividades.
- Dashboard atualizado para exibir data/saudação dinâmicas e indicadores reais do banco.
- Criado CRUD completo de usuários (`GET/POST/PATCH/DELETE /users`) com listagem paginada, criação com hash bcrypt, atualização (inclusive senha), soft delete e proteção contra auto-exclusão.
- Criado CRUD unificado de cadastros (`GET/POST/PATCH/DELETE /registries`) combinando setores, locais e funções em uma única listagem com busca.
- Criada tabela `module_records` (migration `0009`) para módulos genéricos sem tabela própria.
- Criado CRUD de módulos genéricos (`GET/POST/PATCH/DELETE /modules/{slug}`) para reuniões, relatórios de turno, inspeções, diário de obra, manutenção e mural.
- Todos os novos endpoints incluem auditoria via `audit_events`, isolamento por `company_id` e paginação server-side.
- Frontend atualizado: todas as telas buscam dados reais da API, formulários adaptados por tipo (usuários com campo de senha, cadastros com seletor de tipo, etc.).
- Eliminados botão "Restaurar dados fictícios" e aviso de "modo leitura" para módulos API-backed.
- Documentação atualizada em `api-reference.md`, `domain-model.md`, `web-rotas-ui.md`, `mapa.md`, `backlog.md` e `registro-trabalho.md`.

## 2026-06-20 — Padronização de design tokens

- Criado sistema de design tokens no `globals.css` com 40+ variáveis CSS organizadas por categoria.
- **Cores**: eliminados ~15 hexadecimais hardcoded; criadas variáveis `--blue-hover`, `--blue-focus`, `--label`, `--placeholder`, `--hover`, `--field-bg`, `--field-border`, `--red`, `--red-soft`, `--yellow`, `--yellow-soft`.
- **Espaçamento**: escala de 7 níveis (`--sp-1` 4px a `--sp-7` 32px), substituindo gaps inconsistentes de 14/15/16/18/20/22px.
- **Raios**: 5 tokens (`--radius-sm` 7px, `--radius-md` 9px, `--radius-lg` 14px, `--radius-xl` 18px, `--radius-pill` 999px), unificando 8 valores diferentes.
- **Sombras**: 7 tokens semânticos (`--shadow-sm` a `--shadow-modal`), consolidando ~10 combinações de box-shadow.
- **Tipografia**: 6 tokens de tamanho (`--font-xs` 10px a `--font-xl` 31px).
- **Componentes**: `--btn-height` 40px, `--btn-icon-size` 36px, `--input-height` 44px.
- **Transição**: unificada em `--transition: .2s ease` (antes misturava .15s e .22s).
- Font-weights reduzidos de 6 valores (650/700/750/800/850/900) para 4 (600/700/800).
- Cores de label unificadas: `#445066`/`#4d586b`/`#4a566b` → `var(--label)`.
- Hover states unificados: `#f0f3f8`/`#f3f6fa` → `var(--hover)`.
- Status color `#1763c6` → `var(--blue)` consistente.
- Adicionadas transitions em elementos interativos que não tinham (nav-items, icon-buttons, etc.).
- Layout e visual permanecem idênticos — apenas valores foram unificados para manutenção.

## 2026-06-20 — Remoção de componentes e unificação de layout

- Removido componente `WorkspaceTabs` (abas dinâmicas no topbar) da UI do Registro.
- Código e CSS do componente arquivados em `aloji/docs/agentes/jarvis-workspace-tabs.md` para reutilização em outros projetos.
- Removida barra superior (topbar) de todas as telas. Sino e avatar agora flutuam no canto superior direito sem barra visual (`.top-float` + `.top-float-actions` com `position: fixed`).
- Criado `AppLayout` (`components/app-layout.tsx`) como shell unificado para dashboard e módulos.
- Sidebar, navegação, collapse, drawers de notificação/perfil e menu mobile agora são compartilhados via `AppLayout`.
- `DashboardShell` e `OperationalModule` simplificados para renderizar apenas conteúdo interno (sem sidebar, topbar ou drawers de perfil).
- Removidos ~120 linhas de CSS duplicado (`.module-shell`, `.module-sidebar`, `.module-brand`, `.module-nav-item`, `.module-topbar`, `.module-user`, `.topbar`).
- Busca do dashboard movida para a barra de ferramentas da tabela de atividades recentes (`.table-search`).

## 2026-07-04 — Agente Go de ponto, catálogo de relógios e Portal do Colaborador

### Catálogo de relógios de ponto

- Levantados os relógios de ponto mais usados no Brasil (Control iD, ZKTeco, Henry, Topdata, Madis) com protocolo, homologação REP-P e prioridade de suporte — documentado em `relogios-de-ponto-catalogo.md`. Control iD priorizado por já ter suporte no backend (webhook `POST /integrations/control-id/{webhook_token}/punches`).

### Agente Go de ponte local (`agent/`)

- Criado agente Go standalone (`agent/`, módulo `github.com/icarosimoes/registro-timeclock-agent`) que roda no computador da recepção, conversa com o relógio Control iD via API REST local (login/logout, usuários, logs de acesso) e repassa as batidas para o webhook já existente do Registro.
- `internal/sync`: polling configurável, fila de retry em disco para resiliência offline, cursor de última batida processada.
- `internal/webui`: UI local de configuração em `127.0.0.1:47334` (sem autenticação — postura de app localhost single-user).
- `internal/tray`: ícone de bandeja best-effort (`getlantern/systray`), com fallback headless quando dependências de sistema (GTK/pkg-config) não estão disponíveis.
- Build tags separam a systray real (`-tags systray`) do build padrão headless, evitando dependência de cgo/GTK no build default.
- Verificação: `go build`/`go vet`/`go test` limpos; UI local testada com `curl` manual.

### Portal do Colaborador (ponto mobile, escala, contracheque)

- Backend novo em `api/app/domain/timeclock/mobile_router.py` + `mobile_auth.py`: token JWT `employee_session` completamente isolado do login de `User` (sem `permissions`/`role_id`, dependency própria `require_employee_session`), login por PIN numérico com lockout (`employee_credentials`), geofencing por Haversine na batida (`Location.latitude/longitude/geofence_radius_m`, `Employee.location_id`), escala reaproveitando `get_calendar()` já existente, contracheque (`employee_payslips` + `attachments` com novo `entity_type="employee_payslip"`).
- Migration `20260704_0047_employee_portal.py` aplicada e verificada contra o Postgres real do Docker Compose.
- 14 testes novos em `api/tests/test_timeclock_mobile.py`, incluindo o teste crítico de isolamento de namespace de token nos dois sentidos. Suíte completa: 517 passed, 19 skipped.
- Frontend novo `colaborador/`: PWA Next.js 16 independente (porta 3002), sem menu do Registro — login por PIN + troca obrigatória de PIN default, tela de ponto com `navigator.geolocation`, escala (próximos 14 dias), contracheque (download via route handler que injeta o Bearer token, já que `<a href>` não carrega headers). `next.config.ts` próprio permite `Permissions-Policy: geolocation=(self)` (o `web/` bloqueia geolocalização). Serviço `colaborador` adicionado ao `docker-compose.yml` raiz.
- Documentação: `portal-colaborador.md` (novo), `api-reference.md`, `domain-model.md`, `mapa.md`, `backlog.md` (seção P10) e `memoria-projeto.md` atualizados. Pendências registradas em P10 (PC5-PC8): deploy no Swarm, telas administrativas de geofencing/PIN no `web/`, validação contra hardware real, integração automática de contracheque com folha/ERP.

## 2026-07-04 — Turnos padrão por tenant e reorganização de Configurações

### Turnos padrão (seed automático)

- Adicionado `ensure_default_shifts()` em `api/app/domain/timeclock/service.py`: cadastra 6 turnos padrão (Manhã, Tarde, Noite, Comercial, 12x36 Diurno, 12x36 Noturno) para uma empresa, pulando se ela já tiver algum turno ativo.
- Ligado em `create_tenant` (`api/app/domain/platform/service.py`) — toda empresa criada pelo painel da plataforma já nasce com os turnos.
- Criado `api/app/backfill_default_shifts.py` (idempotente) para aplicar aos tenants que já existiam antes dessa mudança; rodado manualmente em dev via `docker exec registro-api-1 python -m app.backfill_default_shifts` (aplicado com sucesso em `empresa-demo`, `filial-teste` e `aero-hotel`).
- Documentado em `escala-de-trabalho.md`.

### Cadastro de usuários e perfis de acesso dentro de Configurações

- Movidas as telas de usuários (`/usuarios`) e perfis de acesso (`/perfis`) para dentro de `/configuracoes`, como abas "Usuários" e "Perfis de acesso", reaproveitando os componentes existentes (`OperationalModule`, `RoleManager`) sem duplicar lógica.
- `OperationalModule` ganhou os props opcionais `basePath`/`extraParams` (antes navegava sempre para `/${definition.slug}` na paginação/busca; agora aceita uma base de rota diferente para funcionar embutido em `/configuracoes?tab=usuarios`).
- Removidas as entradas "Usuários" e "Perfis de acesso" do submenu "Cadastros" da sidebar (`components/app-layout.tsx`); `/perfis` agora é um redirect para `/configuracoes?tab=perfis` (mantém links antigos funcionando); `/usuarios` continua respondendo via a rota genérica `[module]` (sem alteração), só não aparece mais no menu.
- Verificado em navegador (Playwright headless): as duas abas renderizam corretamente, busca/paginação preservam `tab=usuarios` na URL, sem erros de console.

## 2026-07-05 — Deploy do `colaborador/`, geofencing na UI, banco de horas e ajuste de ponto

### Deploy do `colaborador/` em produção (PC5)

- Serviço `colaborador` adicionado ao `docker-stack.yml` (imagem GHCR, Traefik em `REGISTRO_COLABORADOR_HOST`, porta 3002, `update_config`/`restart_policy` no mesmo padrão de `web`/`admin`).
- `publish.yml`: novo item na matrix de build/push e novo `docker service update` no job de deploy; `colaborador/**` adicionado aos paths que disparam o workflow.
- Runbooks `docs/infra/deploy-swarm.md` e `docs/infra/deploy-novo-dominio.md` atualizados para o quarto host/serviço (DNS, `.env.prod`, validação, rollback, troca de domínio).

### Geofencing de `Local` e reset de PIN na UI administrativa (PC6)

- `PATCH/POST/GET /registries` aceita e retorna `latitude`/`longitude`/`geofence_radius_m` quando `category=Local` (ignorado para Setor/Função); mutações agora geram `AuditEvent` com diff, o que também corrigiu uma lacuna pré-existente (updates de cadastro não eram auditados).
- Formulário de `/cadastros/locais` ganhou os três campos; 2 testes novos em `test_registries.py`.
- Botão "Resetar PIN" em `/cadastros/funcionarios` (permissão `timeclock.manage`), chamando o endpoint já existente `POST /timeclock/employees/{id}/pin/reset` e exibindo o novo PIN uma única vez.

### Banco de horas e ajuste de ponto com aprovação (PC11/PC12)

Migration `20260705_0048_hour_bank_punch_adjustments.py`. Detalhes completos em [escala-de-trabalho.md](escala-de-trabalho.md#banco-de-horas-e-ajuste-de-ponto-2026-07-05).

- `HourBankEntry`: lançamento diário calculado (escala x pontos batidos, via `POST /timeclock/hour-bank/{id}/recalculate`) ou saldo inicial migrado manualmente pelo RH. Consulta em `/ponto/banco-de-horas` (RH) e aba "Banco" no `colaborador/` (funcionário).
- `PunchAdjustmentRequest`: funcionário solicita correção de batida existente ou lançamento de batida esquecida pelo Portal do Colaborador; RH aprova/rejeita em `/ponto/ajustes`, reaproveitando `update_punch`/`create_manual_punch`. Notificação in-app para usuários com permissão `punch_adjustment.manage`.
- 4 novas permissões: `hour_bank.view`, `hour_bank.manage`, `punch_adjustment.view`, `punch_adjustment.manage`.
- 13 testes novos (`test_hour_bank.py`, `test_punch_adjustments.py`); suíte completa em 545 testes passando. `web/` e `colaborador/` com typecheck e build limpos.
- Escopo definido a partir de benchmarking de concorrentes (Sólides Ponto, Flash Controle de Jornada, PontoSimples); itens não priorizados nesta rodada ficam registrados no backlog (férias, sobreaviso, assinatura eletrônica, exportação AFD/ACJEF, integração com ERP de folha).

## 2026-07-06 — Relatórios, abono de ponto com notificações e Espelho de Ponto

### Relatórios (`/relatorios`)

- Novo domínio `api/app/domain/reports/` (`report.view`, migration `20260705_0049`): `GET /reports/occurrences` (por status/setor, taxa de conclusão, tendência diária) e `GET /reports/fiscal-requests-sla` (por status/tipo, `sla_compliance_pct`, breakdown de estado de SLA via `compute_sla_status()` já existente em `app/core/sla.py`, tendência diária). Sem período informado, usa o mês corrente.
- Frontend `/relatorios`: filtro de período na querystring, gráficos de barra reaproveitando o padrão visual do dashboard. Sem exportação nesta entrega (nenhuma tela do sistema tinha export funcionando até então).

### Ajustes e abono de ponto — tela redesenhada + notificações

- Tela `/ponto/ajustes` redesenhada: abas Pendentes/Aprovados/Rejeitados/Todos (`.segmented`) no lugar do `<select>`, painel de estatísticas (tendência mensal de ajustes + ranking de solicitantes mais/menos frequentes, com avatar), e botões "Ajustar Ponto"/"Abonar Ponto" abrindo drawers laterais.
- **Abono de ponto** (`PunchExcusal`, novo): lançado diretamente pelo RH (sem aprovação — quem cria já é quem aprova), neutraliza o banco de horas do dia sem apagar o lançamento `"calculated"`. Detalhes em [escala-de-trabalho.md](escala-de-trabalho.md#abono-de-ponto-espelho-de-ponto-e-notificações-2026-07-06).
- **Bug de isolamento entre tenants corrigido**: `create_punch_excusal` não validava se `employee_id` pertencia à empresa do usuário logado — corrigido para retornar 404.
- **Notificações conectadas ao sino**: abono agora notifica outros gestores (excluindo quem criou); clicar numa notificação de ajuste/abono navega para `/ponto/ajustes` (antes só marcava como lida).
- Novos componentes reutilizáveis: `web/components/avatar.tsx` (imagem com fallback de iniciais) e `web/components/employee-autocomplete.tsx` (busca com filtro por nome, reaproveitando o padrão de `UserAutocomplete` já existente em `operational-module.tsx`, mas com `searchEmployees`).

### Espelho de Ponto (`/ponto/espelho`)

- Grade diária por funcionário/período (1ª/2ª entrada-saída, intervalo, trabalhado, crédito/débito, HE 50%/100%, adicional noturno, saldo) + exportação Excel/PDF. Detalhes completos, incluindo as regras de cálculo assumidas e os cortes de escopo deliberados (sem feriados, sem "hora noturna reduzida", um colaborador por vez, sem AFD/ACJEF), em [escala-de-trabalho.md](escala-de-trabalho.md#abono-de-ponto-espelho-de-ponto-e-notificações-2026-07-06).
- Primeiro uso, no projeto, do padrão de proxy de download via Route Handler Next.js (`web/app/api/ponto/espelho/export/route.ts`) — necessário porque o JWT é `httpOnly` e o browser não pode chamar a API externa diretamente para baixar um arquivo.

### Achados de infraestrutura de testes

- A suíte de testes (`api/tests/`) roda contra o mesmo banco de desenvolvimento — não há `TEST_DATABASE_URL` isolado. Isso causa acúmulo de dados de teste no ambiente de dev a cada execução, e uma colisão real: `test_hour_bank.py::test_recalculate_hour_bank_matches_exact_shift` usa a data hardcoded `2026-07-06`, que colide com a batida de demonstração que o script de seed fictício de ponto gera ancorada em "hoje" quando a data fictícia do ambiente cai exatamente nesse dia. Não corrigido nesta rodada (exigiria banco de teste isolado ou revisão das datas hardcoded) — registrado no backlog.
- Nenhum teste automatizado (`pytest`) foi adicionado para abono/espelho/notificações — verificação foi manual (curl + navegador headless via skill `run-web`).

### Padronização visual dos formulários de filtro (módulo Ponto)

Revisão UI/UX de todas as telas de `/ponto` (Batidas, Banco de Horas, Dispositivos, Vínculos, Escalas de Trabalho, Espelho, Contracheques), verificada telas por tela com a skill `run-web` (Playwright headless) comparando screenshot antes/depois e conferindo `getComputedStyle` quando a diferença visual não era óbvia. Padrão documentado em [web-rotas-ui.md](web-rotas-ui.md#padrão-de-campo-e-filtro-report-filter-field) para ser seguido em toda tela nova.

- **Bug real corrigido**: botões `.primary-button`/`.secondary-button` dentro de `.module-toolbar` (Batidas, Cadastros → Funcionários) ficavam com texto branco sobre fundo branco — completamente invisíveis — por conflito de especificidade CSS (`.module-toolbar button` com seletor elemento+classe vencia `.primary-button` de classe única). Corrigido com regras `.module-toolbar .primary-button`/`.secondary-button` de maior especificidade.
- **Bug real corrigido**: `<input type="date">` soltos (fora de `<label>`) dentro de `.module-toolbar` herdavam `width: 100%` de uma regra pensada para o padrão de busca com ícone, forçando cada campo a quebrar sozinho numa linha cheia. Escopo da regra reduzido para `.module-toolbar label input`.
- Criadas as classes reutilizáveis `.report-filter-field` (label acima do campo + borda/altura padrão), `.report-filter-group` (subgrupo que quebra linha como bloco), `.col-num`/`.balance-negative` (alinhamento numérico em tabelas com saldo/minutos) e `.nav-arrow-button` (navegação `‹ ›` fora de paginação de tabela) em `web/app/globals.css`.
- Estilizado o seletor nativo de arquivo (`input[type="file"]`) via `::file-selector-button`/`::-webkit-file-upload-button` para parecer um `secondary-button` — usado em Contracheques.
- Aplicado em Espelho de Ponto, Banco de Horas, Dispositivos, Vínculos e Escalas de Trabalho, que antes usavam `<input>`/`<select>` sem classe (borda cinza nativa `rgb(118,118,118)`, cantos retos).
- **Limitação de verificação**: o botão de escolha de arquivo (`::file-selector-button`) não renderiza estilizado no Chromium headless shell usado pela skill `run-web` neste ambiente (a mesma engine aplica o CSS via `getComputedStyle` mas não pinta com ele) — comportamento correto esperado em Chrome/Edge/Firefox reais, mas não pôde ser confirmado visualmente aqui. Vale conferir num browser real na próxima vez que a tela de Contracheques for tocada.

### Cadastro de Funcionários: formulário de criação/edição virou modal sobreposto

- `/cadastros/funcionarios` tinha um formulário de 18 campos que era inserido *inline* na página (empurrando a tabela para baixo) tanto para criar quanto para editar. Reativado o padrão `.modal-layer`/`.record-modal`/`.form-grid` (já existente em `globals.css`, mas sem nenhum uso no código até então) — clicar em "Novo funcionário" ou no lápis de editar agora abre um modal centralizado com backdrop, em vez de deformar o layout da lista.
- `.record-modal.has-timeline` (720px) é aplicado dinamicamente quando "Ver histórico" está aberto, para caber a tabela de timeline ao lado/abaixo do formulário sem espremer os campos.
- Fechamento por clique no backdrop (`stopPropagation` no card interno) ou pelo X no header, seguindo o mesmo padrão do drawer usado em `/ponto/ajustes`.
- Botões "Importar CSV"/"Novo funcionário" no toolbar deixaram de ficar escondidos enquanto o formulário estava aberto (não fazia mais sentido escondê-los, já que o formulário não ocupa mais espaço da página).

### Calendário de Escalas: horário do turno visível na célula

- Cada célula do calendário em `/ponto/escalas` mostrava só o nome do turno (ex.: "Tarde"); agora mostra também o horário (`15:00–23:00`) abaixo do nome, usando os campos `start_time`/`end_time` que a API já retornava em `CalendarEntry` mas o frontend não exibia.

## 2026-07-06 — Conformidade CLT no espelho de ponto: feriados, hora noturna reduzida e filtro por setor

Implementação dos três itens pendentes de P11 (feriados, hora noturna reduzida, filtro por equipe) a pedido explícito do usuário, após ele revisar o backlog de conformidade do módulo Ponto. Detalhes completos em [escala-de-trabalho.md](escala-de-trabalho.md#feriados-2026-07-06).

- **Feriados**: novo modelo `Holiday` (`holidays`, migration `20260706_0051`, com RLS e permissões `holiday.view`/`holiday.manage` seedadas na mesma migration). CRUD simples em `/ponto/feriados`, primeira tela nova construída já usando o padrão `report-filter-field` documentado hoje mais cedo. `get_holiday_dates()` busca as datas do período uma vez por chamada do espelho (não uma query por dia). Feriado entra na regra de HE 100% (`is_rest_day`) e aparece na coluna Observações.
- **Hora noturna reduzida**: `mirror.py` mudou de `total * 0.20` para `total * NIGHT_COMBINED_RATE`, onde `NIGHT_COMBINED_RATE = (60/52.5 - 1) + 0.20 ≈ 0,342857` — soma o efeito da hora noturna reduzida (CLT art. 73 §1º: hora noturna = 52min30s de relógio) com o adicional de 20%, aplicado como um único percentual sobre os minutos noturnos reais (simplificação assumida e documentada, em vez de recalcular a jornada em "horas noturnas" separadamente).
- **Filtro por Setor**: `GET /timeclock/mirror/by-sector` (`build_sector_mirrors()`) itera os funcionários ativos do setor e reaproveita `build_employee_mirror()` por funcionário — sem otimização de N+1 entre funcionários. Frontend ganhou um seletor "Filtrar por: Funcionário/Setor"; no modo Setor renderiza um card de espelho por funcionário. Exportação Excel/PDF continua só por funcionário individual (não há export em lote por setor).
- **Testes**: `api/tests/test_holidays.py` (5 testes novos) cobre CRUD de feriados (incluindo conflito de data duplicada), HE 100% com feriado, a taxa combinada do adicional noturno, e o espelho por setor. Suíte completa: 544 passando (era 539 antes desta rodada).
- **Correção incidental**: o horário do turno (não só o nome) passou a aparecer nas células do calendário de `/ponto/escalas`, e o formulário de criar/editar funcionário em `/cadastros/funcionarios` deixou de ser inline e virou modal sobreposto (`.record-modal`), a pedido do usuário na mesma sessão.

## 2026-07-12 — Revisão UI/UX ponta a ponta do painel admin

Revisão solicitada pelo usuário a partir de um print da tela de Configurações mostrando avatar duplicado no cabeçalho e no rodapé da sidebar. Feita por leitura completa do código (`admin/app/`, `admin/components/`) — layout, sidebar, as 8 telas e todos os componentes de `components/ui/` — sem servidor de browser disponível na sessão para screenshot automatizado; validação final por build + typecheck + `vitest run`.

### Achados e correções aplicadas

- **Menu de usuário duplicado**: `TopUserMenu` (avatar no cabeçalho) e `SidebarUserMenu` (avatar no rodapé) eram dois componentes quase idênticos, cada um com seu próprio dropdown e "Sair". `TopUserMenu` removido; o cabeçalho ficou só com o breadcrumb "Plataforma · Super Admin".
- **Dark mode**: dois problemas encontrados em sequência.
  1. Primeiro, contraste quebrado: `input, select, textarea { color: #111827 }` fixo em `globals.css`, incompatível com o `--card` escuro que o tema dark já declarava — texto quase preto sobre fundo quase preto em todos os modais. Trocado para `var(--foreground)`/`var(--background)` (reagem ao tema).
  2. Depois, a pedido explícito do usuário ao ver o resultado (print da Dashboard toda escura): o painel **não deve ter dark mode automático**. Removido o bloco inteiro `@media (prefers-color-scheme: dark)` de `globals.css` — o tema é sempre claro, independente da preferência do SO/navegador. `Toaster` (sonner) trocado de `theme="system"` para `theme="light"` pelo mesmo motivo.
- **Duas paletas de marca coexistindo**: `--color-brand`/`--ring` (usados por `Button`/`Badge`/foco) eram um azul genérico do template (`oklch(0.55 0.18 250)`), enquanto sidebar, login e cabeçalhos de modal usavam o navy/teal reais da marca (`#1D3461`/`#2BC4B4`) via `style={{...}}` hardcoded. Unificado: `--color-brand: #1D3461`, `--ring: var(--color-brand-accent)` (`#2BC4B4`).
- **Ações destrutivas com `confirm()`/`alert()` nativos**: apagar empresa, remover usuário e mudar status de assinatura usavam diálogos do browser (sem estilo, quebram a identidade visual no momento mais crítico). Criado `components/ui/confirm-dialog.tsx` (`ConfirmDialog`, sobre o `Dialog` Radix já existente) e usado nos três fluxos; erros passaram de `alert()` para toast (`sonner`, já estava configurado no projeto mas sem uso).
- **Três dropdowns reimplementados na mão apesar de já existir `DropdownMenu` (Radix)** em `components/ui/dropdown-menu.tsx`: `SidebarUserMenu`, `TopUserMenu` (removido) e o menu de ações de assinatura em Empresas usavam `useState` + listener de `mousedown` manual (sem fechar com Esc, sem ARIA). Os dois que sobraram foram migrados para `DropdownMenu`.
- **Modais reimplementados na mão apesar de já existir `Dialog` (Radix)** em `components/ui/dialog.tsx`: os modais de Nova/Editar empresa e Novo/Editar usuário eram `<div className="fixed inset-0 z-50">` sem focus trap nem Esc para fechar. Migrados para `Dialog`.
- **Login fora do design system**: `<input>`/`<label>`/`<button>` cru em vez de `Input`/`Label`/`Button`. Migrado — e a migração revelou um bug real de acessibilidade: os `<label>` não tinham `htmlFor`, então `getByLabelText` (e leitores de tela) não associavam rótulo e campo. `admin/__tests__/login.test.tsx` tinha esse teste falhando silenciosamente (2 falhas antes da correção, 1 depois).

### Validação

`tsc --noEmit` limpo; `next build` compila; `vitest run` foi de 2 testes falhando para 1 (a falha restante, `/painel da plataforma/i` não encontrado, é pré-existente — o texto real é "Painel SaaS" — e não relacionada a este trabalho; não corrigida por incerteza sobre qual lado está desatualizado, registrada no backlog).

### Pendências identificadas mas não corrigidas nesta rodada

Registradas em `backlog.md` (P12): componentizar o padrão de "pílulas de filtro" duplicado em `support-client.tsx`/`usage-client.tsx`; paginação/filtro na tela de Auditoria; CRUD de Planos (hoje só leitura); Dashboard com apenas 4 stat cards, sem atalhos para pendências (suporte, inadimplência).

### Deploy

Não implantado em produção nesta rodada — apenas `git push origin main` (commits `6016d1c5` e `b4149faf`); `admin/` segue rodando localmente via Docker Compose. Próximo deploy de produção que tocar `admin/` deve incluir essas mudanças.

## 2026-07-12 (continuação) — Sessão expirada quebrava mutações do painel admin

O usuário reportou `Internal Server Error` ao salvar Configurações; investigado nos logs do `registro-api-1` e identificado como um `NameError: name 'PlatformEmailRead' is not defined` transitório durante uma janela de hot-reload do Uvicorn (o `WatchFiles` recarregou `router.py` num instante em que `schemas.py` ainda não tinha o símbolo aplicado) — não reproduzível, confirmado com `POST /platform/settings/email` retornando `200` direto na API.

Na tentativa seguinte, o usuário recebeu `{"detail":"unauthorized"}` cru na tela. Esse era um bug real: o access token da plataforma vive 30min, e o proxy client-side `admin/app/api/proxy/[...path]/route.ts` (usado por toda mutação client-side do painel) não tentava renovar via refresh token como o `platformFetch` (usado no SSR, em `lib/api.ts`) já fazia — qualquer sessão aberta por mais de 30min quebrava todas as mutações com esse JSON cru na tela.

- **Corrigido**: `tryRefreshToken()` de `lib/api.ts` exportado e reaproveitado no proxy — na primeira resposta `401`, tenta renovar e repete a chamada original antes de desistir.
- **Duplicação eliminada**: as 4 cópias quase idênticas de `apiFetch()` (`tenants-client.tsx`, `users-client.tsx`, `usage-client.tsx`, `email-settings-form.tsx`) e o fetch cru em `support-client.tsx` foram substituídas por uma única `apiFetch()` em `admin/lib/client-fetch.ts`, que agora redireciona para `/login` quando a sessão realmente expirou (refresh token também vencido/inválido), em vez de deixar o JSON de erro na tela.
- Validado com `tsc --noEmit` + `next build` limpos; commit `503e8308`.

## 2026-07-13 — Botão de teste de envio para o Brevo por tenant

Pedido do usuário: "configura o brevo nos tenant tb, olha a documentação oficial". Investigação mostrou que a configuração de Brevo por tenant **já existia completa** (backend `/settings/brevo` em `api/app/domain/settings/router.py`, tabela `company_settings`, já consumida por `notifications.py`; frontend na aba Integrações de `/configuracoes` no `web/`) e que a implementação (`api/app/integrations/brevo.py`) já batia com a documentação oficial (`developers.brevo.com`): header `api-key`, `POST https://api.brevo.com/v3/smtp/email`, payload `sender`/`to`/`subject`/`htmlContent`.

O que faltava — confirmado com o usuário via pergunta direta, dado que "configurar o Brevo" é ambíguo (feature vs. credenciais reais vs. validação de domínio) — era um botão de teste de envio, no mesmo padrão que a Evolution API já tinha (`/settings/evolution/test`), mas que nunca tinha sido implementado para Brevo nem exposto no frontend de nenhum dos dois.

- **Backend**: `POST /settings/brevo/test` (`api/app/domain/settings/router.py`) — usa a config já salva (não aceita credenciais no body), `422 not_configured` se a empresa não configurou ainda, `502 send_failed` com o status HTTP da Brevo se o envio for rejeitado.
- **Frontend**: nova action `testBrevoSettings` em `web/app/actions.ts`; `BrevoSettingsSection` (`web/components/settings-sections.tsx`) ganhou uma seção "Testar envio" com campo de e-mail de destino, que só aparece quando `has_credentials` é `true`.
- **Validação end-to-end real**: `docker compose up -d web` (o container não estava rodando), depois skill `run-web` (Playwright headless) — login, salvar config Brevo fake, seção "Testar envio" aparece, clicar "Enviar teste" mostra `Falha ao enviar o e-mail de teste — confira a API key e o remetente.` sem quebrar a tela (chave inválida rejeitada pela Brevo real, como esperado). Testado também direto via `curl` contra a API: `422` sem config, `502` com chave fake (`status: 401` vindo da Brevo). Dados de teste limpos do tenant demo ao final (`api_key`/`from_address`/`from_name` vazios).
- **Achado não corrigido**: `save_brevo`/`save_evolution` retornam `has_credentials: true` incondicionalmente na resposta do `POST`, mesmo quando os campos salvos são vazios — só o `GET` seguinte reporta corretamente `has_credentials: false` (checa truthiness do valor salvo). Descoberto ao limpar os dados de teste; não corrigido por estar fora do escopo pedido, registrado para retomada futura.
- Documentação: `docs/api-reference.md` (novo endpoint) e `docs/plataforma-saas.md`.
