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
  user_id INTEGER NOT NULL,
  date DATE NOT NULL,
  shift_id INTEGER,
  source VARCHAR(20) DEFAULT 'manual',  -- 'manual' ou 'generated'
  notes TEXT,
  created_at TIMESTAMP DEFAULT now(),
  updated_at TIMESTAMP DEFAULT now(),
  UNIQUE (company_id, user_id, date)
);
```

**Exemplo**: `{ user_id: 1, date: "2026-07-06", shift_id: 5, source: "generated" }`

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

---

### Calendário de escala

#### GET `/timeclock/schedule`

Lista entradas de escala para um intervalo de datas com joins automáticos.

**Query params**:
- `start` (obrigatório): data início (YYYY-MM-DD)
- `end` (obrigatório): data fim (YYYY-MM-DD)
- `user_id` (opcional): filtrar por funcionário
- `sector_id` (opcional): filtrar por setor
- `shift_id` (opcional): filtrar por turno

**Resposta**:
```json
[
  {
    "date": "2026-07-06",
    "user_id": 1,
    "user_name": "João Silva",
    "sector_id": 2,
    "sector_name": "Recepção",
    "shift_id": 1,
    "shift_name": "Manhã",
    "shift_color": "#2563eb",
    "start_time": "08:00",
    "end_time": "17:00",
    "source": "generated"
  }
]
```

#### PUT `/timeclock/schedule/{user_id}/{date}`

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
  "user_ids": [1, 2, 3],
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
  "user_ids": [1],
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
- Para cada dia no intervalo, verifica se há entrada com `source="manual"` para esse (user, date)
- Se houver entrada manual, **pula** (não sobrescreve)
- Senão, calcula se o dia é "trabalhado" pelo padrão e insere/atualiza com `source="generated"`
- Retorna quantidade de linhas afetadas

---

## Frontend

### Páginas

#### `/cadastros/turnos`
CRUD de turnos. Crie e edite os templates que serão usados na escala.

**Componentes**: `page.tsx` (Server Component) → `ShiftManager` (Client)  
**Ações**: fetchShifts, createShiftAction, updateShiftAction, deleteShiftAction

#### `/cadastros/escalas`
Calendário mensal de escala por funcionário.

**Componentes**: `page.tsx` (Server Component) → `ScheduleManager` (Client)  
**Ações**: fetchCalendar, setScheduleDayAction, generateScheduleAction

**Funcionalidades**:
- Seleção de mês (prev/next)
- Seleção de funcionário
- Visualização de turnos como caixas coloridas no calendário
- Click em dia para editar (popover com select de turno/folga)
- Campos de edição com "Folga" como opção padrão

**Estruturado para expansão** (não implementadas ainda):
- Vista por Setor: agrupa funcionários por setor, mostra calendário única
- Vista por Turno: agrupa funcionários escalados em um turno específico
- Vista Empresa: todos os funcionários, agrupados por setor

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
setScheduleDayAction(userId, date, body): Promise<MutationResult>
generateScheduleAction(body): Promise<MutationResult>
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

Na tela `/cadastros/turnos`, crie:
- "Manhã" (08:00-17:00)
- "Tarde" (14:00-22:00)
- "Noite" (22:00-06:00)
- "12x36 Diurno" (06:00-18:00)
- etc.

### 2. Gerar escala base

Na tela `/cadastros/escalas`, selecione funcionários e use o botão "Gerar escala" (ainda não implementado no UI, mas o endpoint existe):

```json
POST /timeclock/schedule/generate
{
  "user_ids": [1, 2, 3, 4],
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
CREATE INDEX ix_schedule_entries_date ON schedule_entries(company_id, date);
CREATE INDEX ix_schedule_entries_user_date ON schedule_entries(company_id, user_id, date);
```

Otimizam queries de calendário (`GET /timeclock/schedule`).

### Padrão semanal vs. rotativo

- **Weekly**: recalculado toda semana (estateless)
- **Rotating**: cálculo baseado em dias desde `start_date` (stateless)

Ambos são idempotentes: gerar duas vezes o mesmo período com o mesmo padrão não duplica.

---

## Próximas melhorias possíveis

1. **UI de geração**: Botão "Gerar escala" na tela `/cadastros/escalas` com form
2. **Vistas por Setor/Turno/Empresa**: Expandir `ScheduleManager` com abas
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
