"use client";

import { ChevronLeft, ChevronRight, Search, X, Plus, ShoppingCart } from "lucide-react";
import { useEffect, useRef, useState } from "react";
import type { SaleDetail, SalesInvoice, SaleSummary } from "./actions";
import {
  createInvoiceAction, getSaleAction, listSalesAction, registerPaymentAction, updateSaleAction,
} from "./actions";

function formatCurrency(value: string | null): string {
  if (value == null) return "—";
  return new Intl.NumberFormat("pt-BR", { style: "currency", currency: "BRL" }).format(Number(value));
}

const SALE_STATUS_LABEL: Record<string, string> = {
  confirmada: "Confirmada", entregue: "Entregue", concluida: "Concluída", cancelada: "Cancelada",
};
const SALE_STATUS_CLASS: Record<string, string> = {
  confirmada: "status-progress", entregue: "status-waiting", concluida: "status-done", cancelada: "status-danger",
};
const INSTALL_STATUS_LABEL: Record<string, string> = {
  pendente: "Pendente", agendada: "Agendada", em_andamento: "Em andamento", concluida: "Concluída", cancelada: "Cancelada",
};
const INSTALL_STATUS_CLASS: Record<string, string> = {
  pendente: "status-neutral", agendada: "status-waiting", em_andamento: "status-progress", concluida: "status-done", cancelada: "status-danger",
};
const INVOICE_STATUS_LABEL: Record<string, string> = {
  pendente: "Pendente", faturada: "Faturada", paga: "Paga", atrasada: "Atrasada", cancelada: "Cancelada",
};
const INVOICE_STATUS_CLASS: Record<string, string> = {
  pendente: "status-neutral", faturada: "status-waiting", paga: "status-done", atrasada: "status-danger", cancelada: "status-neutral",
};

// ---- Invoice creation ----

function InvoiceForm({ saleId, onSave, onCancel }: { saleId: number; onSave: () => void; onCancel: () => void }) {
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const formRef = useRef<HTMLFormElement>(null);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    const fd = new FormData(formRef.current!);
    const raw: Record<string, unknown> = {};
    for (const [k, v] of fd.entries()) { if (v !== "") raw[k] = v; }
    setLoading(true);
    setError("");
    const res = await createInvoiceAction(saleId, raw);
    setLoading(false);
    if (!res.ok) { setError(res.error ?? "Erro ao criar fatura."); return; }
    onSave();
  }

  return (
    <form ref={formRef} onSubmit={handleSubmit} className="form-section" style={{ marginBottom: "var(--sp-4)" }}>
      {error && <div className="kanban-form-error">{error}</div>}
      <div className="form-grid">
        <label>Valor *<input name="amount" type="number" step="0.01" min="0.01" required /></label>
        <label>Vencimento<input name="due_date" type="date" /></label>
      </div>
      <div className="form-grid">
        <label>Nº da NF<input name="nf_number" /></label>
        <label>Emitida em<input name="issued_at" type="date" /></label>
      </div>
      <label>Observações<input name="notes" /></label>
      <footer>
        <button type="button" onClick={onCancel}>Cancelar</button>
        <button type="submit" disabled={loading}>{loading ? "Salvando…" : "Criar fatura"}</button>
      </footer>
    </form>
  );
}

// ---- Payment registration ----

function PaymentForm({ invoiceId, onSave, onCancel }: { invoiceId: number; onSave: () => void; onCancel: () => void }) {
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const formRef = useRef<HTMLFormElement>(null);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    const fd = new FormData(formRef.current!);
    const raw: Record<string, unknown> = {};
    for (const [k, v] of fd.entries()) { if (v !== "") raw[k] = v; }
    setLoading(true);
    setError("");
    const res = await registerPaymentAction(invoiceId, raw);
    setLoading(false);
    if (!res.ok) { setError(res.error ?? "Erro ao registrar recebimento."); return; }
    onSave();
  }

  return (
    <form ref={formRef} onSubmit={handleSubmit} className="form-section" style={{ marginBottom: "var(--sp-3)" }}>
      {error && <div className="kanban-form-error">{error}</div>}
      <div className="form-grid">
        <label>Valor recebido *<input name="amount" type="number" step="0.01" min="0.01" required /></label>
        <label>Data *<input name="paid_at" type="date" required defaultValue={new Date().toISOString().slice(0, 10)} /></label>
      </div>
      <label>Forma de pagamento
        <select name="method" defaultValue="pix">
          <option value="pix">Pix</option>
          <option value="boleto">Boleto</option>
          <option value="cartao">Cartão</option>
          <option value="transferencia">Transferência</option>
          <option value="dinheiro">Dinheiro</option>
          <option value="outro">Outro</option>
        </select>
      </label>
      <label>Referência<input name="reference" /></label>
      <footer>
        <button type="button" onClick={onCancel}>Cancelar</button>
        <button type="submit" disabled={loading}>{loading ? "Salvando…" : "Registrar recebimento"}</button>
      </footer>
    </form>
  );
}

// ---- Invoice card ----

function InvoiceCard({ invoice, onChanged }: { invoice: SalesInvoice; onChanged: () => void }) {
  const [showPaymentForm, setShowPaymentForm] = useState(false);
  const remaining = Number(invoice.amount) - Number(invoice.paid_total);

  return (
    <div className="invoice-card">
      <div className="invoice-card-head">
        <div>
          <strong>{invoice.number ?? `Fatura #${invoice.id}`}</strong>
          {invoice.nf_number && <span className="cell-sub"> · NF {invoice.nf_number}</span>}
        </div>
        <span className={`status ${INVOICE_STATUS_CLASS[invoice.status] ?? "status-neutral"}`}>
          {INVOICE_STATUS_LABEL[invoice.status] ?? invoice.status}
        </span>
      </div>
      <div className="invoice-card-amounts">
        <span>Valor: <strong>{formatCurrency(invoice.amount)}</strong></span>
        <span>Recebido: <strong>{formatCurrency(invoice.paid_total)}</strong></span>
        {remaining > 0.001 && <span>Saldo: <strong>{formatCurrency(String(remaining))}</strong></span>}
        {invoice.due_date && <span>Vencimento: {invoice.due_date}</span>}
      </div>
      {invoice.payments.length > 0 && (
        <div className="invoice-payments">
          {invoice.payments.map((p) => (
            <div key={p.id} className="cell-sub">
              {p.paid_at} — {formatCurrency(p.amount)} ({p.method ?? "—"}){p.reference ? ` · ${p.reference}` : ""}
            </div>
          ))}
        </div>
      )}
      {invoice.status !== "cancelada" && invoice.status !== "paga" && (
        showPaymentForm ? (
          <PaymentForm invoiceId={invoice.id} onSave={() => { setShowPaymentForm(false); onChanged(); }} onCancel={() => setShowPaymentForm(false)} />
        ) : (
          <button type="button" className="secondary-button" onClick={() => setShowPaymentForm(true)}>
            <Plus size={14} /> Registrar recebimento
          </button>
        )
      )}
    </div>
  );
}

// ---- Sale detail (delivery/installation + invoices) ----

function SaleDetailPanel({ sale, onChanged }: { sale: SaleDetail; onChanged: () => void }) {
  const [showInvoiceForm, setShowInvoiceForm] = useState(false);
  const [saving, setSaving] = useState(false);

  async function updateField(patch: Record<string, unknown>) {
    setSaving(true);
    await updateSaleAction(sale.id, patch);
    setSaving(false);
    onChanged();
  }

  return (
    <>
      <div className="customer-badges">
        <span className={`status ${SALE_STATUS_CLASS[sale.status] ?? "status-neutral"}`}>{SALE_STATUS_LABEL[sale.status] ?? sale.status}</span>
        <span className={`status ${INSTALL_STATUS_CLASS[sale.installation_status] ?? "status-neutral"}`}>Instalação: {INSTALL_STATUS_LABEL[sale.installation_status] ?? sale.installation_status}</span>
      </div>

      <div className="form-grid">
        <label>Cliente<span>{sale.customer_name ?? "—"}</span></label>
        <label>Valor total<span>{formatCurrency(sale.total_value)}</span></label>
        <label>Faturado<span>{formatCurrency(sale.invoiced_total)}</span></label>
        <label>Recebido<span>{formatCurrency(sale.received_total)}</span></label>
      </div>

      <fieldset className="form-section">
        <legend>Status da venda</legend>
        <div className="form-grid">
          <label>Status
            <select value={sale.status} disabled={saving} onChange={(e) => updateField({ status: e.target.value })}>
              {Object.entries(SALE_STATUS_LABEL).map(([k, v]) => <option key={k} value={k}>{v}</option>)}
            </select>
          </label>
          <label>Entregue em
            <input type="date" defaultValue={sale.delivered_at ?? ""} disabled={saving}
              onBlur={(e) => e.target.value && updateField({ delivered_at: e.target.value })} />
          </label>
        </div>
      </fieldset>

      <fieldset className="form-section">
        <legend>Instalação no cliente</legend>
        <div className="form-grid">
          <label>Status da instalação
            <select value={sale.installation_status} disabled={saving} onChange={(e) => updateField({ installation_status: e.target.value })}>
              {Object.entries(INSTALL_STATUS_LABEL).map(([k, v]) => <option key={k} value={k}>{v}</option>)}
            </select>
          </label>
          <label>Agendada para
            <input type="date" defaultValue={sale.installation_scheduled_at ?? ""} disabled={saving}
              onBlur={(e) => e.target.value && updateField({ installation_scheduled_at: e.target.value })} />
          </label>
          <label>Concluída em
            <input type="date" defaultValue={sale.installation_completed_at ?? ""} disabled={saving}
              onBlur={(e) => e.target.value && updateField({ installation_completed_at: e.target.value })} />
          </label>
        </div>
        <label>Observações da instalação
          <textarea rows={2} defaultValue={sale.installation_notes ?? ""} disabled={saving}
            onBlur={(e) => updateField({ installation_notes: e.target.value })} />
        </label>
      </fieldset>

      <div className="section-header">
        <strong>Faturamento ({sale.invoices.length})</strong>
        {!showInvoiceForm && (
          <button type="button" className="secondary-button" onClick={() => setShowInvoiceForm(true)}>
            <Plus size={14} /> Nova fatura
          </button>
        )}
      </div>
      {showInvoiceForm && (
        <InvoiceForm saleId={sale.id} onSave={() => { setShowInvoiceForm(false); onChanged(); }} onCancel={() => setShowInvoiceForm(false)} />
      )}
      {sale.invoices.length === 0 && !showInvoiceForm && <p className="empty-hint">Nenhuma fatura emitida ainda.</p>}
      {sale.invoices.map((inv) => <InvoiceCard key={inv.id} invoice={inv} onChanged={onChanged} />)}
    </>
  );
}

// ---- Main Component ----

export function SaleManager() {
  const [sales, setSales] = useState<SaleSummary[]>([]);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(1);
  const [search, setSearch] = useState("");
  const [statusFilter, setStatusFilter] = useState("");
  const [loading, setLoading] = useState(true);

  const [selectedSale, setSelectedSale] = useState<SaleDetail | null>(null);

  useEffect(() => { refresh(1, "", ""); }, []);

  async function refresh(p = page, s = search, st = statusFilter) {
    setLoading(true);
    const data = await listSalesAction({ page: p, search: s || undefined, status: st || undefined });
    setSales(data.items);
    setTotal(data.total);
    setLoading(false);
  }

  async function openDetail(id: number) {
    setSelectedSale(await getSaleAction(id));
  }

  async function refreshDetail() {
    if (!selectedSale) return;
    setSelectedSale(await getSaleAction(selectedSale.id));
    await refresh();
  }

  const pageSize = 20;
  const pages = Math.ceil(total / pageSize);

  return (
    <>
      <header className="module-heading">
        <div>
          <p className="eyebrow">Comercial</p>
          <h1>Vendas</h1>
          <p>Entrega, instalação, faturamento e cobrança das vendas confirmadas.</p>
        </div>
      </header>

      <section className="module-panel">
        <div className="module-toolbar">
          <label>
            <Search size={18} />
            <input
              placeholder="Buscar pelo número da venda..."
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              onKeyDown={(e) => { if (e.key === "Enter") { setPage(1); refresh(1, search, statusFilter); } }}
            />
          </label>
          <select value={statusFilter} onChange={(e) => { setStatusFilter(e.target.value); setPage(1); refresh(1, search, e.target.value); }}>
            <option value="">Todos os status</option>
            {Object.entries(SALE_STATUS_LABEL).map(([k, v]) => <option key={k} value={k}>{v}</option>)}
          </select>
        </div>

        {!loading && sales.length === 0 ? (
          <div className="module-state">
            <ShoppingCart />
            <strong>Nenhuma venda encontrada</strong>
            <span>Vendas são criadas automaticamente quando um orçamento é aceito pelo cliente.</span>
          </div>
        ) : (
          <div className="module-table-wrap">
            <table>
              <thead>
                <tr><th>Número</th><th>Cliente</th><th>Total</th><th>Instalação</th><th>Faturado</th><th>Recebido</th><th>Status</th></tr>
              </thead>
              <tbody>
                {sales.map((s) => (
                  <tr key={s.id} onClick={() => openDetail(s.id)}>
                    <td>{s.number ?? "—"}</td>
                    <td>{s.customer_name ?? "—"}</td>
                    <td>{formatCurrency(s.total_value)}</td>
                    <td><span className={`status ${INSTALL_STATUS_CLASS[s.installation_status] ?? "status-neutral"}`}>{INSTALL_STATUS_LABEL[s.installation_status] ?? s.installation_status}</span></td>
                    <td>{formatCurrency(s.invoiced_total)}</td>
                    <td>{formatCurrency(s.received_total)}</td>
                    <td><span className={`status ${SALE_STATUS_CLASS[s.status] ?? "status-neutral"}`}>{SALE_STATUS_LABEL[s.status] ?? s.status}</span></td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}

        <footer className="module-pagination">
          <span>{total} venda{total !== 1 ? "s" : ""}</span>
          {pages > 1 && (
            <div>
              <button disabled={page <= 1} onClick={() => { const p = page - 1; setPage(p); refresh(p); }}><ChevronLeft size={16} /></button>
              <span>{page} / {pages}</span>
              <button disabled={page >= pages} onClick={() => { const p = page + 1; setPage(p); refresh(p); }}><ChevronRight size={16} /></button>
            </div>
          )}
        </footer>
      </section>

      {selectedSale && (
        <div className="modal-layer" role="presentation" onClick={() => setSelectedSale(null)}>
          <section className="record-modal has-timeline" role="dialog" aria-modal="true" style={{ maxWidth: 760 }} onClick={(e) => e.stopPropagation()}>
            <header>
              <div><span>{selectedSale.number ?? `#${selectedSale.id}`}</span><h2>{selectedSale.customer_name}</h2></div>
              <button className="icon-button" onClick={() => setSelectedSale(null)}><X /></button>
            </header>
            <form onSubmit={(e) => e.preventDefault()}>
              <SaleDetailPanel sale={selectedSale} onChanged={refreshDetail} />
            </form>
          </section>
        </div>
      )}

      <style>{`
        .customer-badges { display: flex; gap: var(--sp-2); flex-wrap: wrap; margin-bottom: var(--sp-3); }
        .cell-sub { font-size: var(--font-xs); color: var(--muted); }
        .section-header { display: flex; align-items: center; justify-content: space-between; margin-top: var(--sp-3); }
        .empty-hint { color: var(--muted); font-size: var(--font-sm); text-align: center; padding: var(--sp-4) 0; }
        .record-modal.has-timeline label > span { font-size: var(--font-base); font-weight: 400; color: var(--ink); }

        .invoice-card { border: 1px solid var(--line); border-radius: var(--radius-lg); padding: var(--sp-3); margin-bottom: var(--sp-3); }
        .invoice-card-head { display: flex; align-items: center; justify-content: space-between; margin-bottom: var(--sp-2); }
        .invoice-card-amounts { display: flex; gap: var(--sp-3); flex-wrap: wrap; font-size: var(--font-sm); margin-bottom: var(--sp-2); }
        .invoice-payments { border-top: 1px dashed var(--line); padding-top: var(--sp-2); margin-bottom: var(--sp-2); display: flex; flex-direction: column; gap: 2px; }
      `}</style>
    </>
  );
}
