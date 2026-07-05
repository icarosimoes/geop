# Mapa do sistema

## Estado em 21/06/2026

| Área | Estado | Fonte de dados |
| --- | --- | --- |
| Docker local | operacional | Compose (PostgreSQL + Redis + MinIO + API + Web + Admin) |
| PostgreSQL 17 | ativo com RLS em 24 tabelas, asyncpg | banco principal |
| FastAPI | health, auth, dashboard, CRUD de todos os domínios operacionais + ordens de serviço com workflow | PostgreSQL via SQLAlchemy async |
| Next.js | portal autenticado, todos os módulos operacionais e dashboard com dados reais | todos os módulos via API |
| Painel admin | sidebar Jarvis, dashboard com stat cards, CRUD de empresas, planos, auditoria | Tailwind 4 + Lucide + API plataforma |
| SaaS/Billing | tenants, planos, assinaturas, faturas, lifecycle trial→suspended | Asaas sandbox + webhook idempotente |
| Asaas | AsaasClient async, webhook autenticado, reconciliação periódica | sandbox configurado |
| Laravel V1 | 66 tabelas restauradas em staging | dump local (MySQL via profile `mysql-import`) |
| Swarm | produção ativa em `registro.solidsd.com.br`, `api.registro.solidsd.com.br` e `painel.registro.solidsd.com.br` | GHCR + Traefik + secrets externos |
| Cache | Redis com TTL, invalidação por tenant e readiness | dashboard e permissões |
| ACL | 35 permissões, roles por empresa, wildcard `*` | seed + CRUD via `/roles` |
| Solicitações fiscais | CRUD via API + integração Chess Hotel + SLA + anexos MinIO | `fiscal_requests` isolada por tenant |
| Integração Chess Hotel | launcher no navbar do Chess enviando para API do Registro | `POST /integrations/chess-hotel/tickets` |
| Inspeções/Obra | check suites, inspection suites, vistorias V2, auditorias, diário de obra | tabelas dedicadas com RLS |
| Reuniões | tabela dedicada com participantes, pautas e ata PDF | `meetings` + filhas |
| Relatórios de turno | tabela dedicada com filtro por data e turno | `shift_reports` |
| Ordens de serviço | CRUD + workflow de 5 estados + Kanban com drag-and-drop | `work_orders` com RLS |
| Manutenção preventiva | planos recorrentes (daily→annual) com geração automática de OS | `preventive_plans` |
| Checklists recorrentes | templates com itens, execuções automáticas, toggle individual, conclusão | `checklist_templates` + `checklist_executions` |
| Dashboard KPIs | indicadores avançados de OS, ocorrências e fiscais + tendência 7 dias | `/dashboard/metrics` expandido |
| Estoque e materiais | itens com entrada/saída/ajuste, vínculo com OS e ocorrências, alerta mínimo | `stock_items` + `stock_movements` |
| Pendências de turno | handoff estruturado com leitura e resolução, direcionável por turno/data | `shift_handoffs` |
| Ponto eletrônico (relógio físico) | Control iD via webhook + agente Go de ponte local (bridge LAN→nuvem) | `timeclock` + `agent/` |
| Portal do Colaborador (PWA) | login por PIN (token isolado de `User`), bater ponto com geofencing, escala, contracheque | `timeclock/mobile` + `colaborador/` |

## Caminhos

| Área | Caminho |
| --- | --- |
| API | `api/app/` |
| testes API | `api/tests/` |
| Web | `web/app/`, `web/components/` (`app-layout.tsx` é o shell unificado; `dashboard-shell.tsx` e `operational-module.tsx` renderizam apenas conteúdo) |
| Admin SaaS | `admin/app/`, `admin/lib/` |
| Portal do Colaborador (PWA) | `colaborador/app/`, `colaborador/lib/` — app Next.js independente, sem menu do Registro |
| Agente Go de ponto (relógio físico) | `agent/` — ponte local entre o relógio Control iD (LAN) e o webhook do Registro |
| Compose | `docker-compose.yml` |
| Swarm | `docker-stack.yml` |
| legado local | `docs/v1/` |
| CI | `.github/workflows/ci.yml` |
| ADRs | `docs/adr/` |
| documentação | `docs/` |

## Ordem de migração

| Prioridade | Domínio | Estado novo |
| --- | --- | --- |
| 1 | autenticação, usuários, perfis, ACL e empresas | núcleo V1 importado, ACL com 35 permissões |
| 2 | setores, locais, funções e procedimentos | importado, CRUD completo |
| 3 | ocorrências | CRUD completo, participantes, clone, PDF, soft delete |
| 4 | reuniões | tabela dedicada, participantes, pautas, clone, ata PDF |
| 5 | relatórios de turno | tabela dedicada, filtro por data/turno |
| 6 | inspeções e auditorias | check suites, inspection suites, vistorias V2, audit reports — tabelas dedicadas |
| 7 | diário de obra | tabela dedicada com 4 filhas (activities, teams, equipment, observations) |
| transversal | anexos | MinIO (S3-compatible), validação de tamanho/tipo/quantidade |
| transversal | PDF e Excel | reportlab (PDF), openpyxl (Excel) |
| transversal | notificações | in-app com preferências por usuário/módulo, Brevo para email |
| transversal | auditoria (`audit_events`) | operacional em todos os domínios, diff JSON campo a campo |

## Contratos críticos

IDs e relacionamentos existentes, hashes Laravel, status/soft delete, `company_id`, `role_id`, ACL, anexos e formatos operacionais de exportação devem ser preservados até um corte explicitamente validado.

## Acesso de desenvolvimento

Login: `demo@aerohotel.local` / `Registro@123` (tenant Aero Hotel, admin com wildcard `*`).

## Funcionalidades implementadas vs planejadas

### Implementado e operacional

- Auth JWT multitenant com refresh, ACL e 35 permissões
- Todos os domínios operacionais com CRUD completo (ocorrências, reuniões, turnos, inspeções, obra, fiscais)
- Reuniões e turnos em tabelas dedicadas (`meetings`, `shift_reports`)
- `import_v1.py` grava diretamente em tabelas dedicadas (reuniões, turnos)
- Integração Evolution (WhatsApp) — configuração + envio real + status de conexão
- Notificações multicanal: in-app + e-mail (Brevo) + WhatsApp (Evolution)
- Anexos via MinIO com validação completa
- Auditoria imutável com diff JSON
- 70 testes automatizados (SLA, CRUD, cross-tenant, anexos, auditoria)
- RLS em 25 tabelas PostgreSQL (inclui `work_orders`)
- Ordens de serviço com workflow de 5 estados, Kanban com drag-and-drop, criação, exclusão e transições auditadas
- Portal do Colaborador: ponto por geolocalização, escala e contracheque via PWA dedicado (`colaborador/`), com auth por PIN e token isolado do login de `User` (ver [portal-colaborador.md](portal-colaborador.md))
- Agente Go de ponte local (`agent/`) para relógio de ponto Control iD (ver [relogios-de-ponto-catalogo.md](relogios-de-ponto-catalogo.md))
- Cadastro de usuários e perfis de acesso movido para dentro de `/configuracoes` (abas "Usuários" e "Perfis de acesso"), saindo do submenu "Cadastros" da sidebar
- Toda empresa nova já recebe 6 turnos padrão pré-cadastrados (Manhã, Tarde, Noite, Comercial, 12x36 Diurno/Noturno) — ver [escala-de-trabalho.md](escala-de-trabalho.md)

### Planejado / pendente de produção

- Corte do Laravel — depende de dump atualizado + inventário de anexos físicos
- Inventário de anexos/volumes fora do banco na V1
- Dump MySQL atualizado do servidor V1

### Limitações conhecidas

- Inspeções (4497) permanecem em `module_records` — frontend usa endpoint genérico `/modules/inspecoes`
- Auditorias noturnas (104 registros) permanecem em `module_records` com slug `manutencao` — são dados legados, não manutenção real
- Manutenção real usa tabela dedicada `maintenance_records` (endpoint `/maintenance`); mural usa `bulletin_posts` (endpoint `/bulletin`)
- Diário de obra sem dados V1 (tabela vazia)
- Solicitações fiscais sem dados V1 (apenas criáveis manualmente ou via integração Chess)
