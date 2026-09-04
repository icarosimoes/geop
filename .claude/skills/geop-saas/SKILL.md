---
name: geop-saas
description: Skill de padrões SaaS multi-tenant do GEOP — RLS via GUC do Postgres com 3 roles (registro/registro_app/registro_platform), isolamento por company_id, painel admin da plataforma (admin/), planos/assinaturas (Plan/Subscription/Invoice). Use ao criar ou auditar qualquer rota que toque tabela com RLS, ao trabalhar no painel admin, ou ao mexer em ordem de commit/GUC dentro de um handler. TRIGGER quando o usuário menciona "RLS", "multi-tenant", "tenant isolation", "painel admin", "platform", "assinatura", "plano", "GUC", "current_company_id".
---

Adaptado dos agentes `jarvis-saas` do erpsolid/Aloji, **reescrito com os mecanismos reais do
GEOP** — o GEOP tem sua própria arquitetura de RLS (3 roles Postgres), diferente das duas
referências. Não porte `bypass_rls()`/`skip_tenant_filter` dos outros projetos sem verificar
— não existem aqui como estão lá.

---

## Como o isolamento funciona AQUI

Três roles Postgres (migration `20260831_0070_restricted_app_db_role.py`,
`docs/infra/role-restrita-postgres.md`):

| Role | BYPASSRLS | Uso |
|---|---|---|
| `registro` | (superusuário histórico) | só migrations Alembic — nunca usado por request |
| `registro_app` | NOBYPASSRLS | rotas de tenant — depende do GUC `app.current_company_id` pra RLS filtrar |
| `registro_platform` | BYPASSRLS | só rotas `/platform/*` — precisam ver todos os tenants por design |

`set_tenant_context(session, company_id)` (`api/app/core/rls.py`) roda
`SELECT set_config('app.current_company_id', :cid, false)` — **precisa ser chamado antes de
qualquer query numa tabela com `FORCE ROW LEVEL SECURITY`**, a partir de um `company_id` já
validado (claim de JWT com assinatura verificada). `RESET app.current_company_id` no
`finally` de `require_session`/`require_employee_session` (`api/app/core/dependencies.py`)
limpa o GUC antes da conexão voltar pro pool.

### ⚠️ Achado real (2026-08-31): `is_local` errado é fail-closed silencioso

`is_local=false` no `set_config` é **obrigatório** — escopo de sessão, não de transação. Um
`SET LOCAL`/`is_local=true` some no primeiro `commit()`; qualquer query em tabela RLS numa
transação seguinte da mesma request volta a falhar com "unrecognized configuration
parameter" (fail-closed: quebra a rota, não vaza dado). Esse exato bug já apareceu **duas
vezes** no GEOP:
1. Em `set_tenant_context`/`require_session` (produção) — corrigido junto do rollout dos 3
   roles.
2. Em `tests/conftest.py` (harness de teste, achado numa sessão *depois* — não tinha sido
   replicado lá) — 123 falhas de suíte viraram 65 só com esse fix (o resto eram dados órfãos
   de execuções anteriores, não regressão).

**Se aparecer `InsufficientPrivilegeError`/"unrecognized configuration parameter" numa rota
ou teste que antes funcionava, confira `is_local` antes de suspeitar de outra coisa.**

### ⚠️ `db.commit()` no meio do handler não invalida o GUC (é `is_local=false`), mas cuidado com sessões novas

Como o GUC é escopo de **sessão** (não de transação), um `commit()` no meio de um handler
**não** limpa `app.current_company_id` — diferente do que aconteceria com `SET LOCAL`. O
risco real é outro: se um código de "melhor esforço" abre uma **sessão nova** (ex.: um
serviço de notificação em background, um efeito colateral fora do fluxo principal do
request), essa sessão nova não herda o GUC da sessão original — precisa chamar
`set_tenant_context` de novo, ou vai falhar fail-closed na primeira query RLS. Achado real:
`deliver_notifications` (sessão de background sem GUC) — parte da correção de "RLS estava
inerte" documentada em `docs/backlog.md` (P16).

### Ordem de entrada em qualquer ponto de autenticação: GUC antes de qualquer query RLS

Achado original (`docs/auditoria-2026-06-22.md`/`2026-07-03.md`): a role da API era
superusuário e ignorava RLS incondicionalmente, então consultar uma tabela RLS **antes** de
chamar `set_tenant_context` nunca dava erro — só apareceu ao restringir a role de verdade
(migration `20260831_0070`). Isso afetou **7 pontos de entrada de auth** que consultavam
tabela RLS antes de setar o GUC (login, refresh, impersonação, etc.) — todos reordenados na
mesma sessão que trocou as roles. **Qualquer fluxo de auth novo (SSO, magic link, API key)
precisa chamar `set_tenant_context` antes da primeira query numa tabela RLS, nunca depois.**

### Login cross-tenant por e-mail: `SECURITY DEFINER`

Buscar um usuário por e-mail **sem saber ainda a que empresa ele pertence** (o próprio fluxo
de login) é uma leitura cross-tenant legítima antes do GUC poder ser setado — resolvido com
uma function Postgres `SECURITY DEFINER` (roda com privilégio do dono da function, não da
role da sessão), não com `registro_platform`/BYPASSRLS na rota de login de tenant. Se um
fluxo novo precisar de "achar o tenant a partir de um dado que não inclui `company_id`",
esse é o padrão a seguir, não abrir uma exceção de bypass na rota.

### `RETURNING` de INSERT reavalia a policy de leitura, não só `WITH CHECK`

Um INSERT cross-tenant legítimo (ex.: convite, escrita "em nome de outro registro") pode
falhar mesmo com `WITH CHECK` correto, porque o SQLAlchemy adiciona `RETURNING` automático
em todo INSERT via ORM (pra popular `id`/`created_at`) — Postgres trata isso como uma leitura
da linha recém-escrita, sujeita à policy `USING`. Se um INSERT cross-tenant continuar dando
erro de RLS mesmo com `WITH CHECK` certo, é isso — não é o `WITH CHECK` que está errado.

---

## Escopo por dono, não só por tenant: `support_request`/timeline

Nem todo isolamento no GEOP é só "por empresa" — `support_request` como `entity_type` de
timeline é escopado **por dono do chamado**, não só por `company_id`: outro usuário do
mesmo tenant que não abriu o chamado recebe 404, não a timeline. Ao adicionar uma entidade
nova com esse padrão (dado sensível dentro do próprio tenant, visível só a quem criou),
replique esse escopo mais estreito em vez de assumir que "mesma empresa = mesmo acesso".

---

## Painel Admin (`admin/`, porta 3001) e rotas `/platform/*`

Rotas `/platform/*` usam `registro_platform` (BYPASSRLS) — só elas devem, nunca uma rota de
tenant. Padrões existentes a conferir antes de criar rota nova:

- `GET /platform/audit` — auditoria paginada cross-tenant.
- `GET /platform/support-requests` + `PATCH .../{id}` — chamados de suporte, resposta do
  admin.
- `GET /platform/support-requests/{id}/timeline` — GUC setado explicitamente mesmo a rota
  sendo do admin (o "dono" da timeline é o tenant, não a plataforma) — não assuma que rota
  `/platform/*` nunca precisa de `set_tenant_context`.
- Impersonação: `api/app/domain/platform/router.py`/`service.py` — confirme o mecanismo
  atual (token com claim de admin original) antes de propor um novo.
- Billing: `Plan`/`Subscription`/`Invoice` (`api/app/models/platform.py`) — fatura de
  **assinatura SaaS do GEOP**, não confundir com `SalesInvoice` do módulo comercial
  (fatura que um tenant emite pro *próprio* cliente — ver nota em `docs/domain-model.md`).

---

## Como você opera

1. Antes de mexer em RLS/GUC, leia `docs/infra/role-restrita-postgres.md` e
   `docs/seguranca.md` — a decisão de arquitetura (3 roles) já foi tomada e validada
   ponta a ponta em dev; produção ainda não migrou (depende de troca de credencial de
   banco, decisão do usuário) — confirme o estado atual antes de assumir que já vale pra
   produção.
2. Toda rota de tenant nova: `set_tenant_context` antes da primeira query RLS, filtro
   manual por `company_id` na query como segunda camada (defesa em profundidade, RLS não
   substitui o filtro de aplicação).
3. Toda sessão de background/fire-and-forget que toca tabela RLS: setar o GUC de novo
   nessa sessão, não herdar do request original.
4. Ao criar uma entidade "cross-tenant por design" ou "escopada por dono, não por tenant",
   documente o porquê no código e no domínio correspondente — não deixe parecer um bug de
   isolamento pra quem ler depois.

## Checklist de auditoria SaaS/RLS

- [ ] Toda tabela de negócio tem `company_id` e RLS `ENABLE`+`FORCE` (padrão desde o módulo
      comercial — `20260831_0075`)
- [ ] `set_tenant_context` chamado antes de qualquer query numa tabela RLS, nunca depois
- [ ] `is_local=false` em qualquer `set_config` novo (nunca `SET LOCAL`/`is_local=true`)
- [ ] Sessão nova aberta fora do request principal (background/notificação) seta o GUC de
      novo, não herda do request
- [ ] Rota `/platform/*` usa `registro_platform`; rota de tenant nunca usa BYPASSRLS
- [ ] INSERT cross-tenant legítimo que falha com erro de RLS: verificar se é o `RETURNING`
      automático do ORM antes de mexer na policy
- [ ] Entidade nova escopada "por dono" (não só por tenant, ex.: `support_request`): 404
      pra outro usuário do mesmo tenant, não apenas checagem de `company_id`
- [ ] Credenciais de integração (`CompanySetting` de Brevo/Evolution/Clicksign) nunca
      expostas em listagem — sempre `has_credentials: bool`
- [ ] `Plan`/`Subscription`/`Invoice` (billing da plataforma) não confundidos com
      `SalesInvoice`/`SalesPayment` (billing do cliente do tenant, módulo comercial)
