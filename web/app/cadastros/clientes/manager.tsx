"use client";

import { ChevronLeft, ChevronRight, Phone, Mail, Plus, Search, Trash2, X, Edit2, Users, Loader2 } from "lucide-react";
import { useEffect, useRef, useState } from "react";
import type { CustomerDetail, CustomerSummary } from "./actions";
import { createCustomerAction, deleteCustomerAction, getCustomerAction, listCustomersAction, updateCustomerAction } from "./actions";
import { useCepLookup, useCnpjLookup } from "@/lib/use-document-lookup";
import { formatCEP, formatCNPJ, formatCPF, onlyDigits } from "@/lib/validators";

// ---- Customer Form ----

function CustomerForm({
  initial, onSave, onCancel,
}: {
  initial?: CustomerDetail | null;
  onSave: (data: Record<string, unknown>) => Promise<void>;
  onCancel: () => void;
}) {
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const formRef = useRef<HTMLFormElement>(null);

  const [form, setForm] = useState(() => ({
    name: initial?.name ?? "",
    document_type: initial?.document_type ?? "",
    document: initial?.document ?? "",
    email: initial?.email ?? "",
    phone: initial?.phone ?? "",
    whatsapp: initial?.whatsapp ?? "",
    address_zip: initial?.address_zip ?? "",
    address_street: initial?.address_street ?? "",
    address_number: initial?.address_number ?? "",
    address_complement: initial?.address_complement ?? "",
    address_neighborhood: initial?.address_neighborhood ?? "",
    address_city: initial?.address_city ?? "",
    address_state: initial?.address_state ?? "",
  }));

  function setField<K extends keyof typeof form>(key: K, value: string) {
    setForm((prev) => ({ ...prev, [key]: value }));
  }

  const cep = useCepLookup((fields) => {
    setForm((prev) => ({
      ...prev,
      address_street: fields.address_street ?? prev.address_street,
      address_neighborhood: fields.address_neighborhood ?? prev.address_neighborhood,
      address_city: fields.address_city ?? prev.address_city,
      address_state: fields.address_state ?? prev.address_state,
    }));
  });

  const cnpj = useCnpjLookup((fields) => {
    setForm((prev) => ({
      ...prev,
      name: fields.name || prev.name,
      email: prev.email || fields.email || prev.email,
      phone: prev.phone || fields.phone || prev.phone,
      document_type: "cnpj",
      address_street: fields.address_street ?? prev.address_street,
      address_number: fields.address_number ?? prev.address_number,
      address_complement: fields.address_complement ?? prev.address_complement,
      address_neighborhood: fields.address_neighborhood ?? prev.address_neighborhood,
      address_city: fields.address_city ?? prev.address_city,
      address_state: fields.address_state ?? prev.address_state,
      address_zip: fields.address_zip ?? prev.address_zip,
    }));
  });

  function handleDocumentChange(value: string) {
    const digits = onlyDigits(value);
    const formatted = digits.length > 11 ? formatCNPJ(value) : formatCPF(value);
    setField("document", formatted);
  }

  function handleDocumentBlur(value: string) {
    const digits = onlyDigits(value);
    if (digits.length === 14) { setField("document_type", "cnpj"); cnpj.handleBlur(value); }
    else if (digits.length === 11) { setField("document_type", "cpf"); }
  }

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    const fd = new FormData(formRef.current!);
    const raw: Record<string, unknown> = {};
    for (const [k, v] of fd.entries()) { if (v !== "") raw[k] = v; }
    setLoading(true);
    setError("");
    try { await onSave(raw); }
    catch (err) { setError(err instanceof Error ? err.message : "Erro ao salvar."); }
    finally { setLoading(false); }
  }

  return (
    <form ref={formRef} onSubmit={handleSubmit}>
      {error && <div className="kanban-form-error">{error}</div>}

      <div className="form-grid customer-doc-row">
        <label>Tipo de documento
          <select name="document_type" value={form.document_type} onChange={(e) => setField("document_type", e.target.value)}>
            <option value="">— Selecione —</option>
            <option value="cnpj">CNPJ</option>
            <option value="cpf">CPF</option>
          </select>
        </label>
        <label>CPF/CNPJ
          <span className="field-with-status">
            <input
              name="document"
              value={form.document}
              onChange={(e) => handleDocumentChange(e.target.value)}
              onBlur={(e) => handleDocumentBlur(e.target.value)}
              placeholder="00.000.000/0000-00"
            />
            {cnpj.loading && <Loader2 size={16} className="field-spinner" />}
          </span>
          {cnpj.notFound && <small className="field-error-hint">CNPJ não encontrado.</small>}
        </label>
      </div>

      <label>Nome / Razão social *
        <input name="name" required value={form.name} onChange={(e) => setField("name", e.target.value)} />
      </label>

      <div className="form-grid">
        <label>E-mail<input type="email" name="email" value={form.email} onChange={(e) => setField("email", e.target.value)} /></label>
        <label>Telefone<input name="phone" value={form.phone} onChange={(e) => setField("phone", e.target.value)} /></label>
      </div>
      <label>WhatsApp<input name="whatsapp" value={form.whatsapp} onChange={(e) => setField("whatsapp", e.target.value)} /></label>

      <fieldset className="form-section">
        <legend>Endereço de entrega/instalação</legend>
        <div className="form-grid customer-cep-row">
          <label>CEP
            <span className="field-with-status">
              <input
                name="address_zip"
                value={form.address_zip}
                onChange={(e) => setField("address_zip", formatCEP(e.target.value))}
                onBlur={(e) => cep.handleBlur(e.target.value)}
                placeholder="00000-000"
              />
              {cep.loading && <Loader2 size={16} className="field-spinner" />}
            </span>
            {cep.notFound && <small className="field-error-hint">CEP não encontrado.</small>}
          </label>
          <label>Logradouro<input name="address_street" value={form.address_street} onChange={(e) => setField("address_street", e.target.value)} /></label>
        </div>
        <div className="form-grid customer-address-row">
          <label>Número<input name="address_number" value={form.address_number} onChange={(e) => setField("address_number", e.target.value)} /></label>
          <label>Complemento<input name="address_complement" value={form.address_complement} onChange={(e) => setField("address_complement", e.target.value)} /></label>
          <label>Bairro<input name="address_neighborhood" value={form.address_neighborhood} onChange={(e) => setField("address_neighborhood", e.target.value)} /></label>
        </div>
        <div className="form-grid customer-city-row">
          <label>Cidade<input name="address_city" value={form.address_city} onChange={(e) => setField("address_city", e.target.value)} /></label>
          <label>UF<input name="address_state" maxLength={2} value={form.address_state} onChange={(e) => setField("address_state", e.target.value.toUpperCase())} placeholder="SP" /></label>
        </div>
      </fieldset>

      <label>Observações<textarea name="notes" rows={2} defaultValue={initial?.notes ?? ""} /></label>

      <footer>
        <button type="button" onClick={onCancel}>Cancelar</button>
        <button type="submit" disabled={loading}>{loading ? "Salvando…" : initial ? "Salvar" : "Criar cliente"}</button>
      </footer>
    </form>
  );
}

// ---- Main Component ----

export function CustomerManager() {
  const [customers, setCustomers] = useState<CustomerSummary[]>([]);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(1);
  const [search, setSearch] = useState("");
  const [loading, setLoading] = useState(true);

  const [selectedCustomer, setSelectedCustomer] = useState<CustomerDetail | null>(null);
  const [modalMode, setModalMode] = useState<"none" | "form" | "detail">("none");

  useEffect(() => {
    refreshCustomers(1, "");
  }, []);

  async function refreshCustomers(p = page, s = search) {
    setLoading(true);
    const data = await listCustomersAction({ page: p, search: s || undefined });
    setCustomers(data.items);
    setTotal(data.total);
    setLoading(false);
  }

  async function openCustomerDetail(id: number) {
    const detail = await getCustomerAction(id);
    setSelectedCustomer(detail);
    setModalMode("detail");
  }

  function closeModal() {
    setModalMode("none");
    setSelectedCustomer(null);
  }

  async function handleCreateCustomer(data: Record<string, unknown>) {
    const res = await createCustomerAction(data);
    if (!res.ok) throw new Error(res.error);
    closeModal();
    await refreshCustomers();
  }

  async function handleUpdateCustomer(data: Record<string, unknown>) {
    if (!selectedCustomer) return;
    const res = await updateCustomerAction(selectedCustomer.id, data);
    if (!res.ok) throw new Error(res.error);
    const updated = await getCustomerAction(selectedCustomer.id);
    setSelectedCustomer(updated);
    setModalMode("detail");
    await refreshCustomers();
  }

  async function handleDeleteCustomer(id: number) {
    if (!confirm("Excluir este cliente?")) return;
    await deleteCustomerAction(id);
    closeModal();
    await refreshCustomers();
  }

  const pageSize = 20;
  const pages = Math.ceil(total / pageSize);

  return (
    <>
      <header className="module-heading">
        <div>
          <p className="eyebrow">Cadastros</p>
          <h1>Clientes</h1>
          <p>Cadastro de clientes usados nos orçamentos e vendas.</p>
        </div>
        <button className="primary-button" onClick={() => { setSelectedCustomer(null); setModalMode("form"); }}>
          <Plus size={18} /> Novo cliente
        </button>
      </header>

      <section className="module-panel">
        <div className="module-toolbar">
          <label>
            <Search size={18} />
            <input
              placeholder="Buscar cliente..."
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              onKeyDown={(e) => {
                if (e.key === "Enter") { setPage(1); refreshCustomers(1, search); }
              }}
            />
          </label>
        </div>

        {!loading && customers.length === 0 ? (
          <div className="module-state">
            <Users />
            <strong>Nenhum cliente encontrado</strong>
            <span>Ajuste a busca ou cadastre um novo cliente.</span>
          </div>
        ) : (
          <div className="module-table-wrap">
            <table>
              <thead>
                <tr>
                  <th>Nome</th>
                  <th>CNPJ/CPF</th>
                  <th>Contato</th>
                  <th>Orçamentos</th>
                  <th>Status</th>
                </tr>
              </thead>
              <tbody>
                {customers.map((c) => (
                  <tr key={c.id} onClick={() => openCustomerDetail(c.id)}>
                    <td><strong>{c.name}</strong></td>
                    <td>{c.document ?? "—"}</td>
                    <td>
                      {c.email && <div className="cell-sub"><Mail size={12} /> {c.email}</div>}
                      {c.phone && <div className="cell-sub"><Phone size={12} /> {c.phone}</div>}
                    </td>
                    <td>{c.quote_count} orçamento{c.quote_count !== 1 ? "s" : ""}</td>
                    <td><span className={`status ${c.active ? "status-done" : "status-neutral"}`}>{c.active ? "Ativo" : "Inativo"}</span></td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}

        <footer className="module-pagination">
          <span>{total} cliente{total !== 1 ? "s" : ""}</span>
          {pages > 1 && (
            <div>
              <button disabled={page <= 1} onClick={() => { const p = page - 1; setPage(p); refreshCustomers(p); }}><ChevronLeft size={16} /></button>
              <span>{page} / {pages}</span>
              <button disabled={page >= pages} onClick={() => { const p = page + 1; setPage(p); refreshCustomers(p); }}><ChevronRight size={16} /></button>
            </div>
          )}
        </footer>
      </section>

      {modalMode === "form" && (
        <div className="modal-layer" role="presentation" onClick={closeModal}>
          <section className="record-modal customer-form-modal" role="dialog" aria-modal="true" onClick={(e) => e.stopPropagation()}>
            <header>
              <div>
                <span>Cadastros</span>
                <h2>{selectedCustomer ? "Editar cliente" : "Novo cliente"}</h2>
              </div>
              <button className="icon-button" onClick={closeModal}><X /></button>
            </header>
            <div className="customer-modal-scroll">
              <CustomerForm
                initial={selectedCustomer}
                onSave={selectedCustomer ? handleUpdateCustomer : handleCreateCustomer}
                onCancel={closeModal}
              />
            </div>
          </section>
        </div>
      )}

      {modalMode === "detail" && selectedCustomer && (
        <div className="modal-layer" role="presentation" onClick={closeModal}>
          <section className="record-modal has-timeline" role="dialog" aria-modal="true" style={{ maxWidth: 680 }} onClick={(e) => e.stopPropagation()}>
            <header>
              <div>
                <span>#{selectedCustomer.id}</span>
                <h2>{selectedCustomer.name}</h2>
              </div>
              <button className="icon-button" onClick={closeModal}><X /></button>
            </header>

            <form onSubmit={(e) => e.preventDefault()}>
              <div className="customer-badges">
                <span className={`status ${selectedCustomer.active ? "status-done" : "status-neutral"}`}>{selectedCustomer.active ? "Ativo" : "Inativo"}</span>
              </div>

              <div className="customer-actions">
                <button type="button" className="secondary-button" onClick={() => setModalMode("form")}>
                  <Edit2 size={14} /> Editar
                </button>
                <button type="button" className="secondary-button" style={{ color: "var(--red)" }} onClick={() => handleDeleteCustomer(selectedCustomer.id)}>
                  <Trash2 size={14} /> Excluir
                </button>
              </div>

              <div className="form-grid">
                {selectedCustomer.document && <label>CNPJ/CPF<span>{selectedCustomer.document}</span></label>}
                {selectedCustomer.email && <label>E-mail<span><a href={`mailto:${selectedCustomer.email}`}>{selectedCustomer.email}</a></span></label>}
                {selectedCustomer.phone && <label>Telefone<span>{selectedCustomer.phone}</span></label>}
                {selectedCustomer.whatsapp && <label>WhatsApp<span>{selectedCustomer.whatsapp}</span></label>}
                {selectedCustomer.address_street && (
                  <label style={{ gridColumn: "1 / -1" }}>Endereço<span>{[selectedCustomer.address_street, selectedCustomer.address_number, selectedCustomer.address_complement, selectedCustomer.address_neighborhood, selectedCustomer.address_city, selectedCustomer.address_state, selectedCustomer.address_zip].filter(Boolean).join(", ")}</span></label>
                )}
                {selectedCustomer.notes && (
                  <label style={{ gridColumn: "1 / -1" }}>Observações<span style={{ whiteSpace: "pre-wrap", fontWeight: 400 }}>{selectedCustomer.notes}</span></label>
                )}
              </div>
            </form>
          </section>
        </div>
      )}

      <style>{`
        .customer-badges { display: flex; gap: var(--sp-2); flex-wrap: wrap; }
        .customer-actions { display: flex; gap: var(--sp-2); flex-wrap: wrap; margin-bottom: var(--sp-3); }
        .cell-sub { font-size: var(--font-xs); color: var(--muted); display: flex; align-items: center; gap: 4px; }
        .record-modal.has-timeline label > span { font-size: var(--font-base); font-weight: 400; color: var(--ink); }

        .record-modal.customer-form-modal {
          width: min(880px, 96vw);
          display: flex;
          flex-direction: column;
          overflow: hidden;
        }
        .customer-modal-scroll {
          overflow-y: auto;
          border-radius: 0 0 var(--radius-xl) var(--radius-xl);
        }
        .customer-doc-row { grid-template-columns: 180px 1fr; }
        .customer-cep-row { grid-template-columns: 200px 1fr; }
        .customer-address-row { grid-template-columns: 1fr 1fr 1fr; }
        .customer-city-row { grid-template-columns: 2fr 100px; }
        @media (max-width: 680px) {
          .customer-doc-row, .customer-cep-row, .customer-address-row, .customer-city-row { grid-template-columns: 1fr; }
        }
      `}</style>
    </>
  );
}
