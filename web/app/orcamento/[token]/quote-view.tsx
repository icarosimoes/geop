"use client";

import { CheckCircle2, XCircle, Building2, FileText } from "lucide-react";
import { useState } from "react";
import type { PublicQuote } from "./actions";
import { decidePublicQuoteAction } from "./actions";

function formatCurrency(value: string): string {
  return new Intl.NumberFormat("pt-BR", { style: "currency", currency: "BRL" }).format(Number(value));
}

const STATUS_LABEL: Record<string, string> = {
  enviado: "Aguardando sua decisão", aceito: "Aprovado", recusado: "Recusado", expirado: "Expirado",
};

export function QuoteView({ token, initial }: { token: string; initial: PublicQuote }) {
  const [quote, setQuote] = useState(initial);
  const [decisionNote, setDecisionNote] = useState("");
  const [loading, setLoading] = useState<"accept" | "reject" | null>(null);
  const [error, setError] = useState("");
  const [showRejectForm, setShowRejectForm] = useState(false);

  const canDecide = quote.status === "enviado" && !quote.expired;

  async function handleDecide(approved: boolean) {
    setLoading(approved ? "accept" : "reject");
    setError("");
    const res = await decidePublicQuoteAction(token, approved, decisionNote);
    setLoading(null);
    if (!res.ok || !res.data) { setError(res.error ?? "Erro ao registrar sua decisão."); return; }
    setQuote(res.data);
  }

  return (
    <main className="tenant-login-page">
      <div className="quote-public-card">
        <header className="quote-public-header">
          <div className="quote-public-company"><Building2 size={16} /> {quote.company_name}</div>
          <h1>{quote.title}</h1>
          <p>Orçamento {quote.number ?? ""} para {quote.customer_name}</p>
        </header>

        <div className="quote-public-status-row">
          <div className={`status status-${quote.status === "aceito" ? "done" : quote.status === "recusado" || quote.expired ? "danger" : "waiting"}`}>
            {quote.expired ? "Orçamento expirado" : STATUS_LABEL[quote.status] ?? quote.status}
          </div>
          <a className="secondary-button" href={`/api/public/quotes/${token}/pdf`} target="_blank" rel="noopener noreferrer">
            <FileText size={14} /> Baixar PDF
          </a>
        </div>

        {quote.description && <p className="quote-public-desc">{quote.description}</p>}

        <div className="module-table-wrap">
          <table>
            <thead><tr><th>Item</th><th>Qtd</th><th>Preço unit.</th><th>Total</th></tr></thead>
            <tbody>
              {quote.items.map((i) => (
                <tr key={i.id}>
                  <td>{i.description} <span className="cell-sub">({i.item_type === "produto" ? "Produto" : "Serviço"})</span></td>
                  <td>{i.quantity} {i.unit}</td>
                  <td>{formatCurrency(i.unit_price)}</td>
                  <td>{formatCurrency(i.line_total)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>

        <div className="quote-totals">
          <div>Subtotal <strong>{formatCurrency(quote.subtotal)}</strong></div>
          <div>Desconto <strong>-{formatCurrency(quote.discount_amount)}</strong></div>
          <div className="quote-total-final">Total <strong>{formatCurrency(quote.total)}</strong></div>
        </div>

        {quote.conditions && (
          <div className="quote-public-block">
            <strong>Condições</strong>
            <p>{quote.conditions}</p>
          </div>
        )}

        {quote.valid_until && <p className="cell-sub">Válido até {quote.valid_until}</p>}

        {error && <div className="kanban-form-error">{error}</div>}

        {canDecide && (
          <div className="quote-public-actions">
            {!showRejectForm ? (
              <>
                <button type="button" className="quote-accept-button" disabled={loading !== null} onClick={() => handleDecide(true)}>
                  <CheckCircle2 size={18} /> {loading === "accept" ? "Enviando…" : "Aprovar orçamento"}
                </button>
                <button type="button" className="secondary-button" disabled={loading !== null} onClick={() => setShowRejectForm(true)}>
                  <XCircle size={18} /> Recusar
                </button>
              </>
            ) : (
              <div className="quote-reject-form">
                <label>Motivo da recusa (opcional)
                  <textarea rows={2} value={decisionNote} onChange={(e) => setDecisionNote(e.target.value)} />
                </label>
                <div className="quote-public-actions">
                  <button type="button" onClick={() => setShowRejectForm(false)}>Voltar</button>
                  <button type="button" className="secondary-button" style={{ color: "var(--red)" }} disabled={loading !== null} onClick={() => handleDecide(false)}>
                    {loading === "reject" ? "Enviando…" : "Confirmar recusa"}
                  </button>
                </div>
              </div>
            )}
          </div>
        )}

        {quote.status === "aceito" && <p className="quote-public-thanks">Orçamento aprovado — nossa equipe entrará em contato para os próximos passos.</p>}
        {quote.status === "recusado" && <p className="quote-public-thanks">Orçamento recusado. Obrigado pelo retorno.</p>}
        {quote.expired && quote.status === "enviado" && <p className="quote-public-thanks">Este orçamento expirou — entre em contato para solicitar um novo.</p>}
      </div>

      <style>{`
        .quote-public-card {
          width: min(720px, 100%);
          padding: var(--sp-6);
          border-radius: var(--radius-xl);
          background: white;
          box-shadow: var(--shadow-xl);
          position: relative;
          z-index: 1;
        }
        .quote-public-header h1 { margin: var(--sp-2) 0 4px; }
        .quote-public-header p { color: var(--muted); margin: 0; }
        .quote-public-company { display: flex; align-items: center; gap: 6px; color: var(--muted); font-size: var(--font-sm); font-weight: 600; }
        .quote-public-status-row { display: flex; align-items: center; justify-content: space-between; gap: var(--sp-3); flex-wrap: wrap; margin: var(--sp-3) 0; }
        .quote-public-desc { white-space: pre-wrap; margin: var(--sp-3) 0; }
        .cell-sub { font-size: var(--font-xs); color: var(--muted); }
        .quote-totals { display: flex; flex-direction: column; align-items: flex-end; gap: 4px; margin: var(--sp-4) 0; }
        .quote-totals > div { display: flex; gap: var(--sp-3); }
        .quote-total-final { font-size: var(--font-lg); border-top: 1px solid var(--line); padding-top: 4px; margin-top: 4px; }
        .quote-public-block { margin: var(--sp-4) 0; }
        .quote-public-block p { white-space: pre-wrap; color: var(--muted); }
        .quote-public-actions { display: flex; gap: var(--sp-3); flex-wrap: wrap; margin-top: var(--sp-5); }
        .quote-accept-button {
          display: flex; align-items: center; gap: 8px;
          background: var(--blue); color: white; border: 0; border-radius: var(--radius-md);
          padding: 0 var(--sp-5); height: 48px; font-weight: 700; cursor: pointer;
        }
        .quote-accept-button:hover { background: var(--blue-hover); }
        .quote-accept-button:disabled { opacity: .6; cursor: not-allowed; }
        .quote-reject-form { display: flex; flex-direction: column; gap: var(--sp-2); width: 100%; }
        .quote-public-thanks { margin-top: var(--sp-4); color: var(--muted); }
      `}</style>
    </main>
  );
}
