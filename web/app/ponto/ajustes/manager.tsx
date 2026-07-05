"use client";

import { useEffect, useState } from "react";
import { Check, X } from "lucide-react";
import {
  fetchPunchAdjustments,
  reviewPunchAdjustmentAction,
  type PunchAdjustment,
} from "@/app/actions";

const STATUS_LABELS: Record<string, string> = {
  pending: "Pendente",
  approved: "Aprovado",
  rejected: "Rejeitado",
};

const PUNCH_TYPE_LABELS: Record<string, string> = {
  in: "Entrada",
  out: "Saída",
};

function statusClass(status: string) {
  if (status === "approved") return "status status-done";
  if (status === "rejected") return "status status-waiting";
  return "status status-progress";
}

export function AdjustmentManager() {
  const [items, setItems] = useState<PunchAdjustment[]>([]);
  const [total, setTotal] = useState(0);
  const [statusFilter, setStatusFilter] = useState("pending");
  const [loading, setLoading] = useState(true);
  const [reviewing, setReviewing] = useState<number | null>(null);
  const [toast, setToast] = useState("");

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
    } else {
      showToast(result.error ?? "Erro ao revisar solicitação.");
    }
  }

  return (
    <section className="module-panel">
      <div
        className="module-toolbar"
        style={{ padding: "var(--sp-3) var(--sp-5)", borderBottom: "1px solid var(--field-border)" }}
      >
        <select value={statusFilter} onChange={(e) => setStatusFilter(e.target.value)}>
          <option value="pending">Pendentes</option>
          <option value="approved">Aprovados</option>
          <option value="rejected">Rejeitados</option>
          <option value="">Todos</option>
        </select>
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
                    <strong>{item.employee_name}</strong>
                    <div className="muted" style={{ fontSize: 12 }}>
                      {item.punch_id ? "Correção de batida existente" : "Batida esquecida"}
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
      {toast && (
        <div className="module-toast" role="status">
          {toast}
        </div>
      )}
    </section>
  );
}
