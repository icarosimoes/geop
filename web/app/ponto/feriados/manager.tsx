"use client";

import { useEffect, useState } from "react";
import { Plus, Trash2, X } from "lucide-react";
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
  const [error, setError] = useState("");
  const [toast, setToast] = useState("");
  const [showForm, setShowForm] = useState(false);

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

  function closeModal() {
    setShowForm(false);
    setDate("");
    setName("");
    setError("");
  }

  async function handleCreate(e: React.FormEvent) {
    e.preventDefault();
    if (!date || !name.trim()) return;
    setSaving(true);
    setError("");
    const result = await createHolidayAction({ date, name: name.trim() });
    setSaving(false);
    if (result.ok) {
      closeModal();
      showToast("Feriado cadastrado.");
      reload();
    } else {
      setError(result.error ?? "Erro ao cadastrar feriado.");
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
    <>
      <header className="module-heading">
        <div>
          <p className="eyebrow">Ponto</p>
          <h1>Feriados</h1>
          <p>Cadastre os feriados considerados no cálculo de hora extra 100% do espelho de ponto.</p>
        </div>
        <button className="primary-button" onClick={() => setShowForm(true)}>
          <Plus size={18} /> Novo feriado
        </button>
      </header>

      <section className="module-panel">
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
      </section>

      {showForm && (
        <div className="modal-layer" role="presentation" onClick={closeModal}>
          <section className="record-modal" role="dialog" aria-modal="true" onClick={(e) => e.stopPropagation()}>
            <header>
              <div>
                <span>Ponto</span>
                <h2>Novo feriado</h2>
              </div>
              <button className="icon-button" onClick={closeModal}><X /></button>
            </header>
            <form onSubmit={handleCreate}>
              {error && <div className="kanban-form-error">{error}</div>}
              <label>Data *
                <input type="date" value={date} onChange={(e) => setDate(e.target.value)} required autoFocus />
              </label>
              <label>Nome *
                <input
                  value={name}
                  onChange={(e) => setName(e.target.value)}
                  placeholder="Ex.: Independência do Brasil"
                  required
                />
              </label>
              <footer>
                <button type="button" onClick={closeModal}>Cancelar</button>
                <button type="submit" disabled={saving}>{saving ? "Salvando…" : "Criar feriado"}</button>
              </footer>
            </form>
          </section>
        </div>
      )}

      {toast && (
        <div className="module-toast" role="status">
          {toast}
        </div>
      )}
    </>
  );
}
