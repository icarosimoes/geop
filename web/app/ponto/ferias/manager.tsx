"use client";

import { useEffect, useState, type FormEvent } from "react";
import { Check, Plus, X } from "lucide-react";
import {
  createVacationRequestAdminAction,
  fetchRegistryOptions,
  fetchVacationRequestStats,
  fetchVacationRequests,
  reviewVacationRequestAction,
  type RegistryOption,
  type VacationRequestItem,
  type VacationRequestStats,
} from "@/app/actions";
import { Avatar } from "@/components/avatar";
import { EmployeeAutocomplete } from "@/components/employee-autocomplete";
import type { TenantUser } from "@/lib/api";

const STATUS_LABELS: Record<string, string> = {
  pending: "Pendente",
  approved: "Aprovado",
  rejected: "Rejeitado",
  cancelled: "Cancelado",
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
  if (status === "cancelled") return "status status-waiting";
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

function formatDate(iso: string) {
  const [year, month, day] = iso.split("-");
  return `${day}/${month}/${year}`;
}

function calcDays(start: string, end: string) {
  if (!start || !end) return 0;
  const s = new Date(start);
  const e = new Date(end);
  if (e < s) return 0;
  return Math.round((e.getTime() - s.getTime()) / 86400000) + 1;
}

function MonthlyTrendChart({ trend }: { trend: VacationRequestStats["monthly_trend"] }) {
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

interface ReviewModalState {
  request: VacationRequestItem;
  approve: boolean;
}

export function VacationRequestManager({ user }: { user: TenantUser }) {
  const canManage = hasPermission(user, "ponto-ferias");

  const [statusFilter, setStatusFilter] = useState("pending");
  const [sectorFilter, setSectorFilter] = useState("");
  const [sectors, setSectors] = useState<RegistryOption[]>([]);
  const [items, setItems] = useState<VacationRequestItem[]>([]);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(true);
  const [reviewing, setReviewing] = useState<number | null>(null);
  const [toast, setToast] = useState("");

  const [stats, setStats] = useState<VacationRequestStats | null>(null);

  // Drawer de criação
  const [drawer, setDrawer] = useState(false);
  const [saving, setSaving] = useState(false);
  const [newEmployeeId, setNewEmployeeId] = useState("");
  const [newStart, setNewStart] = useState("");
  const [newEnd, setNewEnd] = useState("");
  const [newNotes, setNewNotes] = useState("");
  const [drawerError, setDrawerError] = useState<string | null>(null);

  // Modal de revisão
  const [reviewModal, setReviewModal] = useState<ReviewModalState | null>(null);
  const [reviewNotes, setReviewNotes] = useState("");
  const [reviewSaving, setReviewSaving] = useState(false);
  const [reviewError, setReviewError] = useState<string | null>(null);

  const previewDays = calcDays(newStart, newEnd);

  function showToast(msg: string) {
    setToast(msg);
    setTimeout(() => setToast(""), 2600);
  }

  function reload() {
    setLoading(true);
    fetchVacationRequests({
      status: statusFilter || undefined,
      sectorId: sectorFilter ? Number(sectorFilter) : undefined,
      pageSize: 50,
    })
      .then((res) => {
        setItems(res.items);
        setTotal(res.total);
      })
      .finally(() => setLoading(false));
  }

  useEffect(() => {
    reload();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [statusFilter, sectorFilter]);

  useEffect(() => {
    fetchVacationRequestStats().then(setStats);
    fetchRegistryOptions("Setor").then(setSectors);
  }, []);

  function closeDrawer() {
    setDrawer(false);
    setNewEmployeeId("");
    setNewStart("");
    setNewEnd("");
    setNewNotes("");
    setDrawerError(null);
  }

  async function handleCreate(e: FormEvent) {
    e.preventDefault();
    setDrawerError(null);
    if (!newEmployeeId || !newStart || !newEnd) return;
    if (previewDays < 1) {
      setDrawerError("A data de fim deve ser igual ou posterior ao início.");
      return;
    }
    setSaving(true);
    const result = await createVacationRequestAdminAction({
      employee_id: Number(newEmployeeId),
      start_date: newStart,
      end_date: newEnd,
      notes: newNotes || undefined,
    });
    setSaving(false);
    if (result.ok) {
      showToast("Férias registradas.");
      closeDrawer();
      reload();
      fetchVacationRequestStats().then(setStats);
    } else {
      setDrawerError(result.error ?? "Erro ao registrar.");
    }
  }

  function openReviewModal(request: VacationRequestItem, approve: boolean) {
    setReviewModal({ request, approve });
    setReviewNotes("");
    setReviewError(null);
  }

  async function submitReview() {
    if (!reviewModal) return;
    setReviewSaving(true);
    setReviewError(null);
    const result = await reviewVacationRequestAction(
      reviewModal.request.id,
      reviewModal.approve,
      reviewNotes || undefined,
    );
    setReviewSaving(false);
    if (result.ok) {
      showToast(reviewModal.approve ? "Férias aprovadas." : "Solicitação rejeitada.");
      setReviewModal(null);
      reload();
      fetchVacationRequestStats().then(setStats);
    } else {
      setReviewError(result.error ?? "Erro ao processar.");
    }
  }

  const today = new Date().toISOString().split("T")[0];

  return (
    <>
      <header className="module-heading">
        <div>
          <p className="eyebrow">Ponto</p>
          <h1>Gestão de Férias</h1>
          <p>
            Solicitações enviadas pelos colaboradores e férias registradas diretamente pelo RH.
          </p>
        </div>
        {canManage && (
          <button className="primary-button" onClick={() => setDrawer(true)}>
            <Plus size={18} /> Registrar férias
          </button>
        )}
      </header>

      {/* KPIs */}
      {stats && (
        <div className="kpi-grid">
          <div className="kpi-panel">
            <h3>Solicitações por mês</h3>
            <MonthlyTrendChart trend={stats.monthly_trend} />
          </div>
          <div className="kpi-panel">
            <div style={{ display: "flex", flexDirection: "column", gap: "var(--sp-4)" }}>
              <div>
                <div className="kpi-label">Aguardando aprovação</div>
                <div className="kpi-value">{stats.pending}</div>
              </div>
              <div>
                <div className="kpi-label">Férias aprovadas (total)</div>
                <div className="kpi-value">{stats.approved_total}</div>
              </div>
              <div>
                <div className="kpi-label">Próximas férias (60 dias)</div>
                <div className="kpi-value">{stats.upcoming_60d}</div>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* Tabela */}
      <section className="module-panel">
        <div
          className="module-toolbar"
          style={{ padding: "var(--sp-3) var(--sp-5)", borderBottom: "1px solid var(--field-border)", gap: "var(--sp-3)", flexWrap: "wrap" }}
        >
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
          {sectors.length > 0 && (
            <select
              value={sectorFilter}
              onChange={(e) => setSectorFilter(e.target.value)}
              style={{ fontSize: 13 }}
              aria-label="Filtrar por setor"
            >
              <option value="">Todos os setores</option>
              {sectors.map((s) => (
                <option key={s.id} value={s.id}>{s.name}</option>
              ))}
            </select>
          )}
        </div>

        {loading ? (
          <div className="module-state">Carregando...</div>
        ) : items.length === 0 ? (
          <div className="module-state">
            <strong>Nenhuma solicitação</strong>
            <span>Não há férias neste filtro.</span>
          </div>
        ) : (
          <div className="module-table-wrap">
            <table>
              <thead>
                <tr>
                  <th>Colaborador</th>
                  <th>Setor</th>
                  <th>Período</th>
                  <th>Dias</th>
                  <th>Dias úteis</th>
                  <th>Observações</th>
                  <th>Status</th>
                  <th>Notas do RH</th>
                  {canManage && statusFilter === "pending" && <th>Ações</th>}
                </tr>
              </thead>
              <tbody>
                {items.map((req) => (
                  <tr key={req.id}>
                    <td>
                      <div style={{ display: "flex", alignItems: "center", gap: "var(--sp-2)" }}>
                        <Avatar
                          name={req.employee_name}
                          avatarUrl={req.employee_avatar_url}
                          size={28}
                        />
                        <strong>{req.employee_name}</strong>
                      </div>
                    </td>
                    <td className="muted" style={{ fontSize: 13 }}>
                      {req.employee_sector_name ?? "—"}
                    </td>
                    <td style={{ whiteSpace: "nowrap" }}>
                      {formatDate(req.start_date)} → {formatDate(req.end_date)}
                    </td>
                    <td>{req.days}</td>
                    <td className="muted">{req.working_days ?? "—"}</td>
                    <td className="muted" style={{ fontSize: 13, maxWidth: 200 }}>
                      {req.notes ?? "—"}
                    </td>
                    <td>
                      <span className={statusClass(req.status)}>
                        {STATUS_LABELS[req.status] ?? req.status}
                      </span>
                    </td>
                    <td className="muted" style={{ fontSize: 13, maxWidth: 220 }}>
                      {req.review_notes ?? "—"}
                    </td>
                    {canManage && statusFilter === "pending" && (
                      <td>
                        <div className="row-actions">
                          <button
                            onClick={() => openReviewModal(req, true)}
                            disabled={reviewing === req.id}
                            aria-label="Aprovar"
                            title="Aprovar"
                          >
                            <Check size={16} />
                          </button>
                          <button
                            onClick={() => openReviewModal(req, false)}
                            disabled={reviewing === req.id}
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

      {/* Drawer — Registrar férias pelo RH */}
      {drawer && (
        <div className="modal-layer" role="presentation" onClick={closeDrawer}>
          <section
            className="record-modal"
            role="dialog"
            aria-modal="true"
            onClick={(e) => e.stopPropagation()}
          >
            <header>
              <div>
                <span>Ponto</span>
                <h2>Registrar férias</h2>
              </div>
              <button className="icon-button" onClick={closeDrawer} aria-label="Fechar">
                <X />
              </button>
            </header>

            <form onSubmit={handleCreate}>
              <label>
                Colaborador
                <EmployeeAutocomplete
                  key="vacation-create"
                  onChange={(id) => setNewEmployeeId(id)}
                  placeholder="Digite o nome do colaborador..."
                  required
                />
              </label>
              <label>
                Início das férias
                <input
                  type="date"
                  min={today}
                  value={newStart}
                  onChange={(e) => setNewStart(e.target.value)}
                  required
                />
              </label>
              <label>
                Fim das férias
                <input
                  type="date"
                  min={newStart || today}
                  value={newEnd}
                  onChange={(e) => setNewEnd(e.target.value)}
                  required
                />
              </label>
              {previewDays > 0 && (
                <p className="muted" style={{ margin: "-var(--sp-2) 0 var(--sp-2)", fontSize: 13 }}>
                  Período de <strong>{previewDays} dia{previewDays !== 1 ? "s" : ""}</strong>
                </p>
              )}
              <label>
                Observações (opcional)
                <input
                  value={newNotes}
                  onChange={(e) => setNewNotes(e.target.value)}
                  placeholder="Informação adicional..."
                />
              </label>
              {drawerError && (
                <p style={{ color: "var(--red)", fontSize: 13, margin: 0 }}>{drawerError}</p>
              )}
              <footer>
                <button type="button" onClick={closeDrawer}>Cancelar</button>
                <button type="submit" disabled={saving}>
                  {saving ? "Salvando…" : "Registrar como aprovado"}
                </button>
              </footer>
            </form>
          </section>
        </div>
      )}

      {/* Modal de revisão (aprovar / rejeitar) */}
      {reviewModal && (
        <div
          className="modal-layer"
          role="presentation"
          onClick={() => setReviewModal(null)}
        >
          <section
            className="record-modal"
            role="dialog"
            aria-modal="true"
            style={{ maxWidth: 440 }}
            onClick={(e) => e.stopPropagation()}
          >
            <header>
              <div>
                <span>Férias</span>
                <h2>{reviewModal.approve ? "Aprovar solicitação" : "Rejeitar solicitação"}</h2>
              </div>
              <button
                className="icon-button"
                onClick={() => setReviewModal(null)}
                aria-label="Fechar"
              >
                <X />
              </button>
            </header>

            <p style={{ margin: "0 0 var(--sp-4)", fontSize: "0.9rem" }}>
              <strong>{reviewModal.request.employee_name}</strong>
              {" — "}
              {formatDate(reviewModal.request.start_date)} até{" "}
              {formatDate(reviewModal.request.end_date)}{" "}
              ({reviewModal.request.days} dias)
            </p>

            <label>
              {reviewModal.approve ? "Notas (opcional)" : "Motivo da rejeição (opcional)"}
              <textarea
                rows={3}
                style={{ width: "100%", resize: "vertical" }}
                value={reviewNotes}
                onChange={(e) => setReviewNotes(e.target.value)}
                placeholder={
                  reviewModal.approve ? "Alguma observação..." : "Explique o motivo..."
                }
              />
            </label>

            {reviewError && (
              <p style={{ color: "var(--red)", fontSize: 13, margin: 0 }}>{reviewError}</p>
            )}

            <footer>
              <button type="button" onClick={() => setReviewModal(null)} disabled={reviewSaving}>
                Cancelar
              </button>
              <button
                type="button"
                onClick={submitReview}
                disabled={reviewSaving}
              >
                {reviewSaving
                  ? "Processando…"
                  : reviewModal.approve
                  ? "Confirmar aprovação"
                  : "Confirmar rejeição"}
              </button>
            </footer>
          </section>
        </div>
      )}

      {/* Toast */}
      {toast && (
        <div className="module-toast" role="status">
          {toast}
        </div>
      )}
    </>
  );
}
