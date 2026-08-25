"use client";

import { useEffect, useState } from "react";
import { Check, X } from "lucide-react";
import {
  fetchVacationRequests,
  reviewVacationRequestAction,
  type VacationRequestItem,
} from "@/app/actions";
import { Avatar } from "@/components/avatar";
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

function formatDate(iso: string) {
  const [year, month, day] = iso.split("-");
  return `${day}/${month}/${year}`;
}

function hasPermission(user: TenantUser, code: string) {
  return user.permissions.includes("*") || user.permissions.includes(code);
}

interface ReviewModalState {
  request: VacationRequestItem;
  approve: boolean;
}

export function VacationRequestManager({ user }: { user: TenantUser }) {
  const canReview = hasPermission(user, "ponto-ferias");

  const [activeTab, setActiveTab] = useState("pending");
  const [items, setItems] = useState<VacationRequestItem[]>([]);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(1);
  const [loading, setLoading] = useState(true);

  const [reviewModal, setReviewModal] = useState<ReviewModalState | null>(null);
  const [reviewNotes, setReviewNotes] = useState("");
  const [reviewing, setReviewing] = useState(false);
  const [reviewError, setReviewError] = useState<string | null>(null);

  const PAGE_SIZE = 20;

  async function load(tab: string, p: number) {
    setLoading(true);
    const data = await fetchVacationRequests({ page: p, pageSize: PAGE_SIZE, status: tab || undefined });
    setItems(data.items);
    setTotal(data.total);
    setLoading(false);
  }

  useEffect(() => {
    load(activeTab, page);
  }, [activeTab, page]);

  function switchTab(tab: string) {
    setActiveTab(tab);
    setPage(1);
  }

  function openReview(request: VacationRequestItem, approve: boolean) {
    setReviewModal({ request, approve });
    setReviewNotes("");
    setReviewError(null);
  }

  async function submitReview() {
    if (!reviewModal) return;
    setReviewing(true);
    setReviewError(null);
    const result = await reviewVacationRequestAction(
      reviewModal.request.id,
      reviewModal.approve,
      reviewNotes || undefined,
    );
    setReviewing(false);
    if (!result.ok) {
      setReviewError(result.error ?? "Erro ao processar.");
      return;
    }
    setReviewModal(null);
    await load(activeTab, page);
  }

  const totalPages = Math.ceil(total / PAGE_SIZE);

  return (
    <div className="page-content">
      <div className="page-header">
        <h1>Requisições de Férias</h1>
        <p className="page-subtitle">
          Gerencie as solicitações de férias dos colaboradores.
        </p>
      </div>

      {/* Tabs de status */}
      <div className="tabs" style={{ marginBottom: "var(--sp-4)" }}>
        {TABS.map((tab) => (
          <button
            key={tab.value}
            type="button"
            className={`tab ${activeTab === tab.value ? "active" : ""}`}
            onClick={() => switchTab(tab.value)}
          >
            {tab.label}
          </button>
        ))}
      </div>

      {/* Tabela */}
      <div className="table-card">
        {loading ? (
          <div className="table-empty">Carregando...</div>
        ) : items.length === 0 ? (
          <div className="table-empty">Nenhuma solicitação encontrada.</div>
        ) : (
          <table className="data-table">
            <thead>
              <tr>
                <th>Colaborador</th>
                <th>Período</th>
                <th>Dias</th>
                <th>Observações</th>
                <th>Status</th>
                <th>Notas do RH</th>
                {canReview && activeTab === "pending" && <th>Ações</th>}
              </tr>
            </thead>
            <tbody>
              {items.map((req) => (
                <tr key={req.id}>
                  <td>
                    <div style={{ display: "flex", alignItems: "center", gap: "var(--sp-2)" }}>
                      <Avatar name={req.employee_name} url={req.employee_avatar_url} size={28} />
                      <span>{req.employee_name}</span>
                    </div>
                  </td>
                  <td style={{ whiteSpace: "nowrap" }}>
                    {formatDate(req.start_date)} → {formatDate(req.end_date)}
                  </td>
                  <td>{req.days}</td>
                  <td style={{ maxWidth: "200px", color: "var(--muted)", fontSize: "0.85rem" }}>
                    {req.notes ?? "—"}
                  </td>
                  <td>
                    <span className={statusClass(req.status)}>
                      {STATUS_LABELS[req.status] ?? req.status}
                    </span>
                  </td>
                  <td style={{ fontSize: "0.85rem", color: "var(--muted)", maxWidth: "200px" }}>
                    {req.review_notes ?? "—"}
                  </td>
                  {canReview && activeTab === "pending" && (
                    <td>
                      <div style={{ display: "flex", gap: "var(--sp-1)" }}>
                        <button
                          type="button"
                          className="icon-btn success"
                          title="Aprovar"
                          onClick={() => openReview(req, true)}
                        >
                          <Check size={16} />
                        </button>
                        <button
                          type="button"
                          className="icon-btn danger"
                          title="Rejeitar"
                          onClick={() => openReview(req, false)}
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
        )}
      </div>

      {/* Paginação */}
      {totalPages > 1 && (
        <div className="pagination" style={{ marginTop: "var(--sp-3)" }}>
          <button
            type="button"
            onClick={() => setPage((p) => Math.max(1, p - 1))}
            disabled={page === 1}
            className="btn-secondary"
          >
            Anterior
          </button>
          <span style={{ fontSize: "0.85rem", color: "var(--muted)" }}>
            {page} / {totalPages}
          </span>
          <button
            type="button"
            onClick={() => setPage((p) => Math.min(totalPages, p + 1))}
            disabled={page === totalPages}
            className="btn-secondary"
          >
            Próxima
          </button>
        </div>
      )}

      {/* Modal de revisão */}
      {reviewModal && (
        <div className="modal-overlay" onClick={() => setReviewModal(null)}>
          <div className="modal" onClick={(e) => e.stopPropagation()}>
            <h2 style={{ marginBottom: "var(--sp-3)", fontSize: "1.05rem" }}>
              {reviewModal.approve ? "Aprovar" : "Rejeitar"} solicitação
            </h2>
            <p style={{ fontSize: "0.9rem", marginBottom: "var(--sp-3)" }}>
              <strong>{reviewModal.request.employee_name}</strong>
              {" — "}
              {formatDate(reviewModal.request.start_date)} até{" "}
              {formatDate(reviewModal.request.end_date)}{" "}
              ({reviewModal.request.days} dias)
            </p>

            <label htmlFor="review_notes" style={{ display: "block", marginBottom: "var(--sp-2)", fontSize: "0.85rem" }}>
              {reviewModal.approve ? "Notas (opcional)" : "Motivo da rejeição (opcional)"}
            </label>
            <textarea
              id="review_notes"
              rows={3}
              style={{ width: "100%", resize: "vertical", marginBottom: "var(--sp-3)" }}
              value={reviewNotes}
              onChange={(e) => setReviewNotes(e.target.value)}
              placeholder={reviewModal.approve ? "Alguma observação..." : "Explique o motivo..."}
            />

            {reviewError && (
              <p style={{ color: "var(--red)", fontSize: "0.85rem", marginBottom: "var(--sp-2)" }}>
                {reviewError}
              </p>
            )}

            <div style={{ display: "flex", gap: "var(--sp-2)", justifyContent: "flex-end" }}>
              <button
                type="button"
                className="btn-secondary"
                onClick={() => setReviewModal(null)}
                disabled={reviewing}
              >
                Cancelar
              </button>
              <button
                type="button"
                className={reviewModal.approve ? "btn-primary" : "btn-danger"}
                onClick={submitReview}
                disabled={reviewing}
              >
                {reviewing
                  ? "Processando..."
                  : reviewModal.approve
                  ? "Confirmar aprovação"
                  : "Confirmar rejeição"}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
