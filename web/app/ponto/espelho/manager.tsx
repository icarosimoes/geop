"use client";

import { Download } from "lucide-react";
import { useEffect, useState, type FormEvent } from "react";
import { fetchRegistryOptions, fetchSectorMirror, fetchTimeclockMirror, type EmployeeMirror, type RegistryOption } from "@/app/actions";
import { EmployeeAutocomplete } from "@/components/employee-autocomplete";

function todayIso(): string {
  return new Date().toISOString().slice(0, 10);
}

function firstDayOfMonthIso(): string {
  const now = new Date();
  return new Date(now.getFullYear(), now.getMonth(), 1).toISOString().slice(0,10);
}

function fmtTime(value: string | null): string {
  if (!value) return "—";
  return new Date(value).toLocaleTimeString("pt-BR", { hour: "2-digit", minute: "2-digit" });
}

function fmtMinutes(value: number): string {
  const sign = value < 0 ? "-" : "";
  const abs = Math.abs(value);
  return `${sign}${String(Math.floor(abs / 60)).padStart(2, "0")}:${String(abs % 60).padStart(2, "0")}`;
}

function fmtMoney(value: number): string {
  return value.toLocaleString("pt-BR", { style: "currency", currency: "BRL" });
}

function fmtDate(value: string): string {
  const [y, m, d] = value.split("-");
  return `${d}/${m}/${y}`;
}

function MirrorCard({
  data,
  exportQuery,
}: {
  data: EmployeeMirror;
  exportQuery: string | null;
}) {
  return (
    <section className="module-panel" style={{ marginBottom: "var(--sp-4)" }}>
      <div
        className="module-toolbar"
        style={{ padding: "var(--sp-4) var(--sp-5)", borderBottom: "1px solid var(--field-border)" }}
      >
        <div>
          <strong>{data.employee_name}</strong>
          <div className="muted" style={{ fontSize: 12 }}>{data.sector_name ?? "Sem setor"}</div>
        </div>
        {exportQuery && (
          <div style={{ display: "flex", gap: "var(--sp-2)", marginLeft: "auto" }}>
            <a className="secondary-button" href={`/api/ponto/espelho/export?${exportQuery}&format=xlsx`}>
              <Download size={16} /> Excel
            </a>
            <a className="secondary-button" href={`/api/ponto/espelho/export?${exportQuery}&format=pdf`}>
              <Download size={16} /> PDF
            </a>
          </div>
        )}
      </div>
      <div className="module-table-wrap">
        <table>
          <thead>
            <tr>
              <th>Data</th>
              <th className="col-num">1ª Entrada</th>
              <th className="col-num">1ª Saída</th>
              <th className="col-num">2ª Entrada</th>
              <th className="col-num">2ª Saída</th>
              <th className="col-num">Crédito</th>
              <th className="col-num">Débito</th>
              <th className="col-num">Interv.</th>
              <th className="col-num">Trab.</th>
              <th className="col-num">HE 50%</th>
              <th className="col-num">HE 100%</th>
              <th className="col-num">A.N.</th>
              <th className="col-num">Saldo</th>
              <th>Obs.</th>
            </tr>
          </thead>
          <tbody>
            {data.days.map((day) => (
              <tr key={day.date}>
                <td>{fmtDate(day.date)}</td>
                <td className="col-num">{fmtTime(day.first_in)}</td>
                <td className="col-num">{fmtTime(day.first_out)}</td>
                <td className="col-num">{fmtTime(day.second_in)}</td>
                <td className="col-num">{fmtTime(day.second_out)}</td>
                <td className="col-num">{fmtMinutes(day.credit_minutes)}</td>
                <td className="col-num">{fmtMinutes(day.debit_minutes)}</td>
                <td className="col-num">{fmtMinutes(day.break_minutes)}</td>
                <td className="col-num">{fmtMinutes(day.worked_minutes)}</td>
                <td className="col-num">
                  {fmtMinutes(day.overtime_50_minutes)}
                  {day.overtime_50_value != null && (
                    <div style={{ fontSize: 11, opacity: 0.75 }}>{fmtMoney(day.overtime_50_value)}</div>
                  )}
                </td>
                <td className="col-num">
                  {fmtMinutes(day.overtime_100_minutes)}
                  {day.overtime_100_value != null && (
                    <div style={{ fontSize: 11, opacity: 0.75 }}>{fmtMoney(day.overtime_100_value)}</div>
                  )}
                </td>
                <td className="col-num">{fmtMinutes(day.night_differential_minutes)}</td>
                <td className={`col-num ${day.balance_minutes < 0 ? "balance-negative" : ""}`}>{fmtMinutes(day.balance_minutes)}</td>
                <td className="muted">{day.notes || "—"}</td>
              </tr>
            ))}
          </tbody>
          <tfoot>
            <tr>
              <td colSpan={5}><strong>Totais do período</strong></td>
              <td className="col-num"><strong>{fmtMinutes(data.totals.credit_minutes)}</strong></td>
              <td className="col-num"><strong>{fmtMinutes(data.totals.debit_minutes)}</strong></td>
              <td className="col-num"><strong>{fmtMinutes(data.totals.break_minutes)}</strong></td>
              <td className="col-num"><strong>{fmtMinutes(data.totals.worked_minutes)}</strong></td>
              <td className="col-num">
                <strong>{fmtMinutes(data.totals.overtime_50_minutes)}</strong>
                {data.totals.overtime_50_value != null && (
                  <div style={{ fontSize: 11, opacity: 0.75 }}>{fmtMoney(data.totals.overtime_50_value)}</div>
                )}
              </td>
              <td className="col-num">
                <strong>{fmtMinutes(data.totals.overtime_100_minutes)}</strong>
                {data.totals.overtime_100_value != null && (
                  <div style={{ fontSize: 11, opacity: 0.75 }}>{fmtMoney(data.totals.overtime_100_value)}</div>
                )}
              </td>
              <td className="col-num"><strong>{fmtMinutes(data.totals.night_differential_minutes)}</strong></td>
              <td className={`col-num ${data.totals.balance_minutes < 0 ? "balance-negative" : ""}`}><strong>{fmtMinutes(data.totals.balance_minutes)}</strong></td>
              <td></td>
            </tr>
          </tfoot>
        </table>
      </div>
    </section>
  );
}

export function EspelhoManager() {
  const [mode, setMode] = useState<"employee" | "sector">("employee");
  const [employeeId, setEmployeeId] = useState("");
  const [sectorId, setSectorId] = useState("");
  const [sectors, setSectors] = useState<RegistryOption[]>([]);
  const [dateFrom, setDateFrom] = useState(firstDayOfMonthIso());
  const [dateTo, setDateTo] = useState(todayIso());
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [data, setData] = useState<EmployeeMirror | null>(null);
  const [sectorData, setSectorData] = useState<EmployeeMirror[] | null>(null);

  useEffect(() => {
    fetchRegistryOptions("Setor").then(setSectors);
  }, []);

  async function handleSubmit(e: FormEvent) {
    e.preventDefault();
    if (!dateFrom || !dateTo) return;
    setLoading(true);
    setError("");
    setData(null);
    setSectorData(null);

    if (mode === "employee") {
      if (!employeeId) {
        setLoading(false);
        return;
      }
      const result = await fetchTimeclockMirror({ employeeId: Number(employeeId), dateFrom, dateTo });
      setLoading(false);
      if (result.ok) setData(result.data);
      else setError(result.error);
    } else {
      if (!sectorId) {
        setLoading(false);
        return;
      }
      const result = await fetchSectorMirror({ sectorId: Number(sectorId), dateFrom, dateTo });
      setLoading(false);
      if (result.ok) setSectorData(result.data);
      else setError(result.error);
    }
  }

  const exportQuery = data
    ? new URLSearchParams({ employee_id: String(employeeId), date_from: dateFrom, date_to: dateTo }).toString()
    : null;

  return (
    <>
      <form className="report-filter-bar" onSubmit={handleSubmit}>
        <div className="report-filter-field">
          <label htmlFor="mirror_mode">Filtrar por</label>
          <select
            id="mirror_mode"
            value={mode}
            onChange={(e) => {
              setMode(e.target.value as "employee" | "sector");
              setData(null);
              setSectorData(null);
              setError("");
            }}
          >
            <option value="employee">Funcionário</option>
            <option value="sector">Setor</option>
          </select>
        </div>

        {mode === "employee" ? (
          <div className="report-filter-field" style={{ flex: "1 1 260px", maxWidth: 360 }}>
            <label>Funcionário</label>
            <EmployeeAutocomplete onChange={(id) => setEmployeeId(id)} placeholder="Digite o nome do funcionário..." required />
          </div>
        ) : (
          <div className="report-filter-field" style={{ flex: "1 1 260px", maxWidth: 360 }}>
            <label htmlFor="mirror_sector">Setor</label>
            <select id="mirror_sector" value={sectorId} onChange={(e) => setSectorId(e.target.value)} required>
              <option value="">Selecione o setor...</option>
              {sectors.map((sector) => (
                <option key={sector.id} value={sector.id}>
                  {sector.name}
                </option>
              ))}
            </select>
          </div>
        )}

        <div className="report-filter-group">
          <div className="report-filter-field">
            <label htmlFor="date_from">De</label>
            <input id="date_from" type="date" value={dateFrom} onChange={(e) => setDateFrom(e.target.value)} required />
          </div>
          <div className="report-filter-field">
            <label htmlFor="date_to">Até</label>
            <input id="date_to" type="date" value={dateTo} onChange={(e) => setDateTo(e.target.value)} required />
          </div>
          <button type="submit" className="primary-button" disabled={loading}>
            {loading ? "Gerando..." : "Gerar relatório"}
          </button>
        </div>
      </form>

      {error && (
        <div className="empty-search">
          <strong>Não foi possível gerar o espelho</strong>
          <span>{error}</span>
        </div>
      )}

      {mode === "sector" && sectorData && sectorData.length === 0 && (
        <div className="empty-search">
          <strong>Nenhum funcionário ativo neste setor</strong>
        </div>
      )}

      {data && <MirrorCard data={data} exportQuery={exportQuery} />}

      {sectorData && sectorData.length > 0 && (
        <>
          <p className="muted" style={{ marginTop: 0 }}>
            {sectorData.length} funcionário(s) — exportação Excel/PDF disponível só por funcionário individual.
          </p>
          {sectorData.map((employeeMirror) => (
            <MirrorCard key={employeeMirror.employee_id} data={employeeMirror} exportQuery={null} />
          ))}
        </>
      )}
    </>
  );
}
