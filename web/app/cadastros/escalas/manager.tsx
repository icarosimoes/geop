"use client";

import { useEffect, useState } from "react";
import { ChevronLeft, ChevronRight } from "lucide-react";
import {
  fetchCalendar,
  fetchShifts,
  searchUsers,
  setScheduleDayAction,
  type CalendarEntry,
  type Shift,
  type UserOption,
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
    entriesMap.get(entry.date)!.set(entry.user_id, entry);
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
  const [users, setUsers] = useState<UserOption[]>([]);
  const [selectedUserId, setSelectedUserId] = useState(1);
  const [date, setDate] = useState(new Date());
  const [entries, setEntries] = useState<CalendarEntry[]>([]);
  const [loading, setLoading] = useState(false);
  const [selectedDay, setSelectedDay] = useState<CalendarEntry | null>(null);
  const [selectedShift, setSelectedShift] = useState<number | null>(null);
  const [saving, setSaving] = useState(false);
  const [toast, setToast] = useState("");
  const canManage = hasPermission(user, "schedule.manage");

  function showToast(msg: string) {
    setToast(msg);
    setTimeout(() => setToast(""), 2600);
  }

  function reload() {
    setLoading(true);
    const start = `${date.getFullYear()}-${String(date.getMonth() + 1).padStart(2, "0")}-01`;
    const daysInMonth = getDaysInMonth(date.getFullYear(), date.getMonth());
    const end = `${date.getFullYear()}-${String(date.getMonth() + 1).padStart(2, "0")}-${String(daysInMonth).padStart(2, "0")}`;

    fetchCalendar({
      start,
      end,
      userId: selectedUserId,
    })
      .then(setEntries)
      .finally(() => setLoading(false));
  }

  useEffect(() => {
    fetchShifts().then(setShifts);
    searchUsers("").then(setUsers);
  }, []);

  useEffect(() => {
    reload();
  }, [selectedUserId, date]);

  async function handleDayClick(day: CalendarDay) {
    if (!canManage || !day.isCurrentMonth) return;
    const entry = day.entries.get(selectedUserId);
    setSelectedDay(entry ?? { date: day.date, user_id: selectedUserId, user_name: "", sector_id: null, sector_name: null, shift_id: null, shift_name: null, shift_color: null, start_time: null, end_time: null, source: "manual" });
    setSelectedShift(entry?.shift_id ?? null);
  }

  async function handleSaveDay() {
    if (!selectedDay) return;
    setSaving(true);
    const result = await setScheduleDayAction(selectedUserId, selectedDay.date, {
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

  const days = buildCalendar(date.getFullYear(), date.getMonth(), entries);
  const year = date.getFullYear();
  const month = date.getMonth();

  return (
    <section className="module-panel">
      <div style={{ padding: "var(--sp-4) var(--sp-5)", borderBottom: "1px solid var(--field-border)" }}>
        <div style={{ display: "flex", gap: "var(--sp-3)", alignItems: "center" }}>
          <select value={selectedUserId} onChange={(e) => setSelectedUserId(Number(e.target.value))}>
            {users.map((u) => (
              <option key={u.id} value={u.id}>
                {u.name}
              </option>
            ))}
          </select>

          <div style={{ marginLeft: "auto", display: "flex", gap: "var(--sp-2)", alignItems: "center" }}>
            <button onClick={() => setDate(new Date(year, month - 1))} aria-label="Mês anterior">
              <ChevronLeft size={16} />
            </button>
            <span style={{ minWidth: 160, textAlign: "center" }}>
              <strong>{MONTH_NAMES[month]} {year}</strong>
            </span>
            <button onClick={() => setDate(new Date(year, month + 1))} aria-label="Próximo mês">
              <ChevronRight size={16} />
            </button>
          </div>
        </div>
      </div>

      {loading ? (
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
                            {day.entries.has(selectedUserId) && (
                              <div
                                style={{
                                  padding: "4px",
                                  borderRadius: 4,
                                  fontSize: 12,
                                  backgroundColor: day.entries.get(selectedUserId)?.shift_color ?? "#f3f4f6",
                                  color: day.entries.get(selectedUserId)?.shift_color ? "#fff" : "#000",
                                }}
                              >
                                {day.entries.get(selectedUserId)?.shift_name ?? "Folga"}
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
              <span>
                <strong>{selectedDay.date}</strong> - {selectedDay.user_name}
              </span>
              <select value={selectedShift ?? ""} onChange={(e) => setSelectedShift(e.target.value ? Number(e.target.value) : null)}>
                <option value="">Folga</option>
                {shifts.map((s) => (
                  <option key={s.id} value={s.id}>
                    {s.name} ({s.start_time}-{s.end_time})
                  </option>
                ))}
              </select>
              <button className="primary-button" onClick={handleSaveDay} disabled={saving} style={{ marginLeft: "auto" }}>
                {saving ? "Salvando..." : "Salvar"}
              </button>
              <button
                type="button"
                onClick={() => setSelectedDay(null)}
                style={{ backgroundColor: "var(--field-border)" }}
              >
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
