"use client";

import { useEffect, useState } from "react";
import {
  fetchWorkSchedule,
  saveWorkScheduleAction,
  searchUsers,
  type UserOption,
  type WorkScheduleEntry,
} from "@/app/actions";

const WEEKDAY_LABELS = ["Segunda", "Terça", "Quarta", "Quinta", "Sexta", "Sábado", "Domingo"];

interface DayState {
  active: boolean;
  start_time: string;
  end_time: string;
  break_start: string;
  break_end: string;
  tolerance_minutes: number;
}

function defaultDay(): DayState {
  return {
    active: false,
    start_time: "08:00",
    end_time: "17:00",
    break_start: "",
    break_end: "",
    tolerance_minutes: 10,
  };
}

export function ScheduleManager() {
  const [users, setUsers] = useState<UserOption[]>([]);
  const [selectedUserId, setSelectedUserId] = useState<number | null>(null);
  const [days, setDays] = useState<DayState[]>(() => Array.from({ length: 7 }, defaultDay));
  const [loading, setLoading] = useState(false);
  const [saving, setSaving] = useState(false);
  const [toast, setToast] = useState("");

  function showToast(msg: string) {
    setToast(msg);
    setTimeout(() => setToast(""), 2600);
  }

  useEffect(() => {
    searchUsers("").then(setUsers);
  }, []);

  useEffect(() => {
    if (!selectedUserId) return;
    setLoading(true);
    fetchWorkSchedule(selectedUserId)
      .then((week) => {
        const next = Array.from({ length: 7 }, defaultDay);
        for (const entry of week?.entries ?? []) {
          next[entry.weekday] = {
            active: true,
            start_time: entry.start_time.slice(0, 5),
            end_time: entry.end_time.slice(0, 5),
            break_start: entry.break_start?.slice(0, 5) ?? "",
            break_end: entry.break_end?.slice(0, 5) ?? "",
            tolerance_minutes: entry.tolerance_minutes,
          };
        }
        setDays(next);
      })
      .finally(() => setLoading(false));
  }, [selectedUserId]);

  function updateDay(weekday: number, patch: Partial<DayState>) {
    setDays((prev) => prev.map((day, i) => (i === weekday ? { ...day, ...patch } : day)));
  }

  async function handleSave() {
    if (!selectedUserId) return;
    const entries: WorkScheduleEntry[] = days
      .map((day, weekday) => ({ day, weekday }))
      .filter(({ day }) => day.active)
      .map(({ day, weekday }) => ({
        weekday,
        start_time: day.start_time,
        end_time: day.end_time,
        break_start: day.break_start || null,
        break_end: day.break_end || null,
        tolerance_minutes: day.tolerance_minutes,
      }));
    setSaving(true);
    const result = await saveWorkScheduleAction(selectedUserId, entries);
    setSaving(false);
    if (result.ok) showToast("Escala salva com sucesso.");
    else showToast(result.error ?? "Erro ao salvar escala.");
  }

  return (
    <section className="module-panel">
      <div
        style={{
          display: "flex",
          gap: "var(--sp-3)",
          padding: "var(--sp-4) var(--sp-5)",
          borderBottom: "1px solid var(--field-border)",
        }}
      >
        <select
          value={selectedUserId ?? ""}
          onChange={(e) => setSelectedUserId(e.target.value ? Number(e.target.value) : null)}
          style={{ flex: 1 }}
        >
          <option value="">Selecione um funcionário...</option>
          {users.map((u) => (
            <option key={u.id} value={u.id}>
              {u.name}
            </option>
          ))}
        </select>
      </div>

      {!selectedUserId ? (
        <div className="module-state">
          <strong>Selecione um funcionário</strong>
          <span>Escolha um funcionário acima para editar a escala semanal.</span>
        </div>
      ) : loading ? (
        <div className="module-state">Carregando escala...</div>
      ) : (
        <div className="module-table-wrap">
          <table>
            <thead>
              <tr>
                <th>Dia</th>
                <th>Trabalha</th>
                <th>Entrada</th>
                <th>Saída</th>
                <th>Intervalo início</th>
                <th>Intervalo fim</th>
                <th>Tolerância (min)</th>
              </tr>
            </thead>
            <tbody>
              {WEEKDAY_LABELS.map((label, weekday) => {
                const day = days[weekday];
                return (
                  <tr key={weekday}>
                    <td>
                      <strong>{label}</strong>
                    </td>
                    <td>
                      <input
                        type="checkbox"
                        checked={day.active}
                        onChange={(e) => updateDay(weekday, { active: e.target.checked })}
                      />
                    </td>
                    <td>
                      <input
                        type="time"
                        value={day.start_time}
                        disabled={!day.active}
                        onChange={(e) => updateDay(weekday, { start_time: e.target.value })}
                      />
                    </td>
                    <td>
                      <input
                        type="time"
                        value={day.end_time}
                        disabled={!day.active}
                        onChange={(e) => updateDay(weekday, { end_time: e.target.value })}
                      />
                    </td>
                    <td>
                      <input
                        type="time"
                        value={day.break_start}
                        disabled={!day.active}
                        onChange={(e) => updateDay(weekday, { break_start: e.target.value })}
                      />
                    </td>
                    <td>
                      <input
                        type="time"
                        value={day.break_end}
                        disabled={!day.active}
                        onChange={(e) => updateDay(weekday, { break_end: e.target.value })}
                      />
                    </td>
                    <td>
                      <input
                        type="number"
                        min={0}
                        max={120}
                        value={day.tolerance_minutes}
                        disabled={!day.active}
                        style={{ width: 72 }}
                        onChange={(e) =>
                          updateDay(weekday, { tolerance_minutes: Number(e.target.value) })
                        }
                      />
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      )}

      {selectedUserId && (
        <footer className="module-pagination">
          <span>{days.filter((d) => d.active).length} dia(s) com escala ativa</span>
          <button className="primary-button" onClick={handleSave} disabled={saving}>
            {saving ? "Salvando..." : "Salvar escala"}
          </button>
        </footer>
      )}
      {toast && (
        <div className="module-toast" role="status">
          {toast}
        </div>
      )}
    </section>
  );
}
