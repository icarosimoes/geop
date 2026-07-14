"use client";

import { Search } from "lucide-react";
import { useRouter } from "next/navigation";
import { useState, type FormEvent } from "react";
import type { FiscalRequestSlaReport, WorkOrderReport } from "@/app/relatorios/page";

const SLA_STATE_LABELS: Record<string, string> = {
  on_time: "No prazo",
  warning: "Próximo do prazo",
  overdue: "Atrasado",
  paused: "Em espera",
  completed: "Concluído",
};

function BarChart({ data, color = "blue" }: { data: Record<string, number>; color?: string }) {
  const entries = Object.entries(data).sort((a, b) => b[1] - a[1]);
  const maxVal = Math.max(...entries.map(([, v]) => v), 1);
  if (!entries.length) return <p className="muted">Sem dados no período.</p>;
  return (
    <div className="kpi-bar-list">
      {entries.map(([label, count]) => (
        <div key={label} className="kpi-bar-row">
          <span className="kpi-bar-label" title={label}>{label}</span>
          <div className="kpi-bar-track">
            <div className={`kpi-bar-fill ${color}`} style={{ width: `${Math.max(2, (count / maxVal) * 100)}%` }} />
          </div>
          <span className="kpi-bar-count">{count}</span>
        </div>
      ))}
    </div>
  );
}

function TrendBars({ trend, color = "blue" }: { trend: Array<{ date: string; count: number }>; color?: string }) {
  if (!trend.length) return null;
  const maxVal = Math.max(...trend.map((d) => d.count), 1);
  const showLabels = trend.length <= 31;
  return (
    <div className="kpi-trend">
      <div className="kpi-trend-chart">
        {trend.map((day) => (
          <div key={day.date} className="kpi-trend-day" title={`${day.date}: ${day.count}`}>
            <div className={`kpi-trend-bar ${color}`} style={{ height: `${(day.count / maxVal) * 100}%` }} />
          </div>
        ))}
      </div>
      {showLabels && (
        <div className="kpi-trend-labels">
          {trend.map((day) => (
            <span key={day.date}>{day.date.slice(8, 10)}</span>
          ))}
        </div>
      )}
    </div>
  );
}

export function ReportsShell({
  dateFrom,
  dateTo,
  workOrders,
  fiscalSla,
  forbidden,
}: {
  dateFrom: string;
  dateTo: string;
  workOrders: WorkOrderReport | null;
  fiscalSla: FiscalRequestSlaReport | null;
  forbidden: boolean;
}) {
  const router = useRouter();
  const [from, setFrom] = useState(dateFrom);
  const [to, setTo] = useState(dateTo);

  function applyFilter(e: FormEvent) {
    e.preventDefault();
    const qs = new URLSearchParams();
    if (from) qs.set("date_from", from);
    if (to) qs.set("date_to", to);
    router.push(`/relatorios${qs.toString() ? `?${qs}` : ""}`);
  }

  return (
    <>
      <div className="page-heading">
        <div>
          <div className="eyebrow">Analytics</div>
          <h1>Relatórios</h1>
          <p>Ordens de Serviço por período e cumprimento de SLA das solicitações fiscais.</p>
        </div>
      </div>

      <form className="report-filter-bar" onSubmit={applyFilter}>
        <div className="report-filter-field">
          <label htmlFor="date_from">De</label>
          <input id="date_from" type="date" value={from} onChange={(e) => setFrom(e.target.value)} />
        </div>
        <div className="report-filter-field">
          <label htmlFor="date_to">Até</label>
          <input id="date_to" type="date" value={to} onChange={(e) => setTo(e.target.value)} />
        </div>
        <button type="submit" className="primary-button">Aplicar</button>
      </form>

      {forbidden ? (
        <div className="empty-search">
          <Search size={28} />
          <strong>Sem acesso</strong>
          <span>Você não tem permissão para ver relatórios.</span>
        </div>
      ) : (
        <div className="reports-grid">
          <section className="kpi-panel">
            <h3>Ordens de Serviço no período</h3>
            <div className="kpi-stat-grid">
              <div className="kpi-stat">
                <span className="kpi-stat-label">Criadas</span>
                <span className="kpi-stat-value accent-blue">{workOrders?.total ?? 0}</span>
              </div>
              <div className="kpi-stat">
                <span className="kpi-stat-label">Atrasadas</span>
                <span className={`kpi-stat-value ${(workOrders?.overdue ?? 0) > 0 ? "accent-red" : "accent-green"}`}>
                  {workOrders?.overdue ?? 0}
                </span>
              </div>
              <div className="kpi-stat">
                <span className="kpi-stat-label">Taxa de conclusão</span>
                <span className={`kpi-stat-value ${(workOrders?.completion_rate_pct ?? 0) >= 70 ? "accent-green" : "accent-orange"}`}>
                  {workOrders?.completion_rate_pct != null ? `${workOrders.completion_rate_pct}%` : "—"}
                </span>
              </div>
              <div className="kpi-stat">
                <span className="kpi-stat-label">Setores em aberto</span>
                <span className="kpi-stat-value">{Object.keys(workOrders?.by_sector ?? {}).length}</span>
              </div>
            </div>
            <h3 style={{ marginTop: "var(--sp-5)" }}>Por status</h3>
            <BarChart data={workOrders?.by_status ?? {}} color="blue" />
            <h3 style={{ marginTop: "var(--sp-5)" }}>Por setor</h3>
            <BarChart data={workOrders?.by_sector ?? {}} color="orange" />
            <h3 style={{ marginTop: "var(--sp-5)" }}>Criadas por dia</h3>
            <TrendBars trend={workOrders?.trend ?? []} color="blue" />
          </section>

          <section className="kpi-panel">
            <h3>SLA de Solicitações Fiscais</h3>
            <div className="kpi-stat-grid">
              <div className="kpi-stat">
                <span className="kpi-stat-label">Criadas</span>
                <span className="kpi-stat-value accent-orange">{fiscalSla?.total ?? 0}</span>
              </div>
              <div className="kpi-stat">
                <span className="kpi-stat-label">Atrasadas (SLA)</span>
                <span className={`kpi-stat-value ${(fiscalSla?.overdue ?? 0) > 0 ? "accent-red" : "accent-green"}`}>
                  {fiscalSla?.overdue ?? 0}
                </span>
              </div>
              <div className="kpi-stat">
                <span className="kpi-stat-label">SLA cumprido</span>
                <span className={`kpi-stat-value ${(fiscalSla?.sla_compliance_pct ?? 0) >= 80 ? "accent-green" : "accent-orange"}`}>
                  {fiscalSla?.sla_compliance_pct != null ? `${fiscalSla.sla_compliance_pct}%` : "—"}
                </span>
              </div>
              <div className="kpi-stat">
                <span className="kpi-stat-label">Tempo médio de resolução</span>
                <span className="kpi-stat-value">
                  {fiscalSla?.avg_resolution_hours != null ? `${fiscalSla.avg_resolution_hours}h` : "—"}
                </span>
              </div>
            </div>
            <h3 style={{ marginTop: "var(--sp-5)" }}>Estado do SLA</h3>
            <BarChart
              data={Object.fromEntries(
                Object.entries(fiscalSla?.sla_states ?? {})
                  .filter(([, v]) => v > 0)
                  .map(([k, v]) => [SLA_STATE_LABELS[k] ?? k, v]),
              )}
              color="purple"
            />
            <h3 style={{ marginTop: "var(--sp-5)" }}>Por tipo</h3>
            <BarChart data={fiscalSla?.by_type ?? {}} color="green" />
            <h3 style={{ marginTop: "var(--sp-5)" }}>Criadas por dia</h3>
            <TrendBars trend={fiscalSla?.trend ?? []} color="orange" />
          </section>
        </div>
      )}
    </>
  );
}
