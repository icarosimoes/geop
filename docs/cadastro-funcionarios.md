# Cadastro de Funcionários

## Visão geral

O `Employee` é a entidade de RH que representa quem trabalha no hotel — separada de `User` (conta de login do sistema). Antes desta separação, o módulo de ponto/escala usava `User` como se fosse o "funcionário", misturando dois conceitos distintos:

- **User**: quem tem login e senha no Registro (pode ser um gerente, recepcionista, ou até um usuário de plataforma sem vínculo operacional).
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

  -- Vínculo opcional com User (nem todo employee loga no sistema)
  user_id INTEGER REFERENCES users(id) ON DELETE SET NULL,

  created_at TIMESTAMP DEFAULT now(),
  updated_at TIMESTAMP DEFAULT now(),
  deleted_at TIMESTAMP,

  UNIQUE (company_id, cpf)
);
```

**Escopo atual (MVP)**: dados pessoais básicos + status. Campos contratuais (cargo, admissão, salário, matrícula, banco, documentos) ficam fora por enquanto — o modelo deixa espaço para crescer.

**CPF**: opcional (nem todo funcionário precisa ter CPF cadastrado de imediato), mas único por empresa quando informado. Validado no schema Pydantic com dígito verificador real (mesmo algoritmo de `app.core.validators.validate_cpf`, usado em `fiscal_requests`) e normalizado para 11 dígitos sem pontuação antes de persistir.

**birth_date**: validado no formato `YYYY-MM-DD`; qualquer outro formato retorna `422`.

**address_zip**: validado como CEP brasileiro de 8 dígitos e normalizado para `XXXXX-XXX` (coluna `VARCHAR(10)` desde a migration `20260704_0045`, que corrigiu o tamanho original de 8 caracteres — insuficiente para o hífen).

**status**: `Literal["active", "inactive", "terminated"]` no schema Pydantic (não é mais string livre) — alinhado com `STATUS_LABELS` do frontend em `web/app/cadastros/funcionarios/manager.tsx`.

**Soft delete**: `deleted_at`, igual ao padrão de `User`/`Shift`. Registros deletados não aparecem em listagens.

### EmployeeExternalId (integrações futuras)

Tabela 1:N para guardar identificadores de sistemas externos (ERP, folha de pagamento), pensando na integração futura do Registro com outros sistemas:

```sql
CREATE TABLE employee_external_ids (
  id INTEGER PRIMARY KEY,
  company_id INTEGER NOT NULL,
  employee_id INTEGER NOT NULL REFERENCES employees(id) ON DELETE CASCADE,
  system VARCHAR(40) NOT NULL,      -- ex: 'totvs', 'senior', 'chess-hotel'
  external_id VARCHAR(120) NOT NULL,
  created_at TIMESTAMP DEFAULT now(),
  updated_at TIMESTAMP DEFAULT now(),

  UNIQUE (company_id, system, external_id)
);
```

**Exemplo de uso**: quando o Registro integrar com um ERP de folha de pagamento, o `employee_id=5` pode ter um `EmployeeExternalId(system="totvs", external_id="00123")` guardando o código do funcionário nesse sistema — sem precisar de uma coluna nova em `employees` a cada integração nova.

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

## Permissões

- `employee.view`: Visualizar funcionários
- `employee.manage`: Criar/editar/deletar funcionários

Concedidas ao role `admin` por padrão.

## Auditoria

Toda mutação (`create`, `update`, `delete`) de `Employee` gera um `AuditEvent` via `record_event()`, com diff campo a campo, seguindo o padrão dos demais domínios (`users`, `shifts`, etc.).

Criação e remoção de `EmployeeExternalId` também geram `AuditEvent` (`entity_type="employee_external_id"`), igualando a convenção.

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

## Relação com integração de sistemas externos

O Registro planeja se comunicar futuramente com sistemas externos (ERP, folha de pagamento). O cadastro de Funcionários nasce preparado para isso via `EmployeeExternalId` — ao integrar com um novo sistema, basta gravar o par `(system, external_id)` sem alterar o schema de `employees`.

Isso é análogo ao padrão já usado pela integração do [Chess Hotel](integracao-escala-ponto.md), mas desacoplado: cada sistema externo pode ter seu próprio identificador para o mesmo funcionário, sem conflito.

## Correções pós-implementação (2026-07-04)

Levantamento do domínio recém-implementado encontrou e corrigiu:

- **Índice duplicado em `Employee.status`**: a coluna tinha `index=True` junto com o índice composto `ix_employees_status` já declarado em `__table_args__`, mesmo nome — colidia na criação de tabelas e derrubava toda a suíte de testes (482 testes afetados). Corrigido removendo o `index=True` redundante.
- **Backfill incorreto na migration `20260703_0044`**: copiava `user_id` direto para `employee_id`, assumindo `employees.id == users.id` — válido só quando não há gaps na sequência de IDs (usuário soft-deletado, múltiplas empresas). Corrigido para `JOIN` real via `employees.user_id`.
- **`POST /employees/{id}/external-ids` sem schema**: recebia `body: dict` solto; agora usa `EmployeeExternalIdCreate`.
- **Isolamento em `delete_employee_external_id`**: não validava que o `external_id` pertencia ao `employee_id` do path; agora exige ambos.
- **Auditoria ausente em `EmployeeExternalId`**: create/delete agora geram `AuditEvent`.
- **Validação de dados**: `status` virou `Literal`, `cpf` valida dígito verificador, `birth_date` valida formato, `address_zip` valida e normaliza CEP.

Itens ainda pendentes: ver `docs/backlog.md`, seção P9.

## Próximas melhorias possíveis

1. **Campos contratuais**: cargo, data de admissão/desligamento, salário, matrícula, dados bancários, documentos anexados
2. **Vínculo organizacional**: setor/departamento (hoje removido do calendário de escala por não existir ainda)
3. **Upload de avatar**: já existe o campo `avatar_url`, falta o fluxo de upload (padrão S3/MinIO já usado em `attachments`)
4. **Histórico de status**: registrar quando e por que um funcionário foi desligado
5. **Importação em lote**: CSV/planilha para cadastro inicial de funcionários existentes
