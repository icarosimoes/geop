# Memória do projeto

## 2026-07-04 — Portal do Colaborador: namespace de token separado por design

Decisão: o `Employee` (cadastro de RH) nunca ganhou uma extensão do token `access` de
`User` — foi criado um tipo de JWT novo e paralelo (`employee_session`, sem
`permissions`/`role_id`), com dependency própria (`require_employee_session`) que rejeita
qualquer outro tipo de token, e vice-versa. Testado explicitamente nos dois sentidos.

Motivos:

- `Employee` é puramente RH (nem todo funcionário tem `User`/login); misturar os dois
  namespaces de auth criaria risco de escalada de privilégio caso um token vazasse.
- O caso de uso (bater ponto, ver escala, baixar contracheque) nunca deveria abrir acesso a
  nenhuma rota administrativa da API, mesmo que o mesmo `secret` JWT seja reaproveitado.

Como aplicar: qualquer nova funcionalidade de autoatendimento do colaborador deve entrar
sob `require_employee_session`/`timeclock/mobile`, nunca sob `require_permission`. PIN
numérico curto (não senha forte) foi aceito conscientemente para esse token de baixo
escopo e TTL curto (60min, sem refresh) — não é o padrão a seguir se um recurso futuro do
Portal do Colaborador expuser dados mais sensíveis. Ver [portal-colaborador.md](portal-colaborador.md).

## 2026-06-19 — Arquitetura de modernização

Decisão: migrar gradualmente para FastAPI + Next.js App Router. As regras Jarvis aplicáveis foram adaptadas e versionadas em `docs/agentes/`; o Aloji permanece como referência de origem.

Motivos:

- alinhar o Registro à stack moderna já usada no ecossistema Aloji;
- separar regras de negócio da camada de apresentação;
- manter o sistema operacional durante a reescrita;
- permitir que SQLAlchemy acesse o MySQL atual e, posteriormente, PostgreSQL;
- reduzir o risco de uma substituição integral em uma única entrega.

### Restrições (atualizadas em 21/06/2026)

- O Laravel V1 permanece em operação até o corte final; não foi removido.
- O PostgreSQL 17 com RLS é o banco principal desde 20/06/2026. MySQL é usado apenas para leitura do dump V1 via profile `mysql-import`.
- Um módulo terá somente um escritor por vez.
- Não haverá dual-write.

### Padrões Jarvis adotados

- Backend organizado por domínio: router, service, models e schemas.
- Router sem regra de negócio e service sem dependência de HTTP.
- Next.js com Server Components por padrão e Client Components somente para interação.
- Navegação interna com `Link`; buscas independentes executadas em paralelo.
- Validação nas fronteiras e respostas de erro estruturadas.
- Valores monetários em centavos/Decimal, nunca `float` como fonte contábil.
- Estados de carregamento, vazio, erro, sucesso e permissão em todos os fluxos.
- Documentação e registro atualizados junto das mudanças.

### Multiempresa

RLS (Row-Level Security) ativo em 24 tabelas com `company_id`. O GUC `app.current_company_id` é setado na dependency `current_user` e resetado no `finally` da session. Tabelas filhas herdam isolamento via FK CASCADE. Rotas platform (admin) não setam o GUC — o owner tem `BYPASSRLS`.

## 2026-06-19 — Nome e arquivamento da V1

- O nome da aplicação passou de Aero para **Registro**.
- A aplicação Laravel completa foi movida para `docs/v1/` e removida do índice do Git; permanece somente no ambiente local.
- A organização é apenas física: o schema e o nome do banco MySQL não foram alterados.
- A V1 deve permanecer imutável, salvo correção crítica necessária durante a transição.

## 2026-06-19 — Docker e produção

- Docker é obrigatório em todos os ambientes da nova aplicação.
- Desenvolvimento usa `docker compose`; produção usa Docker Swarm.
- Diretório padrão na VPS: `/opt/registro`.
- Imagens de produção ficam no GHCR e usam tags imutáveis baseadas no SHA completo.
- Deploy Swarm sempre usa `--with-registry-auth`, healthchecks, rolling update e rollback automático.
- Secrets do banco são fornecidos por Docker Secrets; nunca entram no repositório ou na imagem.
- O banco permanece externo à stack enquanto o Registro utilizar o MySQL legado.

## 2026-06-19 — Autenticação compatível

- A nova API autentica por leitura do `users` legado e valida hashes bcrypt do Laravel.
- Tokens HS256 carregam usuário, empresa, papel e permissões, com algoritmo fixo na validação.
- A chave JWT de produção vem do Docker Secret `registro_jwt_secret`.
- Esta etapa não cria tabelas, não altera senhas e não escreve no MySQL.

## 2026-06-19 — Documentação autossuficiente

- O padrão documental do Aloji foi adaptado ao Registro.
- Arquitetura, domínios, API, UI, desenvolvimento, segurança, backlog, legado, testes, produção e migração de banco possuem fontes de verdade próprias.
- Regras Jarvis de engenharia, layout/CRUD, performance, segurança e multiempresa foram trazidas para o repositório.
- Agentes e documentos de reservas, Channex, Asaas, CRM e financeiro não foram copiados por não pertencerem ao escopo atual.

## 2026-06-19 — Fundação SaaS comercial

- A decisão de comercializar o Registro tornou SaaS e Asaas aderentes ao produto; as regras Jarvis correspondentes passaram a integrar a documentação.
- Foi criada uma base MySQL 8.4 nova para desenvolvimento, com Alembic e seed fictício. Ela não substitui nem representa o dump Laravel.
- Tenant, operador da plataforma e seus tokens são identidades separadas.
- O painel administrativo é outra aplicação Next.js, publicada em domínio próprio no Swarm.
- Planos, assinaturas, faturas e auditoria formam o núcleo comercial; o Asaas permanece desativado até sandbox, credenciais e política comercial.
- O dump legado será restaurado em base temporária e importado por processo repetível, nunca diretamente sobre o banco novo.

## 2026-06-20 — Governança documental obrigatória

Decisão: o diretório `/docs` é a memória oficial e a fonte de verdade técnica, funcional, operacional e histórica do Registro.

- Toda informação pertinente ao desenvolvimento ou ao funcionamento do sistema deve ser registrada em `/docs`.
- Mudanças de código, banco, contrato, interface, segurança, tenant, deploy, integração, migração ou operação devem atualizar a documentação correspondente durante o mesmo trabalho.
- `backlog.md` registra trabalho pendente, prioridade, riscos encontrados e critérios de conclusão.
- `memoria-projeto.md` registra decisões duráveis, contexto e restrições que não podem depender apenas do histórico do chat ou do conhecimento de uma pessoa.
- `registro-trabalho.md` registra cronologicamente o que foi executado, validado, alterado ou identificado.
- Documentos de arquitetura, domínio, API, UI e infraestrutura devem refletir o estado implementado; funcionalidades futuras precisam ser marcadas explicitamente como planejadas.
- Correções e descobertas relevantes devem ser documentadas mesmo quando não forem implementadas imediatamente.
- Nenhuma credencial, secret, dump, dado pessoal desnecessário ou informação sensível deve ser copiada para a documentação versionada.

Essa regra passa a integrar a Definition of Done: código sem a atualização documental pertinente não é considerado concluído.

## 2026-06-20 — Revisão técnica do estado atual

- O ambiente Docker local foi validado com API, web, admin e MySQL ativos.
- O frontend passou em `typecheck` e build de produção; a API passou em 7 testes dentro do container.
- O tenant `Aero Hotel` (`aero-hotel`) possui 60 usuários e 375 ocorrências importadas no banco local.
- Foi identificado risco no login multitenant: a lista de empresas é produzida antes da validação da senha.
- A interface de ocorrências busca no máximo 100 registros e dados antigos do `localStorage` podem prevalecer sobre a API.
- Tratativas, mutações operacionais e solicitações fiscais ainda são persistidas somente no navegador.
- Anexos fiscais ainda usam Data URL/Base64 sem limites ou validação adequada e precisam migrar para armazenamento controlado pela API.
- O backlog foi atualizado com as correções de autenticação, paginação, persistência, auditoria, anexos, SLA, testes, documentação e higiene do repositório.

## 2026-06-20 — Correção do primeiro bloco crítico

- O login multitenant passou a validar a senha antes de retornar qualquer empresa.
- Quando diferentes tenants possuem o mesmo e-mail, somente usuários cuja senha confere participam da seleção; senha inválida não revela tenants.
- `company_id` opcional passou a aceitar somente inteiros positivos.
- Foram adicionados testes para tenant único, senha inválida, múltiplos tenants, senhas diferentes e seleção explícita; a suíte passou a 12 testes.
- Ocorrências passaram a consumir todas as páginas disponíveis da API, eliminando o corte nos primeiros 100 registros.
- Dados reais de ocorrências não são mais substituídos por cópias antigas do `localStorage`.
- Como mutações ainda não existem na API, ocorrências reais ficam em modo leitura e a interface comunica essa limitação.
- Para crescimento de volume, permanece planejada paginação e busca server-side sob demanda, sem hidratar todo o conjunto no Next.js.

## 2026-06-23 — Simplificação do produto e inspeções

### Reestruturação do menu lateral

O menu lateral foi simplificado de ~22 para ~16 itens:
- Diário de obra e Manutenção corretiva removidos do menu (rotas permanecem acessíveis via URL)
- Estoque ocultado do menu
- Pendências de turno absorvidas como seção dentro de Relatórios de turno (componente `HandoffSection`)
- Checklists absorvidos como aba dentro de Inspeções (aba "Checklists" em `/inspecoes?tab=checklists`)
- Procedimentos movidos de Administração para Cadastros (`/cadastros/procedimentos`)
- Usuários e Perfis de acesso movidos para Cadastros
- Configurações, Minha conta e Estabelecimento unificados em `/configuracoes` com 3 abas
- Seção "Administração" eliminada (Mural subiu para Operação)

### Inspeções — dados do payload expostos

As 4.497 conferências de suíte armazenadas em `module_records` possuem um `payload` JSON com dados que o frontend não exibia:
- `date` (data da conferência), `maid` (camareira), `obs` (observação), `location_id` (local/UH)
- `items[]` com 30 itens de checklist, cada um com `valuation` (sim/nao), `register` (observação) e `occurrence_id`

A tela de inspeções foi reescrita com componente dedicado (`InspectionViewer`) que exibe tabela com camareira, local, data, score de itens, e drawer de detalhes com checklist completo. CRUD completo implementado com formulário interativo (toggle sim/não por item).

Os nomes dos 30 itens do checklist foram extraídos do template Blade da V1 (`check_suites/create.blade.php`) e hardcoded no componente. Se os itens mudarem no Chess Hotel, o array `CHECKLIST_LABELS` em `inspection-viewer.tsx` precisa ser atualizado.

### Categorias de OS

Adicionado endpoint `GET /work-orders/categories` que retorna categorias distintas (merge entre as usadas em OS existentes e as cadastradas via `company_settings`). CRUD de categorias em `/cadastros/categorias-os`. O campo categoria nos modais de OS (Kanban) foi alterado de texto livre para `<select>` com as opções existentes + opção "Nova categoria".

### Ocorrências — campo Setor/Local

O campo "Categoria" no formulário de ocorrências foi substituído por um `<select>` de Locais (vindos de `/cadastros/locais`), que é o que a API realmente aceita como `sector_id`. O campo de texto livre "Geral" que existia antes era ignorado pela API.

### Migração V1 para produção — pontos de atenção

- **`module_records.payload`**: o endpoint genérico `/modules/{slug}` agora retorna e aceita `payload` (JSON). Ao migrar dados da V1, garantir que o campo `payload` seja populado com a estrutura `{date, maid, obs, location_id, items[]}` para inspeções.
- **`location_id` no payload de inspeções**: referencia IDs da tabela `locations` (cadastro de Locais). Se os IDs mudarem na migração, o `location_id` dentro do payload JSON precisará ser remapeado — diferente de FKs normais, o JSON não é atualizado por CASCADE.
- **Categorias de OS**: as categorias existentes (Acabamento, Elétrica, HVAC, Hidráulica) vêm do campo `work_orders.category`. Ao migrar, elas aparecem automaticamente. Categorias adicionais podem ser pré-cadastradas via `company_settings` com key `work_order_categories`.
- **Nomes dos itens de checklist**: hardcoded em `CHECKLIST_LABELS` no frontend (`web/components/inspection-viewer.tsx`). São os mesmos 30 itens do template Blade V1. Se o Chess Hotel usar itens diferentes por tipo de suíte, será necessário tornar essa lista dinâmica (ex: vindo de um `checklist_template`).

## 2026-07-12 — Painel admin: sempre tema claro, sem dark mode automático

Decisão: o `admin/` teve o bloco `@media (prefers-color-scheme: dark)` removido de
`globals.css` (junto com `Toaster theme="system"` → `theme="light"`). O painel deve
renderizar sempre no tema claro, independentemente da preferência de SO/navegador do
operador.

Motivos:

- Ninguém havia pedido dark mode; ele existia só porque o boilerplate/template original do
  Tailwind trazia a media query pronta, e ninguém tinha notado até um operador com o SO em
  modo escuro ver o painel inteiro escurecido sem ter escolhido isso.
- Um dark mode "de fábrica" sem revisão visual dedicada tende a acumular bugs de contraste
  silenciosos (o de inputs ilegíveis, corrigido na mesma sessão antes da decisão de remover
  o dark mode por completo, é um exemplo).

Como aplicar: se dark mode for pedido no futuro, ele precisa ser uma decisão de produto
explícita (com toggle manual, não `prefers-color-scheme`) e revisão visual tela a tela —
não reintroduzir a media query como atalho. `web/` e `colaborador/` não foram tocados por
esta decisão; verificar se têm o mesmo padrão antes de assumir que estão livres do problema.

## 2026-07-12 — Painel admin: preferir os componentes de `components/ui/` a reimplementações manuais

Decisão: modais, dropdowns e confirmações no `admin/` devem usar os componentes já
existentes em `components/ui/` (`Dialog`, `DropdownMenu`, e o novo `ConfirmDialog` sobre o
`Dialog`) em vez de `<div className="fixed inset-0">` e `useState`/listener de
`mousedown` feitos à mão.

Motivos:

- Os componentes Radix (`Dialog`/`DropdownMenu`) já existiam no repositório, prontos e
  testados, mas três componentes diferentes (`SidebarUserMenu`, `TopUserMenu`, o menu de
  assinatura de Empresas) reimplementaram um dropdown na mão, e três modais
  (Nova/Editar empresa, Novo/Editar usuário) reimplementaram um `Dialog` na mão — todos sem
  focus trap nem fechar com Esc.
- `confirm()`/`alert()` nativos do browser quebram a identidade visual bem no momento mais
  crítico (ações destrutivas) e não tinha padrão nenhum antes desta revisão.

Como aplicar: antes de escrever um modal/dropdown/confirmação novo no `admin/`, checar
`components/ui/` primeiro. Ver revisão completa em
[registro-trabalho.md](registro-trabalho.md#2026-07-12--revisão-uiux-ponta-a-ponta-do-painel-admin).

## 2026-07-14 — Ocorrências fundida em Ordens de Serviço; padrão de CRUD unificado

Decisão: o domínio "Ocorrências" (tabela `occurrences`) deixou de existir como entidade
separada — foi fundido em "Ordens de Serviço" (`work_orders`), a pedido explícito do
usuário ("quero que ocorrencias e ordem de serviços sejam uma tela só"). A tabela
`occurrences` foi **dropada sem migrar dados de nenhum tenant** (autorização explícita:
"não se preocupe com dados atuais em nehum dos tenant"). `work_orders` ganhou os campos
que só existiam em Ocorrência (`sector_id`, `unit`, `comments`, `deadline`) e uma tabela
`work_order_participants` (M2M), além de absorver export XLSX, export PDF e clone. A tela
`/ordens-servico` manteve o Kanban como padrão e ganhou um toggle para visão em Lista. O
rótulo do status `aguardando_material` virou "Aguardando" (cobre qualquer tipo de espera,
não só material — chave do enum não mudou).

Motivos:

- Os dois domínios resolviam o mesmo problema de negócio (abrir, atribuir e acompanhar uma
  situação operacional até a resolução) com telas, permissões e integrações
  (dashboard/relatórios/timeline/anexos/notificações) totalmente duplicadas.
- `work_orders` foi escolhida como tabela sobrevivente por já ter a máquina de estados de
  5 status, SLA e o Kanban — mais rica que o status fixo de 3 valores (inteiro) de
  `Occurrence`.

Consequências e limitações conhecidas (aceitas, não são bugs a corrigir):

- Papéis customizados de tenants que tinham `occurrence.*` concedido explicitamente
  **não ganharam `work_order.*` automaticamente** na migration — só perderam o acesso
  antigo (permissões `occurrence.*` foram removidas de `permissions`/`role_permissions`).
  Ver [usuarios-perfis.md](usuarios-perfis.md#perfis-pré-definidos-seed).
- `api/app/import_v1.py` (importação do MySQL legado V1) foi deletado — o corte/migração
  de dados da V1 já havia sido descontinuado por decisão de 2026-07-04 (não migrar mais
  dados do sistema legado para nenhum tenant), então o script já estava morto (sem
  nenhum router/startup chamando-o) antes mesmo da fusão; ele só criava `Occurrence`, que
  não existe mais.
- Os campos de resposta `open_occurrences`/`my_occurrences` em `GET /dashboard/metrics`
  **mantiveram o nome** por decisão explícita (reduzir churn no contrato), mas agora são
  calculados a partir de `WorkOrder`, não de `Occurrence`. Ver
  [api-reference.md](api-reference.md#dashboard).

Como aplicar: qualquer nova funcionalidade de "ocorrência"/"chamado"/"solicitação de
manutenção" no vocabulário do usuário deve ser modelada como Ordem de Serviço — não
recriar um domínio paralelo. Ver detalhamento completo da execução em
[registro-trabalho.md](registro-trabalho.md#2026-07-14--fusão-de-ocorrências-em-ordens-de-serviço-e-padronização-de-crud).

## 2026-07-04 — Corte V1 descontinuado

Decisão: não migrar mais dados do sistema legado V1 (Laravel/MySQL) para nenhum tenant.
O corte de dados via `api/app/import_v1.py` deixou de ser um fluxo ativo — o script não é
chamado por nenhum router, startup ou comando documentado desde então, e ficou excluído do
coverage de testes (`api/pyproject.toml`). Ele só existia no repositório como referência
histórica até ser deletado em 2026-07-14 (ver entrada acima), quando passou a depender de
`Occurrence`, um model removido.

Como aplicar: não reintroduzir rotas ou automações de importação da V1. Novos tenants
nascem vazios; se um cliente pedir migração de dados do sistema antigo, é uma decisão de
produto nova, não uma retomada do fluxo antigo.
