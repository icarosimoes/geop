"use client";

import { ChevronLeft, ChevronRight, Search, Plus, X, Trash2, Send, Ban, Copy, Check, FileText, ShieldCheck } from "lucide-react";
import { useEffect, useRef, useState } from "react";
import type { CustomerOption } from "@/app/cadastros/clientes/actions";
import { listCustomerOptionsAction } from "@/app/cadastros/clientes/actions";
import type { QuoteDetail, QuoteItem, QuoteSummary } from "./actions";
import {
  cancelQuoteAction, createQuoteAction, deleteQuoteAction, getQuoteAction,
  listQuotesAction, sendQuoteAction, startIcpSignatureAction, updateQuoteAction,
} from "./actions";

const SIGNATURE_METHOD_LABEL: Record<string, string> = {
  simples: "Assinatura eletrônica simples",
  icp_brasil: "Certificado digital ICP-Brasil",
};

function formatCurrency(value: string | null): string {
  if (value == null) return "—";
  return new Intl.NumberFormat("pt-BR", { style: "currency", currency: "BRL" }).format(Number(value));
}

const STATUS_LABEL: Record<string, string> = {
  rascunho: "Rascunho", enviado: "Enviado", aceito: "Aceito",
  recusado: "Recusado", expirado: "Expirado", cancelado: "Cancelado",
};
const STATUS_CLASS: Record<string, string> = {
  rascunho: "status-neutral", enviado: "status-waiting", aceito: "status-done",
  recusado: "status-danger", expirado: "status-danger", cancelado: "status-neutral",
};

type DraftItem = {
  item_type: "produto" | "servico";
  description: string;
  unit: string;
  quantity: string;
  unit_price: string;
  discount_percent: string;
};

function emptyDraftItem(): DraftItem {
  return { item_type: "produto", description: "", unit: "un", quantity: "1", unit_price: "0", discount_percent: "" };
}

function computeLineTotal(item: DraftItem): number {
  const qty = Number(item.quantity) || 0;
  const price = Number(item.unit_price) || 0;
  const discount = Number(item.discount_percent) || 0;
  const gross = qty * price;
  return gross - gross * (discount / 100);
}

// ---- Create/Edit Form ----

function QuoteForm({
  initial, customers, onSave, onCancel,
}: {
  initial?: QuoteDetail | null;
  customers: CustomerOption[];
  onSave: (data: Record<string, unknown>) => Promise<void>;
  onCancel: () => void;
}) {
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const formRef = useRef<HTMLFormElement>(null);
  const [items, setItems] = useState<DraftItem[]>(() =>
    initial?.items.length
      ? initial.items.map((i) => ({
          item_type: i.item_type, description: i.description, unit: i.unit,
          quantity: i.quantity, unit_price: i.unit_price, discount_percent: i.discount_percent ?? "",
        }))
      : [emptyDraftItem()]
  );

  const subtotal = items.reduce((sum, i) => sum + computeLineTotal(i), 0);

  function updateItem(idx: number, patch: Partial<DraftItem>) {
    setItems((prev) => prev.map((it, i) => (i === idx ? { ...it, ...patch } : it)));
  }

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    const fd = new FormData(formRef.current!);
    const raw: Record<string, unknown> = {};
    for (const [k, v] of fd.entries()) { if (v !== "" && k !== "items") raw[k] = v; }
    raw.customer_id = Number(raw.customer_id);
    if (raw.discount_amount == null) raw.discount_amount = "0";

    const validItems = items.filter((i) => i.description.trim());
    raw.items = validItems.map((i) => ({
      item_type: i.item_type,
      description: i.description,
      unit: i.unit || "un",
      quantity: i.quantity || "1",
      unit_price: i.unit_price || "0",
      ...(i.discount_percent ? { discount_percent: i.discount_percent } : {}),
    }));

    setLoading(true);
    setError("");
    try { await onSave(raw); }
    catch (err) { setError(err instanceof Error ? err.message : "Erro ao salvar."); }
    finally { setLoading(false); }
  }

  return (
    <form ref={formRef} onSubmit={handleSubmit}>
      {error && <div className="kanban-form-error">{error}</div>}

      <div className="form-grid">
        <label>Cliente *
          <select name="customer_id" required defaultValue={initial?.customer_id ?? ""}>
            <option value="">— Selecione —</option>
            {customers.map((c) => <option key={c.id} value={c.id}>{c.name}</option>)}
          </select>
        </label>
        <label>Validade até<input type="date" name="valid_until" defaultValue={initial?.valid_until ?? ""} /></label>
      </div>

      <label>Título *<input name="title" required defaultValue={initial?.title ?? ""} placeholder="Ex: Instalação de ar-condicionado — Suíte 302" /></label>

      <div className="form-grid">
        <label>Responsável (user id)<input name="responsible_user_id" type="number" defaultValue={initial?.responsible_user_id ?? ""} /></label>
        <label>Desconto (R$)<input name="discount_amount" type="number" step="0.01" min="0" defaultValue={initial?.discount_amount ?? "0"} /></label>
      </div>

      <label>Descrição<textarea name="description" rows={2} defaultValue={initial?.description ?? ""} /></label>
      <label>Condições (pagamento/prazo/garantia)<textarea name="conditions" rows={2} defaultValue={initial?.conditions ?? ""} /></label>
      <label>Observações internas<textarea name="notes" rows={2} defaultValue={initial?.notes ?? ""} /></label>

      <fieldset className="form-section">
        <legend>Itens</legend>
        <div className="quote-items-table">
          <div className="quote-items-head">
            <span>Tipo</span><span>Descrição</span><span>Un.</span><span>Qtd</span><span>Preço</span><span>Desc. %</span><span>Total</span><span></span>
          </div>
          {items.map((item, idx) => (
            <div className="quote-items-row" key={idx}>
              <select value={item.item_type} onChange={(e) => updateItem(idx, { item_type: e.target.value as DraftItem["item_type"] })}>
                <option value="produto">Produto</option>
                <option value="servico">Serviço</option>
              </select>
              <input value={item.description} onChange={(e) => updateItem(idx, { description: e.target.value })} placeholder="Descrição do item" />
              <input value={item.unit} onChange={(e) => updateItem(idx, { unit: e.target.value })} />
              <input type="number" step="0.001" min="0" value={item.quantity} onChange={(e) => updateItem(idx, { quantity: e.target.value })} />
              <input type="number" step="0.01" min="0" value={item.unit_price} onChange={(e) => updateItem(idx, { unit_price: e.target.value })} />
              <input type="number" step="0.01" min="0" max="100" value={item.discount_percent} onChange={(e) => updateItem(idx, { discount_percent: e.target.value })} />
              <span className="quote-items-total">{formatCurrency(String(computeLineTotal(item)))}</span>
              <button type="button" className="icon-button" onClick={() => setItems((prev) => prev.filter((_, i) => i !== idx))} disabled={items.length === 1}>
                <Trash2 size={14} />
              </button>
            </div>
          ))}
        </div>
        <button type="button" className="secondary-button" onClick={() => setItems((prev) => [...prev, emptyDraftItem()])}>
          <Plus size={14} /> Adicionar item
        </button>
        <div className="quote-subtotal">Subtotal: <strong>{formatCurrency(String(subtotal))}</strong></div>
      </fieldset>

      <footer>
        <button type="button" onClick={onCancel}>Cancelar</button>
        <button type="submit" disabled={loading}>{loading ? "Salvando…" : initial ? "Salvar" : "Criar orçamento"}</button>
      </footer>
    </form>
  );
}

// ---- Main Component ----

export function QuoteManager() {
  const [quotes, setQuotes] = useState<QuoteSummary[]>([]);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(1);
  const [search, setSearch] = useState("");
  const [statusFilter, setStatusFilter] = useState("");
  const [loading, setLoading] = useState(true);
  const [customers, setCustomers] = useState<CustomerOption[]>([]);

  const [selectedQuote, setSelectedQuote] = useState<QuoteDetail | null>(null);
  const [modalMode, setModalMode] = useState<"none" | "form" | "detail">("none");
  const [copied, setCopied] = useState(false);
  const [icpSignUrl, setIcpSignUrl] = useState<string | null>(null);
  const [icpLoading, setIcpLoading] = useState(false);
  const [icpError, setIcpError] = useState("");

  useEffect(() => {
    refresh(1, "", "");
    listCustomerOptionsAction().then(setCustomers);
  }, []);

  async function refresh(p = page, s = search, st = statusFilter) {
    setLoading(true);
    const data = await listQuotesAction({ page: p, search: s || undefined, status: st || undefined });
    setQuotes(data.items);
    setTotal(data.total);
    setLoading(false);
  }

  async function openDetail(id: number) {
    const detail = await getQuoteAction(id);
    setSelectedQuote(detail);
    setModalMode("detail");
    setCopied(false);
    setIcpSignUrl(null);
    setIcpError("");
  }

  function closeModal() {
    setModalMode("none");
    setSelectedQuote(null);
  }

  async function handleCreate(data: Record<string, unknown>) {
    const res = await createQuoteAction(data);
    if (!res.ok) throw new Error(res.error);
    closeModal();
    await refresh();
  }

  async function handleUpdate(data: Record<string, unknown>) {
    if (!selectedQuote) return;
    const res = await updateQuoteAction(selectedQuote.id, data);
    if (!res.ok) throw new Error(res.error);
    await openDetail(selectedQuote.id);
    await refresh();
  }

  async function handleSend(id: number) {
    const res = await sendQuoteAction(id);
    if (!res.ok) { alert(res.error ?? "Erro ao enviar."); return; }
    await openDetail(id);
    await refresh();
  }

  async function handleCancel(id: number) {
    if (!confirm("Cancelar este orçamento?")) return;
    const res = await cancelQuoteAction(id);
    if (!res.ok) { alert(res.error ?? "Erro ao cancelar."); return; }
    await openDetail(id);
    await refresh();
  }

  async function handleDelete(id: number) {
    if (!confirm("Excluir este orçamento?")) return;
    const res = await deleteQuoteAction(id);
    if (!res.ok) { alert(res.error ?? "Erro ao excluir."); return; }
    closeModal();
    await refresh();
  }

  async function handleStartIcp(id: number) {
    setIcpLoading(true);
    setIcpError("");
    const res = await startIcpSignatureAction(id);
    setIcpLoading(false);
    if (!res.ok || !res.sign_url) { setIcpError(res.error ?? "Erro ao solicitar assinatura ICP-Brasil."); return; }
    await openDetail(id);
    setIcpSignUrl(res.sign_url);
  }

  function copyLink(url: string) {
    navigator.clipboard.writeText(url).then(() => {
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    });
  }

  const pageSize = 20;
  const pages = Math.ceil(total / pageSize);

  return (
    <>
      <header className="module-heading">
        <div>
          <p className="eyebrow">Comercial</p>
          <h1>Orçamentos</h1>
          <p>Acompanhe orçamentos enviados a clientes até o aceite (link público, sem login).</p>
        </div>
        <button className="primary-button" onClick={() => { setSelectedQuote(null); setModalMode("form"); }}>
          <Plus size={18} /> Novo orçamento
        </button>
      </header>

      <section className="module-panel">
        <div className="module-toolbar">
          <label>
            <Search size={18} />
            <input
              placeholder="Buscar orçamento..."
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              onKeyDown={(e) => { if (e.key === "Enter") { setPage(1); refresh(1, search, statusFilter); } }}
            />
          </label>
          <select value={statusFilter} onChange={(e) => { setStatusFilter(e.target.value); setPage(1); refresh(1, search, e.target.value); }}>
            <option value="">Todos os status</option>
            {Object.entries(STATUS_LABEL).map(([k, v]) => <option key={k} value={k}>{v}</option>)}
          </select>
        </div>

        {!loading && quotes.length === 0 ? (
          <div className="module-state">
            <FileText />
            <strong>Nenhum orçamento encontrado</strong>
            <span>Ajuste os filtros ou crie um novo orçamento.</span>
          </div>
        ) : (
          <div className="module-table-wrap">
            <table>
              <thead>
                <tr>
                  <th>Número</th><th>Cliente</th><th>Título</th><th>Total</th><th>Validade</th><th>Status</th>
                </tr>
              </thead>
              <tbody>
                {quotes.map((q) => (
                  <tr key={q.id} onClick={() => openDetail(q.id)}>
                    <td>{q.number ?? "—"}</td>
                    <td>{q.customer_name ?? "—"}</td>
                    <td>{q.title}</td>
                    <td>{formatCurrency(q.total)}</td>
                    <td>{q.valid_until ?? "—"}</td>
                    <td><span className={`status ${STATUS_CLASS[q.status] ?? "status-neutral"}`}>{STATUS_LABEL[q.status] ?? q.status}</span></td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}

        <footer className="module-pagination">
          <span>{total} orçamento{total !== 1 ? "s" : ""}</span>
          {pages > 1 && (
            <div>
              <button disabled={page <= 1} onClick={() => { const p = page - 1; setPage(p); refresh(p); }}><ChevronLeft size={16} /></button>
              <span>{page} / {pages}</span>
              <button disabled={page >= pages} onClick={() => { const p = page + 1; setPage(p); refresh(p); }}><ChevronRight size={16} /></button>
            </div>
          )}
        </footer>
      </section>

      {modalMode === "form" && (
        <div className="modal-layer" role="presentation" onClick={closeModal}>
          <section className="record-modal quote-form-modal" role="dialog" aria-modal="true" onClick={(e) => e.stopPropagation()}>
            <header>
              <div><span>Comercial</span><h2>{selectedQuote ? "Editar orçamento" : "Novo orçamento"}</h2></div>
              <button className="icon-button" onClick={closeModal}><X /></button>
            </header>
            <div className="quote-modal-scroll">
              <QuoteForm
                initial={selectedQuote}
                customers={customers}
                onSave={selectedQuote ? handleUpdate : handleCreate}
                onCancel={closeModal}
              />
            </div>
          </section>
        </div>
      )}

      {modalMode === "detail" && selectedQuote && (
        <div className="modal-layer" role="presentation" onClick={closeModal}>
          <section className="record-modal has-timeline" role="dialog" aria-modal="true" style={{ maxWidth: 760 }} onClick={(e) => e.stopPropagation()}>
            <header>
              <div><span>{selectedQuote.number ?? `#${selectedQuote.id}`}</span><h2>{selectedQuote.title}</h2></div>
              <button className="icon-button" onClick={closeModal}><X /></button>
            </header>

            <form onSubmit={(e) => e.preventDefault()}>
              <div className="customer-badges">
                <span className={`status ${STATUS_CLASS[selectedQuote.status] ?? "status-neutral"}`}>{STATUS_LABEL[selectedQuote.status] ?? selectedQuote.status}</span>
              </div>

              <div className="quote-actions">
                {selectedQuote.status === "rascunho" && (
                  <>
                    <button type="button" className="secondary-button" onClick={() => setModalMode("form")}>Editar</button>
                    <button type="button" className="secondary-button" onClick={() => handleSend(selectedQuote.id)}><Send size={14} /> Enviar</button>
                    <button type="button" className="secondary-button" style={{ color: "var(--red)" }} onClick={() => handleDelete(selectedQuote.id)}><Trash2 size={14} /> Excluir</button>
                  </>
                )}
                {selectedQuote.status === "enviado" && (
                  <>
                    <button type="button" className="secondary-button" onClick={() => handleCancel(selectedQuote.id)}><Ban size={14} /> Cancelar envio</button>
                    <button type="button" className="secondary-button" disabled={icpLoading} onClick={() => handleStartIcp(selectedQuote.id)}>
                      <ShieldCheck size={14} /> {icpLoading ? "Solicitando…" : "Solicitar assinatura ICP-Brasil"}
                    </button>
                  </>
                )}
                <a className="secondary-button" href={`/api/commercial/quotes/${selectedQuote.id}/pdf`} target="_blank" rel="noopener noreferrer">
                  <FileText size={14} /> Exportar PDF
                </a>
              </div>

              {icpError && <div className="kanban-form-error">{icpError}</div>}

              {selectedQuote.signature_method && (
                <p className="cell-sub">
                  Assinatura: {SIGNATURE_METHOD_LABEL[selectedQuote.signature_method] ?? selectedQuote.signature_method}
                  {" — "}{selectedQuote.signature_status === "assinado" ? "concluída" : "pendente"}
                  {selectedQuote.signature_signed_at ? ` em ${selectedQuote.signature_signed_at}` : ""}
                </p>
              )}

              {selectedQuote.acceptance_url && (
                <div className="quote-link-box">
                  <span>Link de aceite (envie ao cliente):</span>
                  <div className="quote-link-copy">
                    <input readOnly value={selectedQuote.acceptance_url} onClick={(e) => (e.target as HTMLInputElement).select()} />
                    <button type="button" className="icon-button" onClick={() => copyLink(selectedQuote.acceptance_url!)}>
                      {copied ? <Check size={14} /> : <Copy size={14} />}
                    </button>
                  </div>
                </div>
              )}

              {icpSignUrl && (
                <div className="quote-link-box">
                  <span>Link de assinatura ICP-Brasil (envie ao cliente):</span>
                  <div className="quote-link-copy">
                    <input readOnly value={icpSignUrl} onClick={(e) => (e.target as HTMLInputElement).select()} />
                    <button type="button" className="icon-button" onClick={() => copyLink(icpSignUrl)}>
                      {copied ? <Check size={14} /> : <Copy size={14} />}
                    </button>
                  </div>
                </div>
              )}

              {selectedQuote.decision_note && (
                <p className="empty-hint" style={{ textAlign: "left" }}>Motivo informado pelo cliente: {selectedQuote.decision_note}</p>
              )}

              <div className="form-grid">
                <label>Cliente<span>{selectedQuote.customer_name ?? "—"}</span></label>
                <label>Responsável<span>{selectedQuote.responsible_name ?? "—"}</span></label>
                <label>Enviado em<span>{selectedQuote.issued_at ?? "—"}</span></label>
                <label>Validade<span>{selectedQuote.valid_until ?? "—"}</span></label>
              </div>

              <div className="module-table-wrap">
                <table>
                  <thead><tr><th>Item</th><th>Qtd</th><th>Preço</th><th>Total</th></tr></thead>
                  <tbody>
                    {selectedQuote.items.map((i: QuoteItem) => (
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
                <div>Subtotal <strong>{formatCurrency(selectedQuote.subtotal)}</strong></div>
                <div>Desconto <strong>-{formatCurrency(selectedQuote.discount_amount)}</strong></div>
                <div className="quote-total-final">Total <strong>{formatCurrency(selectedQuote.total)}</strong></div>
              </div>

              {selectedQuote.conditions && <label style={{ gridColumn: "1 / -1" }}>Condições<span style={{ whiteSpace: "pre-wrap", fontWeight: 400 }}>{selectedQuote.conditions}</span></label>}
              {selectedQuote.notes && <label style={{ gridColumn: "1 / -1" }}>Observações<span style={{ whiteSpace: "pre-wrap", fontWeight: 400 }}>{selectedQuote.notes}</span></label>}
            </form>
          </section>
        </div>
      )}

      <style>{`
        .customer-badges { display: flex; gap: var(--sp-2); flex-wrap: wrap; }
        .quote-actions { display: flex; gap: var(--sp-2); flex-wrap: wrap; margin-bottom: var(--sp-3); }
        .cell-sub { font-size: var(--font-xs); color: var(--muted); }
        .record-modal.has-timeline label > span { font-size: var(--font-base); font-weight: 400; color: var(--ink); }
        .record-modal.quote-form-modal { width: min(920px, 96vw); display: flex; flex-direction: column; overflow: hidden; }
        .quote-modal-scroll { overflow-y: auto; border-radius: 0 0 var(--radius-xl) var(--radius-xl); }

        .quote-items-table { display: flex; flex-direction: column; gap: var(--sp-2); margin-bottom: var(--sp-2); }
        .quote-items-head, .quote-items-row {
          display: grid;
          grid-template-columns: 110px 2fr 70px 80px 100px 90px 100px 32px;
          gap: var(--sp-2);
          align-items: center;
        }
        .quote-items-head { font-size: var(--font-xs); color: var(--muted); font-weight: 600; }
        .quote-items-row input, .quote-items-row select { min-height: 36px; padding: 4px 8px; }
        .quote-items-total { font-size: var(--font-sm); font-weight: 600; text-align: right; }
        .quote-subtotal { text-align: right; margin-top: var(--sp-2); font-size: var(--font-sm); }
        @media (max-width: 900px) {
          .quote-items-head { display: none; }
          .quote-items-row { grid-template-columns: 1fr 1fr; grid-auto-rows: auto; }
        }

        .quote-link-box { background: #f2f4f7; border-radius: var(--radius-lg); padding: var(--sp-3); margin-bottom: var(--sp-3); }
        .quote-link-box > span { display: block; font-size: var(--font-xs); color: var(--muted); margin-bottom: var(--sp-2); }
        .quote-link-copy { display: flex; gap: var(--sp-2); }
        .quote-link-copy input { flex: 1; font-size: var(--font-xs); }

        .quote-totals { display: flex; flex-direction: column; align-items: flex-end; gap: 4px; margin: var(--sp-3) 0; font-size: var(--font-sm); }
        .quote-totals > div { display: flex; gap: var(--sp-3); }
        .quote-total-final { font-size: var(--font-base); border-top: 1px solid var(--line); padding-top: 4px; margin-top: 4px; }
      `}</style>
    </>
  );
}
