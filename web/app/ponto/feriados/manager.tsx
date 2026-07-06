"use client";

import { useEffect, useState } from "react";
import { Plus, Trash2 } from "lucide-react";
import { createHolidayAction, deleteHolidayAction, fetchHolidays, type Holiday } from "@/app/actions";

function fmtDate(value: string): string {
  const [y, m, d] = value.split("-");
  return `${d}/${m}/${y}`;
}

export function HolidayManager() {
  const [holidays, setHolidays] = useState<Holiday[]>([]);
  const [loading, setLoading] = useState(true);
  const [date, setDate] = useState("");
  const [name, setName] = useState("");
  const [saving, setSaving] = useState(false);
  const [toast, setToast] = useState("");

  function showToast(msg: string) {
    setToast(msg);
    setTimeout(() => setToast(""), 2600);
  }

  function reload() {
    fetchHolidays().then(setHolidays).finally(() => setLoading(false));
  }

  useEffect(() => {
    reload();
  }, []);

  async function handleCreate(e: React.FormEvent) {
    e.preventDefault();
    if (!date || !name.trim()) return;
    setSaving(true);
    const result = await createHolidayAction({ date, name: name.trim() });
    setSaving(false);
    if (result.ok) {
      setDate("");
      setName("");
      showToast("Feriado cadastrado.");
      reload();
    } else {
      showToast(result.error ?? "Erro ao cadastrar feriado.");
    }
  }

  async function handleDelete(holiday: Holiday) {
    if (!confirm(`Remover o feriado "${holiday.name}" (${fmtDate(holiday.date)})?`)) return;
    const result = await deleteHolidayAction(holiday.id);
    if (result.ok) {
      showToast("Feriado removido.");
      reload();
    } else {
      showToast(result.error ?? "Erro ao remover.");
    }
  }

  const sorted = [...holidays].sort((a, b) => a.date.localeCompare(b.date));

  return (
    <section className="module-panel">
      <form onSubmit={handleCreate} className="report-filter-bar" style={{ margin: 0, boxShadow: "none" }}>
        <div className="report-filter-field">
          <label htmlFor="holiday_date">Data</label>
          <input id="holiday_date" type="date" value={date} onChange={(e) => setDate(e.target.value)} required />
        </div>
        <div className="report-filter-field" style={{ flex: "1 1 240px" }}>
          <label htmlFor="holiday_name">Nome</label>
          <input
            id="holiday_name"
            value={name}
            onChange={(e) => setName(e.target.value)}
            placeholder="Ex.: Independência do Brasil"
            required
          />
        </div>
        <button className="primary-button" type="submit" disabled={saving} style={{ display: "inline-flex", alignItems: "center", gap: 6 }}>
          <Plus size={16} /> {saving ? "Salvando..." : "Adicionar"}
        </button>
      </form>

      {loading ? (
        <div className="module-state">Carregando feriados...</div>
      ) : sorted.length === 0 ? (
        <div className="module-state">
          <strong>Nenhum feriado cadastrado</strong>
          <span>Feriados cadastrados aqui contam como dia de descanso (HE 100%) no espelho de ponto.</span>
        </div>
      ) : (
        <div className="module-table-wrap">
          <table>
            <thead>
              <tr>
                <th>Data</th>
                <th>Nome</th>
                <th>Ações</th>
              </tr>
            </thead>
            <tbody>
              {sorted.map((holiday) => (
                <tr key={holiday.id}>
                  <td>{fmtDate(holiday.date)}</td>
                  <td>
                    <strong>{holiday.name}</strong>
                  </td>
                  <td>
                    <div className="row-actions">
                      <button onClick={() => handleDelete(holiday)} aria-label="Remover">
                        <Trash2 size={16} />
                      </button>
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
      <footer className="module-pagination">
        <span>{holidays.length} feriado(s)</span>
      </footer>
      {toast && (
        <div className="module-toast" role="status">
          {toast}
        </div>
      )}
    </section>
  );
}
