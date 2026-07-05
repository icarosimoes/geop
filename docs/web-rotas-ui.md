# Web — rotas e estados

## Estado atual

| Rota | Tipo | Estado | Dados |
| --- | --- | --- | --- |
| `/` | entrada | redireciona conforme cookie tenant | sessão server-side |
| `/login` | autenticação tenant | operacional | API `/auth/login` |
| `/dashboard` | dashboard autenticado | operacional | métricas reais via API `/dashboard/metrics` |
| `/ocorrencias` | lista e CRUD | CRUD via API, campo Local via select de cadastros | API `occurrences` + `registries` isolada por tenant |
| `/reunioes` | lista e CRUD | CRUD via API + mutações server-side | API `meetings` (tabela dedicada) isolada por tenant |
| `/relatorios-turno` | lista e CRUD + pendências inline | CRUD via API + seção HandoffSection integrada | API `shift-reports` + `handoffs` isolada por tenant |
| `/inspecoes` | tela dedicada com abas | Inspeções: CRUD com checklist 30 itens + payload completo. Checklists: CRUD de templates com itens | API `modules/inspecoes` + `checklists/templates` |
| `/solicitacoes-fiscais` | lista, formulário condicional, SLA, anexos e tratativa | CRUD via API + mutações server-side | API `fiscal_requests` isolada por tenant |
| `/ordens-servico` | Kanban com drag-and-drop | CRUD + transições + categorias via select | API `work-orders` + `work-orders/categories` isolada por tenant |
| `/preventivas` | lista e CRUD | CRUD via API + geração automática de OS | API `preventive-plans` isolada por tenant |
| `/mural` | cartões e CRUD | CRUD via API + mutações server-side | API `bulletin` (tabela dedicada) isolada por tenant |
| `/cadastros/setores` | CRUD simples | registries categoria Setor | API `registries` |
| `/cadastros/locais` | CRUD simples | registries categoria Local, com latitude/longitude/raio de geofencing no formulário | API `registries` |
| `/cadastros/funcoes` | CRUD simples | registries categoria Função | API `registries` |
| `/cadastros/procedimentos` | lista, CRUD e anexos | CRUD via API + upload/download de anexos | API `procedures` + `attachments` |
| `/cadastros/categorias-os` | CRUD de categorias | gerencia categorias de OS via settings | API `settings/work-order-categories` + `work-orders/categories` |
| `/cadastros/funcionarios` | lista, CRUD, avatar, importação em lote e reset de PIN | CRUD via API + upload de avatar + botão "Resetar PIN" do Portal do Colaborador | API `employees` + `employees/import` + `timeclock/employees/{id}/pin/reset` |
| `/cadastros/turnos` | CRUD de turnos | templates de turno reutilizáveis (Manhã, Tarde, 12x36, etc.) | API `timeclock/shifts` |
| `/cadastros/escalas` | calendário de escala | atribuição de turnos/folgas por funcionário e data | API `timeclock/schedule` |
| `/ponto` | batidas | listagem e lançamento manual de pontos | API `timeclock/punches` |
| `/ponto/dispositivos` | CRUD de relógios | dispositivos Control iD autenticados por webhook token | API `timeclock/devices` |
| `/ponto/vinculos` | vínculos | associa matrícula do relógio a um funcionário | API `timeclock/enrollments` |
| `/ponto/ajustes` | fila de aprovação | ajustes de ponto solicitados pelo Portal do Colaborador, aprovar/rejeitar | API `timeclock/adjustments` |
| `/ponto/banco-de-horas` | saldo por funcionário | busca funcionário, recalcula período, lança saldo inicial | API `timeclock/hour-bank` |
| `/usuarios` | lista e CRUD + convite | CRUD via API + convite por e-mail + upload avatar | API `users` + `users/invite` isolada por tenant |
| `/perfis` | gestão de perfis de acesso | CRUD de roles com checkboxes de permissões | API `roles` + `roles/permissions` isolada por tenant |
| `/configuracoes` | tela unificada com 3 abas | Estabelecimento + Integrações (Brevo/Evolution) + Minha conta | API `settings/company` + `settings/brevo` + `settings/evolution` + `users/me` |
| `/definir-senha` | definição de senha (público) | formulário público ativado por token de convite | API `auth/set-password` |

Rotas ocultas do menu (acessíveis via URL): `/diarios-obra`, `/manutencao`, `/estoque`, `/checklists`, `/pendencias`, `/minha-conta`, `/procedimentos`.

## Painel administrativo (`admin/`)

| Rota | Estado | Dados |
| --- | --- | --- |
| `/login` | operacional | autenticação da plataforma |
| `/dashboard` | operacional | métricas, tenants e planos da API |

O admin é uma aplicação separada em `:3001`; a sessão usa cookie `httpOnly` e não compartilha o JWT do tenant.

Todos os módulos operacionais possuem CRUD completo via API com mutações server-side, paginação server-side (20 por página) e busca via query params na URL. O dashboard exibe métricas agregadas em tempo real (ocorrências abertas, solicitações fiscais, concluídos no mês, equipe ativa, KPIs avançados e atividades recentes). Reuniões, relatórios de turno e mural possuem endpoints dedicados (`/meetings`, `/shift-reports`, `/bulletin`). Módulos genéricos remanescentes (inspeções, diários de obra, manutenção) usam a tabela `module_records` via `/modules/{slug}`.

## Integração com a API

Todas as rotas operacionais estão integradas com a API. A tabela abaixo lista o endpoint correspondente:

| Rota | Endpoint API |
| --- | --- |
| `/dashboard` | `GET /dashboard/metrics` |
| `/ocorrencias` | `GET/POST/PATCH/DELETE /occurrences` |
| `/solicitacoes-fiscais` | `GET/POST/PATCH/DELETE /fiscal-requests` |
| `/usuarios` | `GET/POST/PATCH/DELETE /users` + `POST /users/invite` + `POST /users/{id}/avatar` + `GET /roles` + `GET /registries?category=setor` |
| `/perfis` | `GET/POST/PATCH/DELETE /roles` + `GET /roles/permissions` |
| `/definir-senha` | `POST /auth/set-password` |
| `/procedimentos` | `GET/POST/PATCH/DELETE /procedures` + `POST/GET/DELETE /attachments` |
| `/cadastros` | `GET/POST/PATCH/DELETE /registries` |
| `/reunioes` | `GET/POST/PATCH/DELETE /meetings` + subjects + clone |
| `/relatorios-turno` | `GET/POST/PATCH/DELETE /shift-reports` |
| `/inspecoes` | `GET/POST/PATCH/DELETE /modules/inspecoes` |
| `/diarios-obra` | `GET/POST/PATCH/DELETE /modules/diarios-obra` |
| `/manutencao` | `GET/POST/PATCH/DELETE /modules/manutencao` |
| `/mural` | `GET/POST/PATCH/DELETE /bulletin` |
| `/ordens-servico` | `GET/POST/PATCH/DELETE /work-orders` + `POST /work-orders/{id}/transition/{status}` |
| `/preventivas` | `GET/POST/PATCH/DELETE /preventive-plans` + `POST /preventive-plans/generate` |
| `/checklists` | `GET/POST/PATCH/DELETE /checklists/templates` + `GET /checklists/executions` + toggle/complete/generate |
| `/estoque` | `GET/POST/PATCH/DELETE /stock/items` + `POST/GET /stock/movements` |
| `/pendencias` | `GET/POST/PATCH/DELETE /handoffs` + `POST /handoffs/{id}/read` + `POST /handoffs/{id}/resolve` + `GET /handoffs/pending` |

## Workspace tabs (removido)

O componente `WorkspaceTabs` (abas dinâmicas no topbar estilo browser tabs) foi removido da UI em 2026-06-20. O código e o CSS foram arquivados em `aloji/docs/agentes/jarvis-workspace-tabs.md` para reutilização em outros projetos da Solid.

## Layout unificado — `AppLayout`

Desde 2026-06-20, todas as telas usam um shell único (`components/app-layout.tsx`) que fornece:

| Elemento | Detalhe |
| --- | --- |
| Sidebar | Colapsável, navegação unificada, active state por `usePathname()` |
| Ações flutuantes | Sino (notificações) + avatar (perfil) posicionados fixos no canto superior direito, sem barra |
| Menu mobile | Hamburger fixo no canto superior esquerdo (≤ 860px) |
| Drawers | Notificações e perfil (com logout) em todas as telas |

`DashboardShell` e `OperationalModule` agora renderizam apenas o conteúdo interno. A sidebar, os drawers e as ações de topo são responsabilidade do `AppLayout` que envolve os dois nas páginas.

## Design tokens

O `globals.css` utiliza um sistema de design tokens para garantir consistência visual em todas as telas. Os tokens disponíveis são:

| Categoria | Tokens | Exemplo |
| --- | --- | --- |
| Cores | `--blue`, `--blue-hover`, `--blue-soft`, `--blue-focus`, `--orange`, `--green`, `--purple`, `--ink`, `--muted`, `--label`, `--hover`, `--field-bg`, `--field-border`, `--red`, `--yellow` | `color: var(--label)` |
| Espaçamento | `--sp-1` (4px) a `--sp-7` (32px) | `padding: var(--sp-4)` |
| Raios | `--radius-sm` (7px), `--radius-md` (9px), `--radius-lg` (14px), `--radius-xl` (18px), `--radius-pill` (999px) | `border-radius: var(--radius-md)` |
| Sombras | `--shadow-sm`, `--shadow-md`, `--shadow-lg`, `--shadow-xl`, `--shadow-button`, `--shadow-drawer`, `--shadow-modal` | `box-shadow: var(--shadow-md)` |
| Tipografia | `--font-xs` (10px), `--font-sm` (12px), `--font-base` (13px), `--font-md` (16px), `--font-lg` (20px), `--font-xl` (31px) | `font-size: var(--font-base)` |
| Componentes | `--btn-height` (40px), `--btn-icon-size` (36px), `--input-height` (44px), `--sidebar-width` (248px), `--topbar-height` (68px, usado na brand-row da sidebar) | `height: var(--btn-height)` |
| Transição | `--transition` (.2s ease) | `transition: background var(--transition)` |

Todo novo CSS deve usar esses tokens em vez de valores hardcoded.

## Padrão obrigatório de tela

Toda lista tem título, contador, ação principal, filtros, tabela/cartões responsivos, paginação e estados de carregamento, vazio, erro e permissão. Exclusões exigem confirmação; ações exibem feedback. Ações sem permissão não aparecem e continuam bloqueadas na API.

## Cadastros (setores, locais, funções, estabelecimento)

Cadastros são registros simples (nome + categoria fixa). Diferente dos módulos operacionais, clicar na linha da tabela abre diretamente o modal de edição — não o drawer de detalhes com status, tratativa e descrição. Isso porque cadastros não possuem timeline, descrição ou fluxo de tratativa; são entidades auxiliares de CRUD puro.

O formulário de cadastro contém o campo "Nome" em todas as categorias. A categoria é determinada pela sub-rota (`/cadastros/setores` → Setor, `/cadastros/locais` → Local, `/cadastros/funcoes` → Função) e enviada como campo hidden. A categoria "Local" ganha três campos adicionais (latitude, longitude, raio de geofencing em metros), usados pelo Portal do Colaborador para validar a batida de ponto por proximidade — ver [portal-colaborador.md](portal-colaborador.md#geofencing).

### Estabelecimento

A rota `/cadastros/estabelecimento` possui uma page estática dedicada (`web/app/cadastros/estabelecimento/page.tsx`) em vez de usar a rota dinâmica `[sub]`. Isso porque o estabelecimento não é um registry — usa layout `company` com o componente `CompanySettingsSection`, que exibe e edita os dados cadastrais do tenant (nome, e-mail, CNPJ, fuso horário). A rota estática tem prioridade sobre a dinâmica no Next.js.

## Tratativa (timeline de conversa)

Todo registro operacional possui uma timeline de tratativa (`history`) no estilo de conversa de ticket. A thread aparece em dois lugares:

- **Drawer de detalhes**: exibida abaixo dos dados do registro, com campo de comentário para adicionar mensagens.
- **Modal de edição**: exibida abaixo do formulário (somente leitura, sem campo de comentário), para que o usuário veja o histórico completo enquanto edita.

Cada entrada possui:

| Campo | Conteúdo |
| --- | --- |
| `type` | `comment` (mensagem livre), `change` (edição de campos), `create` (criação), `delete` (exclusão), `attachment_add` (anexo adicionado) ou `attachment_remove` (anexo removido) |
| `user` | Nome do usuário que realizou |
| `date` | Data e hora no formato `dd/mm/aaaa hh:mm` |
| `message` | Texto do comentário (em `comment`), mensagem de sistema (em `create`, `delete`, `attachment_add`, `attachment_remove`) |
| `changes` | Diferenças campo a campo (só em `change`) |

Visual por tipo:

| Tipo | Avatar | Conteúdo |
| --- | --- | --- |
| `comment` | azul (iniciais) | balão de mensagem com texto livre |
| `change` | roxo (iniciais) | chips listando cada campo alterado com valor anterior e novo |
| `create` | verde (iniciais) | mensagem em itálico indicando a criação |
| `delete` | vermelho (iniciais) | mensagem indicando exclusão |
| `attachment_add` / `attachment_remove` | azul (iniciais) | mensagem com nome do arquivo anexado ou removido |

A timeline é alimentada pela API (`GET /timeline/{entity_type}/{entity_id}`) que lê de `audit_events`. Módulos API-backed consomem a timeline da API; módulos locais (fallback) usam `localStorage`.

## Solicitações fiscais

O protótipo atual atende solicitações da recepção para o financeiro: dados incorretos do tomador, nota travada, nota solicitada depois do check-out e cancelamento. O formulário apresenta campos condicionais de reserva, nota, CPF/CNPJ, tomador, correção, cancelamento, check-out, responsável e pessoas a notificar. A lista exibe UH, status e contagem regressiva de SLA.

### Persistência

Solicitações fiscais possuem CRUD completo via API (`POST`, `GET`, `PATCH`, `DELETE /fiscal-requests`). A criação e edição passam por server actions (`createFiscalRequestAction`, `updateFiscalRequestAction`, `deleteFiscalRequestAction`) que chamam a API com o token do cookie `tenant_token`. Após cada mutação, a página revalida via `router.refresh()`.

Campos específicos do tipo de solicitação (tomador, reserva, nota, CPF/CNPJ, correção, cancelamento, etc.) são enviados no campo `payload` como JSON.

A integração Chess Hotel cria solicitações via `POST /integrations/chess-hotel/tickets` autenticado por header `X-Registro-Key`.

### Limitações remanescentes

- nomes informados em “Notificar” não correspondem a IDs e não disparam notificações;
- alterações específicas do formulário fiscal (campos do payload como taxpayerDoc, invoiceNumber) ainda não aparecem como diff detalhado na timeline — o diff registra a mudança do objeto `payload` como um todo.
