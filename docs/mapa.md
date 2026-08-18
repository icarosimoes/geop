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
| Swarm | produção ativa em `geop.solidsd.com.br`, `api.geop.solidsd.com.br` e `painel.geop.solidsd.com.br` | GHCR + Traefik + secrets externos |
| Cache | Redis com TTL, invalidação por tenant e readiness | dashboard e permissões |
| ACL | 35 permissões, roles por empresa, wildcard `*` | seed + CRUD via `/roles` |
| Solicitações fiscais | CRUD via API + SLA + anexos MinIO | `fiscal_requests` isolada por tenant |
| Inspeções/Obra | check suites, inspection suites, vistorias V2, auditorias, diário de obra | tabelas dedicadas com RLS |
| Reuniões | tabela dedicada com participantes, pautas e ata PDF | `meetings` + filhas |
| Relatórios de turno | tabela dedicada com filtro por data e turno | `shift_reports` |
| Ordens de serviço | CRUD + workflow de 5 estados + Kanban com drag-and-drop e toggle para visão em Lista. Absorveu "Ocorrências" em 2026-07-14 (participantes, export XLSX/PDF, clone, setor/unidade/prazo/comentários) | `work_orders` com RLS |
| Manutenção preventiva | planos recorrentes (daily→annual) com geração automática de OS | `preventive_plans` |
| Checklists recorrentes | templates com itens, execuções automáticas, toggle individual, conclusão | `checklist_templates` + `checklist_executions` |
| Dashboard KPIs | indicadores avançados de OS e fiscais + tendência 7 dias | `/dashboard/metrics` expandido |
| Estoque e materiais | itens com entrada/saída/ajuste, vínculo com OS, alerta mínimo | `stock_items` + `stock_movements` |
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
| Portal do Colaborador (PWA) | `colaborador/app/`, `colaborador/lib/` — app Next.js independente, sem menu do GEOP |
| Agente Go de ponto (relógio físico) | `agent/` — ponte local entre o relógio Control iD (LAN) e o webhook do GEOP |
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
- Geofencing de `Local` (latitude/longitude/raio) editável em `/cadastros/locais`; reset de PIN do Portal do Colaborador direto em `/cadastros/funcionarios`
- Banco de horas (cálculo por escala x pontos batidos, saldo inicial migrável) e ajuste de ponto com aprovação do RH, com solicitação pelo Portal do Colaborador — ver [escala-de-trabalho.md](escala-de-trabalho.md#banco-de-horas-e-ajuste-de-ponto-2026-07-05)
- Relatórios de ocorrências por período e SLA de solicitações fiscais (`/relatorios`), sem exportação ainda
- Abono de ponto (lançado direto pelo RH, sem aprovação), estatísticas de ajuste de ponto e notificações in-app conectadas ao sino (clique navega para a tela de origem) — ver [escala-de-trabalho.md](escala-de-trabalho.md#abono-de-ponto-espelho-de-ponto-e-notificações-2026-07-06)
- Espelho de ponto (`/ponto/espelho`): grade diária com batidas, crédito/débito, hora extra 50%/100% (considerando feriados cadastrados) e adicional noturno com hora reduzida da CLT, exportável em Excel/PDF por funcionário; filtro por Setor gera um card por funcionário ativo do setor — ver [escala-de-trabalho.md](escala-de-trabalho.md#feriados-2026-07-06)
- Feriados (`/ponto/feriados`): CRUD simples por tenant, usado no cálculo de HE 100% — ver [escala-de-trabalho.md](escala-de-trabalho.md#feriados-2026-07-06)
- Hora extra paga em dinheiro (toggle em `/configuracoes` → Ponto): salário individual do funcionário ou salário-base por cargo, valor em R$ da HE 50%/100% no espelho de ponto, banco de horas para de bancar a HE quando ligado — ver [escala-de-trabalho.md](escala-de-trabalho.md#hora-extra-paga-em-dinheiro-2026-07-06)

### Planejado / pendente de produção

- Corte do Laravel — depende de dump atualizado + inventário de anexos físicos
- Inventário de anexos/volumes fora do banco na V1
- Dump MySQL atualizado do servidor V1

### Limitações conhecidas

- Inspeções (4497) permanecem em `module_records` — frontend usa endpoint genérico `/modules/inspecoes`
- Auditorias noturnas (104 registros) permanecem em `module_records` com slug `manutencao` — são dados legados, não manutenção real
- Manutenção real usa tabela dedicada `maintenance_records` (endpoint `/maintenance`); mural usa `bulletin_posts` (endpoint `/bulletin`)
- Diário de obra sem dados V1 (tabela vazia)
- Solicitações fiscais sem dados V1 (apenas criáveis manualmente)
- Suíte de testes (`api/tests/`) roda contra o mesmo banco de desenvolvimento (sem `TEST_DATABASE_URL` isolado) — acumula dados a cada execução e colide com o seed fictício de ponto em datas hardcoded (ver [escala-de-trabalho.md](escala-de-trabalho.md#abono-de-ponto-espelho-de-ponto-e-notificações-2026-07-06))
- Espelho de ponto: HE 100% não considera feriados (sem calendário integrado); adicional noturno é um adicional simples de 20%, sem a "hora noturna reduzida" da CLT; filtro por um colaborador por vez (sem Equipe/Departamento/Todos)
