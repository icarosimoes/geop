"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";

import {
  createAdjustmentAction,
  fetchAdjustments,
  fetchHourBank,
  type AdjustmentRequest,
  type HourBankSummary,
} from "@/app/actions";
import TabBar from "@/app/components/TabBar";

function formatMinutes(totalMinutes: number): string {
  const sign = totalMinutes < 0 ? "-" : "+";
  const abs = Math.abs(totalMinutes);
  const hours = Math.floor(abs / 60);
  const minutes = abs % 60;
  return `${sign}${hours}h${String(minutes).padStart(2, "0")}`;
}

const STATUS_LABELS: Record<string, string> = {
  pending: "Pendente",
  approved: "Aprovado",
  rejected: "Rejeitado",
};

function todayLocalDatetime(): string {
  const now = new Date();
  now.setSeconds(0, 0);
  return new Date(now.getTime() - now.getTimezoneOffset() * 60000).toISOString().slice(0, 16);
}

export default function BancoPage() {
  const router = useRouter();
  const [summary, setSummary] = useState<HourBankSummary | null>(null);
  const [adjustments, setAdjustments] = useState<AdjustmentRequest[]>([]);
  const [loading, setLoading] = useState(true);
  const [showForm, setShowForm] = useState(false);
  const [when, setWhen] = useState(todayLocalDatetime());
  const [type, setType] = useState("in");
  const [reason, setReason] = useState("");
  const [sending, setSending] = useState(false);
  const [message, setMessage] = useState<{ kind: "success" | "error"; text: string } | null>(null);

  function reload() {
    Promise.all([fetchHourBank(), fetchAdjustments()])
      .then(([bank, reqs]) => {
        setSummary(bank);
        setAdjustments(reqs);
      })
      .catch(() => router.push("/login"))
      .finally(() => setLoading(false));
  }

  useEffect(() => {
    reload();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (!reason.trim()) return;
    setSending(true);
    setMessage(null);
    const result = await createAdjustmentAction({
      requestedPunchedAt: new Date(when).toISOString(),
      requestedPunchType: type,
      reason: reason.trim(),
    });
    setSending(false);
    if (result.ok) {
      setMessage({ kind: "success", text: "Solicitação enviada. Aguarde a aprovação do RH." });
      setShowForm(false);
      setReason("");
      reload();
    } else {
      setMessage({ kind: "error", text: result.error ?? "Não foi possível enviar a solicitação." });
    }
  }

  return (
    <div className="app-content">
      <header className="app-header">
        <h1>Banco de horas</h1>
      </header>

      {message?.kind === "success" && <div className="success-box">{message.text}</div>}
      {message?.kind === "error" && <div className="error-box">{message.text}</div>}

      <div className="card" style={{ textAlign: "center" }}>
        <div className="subtitle">Saldo atual</div>
        <div className="title" style={{ fontSize: "1.8rem" }}>
          {loading ? "..." : formatMinutes(summary?.balance_minutes ?? 0)}
        </div>
      </div>

      {!showForm ? (
        <button type="button" className="secondary" onClick={() => setShowForm(true)}>
          Solicitar ajuste de ponto
        </button>
      ) : (
        <form className="card" onSubmit={handleSubmit}>
          <label>
            Data e hora corretas
            <input
              type="datetime-local"
              value={when}
              onChange={(e) => setWhen(e.target.value)}
              required
            />
          </label>
          <label>
            Tipo
            <select value={type} onChange={(e) => setType(e.target.value)}>
              <option value="in">Entrada</option>
              <option value="out">Saída</option>
            </select>
          </label>
          <label>
            Motivo
            <textarea
              value={reason}
              onChange={(e) => setReason(e.target.value)}
              rows={3}
              placeholder="Explique o que aconteceu"
              required
            />
          </label>
          <button type="submit" className="primary" disabled={sending} style={{ marginTop: 12 }}>
            {sending ? "Enviando..." : "Enviar solicitação"}
          </button>
          <button type="button" className="secondary" onClick={() => setShowForm(false)}>
            Cancelar
          </button>
        </form>
      )}

      <div className="card">
        <div className="subtitle" style={{ marginBottom: 8 }}>
          Minhas solicitações
        </div>
        {adjustments.length === 0 && !loading && (
          <p className="center-message">Nenhuma solicitação enviada.</p>
        )}
        {adjustments.map((adj) => (
          <div className="list-item" key={adj.id}>
            <div>
              <div className="title">
                {new Date(adj.requested_punched_at).toLocaleString("pt-BR", {
                  day: "2-digit",
                  month: "2-digit",
                  hour: "2-digit",
                  minute: "2-digit",
                })}
              </div>
              <div className="subtitle">{adj.reason}</div>
              {adj.review_notes && <div className="subtitle">Retorno: {adj.review_notes}</div>}
            </div>
            <span className="badge">{STATUS_LABELS[adj.status] ?? adj.status}</span>
          </div>
        ))}
      </div>

      <TabBar />
    </div>
  );
}
