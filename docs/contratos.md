# Módulo de Contratos

Gerenciamento completo do ciclo de vida de contratos com fornecedores, incluindo fluxo de aprovação, aditivos e integração com centro de custo/financeiro.

## Entidades

### Supplier (Fornecedor)

Cadastro de fornecedores por empresa (`company_id`). Suporta soft delete (`deleted_at`).

| Campo | Tipo | Descrição |
|---|---|---|
| `name` | string | Razão social ou nome |
| `document` | string? | CNPJ ou CPF |
| `document_type` | string? | `cnpj` \| `cpf` |
| `category` | string? | Categoria livre (ex: "Limpeza", "TI") |
| `email` | string? | E-mail principal |
| `phone` | string? | Telefone |
| `website` | string? | Site |
| `address_*` | string? | Endereço completo (street, number, complement, city, state, zip) |
| `active` | bool | Ativo por padrão; desativado não aparece em opções de vínculo |
| `notes` | text? | Observações internas |

### SupplierContact (Contato do Fornecedor)

Múltiplos contatos por fornecedor. Apenas um pode ser `is_primary`. Suporta soft delete.

| Campo | Tipo | Descrição |
|---|---|---|
| `name` | string | Nome do contato |
| `role` | string? | Cargo ou função |
| `email` | string? | E-mail |
| `phone` | string? | Telefone |
| `whatsapp` | string? | WhatsApp |
| `is_primary` | bool | Contato principal |
| `notes` | text? | Observações |

### Contract (Contrato)

Entidade central. Suporta soft delete, auditoria e anexos genéricos (`entity_type="contract"`).

| Campo | Tipo | Descrição |
|---|---|---|
| `number` | string? | Número/código interno do contrato |
| `title` | string | Título descritivo |
| `contract_type` | string | `servico` \| `fornecimento` \| `manutencao` \| `locacao` \| `outros` |
| `supplier_id` | int? | FK → `suppliers` |
| `responsible_user_id` | int? | FK → `users` (responsável interno) |
| `created_by_user_id` | int? | FK → `users` (criador) |
| `status` | string | Ver estados abaixo |
| `description` | text? | Objeto do contrato |
| `conditions` | text? | Condições e obrigações |
| `notes` | text? | Observações internas |
| `signed_at` | date? | Data de assinatura |
| `start_date` | date? | Início da vigência |
| `end_date` | date? | Fim da vigência |
| `alert_days` | int | Dias de antecedência para alerta de vencimento (padrão: 60) |
| `auto_renew` | bool | Renovação automática |
| `indexer` | string? | Indexador de reajuste (ex: "IPCA", "IGP-M") |
| `total_value` | decimal? | Valor total do contrato |
| `monthly_value` | decimal? | Valor mensal |
| `currency` | string | Moeda (padrão: `BRL`) |
| `payment_frequency` | string? | `mensal` \| `trimestral` \| `semestral` \| `anual` |
| `payment_day` | int? | Dia do mês para pagamento |
| `cost_center` | string? | Centro de custo |
| `budget_category` | string? | Categoria orçamentária |

#### Estados do contrato

```
rascunho → em_aprovacao → ativo → suspenso
                       ↘ encerrado
         ↙ (rejeição volta para rascunho)
```

| Status | Descrição |
|---|---|
| `rascunho` | Criado, não enviado para aprovação |
| `em_aprovacao` | Aguardando aprovação dos aprovadores cadastrados |
| `ativo` | Todos aprovadores aprovaram ou ativado manualmente |
| `suspenso` | Suspenso temporariamente |
| `encerrado` | Encerrado definitivamente |

### ContractAmendment (Aditivo)

Registra alterações formais ao contrato. Pode atualizar a data de término e/ou valor.

| Campo | Tipo | Descrição |
|---|---|---|
| `amendment_type` | string | `prazo` \| `valor` \| `objeto` \| `outros` |
| `description` | text | Descrição do aditivo |
| `new_end_date` | date? | Nova data de término (aplicada ao contrato) |
| `new_value` | decimal? | Novo valor total (aplicado ao contrato) |
| `signed_at` | date? | Data de assinatura do aditivo |

### ContractApprovalStep (Etapa de Aprovação)

Fluxo de aprovação sequential. Cada etapa tem um aprovador e um estado.

| Campo | Tipo | Descrição |
|---|---|---|
| `step_order` | int | Ordem da etapa (1, 2, 3…) |
| `approver_user_id` | int | FK → `users` |
| `status` | string | `pendente` \| `aprovado` \| `rejeitado` |
| `comment` | text? | Comentário da decisão |
| `decided_at` | datetime? | Momento da decisão |

**Regra**: quando todas as etapas estão `aprovado`, o contrato passa para `ativo`. Se qualquer etapa for `rejeitado`, o contrato volta para `rascunho` e todas as etapas pendentes são canceladas.

## Permissões

| Código | Escopo |
|---|---|
| `contract.view` | Listar e visualizar contratos e fornecedores |
| `contract.create` | Criar contratos e fornecedores |
| `contract.edit` | Editar, adicionar aditivos, gerenciar contatos, alterar status |
| `contract.delete` | Excluir contratos e fornecedores (soft delete) |
| `contract.approve` | Aprovar ou rejeitar etapas de aprovação |

## API

### Fornecedores

| Método | Rota | Permissão | Descrição |
|---|---|---|---|
| `GET` | `/contracts/suppliers` | `contract.view` | Lista fornecedores paginada (filtro: search, active_only) |
| `GET` | `/contracts/suppliers/options` | `contract.view` | Lista simplificada para select/autocomplete |
| `GET` | `/contracts/suppliers/{id}` | `contract.view` | Detalhe com contatos |
| `POST` | `/contracts/suppliers` | `contract.create` | Cria fornecedor |
| `PATCH` | `/contracts/suppliers/{id}` | `contract.edit` | Atualiza fornecedor |
| `DELETE` | `/contracts/suppliers/{id}` | `contract.delete` | Soft delete |
| `POST` | `/contracts/suppliers/{id}/contacts` | `contract.edit` | Adiciona contato |
| `PATCH` | `/contracts/contacts/{id}` | `contract.edit` | Atualiza contato |
| `DELETE` | `/contracts/contacts/{id}` | `contract.edit` | Remove contato |

### Contratos

| Método | Rota | Permissão | Descrição |
|---|---|---|---|
| `GET` | `/contracts` | `contract.view` | Lista contratos paginada (filtros abaixo) |
| `GET` | `/contracts/{id}` | `contract.view` | Detalhe com aditivos e etapas de aprovação |
| `POST` | `/contracts` | `contract.create` | Cria contrato (inclui `approver_user_ids` para montar o fluxo) |
| `PATCH` | `/contracts/{id}` | `contract.edit` | Atualiza dados do contrato |
| `PATCH` | `/contracts/{id}/status` | `contract.edit` | Altera status manualmente |
| `DELETE` | `/contracts/{id}` | `contract.delete` | Soft delete |
| `POST` | `/contracts/{id}/amendments` | `contract.edit` | Registra aditivo (atualiza end_date/total_value no contrato) |
| `POST` | `/contracts/{id}/approve` | `contract.approve` | Aprovador decide sua etapa (`{approved: bool, comment?}`) |

#### Filtros de listagem (`GET /contracts`)

| Parâmetro | Tipo | Descrição |
|---|---|---|
| `search` | string? | Busca por título ou número |
| `status` | string? | Filtra por status |
| `contract_type` | string? | Filtra por tipo |
| `supplier_id` | int? | Filtra por fornecedor |
| `expiring_in_days` | int? | Contratos vencendo nos próximos N dias |
| `page` | int | Página (padrão: 1) |
| `page_size` | int | Itens por página (padrão: 20, máx: 100) |

## Frontend

Rota: `/contratos`

Abas:
- **Contratos** — tabela com título, tipo, fornecedor, vigência (badge de vencimento próximo), valor mensal e status
- **Fornecedores** — tabela com nome, documento, categoria, contato, contagem de contratos

Drawer de detalhe do contrato com 4 sub-abas:
- **Informações** — dados gerais, datas, responsável, fornecedor
- **Financeiro** — valores, moeda, indexador, frequência de pagamento, centro de custo, categoria orçamentária
- **Aditivos** — histórico de aditivos com formulário inline para novo aditivo
- **Aprovação** — etapas do fluxo com painel de decisão se o usuário logado é aprovador pendente

Drawer de detalhe do fornecedor:
- Dados cadastrais completos
- Lista de contatos com formulário inline para adicionar/editar

## Migrations

| Revisão | Descrição |
|---|---|
| `20260709_0053` | Criação das tabelas: `suppliers`, `supplier_contacts`, `contracts`, `contract_amendments`, `contract_approval_steps` |
| `20260709_0054` | Seed das permissões: `contract.view/create/edit/delete/approve` |

## Anexos

Contratos usam o sistema genérico de anexos existente:

```
POST /attachments          → entity_type="contract", entity_id=<id>
GET  /attachments?entity_type=contract&entity_id=<id>
```

Não requer nenhuma adaptação no backend.
