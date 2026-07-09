"use client";

import {
  ChevronLeft, ChevronRight, Phone, Mail,
  Plus, Search, Trash2, X, Edit2, Star,
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
    <form ref={formRef} onSubmit={handleSubmit} className="drawer-form">
      <div className="form-grid">
        <div className="field span-2">
          <label>Nome / Razão social *</label>
          <input name="name" required defaultValue={initial?.name} />
        </div>
        <div className="field">
          <label>Tipo de documento</label>
          <select name="document_type" defaultValue={initial?.document_type ?? ""}>
            <option value="">— Selecione —</option>
            <option value="cnpj">CNPJ</option>
            <option value="cpf">CPF</option>
          </select>
        </div>
        <div className="field">
          <label>CPF/CNPJ</label>
          <input name="document" defaultValue={initial?.document ?? ""} placeholder="00.000.000/0000-00" />
        </div>
        <div className="field span-2">
          <label>Categoria</label>
          <input name="category" defaultValue={initial?.category ?? ""} placeholder="Ex: Tecnologia, Limpeza, Segurança..." />
        </div>
        <div className="field">
          <label>E-mail</label>
          <input type="email" name="email" defaultValue={initial?.email ?? ""} />
        </div>
        <div className="field">
          <label>Telefone</label>
          <input name="phone" defaultValue={initial?.phone ?? ""} />
        </div>
        <div className="field span-2">
          <label>Website</label>
          <input name="website" defaultValue={initial?.website ?? ""} placeholder="https://" />
        </div>
        <div className="field-section-title span-2">Endereço</div>
        <div className="field span-2">
          <label>Logradouro</label>
          <input name="address_street" defaultValue={initial?.address_street ?? ""} />
        </div>
        <div className="field">
          <label>Número</label>
          <input name="address_number" defaultValue={initial?.address_number ?? ""} />
        </div>
        <div className="field">
          <label>Complemento</label>
          <input name="address_complement" defaultValue={initial?.address_complement ?? ""} />
        </div>
        <div className="field">
          <label>Cidade</label>
          <input name="address_city" defaultValue={initial?.address_city ?? ""} />
        </div>
        <div className="field" style={{ maxWidth: 80 }}>
          <label>UF</label>
          <input name="address_state" maxLength={2} defaultValue={initial?.address_state ?? ""} placeholder="SP" />
        </div>
        <div className="field">
          <label>CEP</label>
          <input name="address_zip" defaultValue={initial?.address_zip ?? ""} placeholder="00000-000" />
        </div>
        <div className="field span-2">
          <label>Observações</label>
          <textarea name="notes" rows={2} defaultValue={initial?.notes ?? ""} />
        </div>
      </div>
      {error && <p className="form-error">{error}</p>}
      <div className="drawer-actions">
        <button type="button" className="btn-secondary" onClick={onCancel}>Cancelar</button>
        <button type="submit" className="btn-primary" disabled={loading}>{loading ? "Salvando…" : initial ? "Salvar" : "Criar fornecedor"}</button>
      </div>
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
    <form ref={formRef} onSubmit={handleSubmit} className="inline-form">
      <div className="form-grid">
        <div className="field"><label>Nome *</label><input name="name" required /></div>
        <div className="field"><label>Cargo</label><input name="role" /></div>
        <div className="field"><label>E-mail</label><input type="email" name="email" /></div>
        <div className="field"><label>Telefone</label><input name="phone" /></div>
        <div className="field"><label>WhatsApp</label><input name="whatsapp" /></div>
        <div className="field">
          <label>Contato principal</label>
          <label className="checkbox-wrap"><input type="checkbox" name="is_primary" /><span>Sim</span></label>
        </div>
      </div>
      <div className="drawer-actions">
        <button type="button" className="btn-secondary" onClick={onCancel}>Cancelar</button>
        <button type="submit" className="btn-primary" disabled={loading}>{loading ? "Salvando…" : "Adicionar contato"}</button>
      </div>
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
  const [drawerMode, setDrawerMode] = useState<"none" | "form" | "detail">("none");
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
    setDrawerMode("detail");
  }

  function closeDrawer() {
    setDrawerMode("none");
    setSelectedSupplier(null);
    setShowContactForm(false);
  }

  async function handleCreateSupplier(data: Record<string, unknown>) {
    const res = await createSupplierAction(data);
    if (!res.ok) throw new Error(res.error);
    closeDrawer();
    await refreshSuppliers();
  }

  async function handleUpdateSupplier(data: Record<string, unknown>) {
    if (!selectedSupplier) return;
    const res = await updateSupplierAction(selectedSupplier.id, data);
    if (!res.ok) throw new Error(res.error);
    const updated = await getSupplierAction(selectedSupplier.id);
    setSelectedSupplier(updated);
    setDrawerMode("detail");
    await refreshSuppliers();
  }

  async function handleDeleteSupplier(id: number) {
    if (!confirm("Excluir este fornecedor?")) return;
    await deleteSupplierAction(id);
    closeDrawer();
    await refreshSuppliers();
  }

  const pageSize = 20;
  const pages = Math.ceil(total / pageSize);

  return (
    <>
      <div className="heading-actions">
        <button className="btn-primary" onClick={() => setDrawerMode("form")}>
          <Plus size={16} /> Novo fornecedor
        </button>
      </div>

      <div className="list-toolbar">
        <div className="search-wrap">
          <Search size={15} />
          <input
            placeholder="Buscar fornecedor…"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === "Enter") { setPage(1); refreshSuppliers(1, search); }
            }}
          />
        </div>
      </div>

      <div className="data-table-wrap">
        <table className="data-table">
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
            {!loading && suppliers.length === 0 && (
              <tr><td colSpan={6} className="empty-cell">Nenhum fornecedor encontrado.</td></tr>
            )}
            {suppliers.map((s) => (
              <tr key={s.id} className="clickable" onClick={() => openSupplierDetail(s.id)}>
                <td><div className="cell-title">{s.name}</div></td>
                <td>{s.document ?? "—"}</td>
                <td>{s.category ?? "—"}</td>
                <td>
                  {s.email && <div className="cell-sub"><Mail size={12} /> {s.email}</div>}
                  {s.phone && <div className="cell-sub"><Phone size={12} /> {s.phone}</div>}
                </td>
                <td>
                  <span className="badge badge-blue">{s.contract_count} contrato{s.contract_count !== 1 ? "s" : ""}</span>
                </td>
                <td><span className={`badge ${s.active ? "badge-green" : "badge-grey"}`}>{s.active ? "Ativo" : "Inativo"}</span></td>
              </tr>
            ))}
          </tbody>
        </table>
        {pages > 1 && (
          <div className="pagination">
            <button disabled={page <= 1} onClick={() => { const p = page - 1; setPage(p); refreshSuppliers(p); }}><ChevronLeft size={16} /></button>
            <span>{page} / {pages}</span>
            <button disabled={page >= pages} onClick={() => { const p = page + 1; setPage(p); refreshSuppliers(p); }}><ChevronRight size={16} /></button>
          </div>
        )}
      </div>

      {drawerMode !== "none" && (
        <div className="drawer-overlay" onClick={closeDrawer}>
          <div className="drawer-panel" onClick={(e) => e.stopPropagation()}>
            <div className="drawer-header">
              <h2>
                {drawerMode === "form" && (selectedSupplier ? "Editar fornecedor" : "Novo fornecedor")}
                {drawerMode === "detail" && selectedSupplier?.name}
              </h2>
              <button className="btn-icon" onClick={closeDrawer}><X size={20} /></button>
            </div>

            {drawerMode === "form" && (
              <SupplierForm
                initial={selectedSupplier}
                onSave={selectedSupplier ? handleUpdateSupplier : handleCreateSupplier}
                onCancel={closeDrawer}
              />
            )}

            {drawerMode === "detail" && selectedSupplier && (
              <div className="drawer-content">
                <div className="detail-meta-row">
                  <span className={`badge ${selectedSupplier.active ? "badge-green" : "badge-grey"}`}>{selectedSupplier.active ? "Ativo" : "Inativo"}</span>
                  {selectedSupplier.category && <span className="badge badge-blue">{selectedSupplier.category}</span>}
                </div>
                <div className="status-actions">
                  <button className="btn-sm btn-secondary" onClick={() => setDrawerMode("form")}>
                    <Edit2 size={14} /> Editar
                  </button>
                  <button className="btn-sm btn-red" onClick={() => handleDeleteSupplier(selectedSupplier.id)}>
                    <Trash2 size={14} /> Excluir
                  </button>
                </div>

                <div className="detail-fields">
                  {selectedSupplier.document && <div className="detail-field"><label>CNPJ/CPF</label><span>{selectedSupplier.document}</span></div>}
                  {selectedSupplier.email && <div className="detail-field"><label>E-mail</label><a href={`mailto:${selectedSupplier.email}`}>{selectedSupplier.email}</a></div>}
                  {selectedSupplier.phone && <div className="detail-field"><label>Telefone</label><span>{selectedSupplier.phone}</span></div>}
                  {selectedSupplier.website && <div className="detail-field span-2"><label>Website</label><a href={selectedSupplier.website} target="_blank" rel="noopener noreferrer">{selectedSupplier.website}</a></div>}
                  {(selectedSupplier.address_street) && (
                    <div className="detail-field span-2">
                      <label>Endereço</label>
                      <span>{[selectedSupplier.address_street, selectedSupplier.address_number, selectedSupplier.address_complement, selectedSupplier.address_city, selectedSupplier.address_state, selectedSupplier.address_zip].filter(Boolean).join(", ")}</span>
                    </div>
                  )}
                  {selectedSupplier.notes && <div className="detail-field span-2"><label>Observações</label><p className="text-block">{selectedSupplier.notes}</p></div>}
                </div>

                <div className="section-header">
                  <span>Contatos ({selectedSupplier.contacts.length})</span>
                  {!showContactForm && (
                    <button className="btn-sm btn-secondary" onClick={() => setShowContactForm(true)}>
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
                  <p className="empty-section">Nenhum contato cadastrado.</p>
                )}
                {selectedSupplier.contacts.map((c: SupplierContact) => (
                  <div key={c.id} className="contact-card">
                    <div className="contact-header">
                      <div>
                        <strong>{c.name}</strong>
                        {c.is_primary && <Star size={12} className="primary-star" />}
                        {c.role && <span className="cell-sub">{c.role}</span>}
                      </div>
                      <button className="btn-icon-sm" onClick={async () => {
                        if (!confirm("Remover contato?")) return;
                        await deleteContactAction(c.id);
                        const updated = await getSupplierAction(selectedSupplier.id);
                        setSelectedSupplier(updated);
                      }}><Trash2 size={14} /></button>
                    </div>
                    {c.email && <div className="cell-sub"><Mail size={12} /> {c.email}</div>}
                    {c.phone && <div className="cell-sub"><Phone size={12} /> {c.phone}</div>}
                    {c.whatsapp && <div className="cell-sub"><Phone size={12} /> WhatsApp: {c.whatsapp}</div>}
                    {c.notes && <p className="cell-sub">{c.notes}</p>}
                  </div>
                ))}
              </div>
            )}
          </div>
        </div>
      )}

      <style>{`
        .heading-actions { display:flex; gap:8px; justify-content:flex-end; margin-bottom:12px; }
        .list-toolbar { display:flex; align-items:center; gap:8px; margin-bottom:12px; flex-wrap:wrap; }
        .search-wrap { display:flex; align-items:center; gap:6px; background:var(--input-bg); border:1px solid var(--border); border-radius:6px; padding:6px 10px; min-width:220px; }
        .search-wrap input { border:none; background:none; outline:none; font-size:.875rem; width:100%; }
        .data-table-wrap { overflow-x:auto; }
        .data-table { width:100%; border-collapse:collapse; font-size:.875rem; }
        .data-table th { text-align:left; padding:8px 12px; font-size:.75rem; text-transform:uppercase; letter-spacing:.05em; color:var(--text-muted); border-bottom:1px solid var(--border); }
        .data-table td { padding:10px 12px; border-bottom:1px solid var(--border-light,#f0f0f0); vertical-align:top; }
        .data-table tr.clickable { cursor:pointer; }
        .data-table tr.clickable:hover td { background:var(--hover-bg,rgba(0,0,0,.03)); }
        .cell-title { font-weight:500; }
        .cell-sub { font-size:.8rem; color:var(--text-muted); display:flex; align-items:center; gap:4px; margin-top:2px; }
        .empty-cell { text-align:center; color:var(--text-muted); padding:32px; }
        .pagination { display:flex; align-items:center; gap:8px; justify-content:flex-end; margin-top:12px; font-size:.85rem; }
        .pagination button { padding:4px 8px; border:1px solid var(--border); border-radius:4px; background:none; cursor:pointer; }
        .pagination button:disabled { opacity:.4; cursor:default; }
        .badge { display:inline-flex; align-items:center; padding:2px 8px; border-radius:99px; font-size:.75rem; font-weight:600; }
        .badge-grey { background:#f3f4f6; color:#374151; }
        .badge-green { background:#d1fae5; color:#065f46; }
        .badge-blue { background:#dbeafe; color:#1d4ed8; }
        .badge-red { background:#fee2e2; color:#991b1b; }
        .btn-primary { display:inline-flex; align-items:center; gap:6px; padding:8px 16px; background:var(--primary,#2563eb); color:#fff; border:none; border-radius:6px; font-size:.875rem; font-weight:500; cursor:pointer; }
        .btn-secondary { display:inline-flex; align-items:center; gap:6px; padding:8px 16px; background:none; border:1px solid var(--border); border-radius:6px; font-size:.875rem; cursor:pointer; }
        .btn-icon { background:none; border:none; cursor:pointer; color:var(--text-muted); }
        .btn-icon-sm { background:none; border:none; cursor:pointer; color:var(--text-muted); padding:2px; }
        .btn-sm { display:inline-flex; align-items:center; gap:4px; padding:5px 10px; border-radius:6px; font-size:.8rem; cursor:pointer; border:none; }
        .btn-red { background:#fee2e2; color:#991b1b; }
        .btn-sm.btn-secondary { background:var(--input-bg); border:1px solid var(--border); color:var(--text); }
        .drawer-overlay { position:fixed; inset:0; background:rgba(0,0,0,.4); z-index:100; display:flex; justify-content:flex-end; }
        .drawer-panel { width:min(680px,95vw); background:var(--bg,#fff); height:100vh; overflow-y:auto; display:flex; flex-direction:column; }
        .drawer-header { display:flex; align-items:center; justify-content:space-between; padding:20px 24px 16px; border-bottom:1px solid var(--border); }
        .drawer-header h2 { font-size:1.1rem; font-weight:600; margin:0; }
        .drawer-form { padding:16px 24px 24px; overflow-y:auto; flex:1; }
        .drawer-content { padding:16px 24px; overflow-y:auto; flex:1; }
        .form-grid { display:grid; grid-template-columns:1fr 1fr; gap:12px; }
        .field { display:flex; flex-direction:column; gap:4px; }
        .field.span-2 { grid-column:span 2; }
        .field label { font-size:.8rem; font-weight:500; color:var(--text-muted); }
        .field input, .field select, .field textarea { padding:7px 10px; border:1px solid var(--border); border-radius:6px; font-size:.875rem; background:var(--input-bg,#fff); }
        .field-section-title { font-size:.8rem; font-weight:700; text-transform:uppercase; letter-spacing:.06em; color:var(--text-muted); padding-top:8px; border-top:1px solid var(--border-light,#f0f0f0); }
        .checkbox-wrap { display:flex; align-items:center; gap:8px; font-size:.875rem; cursor:pointer; }
        .form-error { color:#991b1b; font-size:.85rem; margin-top:8px; }
        .drawer-actions { display:flex; gap:8px; justify-content:flex-end; margin-top:16px; padding-top:12px; border-top:1px solid var(--border-light,#f0f0f0); }
        .inline-form { background:var(--hover-bg,rgba(0,0,0,.02)); border:1px solid var(--border); border-radius:8px; padding:12px 16px; margin:8px 0 12px; }
        .detail-meta-row { display:flex; gap:6px; flex-wrap:wrap; margin-bottom:12px; }
        .status-actions { display:flex; gap:6px; flex-wrap:wrap; margin-bottom:12px; }
        .detail-fields { display:grid; grid-template-columns:1fr 1fr; gap:10px; margin-bottom:16px; }
        .detail-field { display:flex; flex-direction:column; gap:2px; }
        .detail-field.span-2 { grid-column:span 2; }
        .detail-field label { font-size:.75rem; font-weight:500; color:var(--text-muted); text-transform:uppercase; letter-spacing:.04em; }
        .detail-field span, .detail-field a { font-size:.875rem; }
        .text-block { font-size:.875rem; white-space:pre-wrap; margin:0; line-height:1.5; }
        .section-header { display:flex; align-items:center; justify-content:space-between; margin:12px 0 8px; }
        .section-header span { font-weight:600; font-size:.9rem; }
        .empty-section { color:var(--text-muted); font-size:.875rem; text-align:center; padding:16px; }
        .contact-card { padding:10px 12px; border:1px solid var(--border); border-radius:8px; margin-bottom:8px; }
        .contact-header { display:flex; align-items:flex-start; justify-content:space-between; margin-bottom:4px; }
        .contact-header strong { font-size:.875rem; }
        .primary-star { color:#f59e0b; margin-left:4px; }
      `}</style>
    </>
  );
}
