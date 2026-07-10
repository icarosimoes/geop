"use client";

import {
  ChevronLeft, ChevronRight, Phone, Mail,
  Plus, Search, Trash2, X, Edit2, Star, Users,
} from "lucide-react";
import { useEffect, useRef, useState } from "react";
import type { SupplierContact, SupplierDetail, SupplierSummary } from "./actions";
import {
  createContactAction, createSupplierAction, deleteContactAction, deleteSupplierAction,
  getSupplierAction, listSuppliersAction, updateContactAction, updateSupplierAction,
} from "./actions";

// ---- Supplier Form ----

function SupplierForm({
  initial, onSave, onCancel,
}: {
  initial?: SupplierDetail | null;
  onSave: (data: Record<string, unknown>) => Promise<void>;
  onCancel: () => void;
}) {
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
    try { await onSave(raw); }
    catch (err) { setError(err instanceof Error ? err.message : "Erro ao salvar."); }
    finally { setLoading(false); }
  }

  return (
    <form ref={formRef} onSubmit={handleSubmit}>
      {error && <div className="kanban-form-error">{error}</div>}

      <label>Nome / Razão social *<input name="name" required defaultValue={initial?.name} /></label>

      <div className="form-grid">
        <label>Tipo de documento
          <select name="document_type" defaultValue={initial?.document_type ?? ""}>
            <option value="">— Selecione —</option>
            <option value="cnpj">CNPJ</option>
            <option value="cpf">CPF</option>
          </select>
        </label>
        <label>CPF/CNPJ<input name="document" defaultValue={initial?.document ?? ""} placeholder="00.000.000/0000-00" /></label>
      </div>

      <label>Categoria<input name="category" defaultValue={initial?.category ?? ""} placeholder="Ex: Tecnologia, Limpeza, Segurança..." /></label>

      <div className="form-grid">
        <label>E-mail<input type="email" name="email" defaultValue={initial?.email ?? ""} /></label>
        <label>Telefone<input name="phone" defaultValue={initial?.phone ?? ""} /></label>
      </div>

      <label>Website<input name="website" defaultValue={initial?.website ?? ""} placeholder="https://" /></label>

      <fieldset className="form-section">
        <legend>Endereço</legend>
        <label>Logradouro<input name="address_street" defaultValue={initial?.address_street ?? ""} /></label>
        <div className="form-grid">
          <label>Número<input name="address_number" defaultValue={initial?.address_number ?? ""} /></label>
          <label>Complemento<input name="address_complement" defaultValue={initial?.address_complement ?? ""} /></label>
          <label>Cidade<input name="address_city" defaultValue={initial?.address_city ?? ""} /></label>
          <label>UF<input name="address_state" maxLength={2} defaultValue={initial?.address_state ?? ""} placeholder="SP" /></label>
        </div>
        <label>CEP<input name="address_zip" defaultValue={initial?.address_zip ?? ""} placeholder="00000-000" /></label>
      </fieldset>

      <label>Observações<textarea name="notes" rows={2} defaultValue={initial?.notes ?? ""} /></label>

      <footer>
        <button type="button" onClick={onCancel}>Cancelar</button>
        <button type="submit" disabled={loading}>{loading ? "Salvando…" : initial ? "Salvar" : "Criar fornecedor"}</button>
      </footer>
    </form>
  );
}

// ---- Contact Form ----

function ContactForm({ supplierId, onSave, onCancel }: { supplierId: number; onSave: () => void; onCancel: () => void }) {
  const [loading, setLoading] = useState(false);
  const formRef = useRef<HTMLFormElement>(null);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    const fd = new FormData(formRef.current!);
    const raw: Record<string, unknown> = {};
    for (const [k, v] of fd.entries()) { if (v !== "") raw[k] = v; }
    raw.is_primary = fd.get("is_primary") === "on";
    setLoading(true);
    await createContactAction(supplierId, raw);
    setLoading(false);
    onSave();
  }

  return (
    <form ref={formRef} onSubmit={handleSubmit} className="form-section" style={{ marginBottom: "var(--sp-4)" }}>
      <div className="form-grid">
        <label>Nome *<input name="name" required /></label>
        <label>Cargo<input name="role" /></label>
        <label>E-mail<input type="email" name="email" /></label>
        <label>Telefone<input name="phone" /></label>
        <label>WhatsApp<input name="whatsapp" /></label>
        <label className="checkbox-row"><input type="checkbox" name="is_primary" /> Contato principal</label>
      </div>
      <footer>
        <button type="button" onClick={onCancel}>Cancelar</button>
        <button type="submit" disabled={loading}>{loading ? "Salvando…" : "Adicionar contato"}</button>
      </footer>
    </form>
  );
}

// ---- Main Component ----

export function SupplierManager() {
  const [suppliers, setSuppliers] = useState<SupplierSummary[]>([]);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(1);
  const [search, setSearch] = useState("");
  const [loading, setLoading] = useState(true);

  const [selectedSupplier, setSelectedSupplier] = useState<SupplierDetail | null>(null);
  const [modalMode, setModalMode] = useState<"none" | "form" | "detail">("none");
  const [showContactForm, setShowContactForm] = useState(false);

  useEffect(() => {
    refreshSuppliers(1, "");
  }, []);

  async function refreshSuppliers(p = page, s = search) {
    setLoading(true);
    const data = await listSuppliersAction({ page: p, search: s || undefined });
    setSuppliers(data.items);
    setTotal(data.total);
    setLoading(false);
  }

  async function openSupplierDetail(id: number) {
    const detail = await getSupplierAction(id);
    setSelectedSupplier(detail);
    setModalMode("detail");
  }

  function closeModal() {
    setModalMode("none");
    setSelectedSupplier(null);
    setShowContactForm(false);
  }

  async function handleCreateSupplier(data: Record<string, unknown>) {
    const res = await createSupplierAction(data);
    if (!res.ok) throw new Error(res.error);
    closeModal();
    await refreshSuppliers();
  }

  async function handleUpdateSupplier(data: Record<string, unknown>) {
    if (!selectedSupplier) return;
    const res = await updateSupplierAction(selectedSupplier.id, data);
    if (!res.ok) throw new Error(res.error);
    const updated = await getSupplierAction(selectedSupplier.id);
    setSelectedSupplier(updated);
    setModalMode("detail");
    await refreshSuppliers();
  }

  async function handleDeleteSupplier(id: number) {
    if (!confirm("Excluir este fornecedor?")) return;
    await deleteSupplierAction(id);
    closeModal();
    await refreshSuppliers();
  }

  const pageSize = 20;
  const pages = Math.ceil(total / pageSize);

  return (
    <>
      <header className="module-heading">
        <div>
          <p className="eyebrow">Cadastros</p>
          <h1>Fornecedores</h1>
          <p>Cadastro de fornecedores e contatos usados nos contratos.</p>
        </div>
        <button className="primary-button" onClick={() => { setSelectedSupplier(null); setModalMode("form"); }}>
          <Plus size={18} /> Novo fornecedor
        </button>
      </header>

      <section className="module-panel">
        <div className="module-toolbar">
          <label>
            <Search size={18} />
            <input
              placeholder="Buscar fornecedor..."
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              onKeyDown={(e) => {
                if (e.key === "Enter") { setPage(1); refreshSuppliers(1, search); }
              }}
            />
          </label>
        </div>

        {!loading && suppliers.length === 0 ? (
          <div className="module-state">
            <Users />
            <strong>Nenhum fornecedor encontrado</strong>
            <span>Ajuste a busca ou cadastre um novo fornecedor.</span>
          </div>
        ) : (
          <div className="module-table-wrap">
            <table>
              <thead>
                <tr>
                  <th>Nome</th>
                  <th>CNPJ/CPF</th>
                  <th>Categoria</th>
                  <th>Contato</th>
                  <th>Contratos</th>
                  <th>Status</th>
                </tr>
              </thead>
              <tbody>
                {suppliers.map((s) => (
                  <tr key={s.id} onClick={() => openSupplierDetail(s.id)}>
                    <td><strong>{s.name}</strong></td>
                    <td>{s.document ?? "—"}</td>
                    <td>{s.category ?? "—"}</td>
                    <td>
                      {s.email && <div className="cell-sub"><Mail size={12} /> {s.email}</div>}
                      {s.phone && <div className="cell-sub"><Phone size={12} /> {s.phone}</div>}
                    </td>
                    <td>{s.contract_count} contrato{s.contract_count !== 1 ? "s" : ""}</td>
                    <td><span className={`status ${s.active ? "status-done" : "status-neutral"}`}>{s.active ? "Ativo" : "Inativo"}</span></td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}

        <footer className="module-pagination">
          <span>{total} fornecedor{total !== 1 ? "es" : ""}</span>
          {pages > 1 && (
            <div>
              <button disabled={page <= 1} onClick={() => { const p = page - 1; setPage(p); refreshSuppliers(p); }}><ChevronLeft size={16} /></button>
              <span>{page} / {pages}</span>
              <button disabled={page >= pages} onClick={() => { const p = page + 1; setPage(p); refreshSuppliers(p); }}><ChevronRight size={16} /></button>
            </div>
          )}
        </footer>
      </section>

      {/* Create / edit modal */}
      {modalMode === "form" && (
        <div className="modal-layer" role="presentation" onClick={closeModal}>
          <section className="record-modal" role="dialog" aria-modal="true" style={{ maxWidth: 720 }} onClick={(e) => e.stopPropagation()}>
            <header>
              <div>
                <span>Cadastros</span>
                <h2>{selectedSupplier ? "Editar fornecedor" : "Novo fornecedor"}</h2>
              </div>
              <button className="icon-button" onClick={closeModal}><X /></button>
            </header>
            <SupplierForm
              initial={selectedSupplier}
              onSave={selectedSupplier ? handleUpdateSupplier : handleCreateSupplier}
              onCancel={closeModal}
            />
          </section>
        </div>
      )}

      {/* Detail modal */}
      {modalMode === "detail" && selectedSupplier && (
        <div className="modal-layer" role="presentation" onClick={closeModal}>
          <section className="record-modal has-timeline" role="dialog" aria-modal="true" style={{ maxWidth: 780 }} onClick={(e) => e.stopPropagation()}>
            <header>
              <div>
                <span>#{selectedSupplier.id}</span>
                <h2>{selectedSupplier.name}</h2>
              </div>
              <button className="icon-button" onClick={closeModal}><X /></button>
            </header>

            <form onSubmit={(e) => e.preventDefault()}>
              <div className="supplier-badges">
                <span className={`status ${selectedSupplier.active ? "status-done" : "status-neutral"}`}>{selectedSupplier.active ? "Ativo" : "Inativo"}</span>
                {selectedSupplier.category && <span className="status status-neutral">{selectedSupplier.category}</span>}
              </div>

              <div className="supplier-actions">
                <button type="button" className="secondary-button" onClick={() => setModalMode("form")}>
                  <Edit2 size={14} /> Editar
                </button>
                <button type="button" className="secondary-button" style={{ color: "var(--red)" }} onClick={() => handleDeleteSupplier(selectedSupplier.id)}>
                  <Trash2 size={14} /> Excluir
                </button>
              </div>

              <div className="form-grid">
                {selectedSupplier.document && <label>CNPJ/CPF<span>{selectedSupplier.document}</span></label>}
                {selectedSupplier.email && <label>E-mail<span><a href={`mailto:${selectedSupplier.email}`}>{selectedSupplier.email}</a></span></label>}
                {selectedSupplier.phone && <label>Telefone<span>{selectedSupplier.phone}</span></label>}
                {selectedSupplier.website && (
                  <label style={{ gridColumn: "1 / -1" }}>Website<span><a href={selectedSupplier.website} target="_blank" rel="noopener noreferrer">{selectedSupplier.website}</a></span></label>
                )}
                {selectedSupplier.address_street && (
                  <label style={{ gridColumn: "1 / -1" }}>Endereço<span>{[selectedSupplier.address_street, selectedSupplier.address_number, selectedSupplier.address_complement, selectedSupplier.address_city, selectedSupplier.address_state, selectedSupplier.address_zip].filter(Boolean).join(", ")}</span></label>
                )}
                {selectedSupplier.notes && (
                  <label style={{ gridColumn: "1 / -1" }}>Observações<span style={{ whiteSpace: "pre-wrap", fontWeight: 400 }}>{selectedSupplier.notes}</span></label>
                )}
              </div>

              <div className="section-header">
                <strong>Contatos ({selectedSupplier.contacts.length})</strong>
                {!showContactForm && (
                  <button type="button" className="secondary-button" onClick={() => setShowContactForm(true)}>
                    <Plus size={14} /> Adicionar
                  </button>
                )}
              </div>
              {showContactForm && (
                <ContactForm
                  supplierId={selectedSupplier.id}
                  onSave={async () => {
                    setShowContactForm(false);
                    const updated = await getSupplierAction(selectedSupplier.id);
                    setSelectedSupplier(updated);
                  }}
                  onCancel={() => setShowContactForm(false)}
                />
              )}
              {selectedSupplier.contacts.length === 0 && !showContactForm && (
                <p className="empty-hint">Nenhum contato cadastrado.</p>
              )}
              {selectedSupplier.contacts.map((c: SupplierContact) => (
                <div key={c.id} className="timeline-entry">
                  {c.is_primary && <Star size={14} className="primary-star" />}
                  <div style={{ flex: 1 }}>
                    <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between" }}>
                      <strong>{c.name}{c.role && <span style={{ color: "var(--muted)", fontWeight: 400 }}> · {c.role}</span>}</strong>
                      <button type="button" className="icon-button" onClick={async () => {
                        if (!confirm("Remover contato?")) return;
                        await deleteContactAction(c.id);
                        const updated = await getSupplierAction(selectedSupplier.id);
                        setSelectedSupplier(updated);
                      }}><Trash2 size={14} /></button>
                    </div>
                    {c.email && <small style={{ display: "block", color: "var(--muted)" }}>{c.email}</small>}
                    {c.phone && <small style={{ display: "block", color: "var(--muted)" }}>{c.phone}</small>}
                    {c.whatsapp && <small style={{ display: "block", color: "var(--muted)" }}>WhatsApp: {c.whatsapp}</small>}
                    {c.notes && <small style={{ display: "block", color: "var(--muted)" }}>{c.notes}</small>}
                  </div>
                </div>
              ))}
            </form>
          </section>
        </div>
      )}

      <style>{`
        .supplier-badges { display: flex; gap: var(--sp-2); flex-wrap: wrap; }
        .supplier-actions { display: flex; gap: var(--sp-2); flex-wrap: wrap; }
        .cell-sub { font-size: var(--font-xs); color: var(--muted); display: flex; align-items: center; gap: 4px; }
        .section-header { display: flex; align-items: center; justify-content: space-between; }
        .empty-hint { color: var(--muted); font-size: var(--font-sm); text-align: center; padding: var(--sp-5) 0; }
        .timeline-entry { display: flex; gap: var(--sp-3); padding: var(--sp-3) 0; border-bottom: 1px solid var(--line); align-items: flex-start; }
        .timeline-entry:last-child { border-bottom: 0; }
        .primary-star { color: #f59e0b; margin-top: 3px; }
        .checkbox-row { display: flex !important; flex-direction: row !important; align-items: center; gap: var(--sp-2); }
        .checkbox-row input { width: auto !important; min-height: 0 !important; }
        .record-modal.has-timeline label > span { font-size: var(--font-base); font-weight: 400; color: var(--ink); }
      `}</style>
    </>
  );
}
