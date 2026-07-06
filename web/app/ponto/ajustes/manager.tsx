"use client";

import { useEffect, useState, type FormEvent } from "react";
import { Check, Plus, X } from "lucide-react";
import {
  createManualPunchAction,
  createPunchExcusalAction,
  fetchAdjustmentStats,
  fetchPunchAdjustments,
  reviewPunchAdjustmentAction,
  type AdjustmentStats,
  type PunchAdjustment,
} from "@/app/actions";
import { Avatar } from "@/components/avatar";
import { EmployeeAutocomplete } from "@/components/employee-autocomplete";
import type { TenantUser } from "@/lib/api";

const STATUS_LABELS: Record<string, string> = {
  pending: "Pendente",
  approved: "Aprovado",
  rejected: "Rejeitado",
};

const PUNCH_TYPE_LABELS: Record<string, string> = {
  in: "Entrada",
  out: "Saída",
};

const TABS: Array<{ value: string; label: string }> = [
  { value: "pending", label: "Pendentes" },
  { value: "approved", label: "Aprovados" },
  { value: "rejected", label: "Rejeitados" },
  { value: "", label: "Todos" },
];

function statusClass(status: string) {
  if (status === "approved") return "status status-done";
  if (status === "rejected") return "status status-waiting";
  return "status status-progress";
}

function hasPermission(user: TenantUser, code: string) {
  return user.permissions.includes("*") || user.permissions.includes(code);
}

function monthLabel(iso: string) {
  const [year, month] = iso.split("-");
  const names = ["Jan", "Fev", "Mar", "Abr", "Mai", "Jun", "Jul", "Ago", "Set", "Out", "Nov", "Dez"];
  return `${names[Number(month) - 1]}/${year.slice(2)}`;
}

function MonthlyTrendChart({ trend }: { trend: AdjustmentStats["monthly_trend"] }) {
  const maxVal = Math.max(...trend.map((d) => d.count), 1);
  return (
    <div className="kpi-trend">
      <div className="kpi-trend-chart">
        {trend.map((d) => (
          <div key={d.month} className="kpi-trend-day" title={`${monthLabel(d.month)}: ${d.count}`}>
            <div className="kpi-trend-bar blue" style={{ height: `${(d.count / maxVal) * 100}%` }} />
          </div>
        ))}
      </div>
      <div className="kpi-trend-labels">
        {trend.map((d) => (
          <span key={d.month}>{monthLabel(d.month)}</span>
        ))}
      </div>
    </div>
  );
}

function RequesterList({ items }: { items: AdjustmentStats["top_requesters"] }) {
  if (!items.length) return <p className="muted">Sem dados.</p>;
  return (
    <div>
      {items.map((r) => (
        <div key={r.employee_id} className="requester-row">
          <Avatar name={r.name} avatarUrl={r.avatar_url} size={32} />
          <span className="requester-row-name">{r.name}</span>
          <span className="requester-row-count">{r.count}</span>
        </div>
      ))}
    </div>
  );
}

export function AdjustmentManager({ user }: { user: TenantUser }) {
  const canManage = hasPermission(user, "timeclock.manage");

  const [items, setItems] = useState<PunchAdjustment[]>([]);
  const [total, setTotal] = useState(0);
  const [statusFilter, setStatusFilter] = useState("pending");
  const [loading, setLoading] = useState(true);
  const [reviewing, setReviewing] = useState<number | null>(null);
  const [toast, setToast] = useState("");

  const [stats, setStats] = useState<AdjustmentStats | null>(null);

  const [drawer, setDrawer] = useState<"ajustar" | "abonar" | null>(null);
  const [saving, setSaving] = useState(false);
  const [adjEmployeeId, setAdjEmployeeId] = useState("");
  const [adjDateTime, setAdjDateTime] = useState("");
  const [adjType, setAdjType] = useState("");
  const [adjNotes, setAdjNotes] = useState("");
  const [excEmployeeId, setExcEmployeeId] = useState("");
  const [excDate, setExcDate] = useState("");
  const [excMinutes, setExcMinutes] = useState("");
  const [excReason, setExcReason] = useState("");

  function showToast(msg: string) {
    setToast(msg);
    setTimeout(() => setToast(""), 2600);
  }

  function reload() {
    setLoading(true);
    fetchPunchAdjustments({ status: statusFilter || undefined, pageSize: 50 })
      .then((res) => {
        setItems(res.items);
        setTotal(res.total);
      })
      .finally(() => setLoading(false));
  }

  useEffect(() => {
    reload();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [statusFilter]);

  useEffect(() => {
    fetchAdjustmentStats().then(setStats);
  }, []);

  async function handleReview(request: PunchAdjustment, approve: boolean) {
    const notes = approve
      ? undefined
      : (window.prompt("Motivo da rejeição (opcional):") ?? undefined);
    setReviewing(request.id);
    const result = await reviewPunchAdjustmentAction(request.id, approve, notes || undefined);
    setReviewing(null);
    if (result.ok) {
      showToast(approve ? "Ajuste aprovado." : "Ajuste rejeitado.");
      reload();
      fetchAdjustmentStats().then(setStats);
    } else {
      showToast(result.error ?? "Erro ao revisar solicitação.");
    }
  }

  function closeDrawer() {
    setDrawer(null);
    setAdjEmployeeId("");
    setAdjDateTime("");
    setAdjType("");
    setAdjNotes("");
    setExcEmployeeId("");
    setExcDate("");
    setExcMinutes("");
    setExcReason("");
  }

  async function handleAjustar(e: FormEvent) {
    e.preventDefault();
    if (!adjEmployeeId || !adjDateTime) return;
    setSaving(true);
    const result = await createManualPunchAction({
      employee_id: Number(adjEmployeeId),
      punched_at: adjDateTime,
      punch_type: adjType || undefined,
      notes: adjNotes || undefined,
    });
    setSaving(false);
    if (result.ok) {
      showToast("Batida lançada.");
      closeDrawer();
    } else {
      showToast(result.error ?? "Erro ao lançar batida.");
    }
  }

  async function handleAbonar(e: FormEvent) {
    e.preventDefault();
    if (!excEmployeeId || !excDate || !excReason) return;
    setSaving(true);
    const result = await createPunchExcusalAction({
      employee_id: Number(excEmployeeId),
      reference_date: excDate,
      minutes: excMinutes ? Number(excMinutes) : undefined,
      reason: excReason,
    });
    setSaving(false);
    if (result.ok) {
      showToast("Ponto abonado.");
      closeDrawer();
    } else {
      showToast(result.error ?? "Erro ao abonar ponto.");
    }
  }

  return (
    <>
      {canManage && (
        <div style={{ display: "flex", gap: "var(--sp-3)", marginBottom: "var(--sp-5)" }}>
          <button className="primary-button" onClick={() => setDrawer("ajustar")}>
            <Plus size={16} /> Ajustar Ponto
          </button>
          <button className="secondary-button" onClick={() => setDrawer("abonar")}>
            <Plus size={16} /> Abonar Ponto
          </button>
        </div>
      )}

      {stats && (
        <div className="kpi-grid">
          <div className="kpi-panel">
            <h3>Ajustes por mês</h3>
            <MonthlyTrendChart trend={stats.monthly_trend} />
          </div>
          <div className="kpi-panel">
            <h3>Solicitantes mais frequentes</h3>
            <RequesterList items={stats.top_requesters} />
          </div>
          <div className="kpi-panel">
            <h3>Solicitantes menos frequentes</h3>
            <RequesterList items={stats.least_requesters} />
          </div>
        </div>
      )}

      <section className="module-panel">
        <div className="module-toolbar" style={{ padding: "var(--sp-3) var(--sp-5)", borderBottom: "1px solid var(--field-border)" }}>
          <div className="segmented">
            {TABS.map((tab) => (
              <button
                key={tab.value}
                className={statusFilter === tab.value ? "selected" : ""}
                onClick={() => setStatusFilter(tab.value)}
              >
                {tab.label}
              </button>
            ))}
          </div>
        </div>

        {loading ? (
          <div className="module-state">Carregando solicitações...</div>
        ) : items.length === 0 ? (
          <div className="module-state">
            <strong>Nenhuma solicitação</strong>
            <span>Não há ajustes de ponto neste filtro.</span>
          </div>
        ) : (
          <div className="module-table-wrap">
            <table>
              <thead>
                <tr>
                  <th>Funcionário</th>
                  <th>Tipo</th>
                  <th>Data/hora solicitada</th>
                  <th>Motivo</th>
                  <th>Status</th>
                  {statusFilter === "pending" && <th>Ações</th>}
                </tr>
              </thead>
              <tbody>
                {items.map((item) => (
                  <tr key={item.id}>
                    <td>
                      <div style={{ display: "flex", alignItems: "center", gap: "var(--sp-2)" }}>
                        <Avatar name={item.employee_name} avatarUrl={item.employee_avatar_url} size={28} />
                        <div>
                          <strong>{item.employee_name}</strong>
                          <div className="muted" style={{ fontSize: 12 }}>
                            {item.punch_id ? "Correção de batida existente" : "Batida esquecida"}
                          </div>
                        </div>
                      </div>
                    </td>
                    <td>{item.requested_punch_type ? PUNCH_TYPE_LABELS[item.requested_punch_type] ?? item.requested_punch_type : "—"}</td>
                    <td>{new Date(item.requested_punched_at).toLocaleString("pt-BR")}</td>
                    <td>{item.reason}</td>
                    <td>
                      <span className={statusClass(item.status)}>{STATUS_LABELS[item.status] ?? item.status}</span>
                      {item.review_notes && (
                        <div className="muted" style={{ fontSize: 12, marginTop: 4 }}>
                          {item.review_notes}
                        </div>
                      )}
                    </td>
                    {statusFilter === "pending" && (
                      <td>
                        <div className="row-actions">
                          <button
                            onClick={() => handleReview(item, true)}
                            disabled={reviewing === item.id}
                            aria-label="Aprovar"
                            title="Aprovar"
                          >
                            <Check size={16} />
                          </button>
                          <button
                            onClick={() => handleReview(item, false)}
                            disabled={reviewing === item.id}
                            aria-label="Rejeitar"
                            title="Rejeitar"
                          >
                            <X size={16} />
                          </button>
                        </div>
                      </td>
                    )}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
        <footer className="module-pagination">
          <span>{total} solicitação(ões)</span>
        </footer>
      </section>

      {drawer && (
        <>
          <button className="panel-backdrop" aria-label="Fechar" onClick={closeDrawer} />
          <aside className="record-drawer">
            <header>
              <div>
                <span>Ponto</span>
                <h2>{drawer === "ajustar" ? "Ajustar Ponto" : "Abonar Ponto"}</h2>
              </div>
              <button className="icon-button" onClick={closeDrawer} aria-label="Fechar">
                <X />
              </button>
            </header>

            {drawer === "ajustar" ? (
              <form className="kanban-create-form" onSubmit={handleAjustar} style={{ paddingTop: "var(--sp-5)" }}>
                <label>
                  Funcionário
                  <EmployeeAutocomplete
                    key={drawer}
                    onChange={(id) => setAdjEmployeeId(id)}
                    placeholder="Digite o nome do funcionário..."
                    required
                  />
                </label>
                <label>
                  Data e hora
                  <input
                    type="datetime-local"
                    value={adjDateTime}
                    onChange={(e) => setAdjDateTime(e.target.value)}
                    required
                  />
                </label>
                <label>
                  Tipo
                  <select value={adjType} onChange={(e) => setAdjType(e.target.value)}>
                    <option value="">Não informado</option>
                    <option value="in">Entrada</option>
                    <option value="out">Saída</option>
                  </select>
                </label>
                <label>
                  Observação
                  <input value={adjNotes} onChange={(e) => setAdjNotes(e.target.value)} placeholder="Opcional" />
                </label>
                <footer>
                  <button type="button" onClick={closeDrawer}>Cancelar</button>
                  <button type="submit" disabled={saving}>{saving ? "Salvando..." : "Salvar"}</button>
                </footer>
              </form>
            ) : (
              <form className="kanban-create-form" onSubmit={handleAbonar} style={{ paddingTop: "var(--sp-5)" }}>
                <label>
                  Funcionário
                  <EmployeeAutocomplete
                    key={drawer}
                    onChange={(id) => setExcEmployeeId(id)}
                    placeholder="Digite o nome do funcionário..."
                    required
                  />
                </label>
                <label>
                  Data
                  <input type="date" value={excDate} onChange={(e) => setExcDate(e.target.value)} required />
                </label>
                <label>
                  Minutos abonados
                  <input
                    type="number"
                    min={1}
                    value={excMinutes}
                    onChange={(e) => setExcMinutes(e.target.value)}
                    placeholder="Deixe em branco para abonar o dia inteiro"
                  />
                </label>
                <label>
                  Motivo
                  <input value={excReason} onChange={(e) => setExcReason(e.target.value)} required />
                </label>
                <footer>
                  <button type="button" onClick={closeDrawer}>Cancelar</button>
                  <button type="submit" disabled={saving}>{saving ? "Salvando..." : "Salvar"}</button>
                </footer>
              </form>
            )}
          </aside>
        </>
      )}

      {toast && (
        <div className="module-toast" role="status">
          {toast}
        </div>
      )}
    </>
  );
}
