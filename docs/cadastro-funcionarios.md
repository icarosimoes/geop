# Cadastro de Funcionários

## Visão geral

O `Employee` é a entidade de RH que representa quem trabalha no hotel — separada de `User` (conta de login do sistema). Antes desta separação, o módulo de ponto/escala usava `User` como se fosse o "funcionário", misturando dois conceitos distintos:

- **User**: quem tem login e senha no GEOP (pode ser um gerente, recepcionista, ou até um usuário de plataforma sem vínculo operacional).
- **Employee**: quem trabalha no hotel e é gerenciado pelo RH (nem todo funcionário loga no sistema; nem todo usuário do sistema é necessariamente um funcionário do hotel).

`Employee` é hoje a entidade referenciada por ponto eletrônico e escala de trabalho (`schedule_entries`, `time_clock_enrollments`, `time_punches`), com vínculo **opcional** para um `User`.

## Modelo de dados

### Employee

```sql
CREATE TABLE employees (
  id INTEGER PRIMARY KEY,
  company_id INTEGER NOT NULL,

  -- Dados pessoais
  name VARCHAR(255) NOT NULL,
  cpf VARCHAR(11),
  rg VARCHAR(20),
  birth_date VARCHAR(10),        -- YYYY-MM-DD
  phone VARCHAR(20),
  personal_email VARCHAR(255),

  -- Endereço
  address_street VARCHAR(255),
  address_number VARCHAR(20),
  address_complement VARCHAR(255),
  address_neighborhood VARCHAR(255),
  address_city VARCHAR(100),
  address_state VARCHAR(2),
  address_zip VARCHAR(10),        -- formato XXXXX-XXX

  -- Organizacional
  status VARCHAR(20) DEFAULT 'active',  -- active | inactive | terminated
  avatar_url VARCHAR(500),

  -- Dados contratuais (migration 20260704_0046)
  job_title VARCHAR(120),
  hire_date VARCHAR(10),          -- YYYY-MM-DD
  termination_date VARCHAR(10),   -- YYYY-MM-DD
  registration_number VARCHAR(40),

  -- Setor/departamento (migration 20260704_0046)
  sector_id INTEGER REFERENCES sectors(id) ON DELETE SET NULL,

  -- Vínculo opcional com User (nem todo employee loga no sistema)
  user_id INTEGER REFERENCES users(id) ON DELETE SET NULL,

  created_at TIMESTAMP DEFAULT now(),
  updated_at TIMESTAMP DEFAULT now(),
  deleted_at TIMESTAMP,

  UNIQUE (company_id, cpf)
);
```

**Escopo atual**: dados pessoais, endereço, status, cargo/admissão/matrícula e setor. Salário, dados bancários e documentos anexados seguem fora do MVP — são dados sensíveis que merecem tratamento à parte (permissão dedicada, criptografia em repouso) e não foram pedidos no backlog atual.

**job_title / hire_date / termination_date / registration_number** (`[E10]`): cargo, datas de admissão/desligamento e matrícula. `hire_date`/`termination_date` seguem a mesma validação de formato `YYYY-MM-DD` de `birth_date`. Nenhum é obrigatório — o desligamento típico é: `PATCH` com `status: "terminated"` e `termination_date` preenchida.

**sector_id** (`[E11]`): reaproveita o cadastro de Setor já usado por `User` (`/cadastros/setores`, categoria `"Setor"` no domínio `registries`) em vez de criar um conceito de departamento paralelo. `EmployeeDetailedSummary.sector_name` traz o nome resolvido (join simples, mesmo padrão de `get_sector_name` em `app/domain/users/service.py`) para a UI não precisar de uma segunda chamada.

**CPF**: obrigatório na criação (`EmployeeCreate.cpf: str`), único por empresa. Validado no schema Pydantic com dígito verificador real (mesmo algoritmo de `app.core.validators.validate_cpf`, usado em `fiscal_requests`) e normalizado para 11 dígitos sem pontuação antes de persistir. Em `EmployeeUpdate` o campo continua opcional (patch parcial), mas quando informado passa pela mesma validação. A coluna no banco (`VARCHAR(11)`) permanece `nullable` porque o backfill da migração `20260703_0043` criou `Employee` sem CPF para `User`s existentes — a obrigatoriedade vale para novos cadastros feitos via API/UI, não retroativamente.

No frontend (`web/app/cadastros/funcionarios/manager.tsx`), o CPF é campo obrigatório do formulário e validado no cliente (dígito verificador via `web/lib/validators.ts`) antes do submit, evitando round-trip para erros óbvios.

**birth_date**: validado no formato `YYYY-MM-DD`; qualquer outro formato retorna `422`.

**address_zip**: validado como CEP brasileiro de 8 dígitos e normalizado para `XXXXX-XXX` (coluna `VARCHAR(10)` desde a migration `20260704_0045`, que corrigiu o tamanho original de 8 caracteres — insuficiente para o hífen). No frontend, ao preencher os 8 dígitos do CEP o formulário consulta a API pública [ViaCEP](https://viacep.com.br) via server action (`lookupCepAction` em `web/app/actions.ts`) e preenche automaticamente logradouro, bairro, cidade e UF — a chamada é feita no servidor (Server Action), não no navegador, porque o CSP do app (`web/next.config.ts`) restringe `connect-src` e não inclui domínios externos.

**status**: `Literal["active", "inactive", "terminated"]` no schema Pydantic (não é mais string livre) — alinhado com `STATUS_LABELS` do frontend em `web/app/cadastros/funcionarios/manager.tsx`.

**Soft delete**: `deleted_at`, igual ao padrão de `User`/`Shift`. Registros deletados não aparecem em listagens.

### EmployeeExternalId (integrações futuras)

Tabela 1:N para guardar identificadores de sistemas externos (ERP, folha de pagamento), pensando na integração futura do GEOP com outros sistemas:

```sql
CREATE TABLE employee_external_ids (
  id INTEGER PRIMARY KEY,
  company_id INTEGER NOT NULL,
  employee_id INTEGER NOT NULL REFERENCES employees(id) ON DELETE CASCADE,
  system VARCHAR(40) NOT NULL,      -- ex: 'totvs', 'senior'
  external_id VARCHAR(120) NOT NULL,
  created_at TIMESTAMP DEFAULT now(),
  updated_at TIMESTAMP DEFAULT now(),

  UNIQUE (company_id, system, external_id)
);
```

**Exemplo de uso**: quando o GEOP integrar com um ERP de folha de pagamento, o `employee_id=5` pode ter um `EmployeeExternalId(system="totvs", external_id="00123")` guardando o código do funcionário nesse sistema — sem precisar de uma coluna nova em `employees` a cada integração nova.

Essa tabela é independente de `TimeClockEnrollment`, que continua existindo e é específica para vincular um funcionário a uma matrícula no relógio de ponto físico.

## APIs

### GET `/employees`

Lista funcionários paginados.

**Query params**:
- `page` (padrão 1), `page_size` (padrão 20, máx 100)
- `status` (opcional): filtrar por `active` | `inactive` | `terminated`

**Resposta**:
```json
{
  "items": [
    {
      "id": 1,
      "name": "João Silva",
      "cpf": "12345678901",
      "personal_email": "joao@example.com",
      "phone": "11999999999",
      "status": "active",
      "user_id": 3,
      "avatar_url": null,
      "created_at": "2026-07-04T10:00:00",
      "updated_at": "2026-07-04T10:00:00"
    }
  ],
  "total": 1,
  "page": 1,
  "page_size": 20
}
```

### GET `/employees/search?q=...`

Autocomplete usado pelos seletores de ponto/escala/vínculos no frontend.

**Resposta**:
```json
[{ "id": 1, "name": "João Silva" }]
```

### GET `/employees/{id}`

Retorna dados completos, incluindo endereço e `external_ids`.

### POST `/employees`

Cria um funcionário.

**Body**:
```json
{
  "name": "João Silva",
  "cpf": "12345678901",
  "rg": "1234567",
  "birth_date": "1990-01-15",
  "phone": "11999999999",
  "personal_email": "joao@example.com",
  "address_street": "Rua das Flores",
  "address_number": "123",
  "address_neighborhood": "Centro",
  "address_city": "São Paulo",
  "address_state": "SP",
  "address_zip": "01000-000",
  "status": "active",
  "user_id": null
}
```

Todos os campos além de `name` são opcionais.

### PATCH `/employees/{id}`

Atualiza campos parciais (mesmo shape de `POST`, todos opcionais).

### DELETE `/employees/{id}`

Soft delete (`deleted_at`).

### POST `/employees/{id}/external-ids`

Adiciona um identificador externo. Validado por schema Pydantic (`EmployeeExternalIdCreate`): `system` (1-40 chars) e `external_id` (1-120 chars) obrigatórios — payload malformado retorna `422` em vez de vazar erro de banco como `500`.

**Body**: `{ "system": "totvs", "external_id": "00123" }`

### DELETE `/employees/{id}/external-ids/{external_id_id}`

Remove um identificador externo. A busca do registro é escopada por `employee_id` **e** `company_id` — deletar um `external_id_id` que pertence a outro funcionário da mesma empresa retorna `404`, mesmo que o ID exista.

### POST `/employees/{id}/avatar` (`[E12]`)

Upload de avatar do funcionário, mesmo fluxo de `POST /users/{id}/avatar`: `multipart/form-data` com campo `file` (máx. 2MB, JPEG/PNG/WebP), validação de assinatura de conteúdo (`app.core.storage.validate_file`) e persistência no bucket MinIO/S3 configurado (`app.core.storage.build_object_key` com `entity_type="employee-avatar"`). Atualiza `avatar_url` e gera `AuditEvent` com o diff da URL.

### POST `/employees/import` (`[E14]`)

Importação em lote via CSV (`multipart/form-data`, campo `file`). Colunas aceitas (cabeçalho na primeira linha): `name, cpf, rg, birth_date, phone, personal_email, address_street, address_number, address_complement, address_neighborhood, address_city, address_state, address_zip, status, job_title, hire_date, termination_date, registration_number`. `sector_id` não é suportado no CSV — setor é atribuído depois, individualmente.

Cada linha passa pelo mesmo schema `EmployeeCreate` do endpoint de criação (CPF, datas e CEP com as mesmas validações), garantindo que uma importação e um cadastro manual nunca divirjam nas regras. Uma linha inválida (CPF ruim, CPF duplicado no lote ou já existente, data mal formatada) não interrompe as demais — a resposta traz o resultado linha a linha:

```json
{
  "total": 3,
  "created": 2,
  "failed": 1,
  "results": [
    { "row": 1, "ok": true, "name": "João Silva", "id": 42 },
    { "row": 2, "ok": true, "name": "Maria Souza", "id": 43 },
    { "row": 3, "ok": false, "name": "CPF Ruim", "error": "CPF inválido" }
  ]
}
```

Arquivos que não terminam em `.csv` (e cujo `Content-Type` não é CSV/texto) são rejeitados com `400` antes de qualquer parsing.

## Permissões

- `employee.view`: Visualizar funcionários
- `employee.manage`: Criar/editar/deletar funcionários

Concedidas ao role `admin` por padrão.

## Auditoria e histórico (`[E13]`)

Toda mutação (`create`, `update`, `delete`) de `Employee` gera um `AuditEvent` via `record_event()`, com diff campo a campo, seguindo o padrão dos demais domínios (`users`, `shifts`, etc.).

Criação e remoção de `EmployeeExternalId` também geram `AuditEvent` (`entity_type="employee_external_id"`), igualando a convenção.

`"employee"` foi adicionado a `VALID_ENTITY_TYPES`/`ENTITY_MODEL_MAP` em `app/domain/timeline/service.py`, então o endpoint genérico `GET /timeline/employee/{id}` já funciona sem nenhum código novo no domínio de funcionários — reaproveita os `AuditEvent`s de auditoria já registrados. É assim que o frontend mostra o histórico de mudança de status (e de qualquer outro campo) na aba "Ver histórico" do formulário de edição.

## RLS (Row-Level Security)

Ambas as tabelas (`employees`, `employee_external_ids`) têm política `tenant_isolation`:

```sql
USING (company_id = current_setting('app.current_company_id')::int)
```

## Migração e backfill

A migração `20260703_0043` criou as tabelas e fez backfill automático: **um `Employee` por `User` existente** (não deletado), copiando `name`, `email → personal_email`, `active → status` e vinculando via `user_id`. Isso evita perder integridade referencial em bases que já tinham `User` sendo usado como "funcionário" em ponto/escala.

A migração `20260703_0044` trocou `user_id` → `employee_id` em `schedule_entries`, `time_clock_enrollments` e `time_punches`, com backfill via `UPDATE ... FROM employees e WHERE e.user_id = tabela.user_id AND e.company_id = tabela.company_id`. Veja [docs/escala-de-trabalho.md](escala-de-trabalho.md) e [docs/integracao-escala-ponto.md](integracao-escala-ponto.md) para os detalhes de cada tabela.

**Importante**: `TimePunch.created_by_user_id` não muda — continua sendo o operador/gestor (`User`) que lançou a batida manual, um conceito diferente de quem bateu o ponto (`employee_id`).

A migração `20260704_0045` corrigiu o tamanho da coluna `address_zip` de `VARCHAR(8)` para `VARCHAR(10)`, necessário para acomodar o formato de CEP com hífen (`XXXXX-XXX`, 9 caracteres).

A migração `20260704_0046` adicionou `job_title`, `hire_date`, `termination_date`, `registration_number` e `sector_id` (`[E10]`/`[E11]`), todos `nullable` — não exige backfill.

## Relação com integração de sistemas externos

O GEOP planeja se comunicar futuramente com sistemas externos (ERP, folha de pagamento). O cadastro de Funcionários nasce preparado para isso via `EmployeeExternalId` — ao integrar com um novo sistema, basta gravar o par `(system, external_id)` sem alterar o schema de `employees`, com cada sistema externo tendo seu próprio identificador para o mesmo funcionário, sem conflito.

## Correções pós-implementação (2026-07-04)

Levantamento do domínio recém-implementado encontrou e corrigiu:

- **Índice duplicado em `Employee.status`**: a coluna tinha `index=True` junto com o índice composto `ix_employees_status` já declarado em `__table_args__`, mesmo nome — colidia na criação de tabelas e derrubava toda a suíte de testes (482 testes afetados). Corrigido removendo o `index=True` redundante.
- **Backfill incorreto na migration `20260703_0044`**: copiava `user_id` direto para `employee_id`, assumindo `employees.id == users.id` — válido só quando não há gaps na sequência de IDs (usuário soft-deletado, múltiplas empresas). Corrigido para `JOIN` real via `employees.user_id`.
- **`POST /employees/{id}/external-ids` sem schema**: recebia `body: dict` solto; agora usa `EmployeeExternalIdCreate`.
- **Isolamento em `delete_employee_external_id`**: não validava que o `external_id` pertencia ao `employee_id` do path; agora exige ambos.
- **Auditoria ausente em `EmployeeExternalId`**: create/delete agora geram `AuditEvent`.
- **Validação de dados**: `status` virou `Literal`, `cpf` valida dígito verificador, `birth_date` valida formato, `address_zip` valida e normaliza CEP.

Itens ainda pendentes: ver `docs/backlog.md`, seção P9.

## Melhorias implementadas em 2026-07-04 (E10-E14)

Depois do MVP inicial, o backlog (`docs/backlog.md`) tinha cinco itens de baixa prioridade mapeados a partir da seção "Próximas melhorias possíveis" desta doc. Todos foram implementados:

- **[E10] Campos contratuais**: `job_title`, `hire_date`, `termination_date`, `registration_number` (cargo, admissão, desligamento, matrícula). Salário e dados bancários ficaram de fora — dados sensíveis o suficiente para merecer um tratamento próprio (permissão dedicada, possível criptografia) em vez de entrar juntos.
- **[E11] Vínculo organizacional**: `sector_id`, reaproveitando o cadastro de Setor já usado por `User`, sem duplicar o conceito de departamento.
- **[E12] Upload de avatar**: `POST /employees/{id}/avatar`, mesmo fluxo de `POST /users/{id}/avatar` (MinIO/S3, validação de assinatura de arquivo).
- **[E13] Histórico de status**: reaproveitado o domínio de timeline genérico (`GET /timeline/employee/{id}`) em vez de criar uma tabela de histórico dedicada — os `AuditEvent`s de `update_employee` já carregavam o diff campo a campo, faltava só registrar `"employee"` como entity type válido.
- **[E14] Importação em lote**: `POST /employees/import`, CSV validado linha a linha com o mesmo schema `EmployeeCreate` do cadastro manual.
