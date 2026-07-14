"use client";

import {
  BellRing,
  ChevronRight,
  FileClock,
  MoreHorizontal,
  Plus,
  Receipt,
  Search,
  ShieldCheck,
  Users,
  X,
} from "lucide-react";
import { useEffect, useMemo, useState } from "react";
import type { TenantUser } from "@/lib/api";
import Link from "next/link";

type TicketStatus = "Em andamento" | "Aguardando" | "Concluído";

type Ticket = {
  id: number;
  title: string;
  module: string;
  area: string;
  owner: string;
  status: TicketStatus;
  updatedAt: string;
};

type TrendDay = {
  date: string;
  work_orders: number;
  fiscal_requests: number;
};

type WorkOrderKpis = {
  total: number;
  by_status: Record<string, number>;
  by_priority: Record<string, number>;
  by_category: Record<string, number>;
  avg_resolution_hours: number | null;
  sla_compliance_pct: number | null;
  overdue: number;
  created_week: number;
  completed_week: number;
};

type FiscalRequestKpis = {
  by_status: Record<string, number>;
  by_type: Record<string, number>;
  sla_compliance_pct: number | null;
  overdue: number;
};

type DashboardKpis = {
  work_orders: WorkOrderKpis;
  fiscal_requests: FiscalRequestKpis;
  trend: TrendDay[];
};

type DashboardMetricsData = {
  open_occurrences: number;
  my_occurrences: number;
  open_fiscal: number;
  completed_month: number;
  active_users: number;
  active_sectors: number;
  recent: Array<{
    id: number;
    title: string;
    module: string;
    area: string;
    owner: string;
    status: string;
    updated_at: string;
  }>;
  kpis?: DashboardKpis;
} | null;

function formatRelativeTime(dateStr: string): string {
  const date = new Date(dateStr);
  const now = new Date();
  const diffMs = now.getTime() - date.getTime();
  const diffMin = Math.floor(diffMs / 60_000);
  if (diffMin < 1) return "agora";
  if (diffMin < 60) return `há ${diffMin} min`;
  const diffH = Math.floor(diffMin / 60);
  if (diffH < 24) return `há ${diffH} h`;
  const diffD = Math.floor(diffH / 24);
  if (diffD === 1) return "ontem";
  return `há ${diffD} dias`;
}

function formatGreeting(): { greeting: string; dateLabel: string } {
  const now = new Date();
  const hour = now.getHours();
  const greeting = hour < 12 ? "Bom dia" : hour < 18 ? "Boa tarde" : "Boa noite";
  const dateLabel = now.toLocaleDateString("pt-BR", {
    weekday: "long",
    day: "numeric",
    month: "long",
  }).replace(/^\w/, (c) => c.toUpperCase());
  return { greeting, dateLabel };
}

const statusClass: Record<TicketStatus, string> = {
  "Em andamento": "status status-progress",
  Aguardando: "status status-waiting",
  Concluído: "status status-done",
};

const WO_STATUS_LABELS: Record<string, string> = {
  aberta: "Aberta",
  em_andamento: "Em andamento",
  aguardando_material: "Aguardando",
  concluida: "Concluída",
  validada: "Validada",
};

const PRIORITY_LABELS: Record<string, string> = {
  urgente: "Urgente",
  alta: "Alta",
  media: "Média",
  baixa: "Baixa",
};

function BarChart({ data, max, color = "blue" }: { data: Record<string, number>; max?: number; color?: string }) {
  const entries = Object.entries(data).sort((a, b) => b[1] - a[1]);
  const maxVal = max ?? Math.max(...entries.map(([, v]) => v), 1);
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

function TrendChart({ trend }: { trend: TrendDay[] }) {
  const maxVal = Math.max(
    ...trend.flatMap((d) => [d.work_orders, d.fiscal_requests]),
    1,
  );
  const dayNames = ["Dom", "Seg", "Ter", "Qua", "Qui", "Sex", "Sáb"];

  return (
    <div className="kpi-trend">
      <div className="kpi-trend-header">
        <h3>Últimos 7 dias</h3>
        <div className="kpi-trend-legend">
          <span><i style={{ background: "var(--blue)" }} /> OS</span>
          <span><i style={{ background: "var(--green)" }} /> Fiscais</span>
        </div>
      </div>
      <div className="kpi-trend-chart">
        {trend.map((day) => (
          <div key={day.date} className="kpi-trend-day">
            <div className="kpi-trend-bar blue" style={{ height: `${(day.work_orders / maxVal) * 100}%` }} />
            <div className="kpi-trend-bar green" style={{ height: `${(day.fiscal_requests / maxVal) * 100}%` }} />
          </div>
        ))}
      </div>
      <div className="kpi-trend-labels">
        {trend.map((day) => {
          const d = new Date(day.date + "T12:00:00");
          return <span key={day.date}>{dayNames[d.getDay()]}</span>;
        })}
      </div>
    </div>
  );
}

export function DashboardShell({ user, metrics }: { user?: TenantUser; metrics?: DashboardMetricsData }) {
  const [query, setQuery] = useState("");
  const [scope, setScope] = useState<"all" | "mine" | "pending">("all");
  const [selectedTicket, setSelectedTicket] = useState<Ticket | null>(null);
  const displayName = user?.name ?? "Usuário";
  const firstName = displayName.split(" ")[0];

  const [mounted, setMounted] = useState(false);
  const [greetingData, setGreetingData] = useState({ greeting: "", dateLabel: "" });
  useEffect(() => { setMounted(true); setGreetingData(formatGreeting()); }, []);
  const { greeting, dateLabel } = greetingData;

  const tickets: Ticket[] = useMemo(() => {
    if (!metrics?.recent?.length) return [];
    return metrics.recent.map((item) => ({
      id: item.id,
      title: item.title,
      module: item.module || "Ordens de Serviço",
      area: item.area,
      owner: item.owner,
      status: item.status as TicketStatus,
      updatedAt: mounted ? formatRelativeTime(item.updated_at) : "",
    }));
  }, [metrics, mounted]);

  const openOccurrences = metrics?.open_occurrences ?? 0;
  const myOccurrences = metrics?.my_occurrences ?? 0;
  const openFiscal = metrics?.open_fiscal ?? 0;
  const completedMonth = metrics?.completed_month ?? 0;
  const activeUsers = metrics?.active_users ?? 0;
  const activeSectors = metrics?.active_sectors ?? 0;
  const kpis = metrics?.kpis ?? null;

  const filteredTickets = useMemo(() => {
    const normalized = query.trim().toLocaleLowerCase("pt-BR");
    return tickets.filter((ticket) =>
      [String(ticket.id), ticket.title, ticket.module, ticket.area, ticket.owner, ticket.status]
        .join(" ")
        .toLocaleLowerCase("pt-BR")
        .includes(normalized) && (scope === "all" || (scope === "mine" ? ticket.owner.includes(firstName) : ticket.status !== "Concluído")),
    );
  }, [firstName, query, scope, tickets]);

  return (
    <>
      <div className="page-heading">
        <div>
          <div className="eyebrow">{dateLabel}</div>
          <h1>{greeting}, {firstName}</h1>
          <p>Acompanhe o que precisa de atenção na operação.</p>
        </div>
        <Link href="/ordens-servico?new=1" className="primary-button"><Plus size={18} /> Nova OS</Link>
      </div>

      <section className="metrics-grid" aria-label="Indicadores principais">
        <article className="metric-card accent-blue"><span>OS abertas</span><strong>{openOccurrences}</strong><small>{myOccurrences} aguardam sua análise</small><FileClock /></article>
        <article className="metric-card accent-orange"><span>Solicitações fiscais</span><strong>{openFiscal}</strong><small>pendentes de resolução</small><Receipt /></article>
        <article className="metric-card accent-green"><span>Concluídos no mês</span><strong>{completedMonth}</strong><small>ocorrências finalizadas</small><ShieldCheck /></article>
        <article className="metric-card accent-purple"><span>Equipe ativa</span><strong>{activeUsers}</strong><small>{activeSectors} setores em operação</small><Users /></article>
      </section>

      {kpis && (
        <section className="kpi-section" aria-label="KPIs avançados">
          <h2>Indicadores detalhados</h2>
          <div className="kpi-grid">
            <div className="kpi-panel">
              <h3>Ordens de Serviço</h3>
              <div className="kpi-stat-grid">
                <div className="kpi-stat">
                  <span className="kpi-stat-label">Total</span>
                  <span className="kpi-stat-value accent-blue">{kpis.work_orders.total}</span>
                </div>
                <div className="kpi-stat">
                  <span className="kpi-stat-label">Atrasadas (SLA)</span>
                  <span className={`kpi-stat-value ${kpis.work_orders.overdue > 0 ? "accent-red" : "accent-green"}`}>{kpis.work_orders.overdue}</span>
                </div>
                <div className="kpi-stat">
                  <span className="kpi-stat-label">Tempo médio</span>
                  <span className="kpi-stat-value">{kpis.work_orders.avg_resolution_hours != null ? `${kpis.work_orders.avg_resolution_hours}h` : "—"}</span>
                </div>
                <div className="kpi-stat">
                  <span className="kpi-stat-label">SLA cumprido</span>
                  <span className={`kpi-stat-value ${(kpis.work_orders.sla_compliance_pct ?? 0) >= 80 ? "accent-green" : "accent-orange"}`}>{kpis.work_orders.sla_compliance_pct != null ? `${kpis.work_orders.sla_compliance_pct}%` : "—"}</span>
                </div>
              </div>
              <BarChart
                data={Object.fromEntries(
                  Object.entries(kpis.work_orders.by_status).map(([k, v]) => [WO_STATUS_LABELS[k] ?? k, v])
                )}
                color="blue"
              />
            </div>

            <div className="kpi-panel">
              <h3>Solicitações Fiscais</h3>
              <div className="kpi-stat-grid">
                <div className="kpi-stat">
                  <span className="kpi-stat-label">Abertas</span>
                  <span className="kpi-stat-value accent-orange">{Object.entries(kpis.fiscal_requests.by_status).filter(([k]) => k !== "Concluído").reduce((s, [, v]) => s + v, 0)}</span>
                </div>
                <div className="kpi-stat">
                  <span className="kpi-stat-label">Atrasadas (SLA)</span>
                  <span className={`kpi-stat-value ${kpis.fiscal_requests.overdue > 0 ? "accent-red" : "accent-green"}`}>{kpis.fiscal_requests.overdue}</span>
                </div>
                <div className="kpi-stat">
                  <span className="kpi-stat-label">SLA cumprido</span>
                  <span className={`kpi-stat-value ${(kpis.fiscal_requests.sla_compliance_pct ?? 0) >= 80 ? "accent-green" : "accent-orange"}`}>{kpis.fiscal_requests.sla_compliance_pct != null ? `${kpis.fiscal_requests.sla_compliance_pct}%` : "—"}</span>
                </div>
                <div className="kpi-stat">
                  <span className="kpi-stat-label">Concluídas</span>
                  <span className="kpi-stat-value accent-green">{kpis.fiscal_requests.by_status["Concluído"] ?? 0}</span>
                </div>
              </div>
              {Object.keys(kpis.fiscal_requests.by_type).length > 0 && (
                <BarChart data={kpis.fiscal_requests.by_type} color="purple" />
              )}
            </div>
          </div>

          {kpis.trend.length > 0 && (
            <div className="kpi-panel">
              <TrendChart trend={kpis.trend} />
            </div>
          )}
        </section>
      )}

      <div className="content-grid">
        <section className="panel activity-panel">
          <div className="panel-heading">
            <div><h2>Atividades recentes</h2><p>Itens que exigem acompanhamento</p></div>
            <Link href="/ordens-servico" className="secondary-button">Ver todas <ChevronRight size={16} /></Link>
          </div>
          <div className="table-tools">
            <div className="segmented"><button className={scope === "all" ? "selected" : ""} onClick={() => setScope("all")}>Todas</button><button className={scope === "mine" ? "selected" : ""} onClick={() => setScope("mine")}>Minhas</button><button className={scope === "pending" ? "selected" : ""} onClick={() => setScope("pending")}>Pendentes</button></div>
            <label className="table-search">
              <Search size={16} />
              <input value={query} onChange={(e) => setQuery(e.target.value)} placeholder="Filtrar atividades…" aria-label="Filtrar atividades" />
            </label>
          </div>
          <div className="table-scroll">
            <table>
              <thead><tr><th>Protocolo</th><th>Atividade</th><th>Módulo</th><th>Área</th><th>Responsável</th><th>Status</th><th>Atualização</th></tr></thead>
              <tbody>
                {filteredTickets.map((ticket) => (
                  <tr key={`${ticket.module}-${ticket.id}`} onClick={() => setSelectedTicket(ticket)}><td className="protocol">#{ticket.id}</td><td><strong>{ticket.title}</strong></td><td><span className="module-badge">{ticket.module}</span></td><td>{ticket.area}</td><td>{ticket.owner}</td><td><span className={statusClass[ticket.status] ?? "status status-progress"}>{ticket.status}</span></td><td className="muted">{ticket.updatedAt}</td></tr>
                ))}
              </tbody>
            </table>
            {!filteredTickets.length && <div className="empty-search"><Search size={28} /><strong>{metrics ? "Nenhuma atividade" : "Carregando..."}</strong><span>{metrics ? "Ainda não há registros nos módulos operacionais." : "Conectando ao servidor..."}</span></div>}
          </div>
        </section>

        <aside className="right-column">
          <section className="panel progress-panel">
            <div className="panel-heading"><div><h2>Resumo</h2><p>{openOccurrences + openFiscal} itens abertos</p></div></div>
            <div className="summary-stats">
              <div><span>OS abertas</span><strong>{openOccurrences}</strong></div>
              <div><span>Solicitações fiscais</span><strong>{openFiscal}</strong></div>
              <div><span>Concluídos (mês)</span><strong>{completedMonth}</strong></div>
              {kpis && <>
                <div><span>OS ativas</span><strong>{kpis.work_orders.total - (kpis.work_orders.by_status.validada ?? 0)}</strong></div>
                <div><span>OS esta semana</span><strong>{kpis.work_orders.created_week}</strong></div>
              </>}
            </div>
          </section>
          <section className="panel notices-panel">
            <div className="panel-heading"><div><h2>Mural de avisos</h2><p>Comunicados da equipe</p></div><BellRing size={19} /></div>
            <Link href="/mural" className="text-button">Abrir mural <ChevronRight size={15} /></Link>
          </section>
        </aside>
      </div>

      {selectedTicket ? <><button className="panel-backdrop" aria-label="Fechar detalhes" onClick={() => setSelectedTicket(null)}/><aside className="record-drawer"><header><div><span>Item #{selectedTicket.id}</span><h2>{selectedTicket.title}</h2></div><button className="icon-button" onClick={() => setSelectedTicket(null)}><X/></button></header><dl><div><dt>Status</dt><dd><span className={statusClass[selectedTicket.status] ?? "status status-progress"}>{selectedTicket.status}</span></dd></div><div><dt>Área</dt><dd>{selectedTicket.area}</dd></div><div><dt>Responsável</dt><dd>{selectedTicket.owner}</dd></div><div><dt>Atualização</dt><dd>{selectedTicket.updatedAt}</dd></div></dl><footer><Link href="/ordens-servico" className="primary-button">Abrir no módulo</Link></footer></aside></> : null}
    </>
  );
}
