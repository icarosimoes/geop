# Integração: Escala vs. Batidas de ponto

Quando um funcionário bate ponto (via dispositivo Control iD ou manualmente), a API compara o horário batido com a escala prevista e atribui um **status** à batida.

## Fluxo de ingesta

```
Device/Manual → POST /integrations/control-id/{token}/punches
              ↓
    resolve_schedule_for_date(user_id, date)
              ↓
        evaluate_status(shift, punched_at, punch_type)
              ↓
        INSERT TimePunch com status
              ↓
    invalidate_dashboard(company_id)
```

## resolve_schedule_for_date()

**Função**: `api/app/domain/timeclock/service.py`

Busca a entrada de escala para a data/funcionário e retorna um tupla: `(Shift | None, forced_status | None)`

```python
async def _resolve_schedule_for_date(
    session: AsyncSession,
    company_id: int,
    user_id: int,
    target_date: date,
) -> tuple[Shift | None, str | None]:
    entry = await session.scalar(
        select(ScheduleEntry).where(
            ScheduleEntry.company_id == company_id,
            ScheduleEntry.user_id == user_id,
            ScheduleEntry.date == target_date,
        )
    )
    # Sem linha na tabela
    if entry is None:
        return None, "unscheduled"
    
    # Linha existe com shift_id = NULL (folga)
    if entry.shift_id is None:
        return None, "day_off"
    
    # Linha existe com turno
    shift = await session.scalar(
        select(Shift).where(Shift.id == entry.shift_id, Shift.deleted_at.is_(None))
    )
    return shift, None
```

### Resultados possíveis:

| Caso | Retorno | Status imposto |
|------|---------|---------------|
| Sem escala | `(None, "unscheduled")` | Ponto é registrado como "unscheduled" |
| Folga explícita | `(None, "day_off")` | Ponto é registrado como "day_off" |
| Turno encontrado | `(Shift, None)` | Sem status forçado; vai pra `evaluate_status()` |
| Turno deletado | `(None, None)` | Trata como sem escala ("unscheduled") |

## evaluate_status()

**Função**: `api/app/domain/timeclock/service.py`

Compara o horário batido com o turno para decidir on_time / late / early_leave.

```python
def evaluate_status(
    shift: Shift | None,
    punched_at: datetime,
    punch_type: str | None,
) -> str:
    if shift is None:
        return "unscheduled"
    
    tolerance = timedelta(minutes=shift.tolerance_minutes)
    punch_dt = datetime.combine(punched_at.date(), punched_at.time())
    start_dt = datetime.combine(punched_at.date(), shift.start_time)
    end_dt = datetime.combine(punched_at.date(), shift.end_time)
    
    # Saída: compara com fim do turno
    if punch_type == "out":
        return "early_leave" if punch_dt < end_dt - tolerance else "on_time"
    
    # Entrada: compara com início do turno
    if punch_type == "in":
        return "late" if punch_dt > start_dt + tolerance else "on_time"
    
    # Tipo não informado: assume o limite mais próximo
    distance_to_start = abs((punch_dt - start_dt).total_seconds())
    distance_to_end = abs((punch_dt - end_dt).total_seconds())
    if distance_to_start <= distance_to_end:
        return "late" if punch_dt > start_dt + tolerance else "on_time"
    return "early_leave" if punch_dt < end_dt - tolerance else "on_time"
```

### Resultados possíveis:

| Cenário | Status |
|---------|--------|
| Sem escala | `"unscheduled"` |
| Folga | `"day_off"` |
| Entrada atrasada | `"late"` |
| Entrada no prazo | `"on_time"` |
| Saída antecipada | `"early_leave"` |
| Saída no prazo | `"on_time"` |

### Exemplos

**Turno**: 08:00-17:00, tolerance=10 min

| Hora batida | Tipo | Status |
|-------------|------|--------|
| 08:05 | "in" | on_time (dentro do tolerance) |
| 08:15 | "in" | late (8:15 > 8:10) |
| 16:50 | "out" | early_leave (16:50 < 16:50) |
| 17:05 | "out" | on_time (17:05 > 16:50) |
| 08:30 | null | late (mais próximo de 08:00) |

## Fluxo completo: Exemplo

### Setup

1. **Turnos criados**:
   - ID 1: "Manhã" (08:00-17:00, tolerance=10)

2. **Escala gerada**:
   ```
   2026-07-06 (seg), user_id=1, shift_id=1, source="generated"
   ```

3. **Dispositivo configurado**:
   - Token: `abc123`
   - Vinculado: user_id=1, external_id="0001"

### Batida recebida

```json
POST /integrations/control-id/abc123/punches
{
  "external_id": "0001",
  "timestamp": "2026-07-06T08:15:00",
  "type": "in",
  "event_id": "evt-2026-07-06-001"
}
```

### Processamento

1. **Autenticação**: `device.webhook_token = "abc123"` ✓
2. **Resolução de usuário**: `TimeClockEnrollment.external_id = "0001"` → `user_id = 1` ✓
3. **Resolução de escala**:
   - `ScheduleEntry.date = 2026-07-06, user_id = 1` encontrado
   - `shift_id = 1`, `Shift.start_time = 08:00`, `tolerance = 10` ✓
   - `forced_status = None` (não é folga/unscheduled)
4. **Avaliação**:
   - `punch_type = "in"`, `punched_at = 08:15`, `start_time = 08:00`
   - `08:15 > 08:10` (start + tolerance) → `"late"` ✓
5. **Inserção**:
   ```json
   TimePunch {
     user_id: 1,
     device_id: X,
     punched_at: "2026-07-06T08:15:00",
     punch_type: "in",
     source: "device",
     status: "late",
     external_event_id: "evt-2026-07-06-001"
   }
   ```

### Visualização

Na tela `/ponto` (Batidas), aparece:

| Data/hora | Funcionário | Origem | Tipo | Status | Observação |
|-----------|-------------|--------|------|--------|-----------|
| 2026-07-06 08:15 | João Silva | Control iD | Entrada | **Atraso** | — |

## Casos edge

### Sem escala definida

**Entrada**: 09:00, user_id=1, data=2026-07-06 (sem ScheduleEntry)

→ `resolve_schedule_for_date()` retorna `(None, "unscheduled")`  
→ `evaluate_status(None, ...)` retorna `"unscheduled"`  
→ Status: **unscheduled**

**Visualização**: "Sem escala" (cor cinzenta)

### Folga explícita

**Escala**: 2026-07-06, user_id=1, shift_id=NULL

**Entrada**: 09:00, user_id=1, data=2026-07-06

→ `resolve_schedule_for_date()` retorna `(None, "day_off")`  
→ `ingest_punch()` força status = `"day_off"`  
→ Status: **day_off**

**Visualização**: "Folga" (cor diferente de unscheduled)

### Turno deletado (soft delete)

**Escala**: shift_id=5, mas Shift com id=5 tem `deleted_at != NULL`

→ `resolve_schedule_for_date()` não encontra o Shift  
→ Retorna `(None, None)` (como se fosse unscheduled)  
→ Status: **unscheduled**

(Note: a escala não desaparece, só o turno é marcado como inativo. Se restaurar o turno, a batida continua "unscheduled".)

### Deduplica por event_id

**Primeira entrada**: `event_id="evt-001"`, timestamp=08:15 → cria TimePunch com status "late"

**Mesma entrada novamente**: `event_id="evt-001"`, timestamp=08:15 → 
→ `ingest_punch()` verifica duplicado  
→ Retorna o TimePunch existente (sem criar novo)

**Visualização**: Aparece só uma batida

## Diagrama de decisão

```
Batida recebida
    ↓
Escala existe?
    ├─ NÃO → status = "unscheduled"
    └─ SIM
        ↓
        shift_id = NULL?
            ├─ SIM → status = "day_off"
            └─ NÃO
                ↓
                Comparar horário vs shift.start/end
                    ├─ Atrasado → "late"
                    ├─ Antecipado → "early_leave"
                    └─ No prazo → "on_time"
```

## Testes

Ver `api/tests/test_timeclock.py`:

- `test_evaluate_status_*` (6 testes): regra pura
- `test_webhook_ingests_punch_and_matches_schedule`: fluxo completo via webhook com escala gerada
- `test_manual_punch_and_correction`: fluxo manual via `/punches` POST/PATCH

Rodar:
```bash
pytest tests/test_timeclock.py -v
```

## Resumo de status

| Status | Significa | Triggerado por |
|--------|-----------|---|
| `on_time` | Ponto batido no horário (dentro do tolerance) | Escala existe + hora OK |
| `late` | Entrada atrasada ou saída adiantada | Escala existe + hora fora |
| `early_leave` | Saída antes do previsto | Escala existe + punch_type="out" + hora < end |
| `unscheduled` | Sem escala definida para esse dia | ScheduleEntry não existe |
| `day_off` | Dia de folga explícito | ScheduleEntry com shift_id=NULL |

Todos os status são armazenados em `TimePunch.status` para auditoria e relatórios.
