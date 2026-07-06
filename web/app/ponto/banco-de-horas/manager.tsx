"use client";

import { useEffect, useState } from "react";
import {
  fetchHourBankSummary,
  getTimeclockSettings,
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
  const [overtimePaidInCash, setOvertimePaidInCash] = useState(false);

  function showToast(msg: string) {
    setToast(msg);
    setTimeout(() => setToast(""), 2600);
  }

  useEffect(() => {
    searchEmployees("").then(setEmployees);
    getTimeclockSettings().then((s) => setOvertimePaidInCash(s.overtime_paid_in_cash));
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
      <form
        onSubmit={handleRecalculate}
        className="report-filter-bar"
        style={{ margin: 0, border: 0, borderRadius: 0, boxShadow: "none", padding: "var(--sp-4) var(--sp-5)", borderBottom: "1px solid var(--field-border)", gap: "var(--sp-3)" }}
      >
        <div className="report-filter-field">
          <label htmlFor="hour_bank_employee">Funcionário</label>
          <select id="hour_bank_employee" value={employeeId} onChange={(e) => setEmployeeId(e.target.value)} style={{ minWidth: 220 }}>
            <option value="">Selecione o funcionário...</option>
            {employees.map((emp) => (
              <option key={emp.id} value={emp.id}>
                {emp.name}
              </option>
            ))}
          </select>
        </div>
        <div className="report-filter-field">
          <label htmlFor="recalc_start">De</label>
          <input id="recalc_start" type="date" value={recalcStart} onChange={(e) => setRecalcStart(e.target.value)} required disabled={!employeeId} />
        </div>
        <div className="report-filter-field">
          <label htmlFor="recalc_end">Até</label>
          <input id="recalc_end" type="date" value={recalcEnd} onChange={(e) => setRecalcEnd(e.target.value)} required disabled={!employeeId} />
        </div>
        <button className="primary-button" type="submit" disabled={!employeeId || recalculating}>
          {recalculating ? "Recalculando..." : "Recalcular período"}
        </button>
        <button type="button" className="secondary-button" onClick={() => setShowInitialForm((v) => !v)} disabled={!employeeId}>
          {showInitialForm ? "Cancelar" : "Lançar saldo inicial"}
        </button>
        <div style={{ marginLeft: "auto", textAlign: "right" }}>
          <p className="eyebrow" style={{ margin: 0 }}>Saldo atual</p>
          <h2 style={{ margin: 0, fontSize: "1.5rem", color: (summary?.balance_minutes ?? 0) < 0 ? "var(--red)" : undefined }}>
            {employeeId ? formatMinutes(summary?.balance_minutes ?? 0) : "—"}
          </h2>
        </div>
      </form>

      {overtimePaidInCash && (
        <p className="muted" style={{ margin: 0, padding: "var(--sp-3) var(--sp-5)", borderBottom: "1px solid var(--field-border)" }}>
          Hora extra (HE 50%/100%) está configurada para ser paga em dinheiro (ver Configurações →
          Ponto) — o excedente não entra neste saldo, só o déficit (trabalhou menos que o esperado).
          Valores em R$ ficam disponíveis no Espelho de Ponto.
        </p>
      )}
      {!employeeId ? (
        <div className="module-state">
          <strong>Selecione um funcionário</strong>
          <span>Escolha um funcionário para ver o saldo do banco de horas.</span>
        </div>
      ) : loading ? (
        <div className="module-state">Carregando...</div>
      ) : (
        <>
          {showInitialForm && (
            <form
              onSubmit={handleSetInitialBalance}
              className="report-filter-bar"
              style={{ margin: 0, border: 0, borderRadius: 0, boxShadow: "none", padding: "var(--sp-4) var(--sp-5)", borderBottom: "1px solid var(--field-border)", backgroundColor: "var(--field-bg)" }}
            >
              <div className="report-filter-field">
                <label htmlFor="initial_date">Data de vigência</label>
                <input id="initial_date" type="date" value={initialDate} onChange={(e) => setInitialDate(e.target.value)} required />
              </div>
              <div className="report-filter-field">
                <label htmlFor="initial_hours">Saldo (horas, use negativo se devedor)</label>
                <input
                  id="initial_hours"
                  type="number"
                  step="0.25"
                  placeholder="Ex: 12.5"
                  value={initialHours}
                  onChange={(e) => setInitialHours(e.target.value)}
                  required
                />
              </div>
              <div className="report-filter-field" style={{ flex: "1 1 200px" }}>
                <label htmlFor="initial_notes">Notas</label>
                <input id="initial_notes" value={initialNotes} onChange={(e) => setInitialNotes(e.target.value)} placeholder="Ex: migração do sistema anterior" />
              </div>
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
                    <th className="col-num">Esperado</th>
                    <th className="col-num">Trabalhado</th>
                    <th className="col-num">Saldo do dia</th>
                    <th>Origem</th>
                    <th>Notas</th>
                  </tr>
                </thead>
                <tbody>
                  {summary.entries.map((entry) => (
                    <tr key={entry.id}>
                      <td>{new Date(`${entry.reference_date}T00:00:00`).toLocaleDateString("pt-BR")}</td>
                      <td className="col-num">{formatMinutes(entry.expected_minutes).replace("+", "")}</td>
                      <td className="col-num">{formatMinutes(entry.worked_minutes).replace("+", "")}</td>
                      <td className={`col-num ${entry.balance_minutes < 0 ? "balance-negative" : ""}`}>{formatMinutes(entry.balance_minutes)}</td>
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
