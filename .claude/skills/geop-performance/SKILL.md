---
name: geop-performance
description: Guia de performance do GEOP — Server Components vs Client Components no Next.js App Router, Promise.all para fetches independentes, agregação SQL vs loop Python, N+1 queries (selectinload/joinedload). Use ao revisar lentidão, ao criar página/query nova, ou quando o usuário menciona "lento", "travando", "performance", "N+1".
---

Portado de `~/dev/erpsolid/.claude/skills/jarvis-performance/` e do guia equivalente do
Aloji, **reescrito para o padrão real do GEOP** — diferente dos dois: o GEOP usa Server
Components de verdade (App Router, fetch direto no servidor), não páginas Client Component
buscando tudo via `useEffect`. Confirmado em 2026-09-04: 32 das 35 `page.tsx` de `web/app/`
não têm `"use client"` — são a minoria, não a maioria (inverso do Aloji/erpsolid).

---

## 1. Server Component por padrão — só vá para Client Component quando precisar de interação

**Padrão real do GEOP** (`web/app/dashboard/page.tsx`, `web/app/comercial/orcamentos/page.tsx`
como referência):

```tsx
// page.tsx — Server Component, sem "use client"
import { currentTenantUser, tenantFetch } from "@/lib/api";
import { redirect } from "next/navigation";

export default async function Page() {
  const user = await currentTenantUser();
  if (!user) redirect("/login");
  const data = await tenantFetch("/algum-endpoint");
  return <AppLayout user={user}><Manager initialData={data} /></AppLayout>;
}
```

A interatividade (formulário, modal, filtro) fica isolada num componente filho
`"use client"` (`manager.tsx`), que recebe os dados iniciais via prop — não refaz o fetch
que o servidor já fez. **Não converta uma página inteira pra Client Component só porque uma
parte dela precisa de estado** — isole só o que precisa de `useState`/`onClick` num
componente próprio.

Mutações passam por Server Actions locais (`actions.ts` no mesmo diretório da feature —
`web/app/comercial/orcamentos/actions.ts`, não um arquivo global único), com `"use server"`
no topo e, quando aplicável, `revalidatePath()` depois de escrever — confirme se a página
precisa de revalidação explícita ou se o padrão do componente já resolve com um
`router.refresh()`/estado local, olhando um `actions.ts` irmão já existente antes de decidir.

---

## 2. `Promise.all()` para fetches independentes

Vale tanto dentro de um Server Component (`async function Page()`) quanto dentro de um
`useEffect` de Client Component — a regra é a mesma: se dois `tenantFetch()`/Server Actions
não dependem um do outro, rodar em paralelo.

```tsx
// ERRADO — sequencial, soma as duas latências
const user = await currentTenantUser();
const funnel = await tenantFetch("/commercial/funnel");

// CORRETO — paralelo, latência é a do mais lento dos dois
const [user, funnel] = await Promise.all([
  currentTenantUser(),
  tenantFetch("/commercial/funnel"),
]);
```

**Exceção legítima para sequencial**: quando o segundo fetch depende do resultado do
primeiro (ex.: resolver `company_id` do usuário antes de buscar dado filtrado por ele, se o
endpoint não aceitar o token sozinho).

---

## 3. Agregação SQL em vez de loop Python

**Regra**: soma/contagem/saldo usa `func.sum()`, `func.count()`, `GROUP BY`/`CASE` no banco
— não carrega todos os registros em Python pra somar em loop.

**Já aplicado no GEOP** — use como referência antes de escrever uma agregação nova em loop:
`api/app/domain/dashboard/service.py` (`func.count(WorkOrder.id)` filtrado por status,
setor, usuário — várias contagens do dashboard operacional) e `api/app/domain/commercial/
service.py` (`GET /commercial/funnel`: `quoted_total`/`approved_total`/`invoiced_total`/
`received_total` somados no banco, não em Python).

```python
# ERRADO — carrega tudo em Python pra somar
sales = (await db.execute(select(Sale).where(Sale.company_id == cid))).scalars().all()
total = sum(s.total for s in sales)

# CORRETO — agregação no banco
total = (await db.execute(
    select(func.coalesce(func.sum(Sale.total), 0)).where(Sale.company_id == cid)
)).scalar_one()
```

---

## 4. N+1 queries em loop

**Regra**: nunca uma query dentro de um `for` que itera sobre uma lista já carregada — vira
`GROUP BY`/join/subquery único, ou `selectinload`/`joinedload` ao serializar um
relacionamento aninhado.

**Já aplicado no GEOP**: `api/app/domain/roles/service.py` usa
`selectinload(Role.permissions)` ao listar/buscar roles — é hoje o único domínio com esse
padrão explícito no código (confirmado via grep em 2026-09-04). Ao adicionar uma listagem
nova que serializa um relacionamento 1:N (ex.: itens de um orçamento, faturas de uma venda,
permissões de um papel), siga esse padrão em vez de acessar `.relationship` dentro de um
loop de serialização.

```python
# ERRADO — 1 query por item da lista
for quote in quotes:
    items = (await db.execute(select(QuoteItem).where(QuoteItem.quote_id == quote.id))).scalars().all()

# CORRETO — eager load, 2 queries no total (não 1+N)
quotes = (await db.execute(
    select(Quote).options(selectinload(Quote.items)).where(Quote.company_id == cid)
)).scalars().all()
```

Sinal de alerta ao revisar um domínio que **não** usa `selectinload`/`joinedload`: não é
violação por si só rodar queries explícitas em vez de acessar `.relationship` — mas
qualquer serialização nova que acesse um relacionamento dentro de um loop de lista pode cair
em N+1 sem ninguém perceber. Ao dúvida, `grep -n "for .* in .*:" <arquivo>` seguido de
`await db.execute` no mesmo bloco é o sinal a procurar.

---

## 5. `<Link>` em vez de `<a>` para rotas internas

Confirmado em 2026-09-04: `grep -rn '<a href="/' web/app/` já retorna zero resultados no
GEOP — mantenha assim. Exceções legítimas: link externo (`target="_blank"`) e download
direto de arquivo (PDF de orçamento/venda, exportação XLSX).

---

## 6. Cache client-side (SWR) — ainda não adotado, avaliar antes de introduzir

O GEOP **não tem `swr` como dependência** (confirmado em `web/package.json`/`admin/
package.json`, 2026-09-04) — diferente do erpsolid, que adotou como padrão obrigatório pra
telas Client Component. Como a maioria das páginas do GEOP já é Server Component com fetch
direto no servidor (item 1), o problema que o SWR resolve no erpsolid (revisitar uma tela
client-side refaz o fetch do zero) se aplica menos aqui — cada navegação já busca dado fresco
via SSR. Só considere introduzir SWR numa tela específica se ela for genuinamente Client
Component com fetch client-side recorrente (ex.: um painel que atualiza em tempo real) — não
como padrão default do projeto.

---

## Checklist de auditoria rápida

```
[ ] page.tsx nova é Server Component (sem "use client") por padrão — só isola em Client
    Component o que precisa de useState/onClick
[ ] Mutação usa Server Action local (actions.ts da própria feature), não um fetch direto
    do cliente
[ ] 2+ fetches/Server Actions independentes usam Promise.all(), não await sequencial
[ ] Dashboard/relatório novo: agregação com func.sum/func.count/CASE no banco, não loop
    Python carregando a tabela inteira (referência: dashboard/service.py, commercial/
    service.py::funnel)
[ ] Serialização de relacionamento 1:N numa lista usa selectinload/joinedload (referência:
    roles/service.py) — não acessa .relationship dentro de um for
[ ] grep -rn '<a href="/' web/app/ admin/app/ colaborador/app/ — zero resultados fora de
    exceções legítimas
```
