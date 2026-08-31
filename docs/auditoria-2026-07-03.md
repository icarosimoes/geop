# Caça a Bugs — 2026-07-03

Revisão adversarial do codebase (backend, frontend, integrações, infra) com foco em
bugs **reais** — falhas exploráveis ou que quebram comportamento, não estilo/lint.
Cada achado de severidade Crítica/Alta/Média foi confirmado relendo o código-fonte;
os marcados *(plausível)* foram reportados por revisor e não reconfirmados linha a linha.

## Resumo

| Severidade | Qtd | Exemplos principais |
|------------|-----|---------------------|
| **Crítico** | 1 | RLS inerte (API conecta como superusuário do Postgres) |
| **Alto** | 6 | Rate limit burlável, escalada cross-tenant via `role_id`, convite quebrado, logout a cada 30min, idempotência Asaas, race de estoque |
| **Médio** | 8 | Email de falha marcado como enviado, convite replayável, vazamento em join de ocorrências, status Asaas bruto, reembolso não tratado, GUC pós-commit, `safeParse` permissivo, HTML injection |
| **Baixo** | 16 | Enumeração por timing, senha >72 bytes, refresh sem revogação, proxy admin, N+1, etc. |

Eixo dominante: **isolamento multitenant**. Como o RLS está inerte (C1), o isolamento
depende 100% do filtro `company_id` na aplicação — então cada query que o esquece (M3)
ou cada FK cross-tenant não validado (H2, M3) vira vazamento real, sem rede de proteção.

---

## Crítico

### C1. RLS completamente inerte — a API conecta como superusuário do Postgres — ✅ corrigido em 2026-08-31

> Este achado ficou órfão por quase dois meses: nunca foi linkado no `README.md` nem virou item no `backlog.md`, então continuou sem correção até ser redescoberto de forma independente em 31/08/2026 (durante a implementação de outra entrega, ao validar um fix que dependia de RLS de fato funcionar). Correção completa (três roles, reordenação do GUC nos pontos de auth, function `SECURITY DEFINER` pro login cross-tenant) em [role-restrita-postgres.md](infra/role-restrita-postgres.md) e [ADR-002](adr/002-rls-isolamento-multitenant.md#atualização-2026-08-31--rls-estava-inerte-desde-a-implementação). Validado de ponta a ponta no dev local; rollout em produção ainda pendente de decisão do usuário (troca de credencial de banco).

**Arquivos:** `docker-compose.yml:8,80`, `api/alembic/versions/20260620_0029_rls_policies.py:48-53`

`POSTGRES_USER=registro` e a mesma role na `DATABASE_URL`. Na imagem oficial `postgres`,
`POSTGRES_USER` é **superusuário**, e superusuário ignora RLS **incondicionalmente —
inclusive com `FORCE ROW LEVEL SECURITY`**. Nenhuma role `NOSUPERUSER`/`NOBYPASSRLS` é
criada. Toda a camada de policies `tenant_isolation` é silenciosamente inútil; o
isolamento entre tenants passa a depender exclusivamente do filtro `company_id` da aplicação.

**Correção:** rodar a API com role dedicada `NOSUPERUSER NOBYPASSRLS` que não seja dona das
tabelas. Adicionar teste que garanta que uma query sem `company_id` é bloqueada pelo banco.

---

## Alto

### H1. Rate limit de login/set-password burlável trivialmente

**Arquivo:** `api/app/core/rate_limit.py:5-9` (afeta `auth/router.py:36,95,149`)

`_get_client_ip` usa o **primeiro** valor de `X-Forwarded-For` — controlado pelo cliente
(um proxy real *anexa*, não substitui) — e `ProxyHeadersMiddleware(trusted_hosts=["*"])`
(`main.py:127`) confia em todo hop. Rotacionando o header a cada request, os limites de
`10/min` (login) e `5/min` (set-password) nunca disparam → brute-force/credential-stuffing
sem freio.

**Correção:** derivar o IP de uma posição fixa de proxy confiável (contagem de hops), não do
XFF mais à esquerda.

### H2. Escalada de privilégio cross-tenant via `role_id` não validado

**Arquivos:** `api/app/domain/users/service.py:98-109,149-150`; `auth/repository.py:35`

`create_user`/`update_user`/`invite_user` gravam o `role_id` do corpo direto no `User`, sem
checar se o role pertence à `company_id`. `map_user` deriva `permissions` de
`user.role.permissions` sem filtrar a empresa dona do role. Um usuário com `user.edit` (mas
sem `role.manage`) faz `PATCH /users/{id}` com `role_id` de um role poderoso de **outro**
tenant (IDs sequenciais) e herda permissões que seu próprio tenant nunca configurou.

**Correção:** validar `Role.id == role_id AND Role.company_id == company_id` antes de
atribuir; rejeitar (404/422) caso contrário.

### H3. Onboarding de convite 100% quebrado pelo middleware

**Arquivo:** `web/middleware.ts:3,15`

`PUBLIC_PATHS = ["/login"]` apenas. O convidado chega sem sessão em `/definir-senha?token=...`;
a regra `if (!token && !PUBLIC_PATHS.includes(pathname))` o redireciona para `/login`. Nenhum
usuário convidado consegue definir a senha. (`/design-preview` é gated do mesmo jeito.)

**Correção:** incluir `/definir-senha` nas rotas públicas e casar por prefixo
(`pathname === p || pathname.startsWith(p + "/")`).

### H4. Usuários deslogados a cada ~30 min apesar do refresh de 7 dias

**Arquivos:** `web/middleware.ts:7,15` e `admin/middleware.ts:7,15`; `web/lib/auth.ts:22`,
`admin/lib/actions.ts:24`

O cookie de access tem `maxAge = expires_in` (~30 min); o middleware só checa a presença
dele. Quando expira, a navegação seguinte cai em `/login`, mesmo com `*_refresh_token` (7d)
válido — o refresh só roda dentro de server actions/`tenantFetch`, nunca na navegação. O
design de refresh fica anulado para page loads.

**Correção:** no middleware, considerar a sessão presente se **qualquer** dos dois cookies
existir; deixar o refresh para o primeiro fetch/server action.

### H5. Idempotência do webhook Asaas chaveada no `payment.id` engole eventos do ciclo de vida

**Arquivos:** `api/app/domain/platform/webhook.py:27` + unique `provider,external_id` em
`models/platform.py`

`external_id = payment.get("id") or event_data.get("id")`. O Asaas dispara vários eventos
para o **mesmo** pagamento (`PAYMENT_CONFIRMED` → depois `PAYMENT_OVERDUE` → `PAYMENT_REFUNDED`),
todos com o mesmo `payment.id`. O primeiro insere; os seguintes batem no `IntegrityError` →
`{"status":"already_processed"}` sem fazer nada. Um pagamento revertido nunca move a
assinatura para `past_due` → tenant inadimplente mantém acesso indefinidamente.

**Correção:** usar o id do envelope do evento — `external_id = event_data.get("id") or
payment.get("id")`.

### H6. Race de lost-update no estoque corrompe inventário

**Arquivo:** `api/app/domain/stock/service.py:182-201` (`create_movement`)

Read-modify-write em Python (`item.current_quantity -= quantity`) com guarda check-then-act,
sem lock nem UPDATE atômico. Duas saídas concorrentes de 10 sobre estoque 10 passam ambas na
guarda, ambas gravam `0`, mas registram **duas** movimentações de 10 (20 consumidos, 10
deduzidos). Ledger e saldo divergem permanentemente.

**Correção:** `UPDATE stock_items SET current_quantity = current_quantity - :q WHERE id=:id
AND company_id=:cid AND current_quantity >= :q` (0 linhas afetadas = estoque insuficiente),
ou `select(...).with_for_update()` no item antes da guarda.

---

## Médio

### M1. Emails do Brevo com falha são marcados como enviados

**Arquivos:** `api/app/integrations/notifications.py:275-277` + `brevo.py:39-41`

`send_email` **retorna** `{"error": True, "status": ...}` (não levanta) em HTTP≥400; o loop de
`deliver_notifications` só filtra `isinstance(result, BaseException)`, então grava
`email_sent_at`. Falha de entrega vira "enviado", sem retry nem visibilidade.

**Correção:** tratar dict com `error` como falha —
`... and not (isinstance(result, dict) and result.get("error"))`.

### M2. Token de convite/reset replayável e válido em usuário já ativo

**Arquivo:** `api/app/domain/auth/router.py:148-192` (`set_password`)

`set_password` não invalida o token (sem `jti`/uso único), não checa `email_verified_at` nem
`User.active`. O mesmo link funciona por 48h e serve também como único mecanismo de reset. Se
o link vazar (email encaminhado, histórico), permite tomar a conta sem senha antiga.

**Correção:** uso único (timestamp/jti) e recusar quando `email_verified_at` já estiver setado.

### M3. Vazamento cross-tenant no join de ocorrências

**Arquivo:** `api/app/domain/occurrences/service.py:97-100` (e `export_occurrences:341`)

A listagem resolve `Sector.name/Location.name/User.name` só com `Sector.id ==
Occurrence.sector_id`, **sem `company_id`** — ao contrário do detalhe (`_resolve_names:45-80`,
que filtra `company_id` e `deleted_at`). Como `create_occurrence`/`update_occurrence` **não
validam** que `sector_id`/`location_id`/`owner_user_id` pertencem ao tenant, um id de outra
empresa é aceito e seu nome vaza na listagem. É exatamente a classe de bug que o RLS (C1)
deveria bloquear.

**Correção:** validar cada FK contra `company_id` no write (rejeitar) **e** adicionar
`company_id` às condições de join.

### M4. `reconcile_billing` grava status bruto do Asaas na coluna local

**Arquivo:** `api/app/domain/platform/service.py:581-586`

`sub.status = remote.get("status","").lower()` grava `active/inactive/expired` numa coluna
que só entende `trial/active/past_due/suspended/canceled`. Um `INACTIVE` vira `"inactive"` e
quebra métricas (`platform_metrics` conta `status == "active"`), pipeline de suspensão e
checagem de acesso. Além disso, um sub local `trial`/`past_due` é falsamente marcado como
discrepância contra `active` remoto a cada reconcile.

**Correção:** mapa explícito remoto→local antes de comparar/atribuir.

### M5. `PAYMENT_REFUNDED` nunca é tratado (mapa morto)

**Arquivo:** `api/app/domain/platform/webhook.py:13-18,48-53`

`ASAAS_STATUS_MAP["REFUNDED"]` existe mas nunca é referenciado; o dispatch só trata
`PAYMENT_CONFIRMED/RECEIVED`, `PAYMENT_OVERDUE`, `SUBSCRIPTION_DELETED`. Reembolso é aceito,
registrado e auditado como processado, mas a invoice segue `paid` e a assinatura `active`.

**Correção:** adicionar branch `PAYMENT_REFUNDED` que marca a invoice como `refunded`.

### M6. GUC de tenant se perde após commit

**Arquivo:** `api/app/core/auth.py:31-33`

`set_config('app.current_company_id', :cid, true)` é transaction-local; após um `commit()` no
meio do request, queries seguintes rodam sem o GUC. Hoje é mascarado por C1 (superuser ignora
RLS); ao corrigir C1, vira quebra real de isolamento (ou erro `unrecognized configuration
parameter`).

**Correção:** reaplicar o GUC por transação de forma consistente após commits.

### M7. `safeParse` retorna dado não-validado em mismatch *(plausível)*

**Arquivo:** `web/lib/schemas.ts:77-84`

No `!result.success`, loga e faz `return data as T` — validação não-impositiva. Um token
malformado flui para `setTokenCookies` e grava `"undefined"` no cookie → estado "logado mas
todo request 401" em vez de falha limpa de login.

**Correção:** lançar (ou retornar fallback tipado) em `!result.success`.

### M8. HTML injection nos emails de notificação

**Arquivo:** `api/app/integrations/notifications.py:85-104` (`_build_html`)

`title/module/actor/detail` (input de usuário: títulos de ocorrência, nomes) entram no HTML
via f-string sem escape.

**Correção:** `html.escape()` em cada campo interpolado.

---

## Baixo

| # | Arquivo | Bug | Correção |
|---|---------|-----|----------|
| L1 | `auth/service.py:39-53` | Enumeração de usuário/tenant por timing (sem bcrypt no no-match) | bcrypt dummy no caminho no-match |
| L2 | `users/service.py:125-166` | `update_user` sem checar email duplicado → `IntegrityError` 500 (não 409) | rechecar unicidade antes do update |
| L3 | create/update/profile/set-password | Senha >72 bytes → `ValueError` 500 não tratado (bcrypt≥5) | `max_length=72` nos inputs de senha |
| L4 | `auth/router.py:94` | Refresh token stateless: troca de senha/logout não revoga (7d) | coluna de versão de token |
| L5 | `admin/.../proxy/[...path]/route.ts:26` | Proxy descarta query string *(plausível)* | anexar `req.nextUrl.search` |
| L6 | idem | Path traversal para fora de `/platform/` *(plausível)* | rejeitar segmentos `..`/`/`/`\` |
| L7 | `checklists/service.py:419-427` | Diff de auditoria hardcoded (mente na transição) | capturar `rec.status` antes de mutar |
| L8 | `occurrences/service.py:256-275`, `work_orders/service.py:263-280` | Mudança de `notify_user_ids` não gera `AuditEvent` | incluir campo no diff/auditar |
| L9 | `core/pagination.py:24-31` | `decode_cursor` engole erros → cursor inválido volta pág.1 | estreitar except / sinalizar erro |
| L10 | `integrations/asaas.py:45` | `resp.json()` em corpo de erro não-JSON → 500 confuso | try/except com fallback `resp.text` |
| L11 | `import_v1.py:179` | `import_users` quebra em email NULL | `(row.get("email") or "").strip().lower()` |
| L12 | `web/app/actions.ts:268-282` | `uploadAvatarAction` sem refresh-on-401 | espelhar `tryRefreshToken` do attachment |
| L13 | `fiscal_requests/router.py:47` | Chave Chess comparada com `!=` (timing) | `hmac.compare_digest` |
| L14 | `fiscal_requests/service.py:47-62` | N+1 no tracking de tickets Chess (2N round-trips) | batch-load de responsáveis/histórico |
| L15 | `occurrences/service.py:341` | Nome de setor/location soft-deleted ainda aparece na listagem | `deleted_at.is_(None)` nos joins |
| L16 | `platform/service.py:359-368` | Provisionamento Asaas não-atômico → cliente duplicado | `with_for_update` / idempotency key |

---

## Plano de correção priorizado

1. **Fundação de isolamento (C1 → M6 → M3, H2):** criar role de app
   `NOSUPERUSER NOBYPASSRLS` sem posse das tabelas; corrigir o GUC transaction-local; então
   tapar os buracos de app-level que o RLS deixava passar (validação de FK cross-tenant no
   write, `company_id` nos joins de listagem, validação de `role_id`). Ataca o eixo
   multitenant inteiro de uma vez.
2. **Auth exposto a força bruta/replay (H1, M2, L1, L3, L4):** corrigir a chave de
   rate-limit, tornar convite de uso único, `max_length=72` nas senhas, revogação de refresh
   por versão.
3. **Sessão do frontend (H3, H4, M7):** consertar o middleware (rota pública de convite +
   presença de qualquer cookie) e o `safeParse`. Quebras de fluxo visíveis a todo usuário.
4. **Billing correto (H5, M1, M4, M5):** idempotência por evento, falha de email como falha,
   mapa de status, branch de reembolso — senão receita e estado de assinatura divergem
   silenciosamente.
5. **Integridade de estoque (H6):** UPDATE atômico com guarda.
6. **Faxina dos BAIXOS** conforme capacidade.

---

## Notas — verificado e sem bug

- **Decodificação de JWT:** `algorithms=["HS256"]` fixado em todos os `decode_*`, cada um
  valida o claim `type`; `exp` verificado por padrão do PyJWT. Sem `verify=False`.
- **`current_user`/`me`/`refresh`:** recarregam o usuário filtrando por `sub` **e**
  `company_id`, retornam 401 para usuário inativo.
- **Webhook Asaas (auth):** `hmac.compare_digest` — comparação constant-time correta.
- **`attachments/service.py`:** todas as queries filtram `company_id` corretamente.
- **`FiscalRequest`** não tem coluna `deleted_at` (hard delete) — ausência de filtro
  `deleted_at` em `list_fiscal_requests` é correta, não bug.
- **Guards de produção** (`config.py:89-102`): rejeitam `jwt_secret` default/curto, chave
  Chess default e origens `*`.
- **SLA** (`core/sla.py`): matemática de deadline/pausa/resume internamente consistente.
- **Acesso async ao DB:** devidamente `await`ed; nenhum lazy-load/MissingGreenlet encontrado.
