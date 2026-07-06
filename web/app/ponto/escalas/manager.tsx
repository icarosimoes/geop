"use client";

import { useEffect, useState } from "react";
import { ChevronLeft, ChevronRight, Wand2 } from "lucide-react";
import {
  fetchCalendar,
  fetchShifts,
  generateScheduleAction,
  searchEmployees,
  setScheduleDayAction,
  type CalendarEntry,
  type EmployeeOption,
  type Shift,
} from "@/app/actions";
import type { TenantUser } from "@/lib/api";

function hasPermission(user: TenantUser, code: string) {
  return user.permissions.includes("*") || user.permissions.includes(code);
}

const MONTH_NAMES = [
  "Janeiro", "Fevereiro", "Março", "Abril", "Maio", "Junho",
  "Julho", "Agosto", "Setembro", "Outubro", "Novembro", "Dezembro",
];

const DAY_NAMES = ["Dom", "Seg", "Ter", "Qua", "Qui", "Sex", "Sab"];

interface CalendarDay {
  date: string;
  dayOfMonth: number;
  isCurrentMonth: boolean;
  entries: Map<number, CalendarEntry>;
}

function fmtDate(value: string): string {
  const [y, m, d] = value.split("-");
  return `${d}/${m}/${y}`;
}

function getDaysInMonth(year: number, month: number): number {
  return new Date(year, month + 1, 0).getDate();
}

function getFirstDayOfMonth(year: number, month: number): number {
  return new Date(year, month, 1).getDay();
}

function buildCalendar(year: number, month: number, entries: CalendarEntry[]): CalendarDay[] {
  const daysInMonth = getDaysInMonth(year, month);
  const firstDay = getFirstDayOfMonth(year, month);
  const entriesMap = new Map<string, Map<number, CalendarEntry>>();

  for (const entry of entries) {
    if (!entriesMap.has(entry.date)) entriesMap.set(entry.date, new Map());
    entriesMap.get(entry.date)!.set(entry.employee_id, entry);
  }

  const days: CalendarDay[] = [];
  for (let i = 0; i < firstDay; i++) {
    days.push({ date: "", dayOfMonth: 0, isCurrentMonth: false, entries: new Map() });
  }

  for (let day = 1; day <= daysInMonth; day++) {
    const date = `${year}-${String(month + 1).padStart(2, "0")}-${String(day).padStart(2, "0")}`;
    days.push({
      date,
      dayOfMonth: day,
      isCurrentMonth: true,
      entries: entriesMap.get(date) ?? new Map(),
    });
  }

  return days;
}

export function ScheduleManager({ user }: { user: TenantUser }) {
  const [shifts, setShifts] = useState<Shift[]>([]);
  const [employees, setEmployees] = useState<EmployeeOption[]>([]);
  const [selectedEmployeeId, setSelectedEmployeeId] = useState<number | null>(null);
  const [date, setDate] = useState(new Date());
  const [entries, setEntries] = useState<CalendarEntry[]>([]);
  const [loading, setLoading] = useState(false);
  const [selectedDay, setSelectedDay] = useState<CalendarEntry | null>(null);
  const [selectedShift, setSelectedShift] = useState<number | null>(null);
  const [saving, setSaving] = useState(false);
  const [toast, setToast] = useState("");
  const canManage = hasPermission(user, "schedule.manage");

  const [showGenerateForm, setShowGenerateForm] = useState(false);
  const [genEmployeeIds, setGenEmployeeIds] = useState<number[]>([]);
  const [genShiftId, setGenShiftId] = useState<number | null>(null);
  const [genStartDate, setGenStartDate] = useState("");
  const [genEndDate, setGenEndDate] = useState("");
  const [genPatternType, setGenPatternType] = useState<"weekly" | "rotating">("weekly");
  const [genWeekdays, setGenWeekdays] = useState<number[]>([0, 1, 2, 3, 4]);
  const [genWorkDays, setGenWorkDays] = useState(12);
  const [genOffDays, setGenOffDays] = useState(36);
  const [generating, setGenerating] = useState(false);

  function showToast(msg: string) {
    setToast(msg);
    setTimeout(() => setToast(""), 2600);
  }

  function reload() {
    if (selectedEmployeeId == null) return;
    setLoading(true);
    const start = `${date.getFullYear()}-${String(date.getMonth() + 1).padStart(2, "0")}-01`;
    const daysInMonth = getDaysInMonth(date.getFullYear(), date.getMonth());
    const end = `${date.getFullYear()}-${String(date.getMonth() + 1).padStart(2, "0")}-${String(daysInMonth).padStart(2, "0")}`;

    fetchCalendar({
      start,
      end,
      employeeId: selectedEmployeeId,
    })
      .then(setEntries)
      .finally(() => setLoading(false));
  }

  useEffect(() => {
    fetchShifts().then(setShifts);
    searchEmployees("").then((results) => {
      setEmployees(results);
      if (results.length > 0) setSelectedEmployeeId((prev) => prev ?? results[0].id);
    });
  }, []);

  useEffect(() => {
    reload();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [selectedEmployeeId, date]);

  async function handleDayClick(day: CalendarDay) {
    if (!canManage || !day.isCurrentMonth || selectedEmployeeId == null) return;
    const entry = day.entries.get(selectedEmployeeId);
    setSelectedDay(
      entry ?? {
        date: day.date,
        employee_id: selectedEmployeeId,
        employee_name: "",
        shift_id: null,
        shift_name: null,
        shift_color: null,
        start_time: null,
        end_time: null,
        source: "manual",
      },
    );
    setSelectedShift(entry?.shift_id ?? null);
  }

  async function handleSaveDay() {
    if (!selectedDay || selectedEmployeeId == null) return;
    setSaving(true);
    const result = await setScheduleDayAction(selectedEmployeeId, selectedDay.date, {
      shift_id: selectedShift,
    });
    setSaving(false);
    if (result.ok) {
      showToast("Dia atualizado.");
      setSelectedDay(null);
      reload();
    } else {
      showToast(result.error ?? "Erro ao salvar.");
    }
  }

  function toggleWeekday(day: number) {
    setGenWeekdays((prev) => (prev.includes(day) ? prev.filter((d) => d !== day) : [...prev, day].sort()));
  }

  function toggleGenEmployee(id: number) {
    setGenEmployeeIds((prev) => (prev.includes(id) ? prev.filter((e) => e !== id) : [...prev, id]));
  }

  async function handleGenerate(e: React.FormEvent) {
    e.preventDefault();
    if (genEmployeeIds.length === 0 || !genShiftId || !genStartDate || !genEndDate) {
      showToast("Preencha funcionários, turno e período.");
      return;
    }
    setGenerating(true);
    const pattern =
      genPatternType === "weekly"
        ? ({ type: "weekly" as const, weekdays: genWeekdays })
        : ({ type: "rotating" as const, work_days: genWorkDays, off_days: genOffDays });
    const result = await generateScheduleAction({
      employee_ids: genEmployeeIds,
      shift_id: genShiftId,
      start_date: genStartDate,
      end_date: genEndDate,
      pattern,
    });
    setGenerating(false);
    if (result.ok) {
      showToast(`Escala gerada (${result.data?.affected ?? 0} dias afetados).`);
      setShowGenerateForm(false);
      setGenEmployeeIds([]);
      setGenShiftId(null);
      setGenStartDate("");
      setGenEndDate("");
      reload();
    } else {
      showToast(result.error ?? "Erro ao gerar escala.");
    }
  }

  const days = buildCalendar(date.getFullYear(), date.getMonth(), entries);
  const year = date.getFullYear();
  const month = date.getMonth();

  return (
    <section className="module-panel">
      <div style={{ padding: "var(--sp-4) var(--sp-5)", borderBottom: "1px solid var(--field-border)" }}>
        <div style={{ display: "flex", gap: "var(--sp-3)", alignItems: "flex-end", flexWrap: "wrap" }}>
          <div className="report-filter-field" style={{ flex: "1 1 220px", maxWidth: 320 }}>
            <label htmlFor="schedule_employee">Funcionário</label>
            <select
              id="schedule_employee"
              value={selectedEmployeeId ?? ""}
              onChange={(e) => setSelectedEmployeeId(e.target.value ? Number(e.target.value) : null)}
            >
              {employees.length === 0 && <option value="">Nenhum funcionário</option>}
              {employees.map((emp) => (
                <option key={emp.id} value={emp.id}>
                  {emp.name}
                </option>
              ))}
            </select>
          </div>

          <div style={{ display: "flex", gap: "var(--sp-2)", alignItems: "center", height: 40 }}>
            <button className="nav-arrow-button" onClick={() => setDate(new Date(year, month - 1))} aria-label="Mês anterior">
              <ChevronLeft size={16} />
            </button>
            <span style={{ minWidth: 160, textAlign: "center" }}>
              <strong>{MONTH_NAMES[month]} {year}</strong>
            </span>
            <button className="nav-arrow-button" onClick={() => setDate(new Date(year, month + 1))} aria-label="Próximo mês">
              <ChevronRight size={16} />
            </button>
          </div>

          {canManage && (
            <button
              className="primary-button"
              type="button"
              onClick={() => setShowGenerateForm((v) => !v)}
              style={{ display: "inline-flex", alignItems: "center", gap: 6, marginLeft: "auto" }}
            >
              <Wand2 size={16} /> Gerar escala
            </button>
          )}
        </div>
      </div>

      {canManage && showGenerateForm && (
        <form
          onSubmit={handleGenerate}
          style={{
            display: "flex",
            flexDirection: "column",
            gap: "var(--sp-3)",
            padding: "var(--sp-4) var(--sp-5)",
            borderBottom: "1px solid var(--field-border)",
            backgroundColor: "var(--field-bg)",
          }}
        >
          <div className="report-filter-field">
            <label>Funcionários *</label>
            <div
              style={{
                display: "flex",
                flexWrap: "wrap",
                gap: "var(--sp-2)",
                marginTop: "var(--sp-1)",
                maxHeight: 120,
                overflowY: "auto",
                padding: "var(--sp-2)",
                border: "1px solid var(--field-border)",
                borderRadius: "var(--radius-md)",
                background: "var(--field-bg)",
              }}
            >
              {employees.map((emp) => (
                <label
                  key={emp.id}
                  style={{
                    display: "inline-flex",
                    alignItems: "center",
                    gap: 4,
                    padding: "4px 8px",
                    borderRadius: 4,
                    border: "1px solid var(--field-border)",
                    cursor: "pointer",
                  }}
                >
                  <input
                    type="checkbox"
                    checked={genEmployeeIds.includes(emp.id)}
                    onChange={() => toggleGenEmployee(emp.id)}
                  />
                  {emp.name}
                </label>
              ))}
            </div>
          </div>

          <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(160px, 1fr))", gap: "var(--sp-3)" }}>
            <div className="report-filter-field">
              <label>Turno *</label>
              <select value={genShiftId ?? ""} onChange={(e) => setGenShiftId(e.target.value ? Number(e.target.value) : null)} required>
                <option value="">Selecione...</option>
                {shifts.map((s) => (
                  <option key={s.id} value={s.id}>
                    {s.name} ({s.start_time}-{s.end_time})
                  </option>
                ))}
              </select>
            </div>
            <div className="report-filter-field">
              <label>Data início *</label>
              <input type="date" value={genStartDate} onChange={(e) => setGenStartDate(e.target.value)} required />
            </div>
            <div className="report-filter-field">
              <label>Data fim *</label>
              <input type="date" value={genEndDate} onChange={(e) => setGenEndDate(e.target.value)} required />
            </div>
            <div className="report-filter-field">
              <label>Padrão</label>
              <select value={genPatternType} onChange={(e) => setGenPatternType(e.target.value as "weekly" | "rotating")}>
                <option value="weekly">Semanal</option>
                <option value="rotating">Rotativo</option>
              </select>
            </div>
          </div>

          {genPatternType === "weekly" ? (
            <div className="report-filter-field">
              <label>Dias da semana</label>
              <div style={{ display: "flex", gap: "var(--sp-2)", marginTop: "var(--sp-1)" }}>
                {DAY_NAMES.map((label, idx) => {
                  const weekday = idx === 0 ? 6 : idx - 1;
                  return (
                    <label
                      key={label}
                      style={{
                        display: "inline-flex",
                        alignItems: "center",
                        gap: 4,
                        padding: "4px 8px",
                        borderRadius: 4,
                        border: "1px solid var(--field-border)",
                        cursor: "pointer",
                      }}
                    >
                      <input type="checkbox" checked={genWeekdays.includes(weekday)} onChange={() => toggleWeekday(weekday)} />
                      {label}
                    </label>
                  );
                })}
              </div>
            </div>
          ) : (
            <div style={{ display: "flex", gap: "var(--sp-3)" }}>
              <div className="report-filter-field">
                <label>Dias trabalhados</label>
                <input type="number" min={1} value={genWorkDays} onChange={(e) => setGenWorkDays(Number(e.target.value))} />
              </div>
              <div className="report-filter-field">
                <label>Dias de folga</label>
                <input type="number" min={1} value={genOffDays} onChange={(e) => setGenOffDays(Number(e.target.value))} />
              </div>
            </div>
          )}

          <div style={{ display: "flex", gap: "var(--sp-2)" }}>
            <button className="primary-button" type="submit" disabled={generating}>
              {generating ? "Gerando..." : "Gerar escala"}
            </button>
            <button type="button" className="secondary-button" onClick={() => setShowGenerateForm(false)}>
              Cancelar
            </button>
          </div>
        </form>
      )}

      {selectedEmployeeId == null ? (
        <div className="module-state">
          <strong>Nenhum funcionário cadastrado</strong>
          <span>Cadastre funcionários em Cadastros → Funcionários para gerenciar a escala.</span>
        </div>
      ) : loading ? (
        <div className="module-state">Carregando escala...</div>
      ) : (
        <>
          <div style={{ overflowX: "auto" }}>
            <table style={{ width: "100%", borderCollapse: "collapse" }}>
              <thead>
                <tr>
                  {DAY_NAMES.map((day) => (
                    <th
                      key={day}
                      style={{
                        padding: "var(--sp-3)",
                        textAlign: "center",
                        borderBottom: "2px solid var(--field-border)",
                      }}
                    >
                      {day}
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {Array.from({ length: Math.ceil(days.length / 7) }).map((_, weekIndex) => (
                  <tr key={weekIndex}>
                    {days.slice(weekIndex * 7, weekIndex * 7 + 7).map((day, dayIndex) => (
                      <td
                        key={`${weekIndex}-${dayIndex}`}
                        onClick={() => handleDayClick(day)}
                        style={{
                          padding: "var(--sp-2)",
                          textAlign: "center",
                          minHeight: 80,
                          backgroundColor: day.isCurrentMonth ? "transparent" : "var(--field-bg)",
                          borderBottom: "1px solid var(--field-border)",
                          cursor: canManage && day.isCurrentMonth ? "pointer" : "default",
                          verticalAlign: "top",
                        }}
                      >
                        {day.isCurrentMonth && (
                          <>
                            <div style={{ fontWeight: "bold", marginBottom: "var(--sp-1)" }}>{day.dayOfMonth}</div>
                            {day.entries.has(selectedEmployeeId) && (
                              <div
                                style={{
                                  padding: "4px",
                                  borderRadius: 4,
                                  fontSize: 12,
                                  lineHeight: 1.3,
                                  backgroundColor: day.entries.get(selectedEmployeeId)?.shift_color ?? "#f3f4f6",
                                  color: day.entries.get(selectedEmployeeId)?.shift_color ? "#fff" : "#000",
                                }}
                              >
                                <div>{day.entries.get(selectedEmployeeId)?.shift_name ?? "Folga"}</div>
                                {day.entries.get(selectedEmployeeId)?.start_time && (
                                  <div style={{ fontSize: 11, opacity: 0.85 }}>
                                    {day.entries.get(selectedEmployeeId)?.start_time?.slice(0, 5)}–
                                    {day.entries.get(selectedEmployeeId)?.end_time?.slice(0, 5)}
                                  </div>
                                )}
                              </div>
                            )}
                          </>
                        )}
                      </td>
                    ))}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          {selectedDay && canManage && (
            <div
              style={{
                padding: "var(--sp-4) var(--sp-5)",
                backgroundColor: "var(--field-bg)",
                borderTop: "1px solid var(--field-border)",
                display: "flex",
                gap: "var(--sp-3)",
                alignItems: "center",
              }}
            >
              <div className="report-filter-field">
                <label>Dia selecionado</label>
                <strong>{fmtDate(selectedDay.date)}</strong>
              </div>
              <div className="report-filter-field">
                <label>Turno</label>
                <select value={selectedShift ?? ""} onChange={(e) => setSelectedShift(e.target.value ? Number(e.target.value) : null)}>
                  <option value="">Folga</option>
                  {shifts.map((s) => (
                    <option key={s.id} value={s.id}>
                      {s.name} ({s.start_time}-{s.end_time})
                    </option>
                  ))}
                </select>
              </div>
              <button className="primary-button" onClick={handleSaveDay} disabled={saving} style={{ marginLeft: "auto" }}>
                {saving ? "Salvando..." : "Salvar"}
              </button>
              <button type="button" className="secondary-button" onClick={() => setSelectedDay(null)}>
                Cancelar
              </button>
            </div>
          )}
        </>
      )}

      {toast && (
        <div className="module-toast" role="status">
          {toast}
        </div>
      )}
    </section>
  );
}
