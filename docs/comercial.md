# Módulo Comercial (orçamento, venda, instalação, faturamento e cobrança)

Pipeline de venda pro cliente do tenant: **Cliente → Orçamento → Aceite (link público) → Venda
→ Instalação → Faturamento → Cobrança**. Complementar a [contratos.md](contratos.md) — Contratos
cobre o lado de compra/fornecedor do tenant; este módulo cobre o lado de venda pro cliente do
tenant. Não confundir com o "Comercial e cobrança" citado em
[domain-model.md](domain-model.md) — aquele é a cobrança do GEOP pro tenant (SaaS, `plans`/
`subscriptions`/`invoices` de plataforma); este é a cobrança do tenant pro cliente dele.

## Entidades

### Customer (Cliente)

Cadastro do cliente do tenant (quem recebe orçamento/venda) — mesmo padrão de `Supplier`, sem
tabela de contatos separada (email/phone/whatsapp direto no registro). Soft delete
(`deleted_at`).

| Campo | Tipo | Descrição |
|---|---|---|
| `name` | string | Razão social ou nome |
| `document` / `document_type` | string? | CNPJ/CPF |
| `email`, `phone`, `whatsapp` | string? | Contato |
| `address_*` | string? | Endereço de entrega/instalação (street, number, complement, neighborhood, city, state, zip) |
| `active` | bool | Desativado não aparece em `/commercial/customers/options` |
| `notes` | text? | Observações internas |

### Quote (Orçamento) + QuoteItem

Um orçamento tem N itens (produto ou serviço, cada um podendo referenciar opcionalmente um
`StockItem` do módulo de estoque — sem dedução automática de estoque nesta rodada, é só
referência). `subtotal`/`total` são recalculados a partir dos itens toda vez que a lista muda
(soma dos `line_total` menos `discount_amount`, nunca negativo).

| Campo | Tipo | Descrição |
|---|---|---|
| `number` | string? | Gerado automaticamente (`ORC-{ano}-{sequencial}`) se não informado |
| `customer_id` | int | FK → `customers` |
| `title` | string | Título do orçamento |
| `status` | string | Ver estados abaixo |
| `responsible_user_id` / `created_by_user_id` | int? | FK → `users` |
| `description`, `conditions`, `notes` | text? | Objeto, condições (pagamento/prazo/garantia), observações internas |
| `issued_at` | date? | Data de envio (setada automaticamente ao enviar) |
| `valid_until` | date? | Validade — expira sozinho ao ser acessado/decidido depois dessa data |
| `discount_amount`, `subtotal`, `total` | decimal | Valores calculados |
| `decided_at`, `decision_note` | datetime?/text? | Quando e por que o cliente decidiu |

`QuoteItem`: `item_type` (`produto`\|`servico`), `stock_item_id?`, `description`, `unit`,
`quantity` (`Numeric(12,3)`, aceita fração), `unit_price`, `discount_percent?`, `line_total`
(calculado: `quantity * unit_price * (1 - discount_percent/100)`), `sort_order`.

#### Estados do orçamento

```
rascunho → enviado → aceito  (cria Sale automaticamente)
                   → recusado
                   → expirado  (valid_until passou, checado on-demand ao acessar)
rascunho|enviado → cancelado  (ação interna, não pelo cliente)
```

| Status | Quem move | Descrição |
|---|---|---|
| `rascunho` | interno | Editável livremente (título, itens, cliente, etc.) |
| `enviado` | interno (`POST /quotes/{id}/send`) | Travado pra edição — só o cliente decide a partir daqui |
| `aceito` | cliente (link público) | Cria `Sale` automaticamente |
| `recusado` | cliente (link público) | Terminal |
| `expirado` | sistema, on-demand | `valid_until` passou antes de uma decisão |
| `cancelado` | interno (`POST /quotes/{id}/cancel`) | Só a partir de `rascunho`/`enviado` |

**Orçamento só é editável (`PATCH`) enquanto `rascunho`** — uma vez enviado, mudar o conteúdo
sob o link que o cliente já está vendo quebraria a integridade da decisão dele; a saída é
cancelar e criar um novo. Tentar editar/excluir fora do estado permitido retorna `422
invalid_state`, não `404` (ver `InvalidStateError` em `service.py`).

### Aceite público (sem login)

Ao enviar (`POST /quotes/{id}/send`), a API gera um JWT assinado
(`create_quote_acceptance_token`, `type=quote_acceptance`, claims `sub=quote_id`+
`company_id`, 90 dias) e devolve `acceptance_url` = `{registro_web_url}/orcamento/{token}`. O
cliente abre esse link **sem autenticação nenhuma** — o router público
(`app/domain/commercial/public_router.py`, prefixo `/public/quotes`) decodifica o token, chama
`set_tenant_context` manualmente (é o único jeito de fazer uma query RLS-protegida sem uma
sessão de `User` — ver `app/core/rls.py` e o mesmo padrão em `timeclock/mobile_auth.py`) e só
então busca o orçamento.

O token em si **não expira a decisão** — quem trava é o `status`: uma vez decidido (ou
`valid_until` vencido), `POST .../accept` e `.../reject` passam a devolver `422 invalid_state`
mesmo com o link ainda "válido" (dentro dos 90 dias). Não há revogação de token nem
armazenamento de nonce — o estado do `Quote` é a única fonte de verdade, o que também significa
que reenviar o mesmo orçamento (`send` de novo, só possível a partir de `rascunho`) gera um
token novo automaticamente.

Aprovar cria a `Sale` no mesmo evento — não existe uma etapa manual de "converter orçamento em
venda".

### Sale (Venda)

Criada 1:1 com o `Quote` aceito (`quote_id` único). Cobre entrega e instalação como estágios da
própria venda, não como domínio próprio — suficiente pra rastrear status/data sem duplicar o
que `work_orders` já resolve pra trabalho interno da equipe.

| Campo | Tipo | Descrição |
|---|---|---|
| `number` | string? | Gerado automaticamente (`VDA-{ano}-{sequencial}`) |
| `quote_id`, `customer_id` | int | FKs |
| `status` | string | `confirmada` \| `entregue` \| `concluida` \| `cancelada` |
| `total_value` | decimal | Copiado do `Quote.total` no momento do aceite (não recalcula depois) |
| `delivered_at` | date? | Data de entrega |
| `installation_status` | string | `pendente` \| `agendada` \| `em_andamento` \| `concluida` \| `cancelada` |
| `installation_scheduled_at`, `installation_completed_at`, `installation_notes` | | Instalação no cliente |
| `erpsolid_external_id` | string? | Preparado pra push futuro (ver seção ERP Solid abaixo) — nada lê/escreve ainda |

`PATCH /commercial/sales/{id}` atualiza qualquer combinação desses campos, sem máquina de
estados — a equipe comercial decide manualmente quando marcar cada estágio.

### SalesInvoice (Fatura) + SalesPayment (Recebimento)

Uma venda pode ter mais de uma fatura (ex.: entrada + saldo) — `sale_id` não é único em
`sales_invoices`. Nomeados `SalesInvoice`/`SalesPayment` (não `Invoice`/`Payment`) pra não
colidir com `app.models.platform.Invoice`, que é a fatura de assinatura SaaS do tenant — domínio
inteiramente diferente.

| Campo (`SalesInvoice`) | Tipo | Descrição |
|---|---|---|
| `sale_id` | int | FK → `sales` |
| `number` | string? | Gerado automaticamente (`FAT-{ano}-{sequencial}`) |
| `nf_number` | string? | Número da nota fiscal (preenchimento manual por ora) |
| `status` | string | `pendente` \| `faturada` \| `paga` \| `atrasada` \| `cancelada` |
| `amount`, `issued_at`, `due_date`, `notes` | | |

`SalesPayment`: `invoice_id`, `amount`, `method` (`pix`\|`boleto`\|`cartao`\|`transferencia`\|
`dinheiro`\|`outro`), `paid_at`, `reference?`, `notes?`. Registrar um pagamento
(`POST /commercial/invoices/{id}/payments`) soma todos os pagamentos da fatura e marca
`status="paga"` automaticamente quando a soma atinge `amount` — sem endpoint separado pra
"quitar manualmente".

## Permissões

| Código | Escopo |
|---|---|
| `commercial.view` | Ver clientes, orçamentos, vendas e faturamento |
| `commercial.create` | Criar clientes e orçamentos |
| `commercial.edit` | Editar orçamentos/vendas, enviar/cancelar orçamento, criar fatura, registrar recebimento |
| `commercial.delete` | Excluir clientes e orçamentos (soft delete; orçamento `aceito` não pode ser excluído — vire `422`, cancele a venda em vez disso) |

O aceite/recusa pelo link público **não passa por permissão nenhuma** — é autenticado só pelo
JWT do token, por natureza (o cliente não é um usuário do tenant).

## API

Prefixo `/commercial` (autenticado, tenant) e `/public/quotes` (sem autenticação).

### Clientes

| Método | Rota | Permissão | Descrição |
|---|---|---|---|
| `GET` | `/commercial/customers` | `commercial.view` | paginado (filtro: search, active_only) |
| `GET` | `/commercial/customers/options` | `commercial.view` | lista simplificada pra select/autocomplete |
| `GET` | `/commercial/customers/{id}` | `commercial.view` | detalhe |
| `POST` | `/commercial/customers` | `commercial.create` | cria cliente |
| `PATCH` | `/commercial/customers/{id}` | `commercial.edit` | atualiza |
| `DELETE` | `/commercial/customers/{id}` | `commercial.delete` | soft delete |

### Orçamentos

| Método | Rota | Permissão | Descrição |
|---|---|---|---|
| `GET` | `/commercial/quotes` | `commercial.view` | paginado (filtros: search, status, customer_id) |
| `GET` | `/commercial/quotes/{id}` | `commercial.view` | detalhe com itens; inclui `acceptance_url` quando `status="enviado"` |
| `POST` | `/commercial/quotes` | `commercial.create` | cria orçamento com itens (`items: []`) |
| `PATCH` | `/commercial/quotes/{id}` | `commercial.edit` | atualiza — só permitido em `rascunho` (`422` fora disso) |
| `DELETE` | `/commercial/quotes/{id}` | `commercial.delete` | soft delete — bloqueado se `aceito` (`422`) |
| `POST` | `/commercial/quotes/{id}/send` | `commercial.edit` | `rascunho` → `enviado`; exige ao menos 1 item; devolve `acceptance_url` |
| `POST` | `/commercial/quotes/{id}/cancel` | `commercial.edit` | `rascunho`\|`enviado` → `cancelado` |

### Vendas, faturamento e cobrança

| Método | Rota | Permissão | Descrição |
|---|---|---|---|
| `GET` | `/commercial/sales` | `commercial.view` | paginado (filtros: search por número, status, installation_status) |
| `GET` | `/commercial/sales/{id}` | `commercial.view` | detalhe, inclui `invoices: []` embutidas com pagamentos |
| `PATCH` | `/commercial/sales/{id}` | `commercial.edit` | atualiza status/entrega/instalação (qualquer combinação de campos) |
| `POST` | `/commercial/sales/{id}/invoices` | `commercial.edit` | cria fatura pra venda |
| `PATCH` | `/commercial/invoices/{id}` | `commercial.edit` | atualiza fatura (status, valor, datas, NF) |
| `POST` | `/commercial/invoices/{id}/payments` | `commercial.edit` | registra recebimento; marca fatura `paga` quando quitada |
| `GET` | `/commercial/funnel` | `commercial.view` | agregados pro widget do dashboard (ver abaixo) |

### Aceite público

| Método | Rota | Autenticação | Descrição |
|---|---|---|---|
| `GET` | `/public/quotes/{token}` | token JWT no path | visualização do orçamento pro cliente |
| `POST` | `/public/quotes/{token}/accept` | token JWT no path | aprova (`{decision_note?}`) — cria a `Sale` |
| `POST` | `/public/quotes/{token}/reject` | token JWT no path | recusa (`{decision_note?}`) |

### `GET /commercial/funnel`

```json
{
  "quoted_count": 8, "quoted_total": "6980.00",
  "approved_count": 4, "approved_total": "4045.00",
  "delivered_count": 0,
  "invoiced_total": "4045.00",
  "received_total": "4045.00"
}
```

`quoted` = orçamentos com `status` != `rascunho`/`cancelado` (ou seja, já foram enviados de
verdade). `approved` = `status="aceito"`. `delivered` = vendas com `delivered_at` preenchido.
`invoiced`/`received` = soma de `SalesInvoice.amount` (excluindo `cancelada`) e de
`SalesPayment.amount`, respectivamente — sem filtro de período por enquanto (é o total
acumulado do tenant).

## Frontend

| Rota | Descrição |
|---|---|
| `/cadastros/clientes` | CRUD de clientes — mesmo padrão visual de `/cadastros/fornecedores`, sem sub-entidade de contatos |
| `/comercial/orcamentos` | Lista + criar/editar (itens dinâmicos com totais calculados no cliente) + modal de detalhe com ações (enviar/cancelar) e link de aceite copiável |
| `/comercial/vendas` | Lista + modal de detalhe: status da venda, status/datas de instalação, faturas embutidas com formulário de nova fatura e registro de recebimento inline |
| `/orcamento/[token]` | **Página pública, fora do `AppLayout`/login** — o cliente vê o orçamento e aprova/recusa. Liberada explicitamente no `middleware.ts` (`PUBLIC_PREFIXES = ["/orcamento/"]`) |

Widget "Funil comercial" no dashboard (`components/commercial-funnel-card.tsx`), buscado via
`GET /commercial/funnel` em `dashboard/page.tsx` — card oculto se a requisição falhar (usuário
sem `commercial.view`).

Todos os módulos autenticados usam o padrão visual existente: `.module-heading`/
`.module-panel`/`.module-toolbar`/`.module-table-wrap`/`.module-pagination` pra listagem,
`.modal-layer`+`.record-modal` pra criar/editar/detalhar. A página pública reaproveita
`.tenant-login-page` (fundo) só como wrapper — o card em si (`.quote-public-card`) é próprio,
mais largo que `.tenant-login-card` (420px) pra caber a tabela de itens.

### `middleware.ts` — rota pública fora do fluxo de auth

`middleware.ts` fica na raiz do `web/`, **fora** dos diretórios montados como volume no
`docker-compose.yml` (`./web/app`, `./web/components`, `./web/lib`) — uma mudança nele só entra
em vigor com `docker compose build web` (não basta `docker restart`), igual o `api/pyproject.toml`
já documentado pro serviço `api`.

## Migrations

| Revisão | Descrição |
|---|---|
| `20260831_0075` | Criação de `customers`, `quotes`, `quote_items`, `sales`, `sales_invoices`, `sales_payments` (todas com RLS `ENABLE`+`FORCE`) e seed das permissões `commercial.view/create/edit/delete` |

## Preparação pra integração com ERP Solid (não conectada ainda)

`Sale.erpsolid_external_id`, `SalesInvoice.erpsolid_external_id` e
`SalesPayment.erpsolid_external_id` existem no schema mas não são lidos nem escritos por
nenhum código ainda — só reservam o campo pro dia em que alguém for espelhar venda/fatura/
recebimento pro erpsolid, seguindo o mesmo padrão já em produção pra contratos/fornecedores/
funcionários em `app/domain/integrations_erpsolid/` (ver a seção "Contracts" desse domínio pra
o `list_contracts_for_erpsolid`/`upsert_*_from_erpsolid` de referência).

## Limitações conhecidas / próximos passos sugeridos

- Sem envio automático de e-mail ao cliente quando o orçamento é enviado — o link fica só na
  tela pra copiar manualmente. A integração Brevo já existe (`app/integrations/brevo.py`,
  usada em `users/service.py::invite_user`) e seria o próximo passo natural.
- Sem geração de PDF do orçamento/venda.
- Sem rate limit no endpoint público de aceite (`/public/quotes/*`) — os demais endpoints
  sensíveis do projeto (login, refresh) usam slowapi; este não tem, por ora.
- `QuoteItem.stock_item_id` é só referência — aceitar um orçamento com itens tipo "produto"
  não deduz `StockItem.current_quantity` automaticamente.
- Numeração (`ORC-`/`VDA-`/`FAT-{ano}-{sequencial}`) é por contagem simples, sem lock — colisão
  teórica sob criação concorrente no mesmo tenant/ano, aceito como risco baixo (mesmo padrão
  já usado em `contracts/service.py::_generate_contract_number`).
