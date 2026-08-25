"use client";

import { useEffect, useState, type FormEvent } from "react";
import { useRouter } from "next/navigation";

import {
  fetchVacationRequests,
  createVacationRequestAction,
  cancelVacationRequestAction,
  type VacationRequest,
} from "@/app/actions";
import TabBar from "@/app/components/TabBar";

const STATUS_LABELS: Record<string, string> = {
  pending: "Pendente",
  approved: "Aprovado",
  rejected: "Rejeitado",
  cancelled: "Cancelado",
};

function statusClass(status: string) {
  if (status === "approved") return "status-badge approved";
  if (status === "rejected") return "status-badge rejected";
  if (status === "cancelled") return "status-badge cancelled";
  return "status-badge pending";
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

type ViewState = "list" | "form";

export default function FeriasPage() {
  const router = useRouter();
  const [view, setView] = useState<ViewState>("list");
  const [requests, setRequests] = useState<VacationRequest[]>([]);
  const [loading, setLoading] = useState(true);

  // Formulário
  const [startDate, setStartDate] = useState("");
  const [endDate, setEndDate] = useState("");
  const [notes, setNotes] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [formError, setFormError] = useState<string | null>(null);
  const [successMsg, setSuccessMsg] = useState<string | null>(null);

  const days = calcDays(startDate, endDate);

  async function load() {
    setLoading(true);
    try {
      const data = await fetchVacationRequests();
      setRequests(data);
    } catch {
      router.push("/login");
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    load();
  }, []);

  async function handleSubmit(e: FormEvent) {
    e.preventDefault();
    setFormError(null);
    if (!startDate || !endDate) {
      setFormError("Preencha as datas de início e fim.");
      return;
    }
    if (days < 1) {
      setFormError("A data de fim deve ser igual ou posterior à data de início.");
      return;
    }
    setSubmitting(true);
    const result = await createVacationRequestAction({ startDate, endDate, notes });
    setSubmitting(false);
    if (!result.ok) {
      setFormError(result.error ?? "Erro ao enviar solicitação.");
      return;
    }
    setStartDate("");
    setEndDate("");
    setNotes("");
    setView("list");
    setSuccessMsg("Solicitação enviada! Aguarde a aprovação do RH.");
    await load();
  }

  async function handleCancel(id: number) {
    if (!confirm("Deseja cancelar esta solicitação?")) return;
    const result = await cancelVacationRequestAction(id);
    if (!result.ok) {
      alert(result.error ?? "Não foi possível cancelar.");
      return;
    }
    await load();
  }

  const today = new Date().toISOString().split("T")[0];

  return (
    <div className="app-content">
      <header className="app-header" style={{ display: "flex", alignItems: "center", justifyContent: "space-between" }}>
        <h1>Férias</h1>
        {view === "list" && (
          <button
            type="button"
            className="btn-icon"
            onClick={() => { setSuccessMsg(null); setFormError(null); setView("form"); }}
            aria-label="Nova solicitação"
          >
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" width="22" height="22">
              <path d="M12 5v14M5 12h14" />
            </svg>
          </button>
        )}
        {view === "form" && (
          <button
            type="button"
            className="btn-icon"
            onClick={() => { setFormError(null); setView("list"); }}
            aria-label="Voltar"
          >
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" width="22" height="22">
              <path d="M19 12H5M12 5l-7 7 7 7" />
            </svg>
          </button>
        )}
      </header>

      {successMsg && (
        <div className="success-box" style={{ marginBottom: "var(--sp-3)" }}>
          {successMsg}
        </div>
      )}

      {view === "form" && (
        <div className="card">
          <h2 style={{ fontSize: "1rem", marginBottom: "var(--sp-4)", fontWeight: 600 }}>
            Nova solicitação de férias
          </h2>
          <form onSubmit={handleSubmit}>
            <div style={{ marginBottom: "var(--sp-3)" }}>
              <label htmlFor="start_date">
                Data de início
              </label>
              <input
                id="start_date"
                type="date"
                min={today}
                value={startDate}
                onChange={(e) => setStartDate(e.target.value)}
                required
              />
            </div>

            <div style={{ marginBottom: "var(--sp-3)" }}>
              <label htmlFor="end_date">
                Data de fim
              </label>
              <input
                id="end_date"
                type="date"
                min={startDate || today}
                value={endDate}
                onChange={(e) => setEndDate(e.target.value)}
                required
              />
            </div>

            {days > 0 && (
              <p style={{ fontSize: "0.85rem", color: "var(--muted)", marginBottom: "var(--sp-3)" }}>
                Período de <strong>{days} dia{days !== 1 ? "s" : ""}</strong>
              </p>
            )}

            <div style={{ marginBottom: "var(--sp-4)" }}>
              <label htmlFor="notes">
                Observações (opcional)
              </label>
              <textarea
                id="notes"
                rows={3}
                maxLength={500}
                placeholder="Ex.: prefiro a segunda quinzena do mês..."
                value={notes}
                onChange={(e) => setNotes(e.target.value)}
                style={{ resize: "vertical" }}
              />
            </div>

            {formError && (
              <div className="error-box" style={{ marginBottom: "var(--sp-3)" }}>
                {formError}
              </div>
            )}

            <button type="submit" className="primary" disabled={submitting}>
              {submitting ? "Enviando..." : "Enviar solicitação"}
            </button>
          </form>
        </div>
      )}

      {view === "list" && (
        <>
          {loading ? (
            <p style={{ color: "var(--muted)", fontSize: "0.9rem" }}>Carregando...</p>
          ) : requests.length === 0 ? (
            <div className="card" style={{ textAlign: "center", color: "var(--muted)" }}>
              <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5"
                width="40" height="40" style={{ marginBottom: "var(--sp-2)", opacity: 0.4 }}>
                <rect x="3" y="4" width="18" height="17" rx="2" />
                <path d="M3 9h18M8 2v4M16 2v4" />
              </svg>
              <p style={{ marginTop: 0 }}>Nenhuma solicitação ainda.</p>
              <button type="button" className="primary" onClick={() => setView("form")}
                style={{ marginTop: "var(--sp-3)" }}>
                Solicitar férias
              </button>
            </div>
          ) : (
            <ul style={{ listStyle: "none", padding: 0, margin: 0 }}>
              {requests.map((req) => (
                <li key={req.id} className="card" style={{ marginBottom: "var(--sp-3)" }}>
                  <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", gap: "var(--sp-2)" }}>
                    <div>
                      <p style={{ margin: 0, fontWeight: 600, fontSize: "0.95rem" }}>
                        {formatDate(req.start_date)} → {formatDate(req.end_date)}
                      </p>
                      <p style={{ margin: "2px 0 0", fontSize: "0.82rem", color: "var(--muted)" }}>
                        {req.days} dia{req.days !== 1 ? "s" : ""}
                      </p>
                    </div>
                    <span className={statusClass(req.status)} style={{ flexShrink: 0 }}>
                      {STATUS_LABELS[req.status] ?? req.status}
                    </span>
                  </div>

                  {req.notes && (
                    <p style={{ margin: "var(--sp-2) 0 0", fontSize: "0.85rem", color: "var(--muted)" }}>
                      {req.notes}
                    </p>
                  )}

                  {req.review_notes && (
                    <p style={{ margin: "var(--sp-2) 0 0", fontSize: "0.85rem",
                      color: req.status === "rejected" ? "var(--red)" : "var(--muted)" }}>
                      <strong>RH:</strong> {req.review_notes}
                    </p>
                  )}

                  {req.status === "pending" && (
                    <button
                      type="button"
                      className="secondary"
                      style={{ marginTop: "var(--sp-3)", fontSize: "0.82rem" }}
                      onClick={() => handleCancel(req.id)}
                    >
                      Cancelar solicitação
                    </button>
                  )}
                </li>
              ))}
            </ul>
          )}
        </>
      )}

      <TabBar />
    </div>
  );
}
