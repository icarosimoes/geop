"use client";

import { useEffect, useState } from "react";
import {
  fetchHourBankSummary,
  recalculateHourBankAction,
  searchEmployees,
  setHourBankInitialBalanceAction,
  type EmployeeOption,
  type HourBankSummary,
} from "@/app/actions";

function formatMinutes(totalMinutes: number): string {
  const sign = totalMinutes < 0 ? "-" : "+";
  const abs = Math.abs(totalMinutes);
  const hours = Math.floor(abs / 60);
  const minutes = abs % 60;
  return `${sign}${hours}h${String(minutes).padStart(2, "0")}`;
}

const SOURCE_LABELS: Record<string, string> = {
  calculated: "Calculado (escala x ponto)",
  initial_balance: "Saldo inicial",
};

export function HourBankManager() {
  const [employees, setEmployees] = useState<EmployeeOption[]>([]);
  const [employeeId, setEmployeeId] = useState("");
  const [summary, setSummary] = useState<HourBankSummary | null>(null);
  const [loading, setLoading] = useState(false);
  const [recalcStart, setRecalcStart] = useState("");
  const [recalcEnd, setRecalcEnd] = useState("");
  const [recalculating, setRecalculating] = useState(false);
  const [showInitialForm, setShowInitialForm] = useState(false);
  const [initialDate, setInitialDate] = useState("");
  const [initialHours, setInitialHours] = useState("");
  const [initialNotes, setInitialNotes] = useState("");
  const [savingInitial, setSavingInitial] = useState(false);
  const [toast, setToast] = useState("");

  function showToast(msg: string) {
    setToast(msg);
    setTimeout(() => setToast(""), 2600);
  }

  useEffect(() => {
    searchEmployees("").then(setEmployees);
  }, []);

  function reloadSummary(id: string) {
    if (!id) {
      setSummary(null);
      return;
    }
    setLoading(true);
    fetchHourBankSummary(Number(id))
      .then(setSummary)
      .finally(() => setLoading(false));
  }

  useEffect(() => {
    reloadSummary(employeeId);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [employeeId]);

  async function handleRecalculate(e: React.FormEvent) {
    e.preventDefault();
    if (!employeeId || !recalcStart || !recalcEnd) return;
    setRecalculating(true);
    const result = await recalculateHourBankAction(Number(employeeId), recalcStart, recalcEnd);
    setRecalculating(false);
    if (result.ok) {
      showToast(`${result.affected} dia(s) recalculado(s).`);
      reloadSummary(employeeId);
    } else {
      showToast(result.error);
    }
  }

  async function handleSetInitialBalance(e: React.FormEvent) {
    e.preventDefault();
    if (!employeeId || !initialDate || !initialHours) return;
    setSavingInitial(true);
    const result = await setHourBankInitialBalanceAction(Number(employeeId), {
      effective_date: initialDate,
      balance_minutes: Math.round(Number(initialHours) * 60),
      notes: initialNotes || undefined,
    });
    setSavingInitial(false);
    if (result.ok) {
      showToast("Saldo inicial lançado.");
      setShowInitialForm(false);
      setInitialDate("");
      setInitialHours("");
      setInitialNotes("");
      reloadSummary(employeeId);
    } else {
      showToast(result.error ?? "Erro ao lançar saldo inicial.");
    }
  }

  return (
    <section className="module-panel">
      <div
        className="module-toolbar"
        style={{ padding: "var(--sp-3) var(--sp-5)", borderBottom: "1px solid var(--field-border)" }}
      >
        <select value={employeeId} onChange={(e) => setEmployeeId(e.target.value)} style={{ minWidth: 260 }}>
          <option value="">Selecione o funcionário...</option>
          {employees.map((emp) => (
            <option key={emp.id} value={emp.id}>
              {emp.name}
            </option>
          ))}
        </select>
      </div>

      {!employeeId ? (
        <div className="module-state">
          <strong>Selecione um funcionário</strong>
          <span>Escolha um funcionário para ver o saldo do banco de horas.</span>
        </div>
      ) : loading ? (
        <div className="module-state">Carregando...</div>
      ) : (
        <>
          <div style={{ padding: "var(--sp-4) var(--sp-5)", borderBottom: "1px solid var(--field-border)" }}>
            <p className="eyebrow">Saldo atual</p>
            <h2 style={{ margin: 0, fontSize: "1.8rem" }}>
              {formatMinutes(summary?.balance_minutes ?? 0)}
            </h2>
          </div>

          <form
            onSubmit={handleRecalculate}
            style={{
              display: "flex",
              gap: "var(--sp-3)",
              alignItems: "flex-end",
              flexWrap: "wrap",
              padding: "var(--sp-4) var(--sp-5)",
              borderBottom: "1px solid var(--field-border)",
            }}
          >
            <label>
              De
              <input type="date" value={recalcStart} onChange={(e) => setRecalcStart(e.target.value)} required />
            </label>
            <label>
              Até
              <input type="date" value={recalcEnd} onChange={(e) => setRecalcEnd(e.target.value)} required />
            </label>
            <button className="primary-button" type="submit" disabled={recalculating}>
              {recalculating ? "Recalculando..." : "Recalcular período"}
            </button>
            <button type="button" onClick={() => setShowInitialForm((v) => !v)} style={{ backgroundColor: "var(--field-bg)" }}>
              {showInitialForm ? "Cancelar" : "Lançar saldo inicial"}
            </button>
          </form>

          {showInitialForm && (
            <form
              onSubmit={handleSetInitialBalance}
              style={{
                display: "flex",
                gap: "var(--sp-3)",
                alignItems: "flex-end",
                flexWrap: "wrap",
                padding: "var(--sp-4) var(--sp-5)",
                borderBottom: "1px solid var(--field-border)",
                backgroundColor: "var(--field-bg)",
              }}
            >
              <label>
                Data de vigência
                <input type="date" value={initialDate} onChange={(e) => setInitialDate(e.target.value)} required />
              </label>
              <label>
                Saldo (horas, use negativo se devedor)
                <input
                  type="number"
                  step="0.25"
                  placeholder="Ex: 12.5"
                  value={initialHours}
                  onChange={(e) => setInitialHours(e.target.value)}
                  required
                />
              </label>
              <label style={{ flex: 1, minWidth: 200 }}>
                Notas
                <input value={initialNotes} onChange={(e) => setInitialNotes(e.target.value)} placeholder="Ex: migração do sistema anterior" />
              </label>
              <button className="primary-button" type="submit" disabled={savingInitial}>
                {savingInitial ? "Salvando..." : "Salvar saldo inicial"}
              </button>
            </form>
          )}

          {!summary || summary.entries.length === 0 ? (
            <div className="module-state">
              <strong>Sem lançamentos</strong>
              <span>Recalcule um período para gerar o extrato diário.</span>
            </div>
          ) : (
            <div className="module-table-wrap">
              <table>
                <thead>
                  <tr>
                    <th>Data</th>
                    <th>Esperado</th>
                    <th>Trabalhado</th>
                    <th>Saldo do dia</th>
                    <th>Origem</th>
                    <th>Notas</th>
                  </tr>
                </thead>
                <tbody>
                  {summary.entries.map((entry) => (
                    <tr key={entry.id}>
                      <td>{new Date(`${entry.reference_date}T00:00:00`).toLocaleDateString("pt-BR")}</td>
                      <td>{formatMinutes(entry.expected_minutes).replace("+", "")}</td>
                      <td>{formatMinutes(entry.worked_minutes).replace("+", "")}</td>
                      <td>{formatMinutes(entry.balance_minutes)}</td>
                      <td>{SOURCE_LABELS[entry.source] ?? entry.source}</td>
                      <td className="muted">{entry.notes ?? "—"}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
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
