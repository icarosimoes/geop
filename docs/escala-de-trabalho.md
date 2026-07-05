# Escala de trabalho e turnos

## Visão geral

Sistema de gestão de escalas de trabalho com suporte a:
- **Turnos** (templates reutilizáveis): Manhã, Tarde, Noite, 12x36, etc.
- **Escalas concretas**: atribuição de turnos/folgas a funcionários por data específica
- **Padrões recorrentes**: semanais (seg-sex) ou rotativos (12x36, 1x2, etc.)
- **Exceções manuais**: edição de dias individuais sem perder o padrão gerado
- **Comparação com batidas**: status de ponto (on_time, late, early_leave, unscheduled, day_off)

## Modelos de dados

### Shift (Turno)

```sql
CREATE TABLE shifts (
  id INTEGER PRIMARY KEY,
  company_id INTEGER NOT NULL,
  name VARCHAR(80) NOT NULL,
  start_time TIME NOT NULL,
  end_time TIME NOT NULL,
  break_start TIME,
  break_end TIME,
  tolerance_minutes INTEGER DEFAULT 10,
  color VARCHAR(7) DEFAULT '#2563eb',
  active BOOLEAN DEFAULT TRUE,
  created_at TIMESTAMP DEFAULT now(),
  updated_at TIMESTAMP DEFAULT now(),
  deleted_at TIMESTAMP
);
```

**Exemplo**: `{ name: "Manhã", start_time: "08:00", end_time: "17:00", tolerance_minutes: 10, color: "#2563eb" }`

### ScheduleEntry (Escala concreta)

```sql
CREATE TABLE schedule_entries (
  id INTEGER PRIMARY KEY,
  company_id INTEGER NOT NULL,
  employee_id INTEGER NOT NULL,
  date DATE NOT NULL,
  shift_id INTEGER,
  source VARCHAR(20) DEFAULT 'manual',  -- 'manual' ou 'generated'
  notes TEXT,
  created_at TIMESTAMP DEFAULT now(),
  updated_at TIMESTAMP DEFAULT now(),
  UNIQUE (company_id, employee_id, date)
);
```

**Exemplo**: `{ employee_id: 1, date: "2026-07-06", shift_id: 5, source: "generated" }`

> **Nota (2026-07-04)**: até a migração `20260703_0044`, esta tabela usava `user_id` (conta de login). Agora referencia `employee_id` (cadastro de RH). Veja [docs/cadastro-funcionarios.md](cadastro-funcionarios.md) para o motivo da separação.

**source="manual"**: Protegido contra sobrescrita por `generate`. Ideal para exceções (folga pontual, troca de turno).  
**source="generated"**: Vem de um padrão recorrente. Pode ser sobrescrito se você gerar novamente.  
**shift_id=NULL**: Dia de folga.

## APIs

### Turnos

#### GET `/timeclock/shifts`
Lista todos os turnos da empresa.

**Resposta**:
```json
[
  {
    "id": 1,
    "name": "Manhã",
    "start_time": "08:00",
    "end_time": "17:00",
    "break_start": null,
    "break_end": null,
    "tolerance_minutes": 10,
    "color": "#2563eb",
    "active": true
  }
]
```

#### POST `/timeclock/shifts`
Cria um novo turno.

**Body**:
```json
{
  "name": "Tarde",
  "start_time": "14:00",
  "end_time": "22:00",
  "tolerance_minutes": 10,
  "color": "#f59e0b"
}
```

#### PATCH `/timeclock/shifts/{id}`
Atualiza um turno (campos opcionais).

#### DELETE `/timeclock/shifts/{id}`
Marca um turno como deletado (soft delete).

**Correção (2026-07-04)**: se o turno estiver referenciado em algum `ScheduleEntry` (ativo ou passado), a exclusão é **bloqueada** com `409 Conflict`:
```json
{ "code": "shift_in_use", "message": "Turno usado em N entradas de escala" }
```
Isso evita órfãos onde `schedule_entries.shift_id` aponta para um turno inexistente/deletado.

---

### Calendário de escala

#### GET `/timeclock/schedule`

Lista entradas de escala para um intervalo de datas com joins automáticos.

**Query params**:
- `start` (obrigatório): data início (YYYY-MM-DD)
- `end` (obrigatório): data fim (YYYY-MM-DD)
- `employee_id` (opcional): filtrar por funcionário
- `shift_id` (opcional): filtrar por turno

> **Nota**: o filtro `sector_id` foi removido junto com a migração para `employee_id` — o cadastro de Funcionários ainda não tem vínculo organizacional (setor). Ver "Próximas melhorias possíveis".

**Resposta**:
```json
[
  {
    "date": "2026-07-06",
    "employee_id": 1,
    "employee_name": "João Silva",
    "shift_id": 1,
    "shift_name": "Manhã",
    "shift_color": "#2563eb",
    "start_time": "08:00",
    "end_time": "17:00",
    "source": "generated"
  }
]
```

#### PUT `/timeclock/schedule/{employee_id}/{date}`

Edita um dia específico (cria ou atualiza entrada).

**Body**:
```json
{
  "shift_id": 1,
  "notes": "Troca com João"
}
```

Define automaticamente `source="manual"`, protegendo contra sobrescrita por gerações futuras.

#### POST `/timeclock/schedule/generate`

Gera escala em lote para um intervalo de datas com um padrão recorrente.

**Body**:
```json
{
  "employee_ids": [1, 2, 3],
  "shift_id": 1,
  "start_date": "2026-07-01",
  "end_date": "2026-07-31",
  "pattern": {
    "type": "weekly",
    "weekdays": [0, 1, 2, 3, 4]
  }
}
```

Ou padrão rotativo:
```json
{
  "employee_ids": [1],
  "shift_id": 2,
  "start_date": "2026-07-01",
  "end_date": "2026-07-31",
  "pattern": {
    "type": "rotating",
    "work_days": 12,
    "off_days": 36
  }
}
```

**Resposta**:
```json
{
  "affected": 31
}
```

**Comportamento**:
- Para cada dia no intervalo, verifica se há entrada com `source="manual"` para esse (employee, date)
- Se houver entrada manual, **pula** (não sobrescreve)
- Senão, calcula se o dia é "trabalhado" pelo padrão e insere/atualiza com `source="generated"`
- Retorna quantidade de linhas afetadas
- **Auditoria (correção 2026-07-04)**: registra um `AuditEvent` por `employee_id` afetado (`entity_type="schedule_entry"`, `entity_id=employee_id`), com diff dos dias alterados — não um evento genérico único por chamada

---

## Frontend

### Páginas

#### `/cadastros/turnos`
CRUD de turnos. Crie e edite os templates que serão usados na escala.

**Componentes**: `page.tsx` (Server Component) → `ShiftManager` (Client)  
**Ações**: fetchShifts, createShiftAction, updateShiftAction, deleteShiftAction

#### `/ponto/escalas`
Calendário mensal de escala por funcionário.

**Componentes**: `page.tsx` (Server Component) → `ScheduleManager` (Client)  
**Ações**: fetchCalendar, setScheduleDayAction, generateScheduleAction

**Funcionalidades**:
- Seleção de mês (prev/next)
- Seleção de funcionário (busca via `searchEmployees`, cadastro de RH — não mais usuários do sistema)
- Visualização de turnos como caixas coloridas no calendário
- Click em dia para editar (popover com select de turno/folga)
- Campos de edição com "Folga" como opção padrão

**Estruturado para expansão** (não implementadas ainda):
- Vista por Turno: agrupa funcionários escalados em um turno específico
- Vista Empresa: todos os funcionários
- Vista por Setor: depende do cadastro de Funcionários ganhar vínculo organizacional (setor) — hoje removido do calendário, ver "Próximas melhorias"

---

## Server Actions (`web/app/actions.ts`)

```typescript
// Turnos
fetchShifts(): Promise<Shift[]>
createShiftAction(body): Promise<MutationResult>
updateShiftAction(id, body): Promise<MutationResult>
deleteShiftAction(id): Promise<MutationResult>

// Calendário
fetchCalendar(params): Promise<CalendarEntry[]>
setScheduleDayAction(employeeId, date, body): Promise<MutationResult>
generateScheduleAction(body): Promise<MutationResult>

// Funcionários (seletor usado por calendário e vínculos de ponto)
searchEmployees(query): Promise<EmployeeOption[]>
```

Todas utilizam `authedFetch()` com token Bearer em cookies.

---

## Padrões de escala

### Weekly (Semanal)

```json
{
  "type": "weekly",
  "weekdays": [0, 1, 2, 3, 4]
}
```

Aplicado a cada semana. Weekdays: 0=seg, 1=ter, ..., 6=dom.

**Exemplo**: `[0,1,2,3,4]` = segunda a sexta (dias úteis)  
**Exemplo**: `[0,2,4]` = segunda, quarta, sexta

### Rotating (Rotativo)

```json
{
  "type": "rotating",
  "work_days": 12,
  "off_days": 36
}
```

Ciclo: 12 dias trabalhando, 36 dias de folga. Total = 48 dias, depois repete.

**Cálculo**:
```python
cycle = work_days + off_days
offset = (target_date - start_date).days % cycle
is_working = offset < work_days
```

**Exemplos comuns**:
- `12x36`: 12 dias trabalho, 36 folga (24h em hotel)
- `1x2`: 1 dia trabalho, 2 folga (para escalas de 3 dias)
- `5x2`: 5 dias trabalho, 2 folga (semana com fim de semana)

---

## Fluxo de uso

### 1. Criar turnos

Na tela `/cadastros/turnos`, crie turnos adicionais conforme a operação exigir,
ou ajuste os turnos padrão (ver seção abaixo).

### Turnos padrão (seed automático)

Toda empresa nova já nasce com 6 turnos pré-cadastrados, para não obrigar o
gestor a montar a escala do zero (`DEFAULT_SHIFTS` em
`api/app/domain/timeclock/service.py`):

| Turno | Horário | Observação |
| --- | --- | --- |
| Manhã | 07:00–15:00 | Recepção |
| Tarde | 15:00–23:00 | Recepção |
| Noite | 23:00–07:00 | Recepção |
| Comercial | 08:00–18:00 (almoço 12:00–13:00) | Administrativo |
| 12x36 Diurno | 07:00–19:00 | Portaria/segurança |
| 12x36 Noturno | 19:00–07:00 | Portaria/segurança |

`ensure_default_shifts()` só cadastra os turnos se a empresa ainda não tiver
nenhum (`Shift.company_id == company_id, deleted_at IS NULL`), e é chamada em
dois pontos:

1. **`create_tenant`** (`api/app/domain/platform/service.py`): toda empresa
   criada pelo painel da plataforma recebe os turnos automaticamente.
2. **Backfill manual** (`api/app/backfill_default_shifts.py`): script
   idempotente para aplicar aos tenants que já existiam antes dessa mudança.
   Rodar com `.venv/bin/python -m app.backfill_default_shifts` (ou
   `docker exec registro-api-1 python -m app.backfill_default_shifts` em
   containers já subindo).

Esses turnos são apenas o ponto de partida — o gestor pode renomear, ajustar
horários/tolerância ou desativar (`active=false`) qualquer um deles em
`/cadastros/turnos`, como qualquer outro turno.

### 2. Gerar escala base

O endpoint já existe e está migrado para `employee_id`; falta o botão/formulário "Gerar escala" na tela `/ponto/escalas` (ver "Próximas melhorias possíveis"). Por ora, chame diretamente:

```json
POST /timeclock/schedule/generate
{
  "employee_ids": [1, 2, 3, 4],
  "shift_id": 1,
  "start_date": "2026-07-01",
  "end_date": "2026-07-31",
  "pattern": {
    "type": "weekly",
    "weekdays": [0, 1, 2, 3, 4]
  }
}
```

Resultado: todos os dias úteis de julho com o turno "Manhã".

### 3. Fazer exceções manuais

Clique em um dia do calendário para editar:
- Trocar turno (ex.: João sai do Manhã e entra Tarde)
- Marcar folga (shift_id=NULL)
- Adicionar notas ("Troca com Maria")

Essa edição fica protegida: se você gerar escala novamente para o mesmo período, esse dia **não será sobrescrito**.

### 4. Integração com batidas

Quando um funcionário bate ponto, a API compara:
- Horário batido vs. `shift.start_time + tolerance`
- Se agendado para folga (`shift_id=NULL`), status="day_off"
- Se sem escala definida, status="unscheduled"
- Senão, calcula `on_time` / `late` / `early_leave`

Veja `/api/v1/timeclock/punches` para ver os status.

#### Turnos noturnos (atravessam meia-noite)

**Correção (2026-07-04)**: `evaluate_status()` detecta turnos onde `end_time < start_time` (ex.: 22:00–06:00) e ajusta a data de referência conforme o tipo de batida:
- **Entrada** (22:00–23:59): compara contra `start_dt` no dia agendado
- **Saída** (00:00–06:00 do dia seguinte): compara contra `end_dt` = dia agendado + 1
- **Tipo não informado**: infere pela hora do relógio (madrugada → saída do turno anterior; noite → entrada do turno do dia)

Antes da correção, uma batida de saída às 06:10 do dia seguinte a um turno 22:00–06:00 era comparada contra o `end_time` do mesmo dia da escala, gerando status incorreto (`unscheduled` ou `late` com atraso de quase 24h).

---

## Testes

14 testes em `api/tests/test_timeclock.py`:

```bash
pytest tests/test_timeclock.py -v
```

Cobertura:
- `evaluate_status()`: regra pura de comparação horário (6 testes)
- CRUD turnos (1 teste)
- Calendário: set day, get calendar (2 testes)
- Geração: weekly e rotating patterns (2 testes)
- Proteção contra sobrescrita manual (1 teste)
- Webhook: ingesta e deduplicação (3 testes)
- Punch manual e correção (1 teste)

---

## Permissões

4 permissões novas:
- `shift.view`: Visualizar turnos
- `shift.manage`: Criar/editar/deletar turnos
- `schedule.view`: Visualizar calendário de escala
- `schedule.manage`: Editar dias e gerar escalas

Concedidas ao role `admin` por padrão. Configure em `/perfis` para usuários normais se necessário.

---

## Banco de horas e ajuste de ponto (2026-07-05)

Duas features inspiradas em concorrentes (Sólides, Flash, PontoSimples), construídas sobre a base de turnos/escala/pontos já existente. Migration `20260705_0048`.

### Banco de horas

`HourBankEntry` (`hour_bank_entries`) guarda um lançamento por dia e por funcionário:

- **`source="calculated"`**: gerado por `recalculate_hour_bank()` — para cada dia do período, resolve o turno agendado (`_resolve_schedule_for_date`), calcula `expected_minutes` (duração do turno menos intervalo) e pareia as batidas `in`/`out` do dia em `_pair_punches_worked_minutes()` para obter `worked_minutes`. `balance_minutes = worked - expected`. Idempotente: recalcular o mesmo período substitui os lançamentos existentes.
- **`source="initial_balance"`**: um único lançamento por funcionário, com `balance_minutes` definido manualmente pelo RH (ex.: saldo migrado de outro sistema), com data de vigência.
- Saldo total do funcionário = soma de todos os lançamentos (`GET /timeclock/hour-bank/{employee_id}`).

**Limitação conhecida**: turnos noturnos cuja saída cai no dia seguinte contam o tempo trabalhado no dia da batida de saída, não no dia do turno — o cálculo por par in/out é por data corrida, não por "dia de turno". Aceitável para o MVP; revisar se virar ponto de atrito real.

Endpoints (`hour_bank.view`/`hour_bank.manage`):
- `GET /timeclock/hour-bank/{employee_id}` — saldo total + extrato
- `POST /timeclock/hour-bank/{employee_id}/recalculate` — recalcula um intervalo de datas
- `POST /timeclock/hour-bank/{employee_id}/initial-balance` — define/substitui o saldo inicial
- `GET /timeclock/mobile/hour-bank` — o próprio funcionário vê seu saldo (Portal do Colaborador)

Frontend: `/ponto/banco-de-horas` (RH, busca por funcionário) e aba "Banco" no app `colaborador/`.

### Ajuste de ponto com aprovação

`PunchAdjustmentRequest` (`punch_adjustment_requests`): o funcionário solicita pelo Portal do Colaborador a correção de uma batida existente (`punch_id` informado) ou o lançamento de uma batida esquecida (`punch_id=null`), com motivo obrigatório. Fica `status="pending"` até um gestor aprovar ou rejeitar.

- **Aprovar** uma correção de batida existente chama `update_punch()` (recalcula o `status` on_time/late/etc. automaticamente); aprovar uma batida esquecida chama `create_manual_punch()` — ambos reaproveitados do fluxo administrativo já existente.
- **Rejeitar** apenas marca `status="rejected"` com `review_notes` opcional; nenhuma batida é criada/alterada.
- Uma solicitação só pode ser revisada uma vez (`409 already_reviewed` numa segunda tentativa).
- Ao criar a solicitação, todos os usuários com permissão `punch_adjustment.manage` (ou wildcard `*`) recebem notificação in-app.

Endpoints:
- `POST /timeclock/mobile/adjustments` / `GET /timeclock/mobile/adjustments` — funcionário cria e lista as próprias solicitações
- `GET /timeclock/adjustments` (`punch_adjustment.view`) — RH lista por status/funcionário
- `POST /timeclock/adjustments/{id}/review` (`punch_adjustment.manage`) — aprova (`approve: true`) ou rejeita (`approve: false`)

Frontend: `/ponto/ajustes` (fila de aprovação, RH) e aba "Banco" no app `colaborador/` (solicitar + acompanhar status).

### Testes

`api/tests/test_hour_bank.py` (5 testes) e `api/tests/test_punch_adjustments.py` (8 testes): cálculo exato/com hora extra, saldo inicial substituindo o anterior, correção de batida existente vs. batida esquecida, dupla revisão bloqueada, isolamento por permissão.

---

## Notas de implementação

### Soft delete vs. hard delete

- **Shifts**: soft delete (`deleted_at`)
- **ScheduleEntries**: sem soft delete (são ephemeral, sempre regeneráveis)

### RLS (Row-Level Security)

Ambas as tabelas têm política `tenant_isolation`:
```sql
USING (company_id = current_setting('app.current_company_id')::int)
```

Garante que um usuário da empresa A nunca vê dados da empresa B.

### Índices

```sql
CREATE INDEX ix_schedule_entries_employee_date ON schedule_entries(company_id, employee_id, date);
```

Otimizam queries de calendário (`GET /timeclock/schedule`).

### Padrão semanal vs. rotativo

- **Weekly**: recalculado toda semana (estateless)
- **Rotating**: cálculo baseado em dias desde `start_date` (stateless)

Ambos são idempotentes: gerar duas vezes o mesmo período com o mesmo padrão não duplica.

---

## Próximas melhorias possíveis

1. **UI de geração** (pendente): Botão "Gerar escala" na tela `/ponto/escalas` com form (endpoint já pronto e migrado para `employee_id`)
2. **Vistas por Turno/Empresa/Setor**: Expandir `ScheduleManager` com abas (Vista por Setor depende do cadastro de Funcionários ganhar vínculo organizacional)
3. **Histórico**: Auditar mudanças em escalas (já temos `AuditEvent`)
4. **Publicação de período**: Congelar escala de julho e marcar como "oficial"
5. **Conflitos automáticos**: Alertar se 2 funcionários do mesmo turno estão de folga no mesmo dia
6. **Impressão**: Exportar calendário como PDF para mural
7. **Notificações**: Avisar funcionário quando escala mudar
8. **Integração Mobile**: App pra funcionários ver sua escala pessoal

---

## Deployment

A migration `20260703_0042` dropcou `work_schedules` e criou `shifts + schedule_entries`.

Se precisar reverter (não recomendado em produção):
```bash
alembic downgrade -1
```

Isso recria `work_schedules` e deleta as novas tabelas.
